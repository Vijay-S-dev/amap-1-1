/**
 * AMAP Worker Gesture Interaction Engine (frontend/worker/lib/gestureEngine.ts)
 *
 * Real-time, frame-driven state machine that converts MediaPipe hand landmark
 * frames into REAL application actions:
 *
 *   Camera -> MediaPipe landmarks -> pose classification -> state machine
 *   -> gesture->action mapping (worker-personalized, PostgreSQL-backed)
 *   -> typed action events -> UI action executor + backend persistence
 *
 * Responsibilities:
 *  - Virtual pointer: index-fingertip driven, smoothed (EMA), jitter-deadband,
 *    configurable sensitivity, camera-mirrored to user frame of reference.
 *  - Pinch click: quick pinch = left click (debounced), sustained pinch =
 *    select, pinch + movement = drag (continuous, not isolated events).
 *  - Two-finger: right click when released still, continuous scroll while moving.
 *  - Swipes (pointing pose flicks): navigation + discrete scroll.
 *  - FIST = immediate emergency stop (bypasses debounce and pause locks).
 *  - Temporal state machine: IDLE, HOVER, ARMED, TRIGGERED, HELD, DRAGGING,
 *    RELEASED, PAUSED, EMERGENCY_STOPPED.
 *
 * This module is pure logic (no React, no DOM) so it is unit-testable.
 */

import {
  classifyHandPose,
  detectSwipe,
  HandPose,
  Landmark3D,
  poseToGestureKey,
  SwipeDirection,
} from './handPoses';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type InteractionState =
  | 'IDLE'
  | 'HOVER'
  | 'ARMED'
  | 'TRIGGERED'
  | 'HELD'
  | 'DRAGGING'
  | 'RELEASED'
  | 'PAUSED'
  | 'EMERGENCY_STOPPED';

export interface EngineCalibration {
  /** Dwell time for pose confirmation (ms). */
  dwellTimeMs: number;
  /** Minimum spacing between discrete click actions (ms). */
  clickDebounceMs: number;
  /** Two clicks within this window combine into a double click (ms). */
  doubleClickWindowMs: number;
  /** Pinch held shorter than this = click tap (ms). */
  pinchClickMaxMs: number;
  /** Pinch held at least this long (stationary) = select (ms). */
  pinchSelectMinMs: number;
  /** Pinch held at least this long before movement counts as drag (ms). */
  pinchDragMinMs: number;
  /** Pointer amplification factor (1.0 = direct mapping). */
  pointerSensitivity: number;
  /** Scroll pixels per unit of normalized hand travel. */
  scrollSensitivity: number;
  /** Minimum spacing between generated scroll events (ms). */
  scrollThrottleMs: number;
  /** EMA smoothing factor for the pointer (0..1, lower = smoother). */
  smoothingAlpha: number;
  /** Normalized pointer movement below this is ignored (jitter deadband). */
  jitterThreshold: number;
  /** Preferred hand: 'Left' | 'Right' | 'Either'. */
  handedness: 'Left' | 'Right' | 'Either';
  /** Per-gesture enable switches. */
  enabledGestures: Record<string, boolean>;
}

export const DEFAULT_ENGINE_CALIBRATION: EngineCalibration = {
  dwellTimeMs: 500,
  clickDebounceMs: 700,
  doubleClickWindowMs: 400,
  pinchClickMaxMs: 450,
  pinchSelectMinMs: 650,
  pinchDragMinMs: 350,
  pointerSensitivity: 1.4,
  scrollSensitivity: 220,
  scrollThrottleMs: 180,
  smoothingAlpha: 0.35,
  jitterThreshold: 0.012,
  handedness: 'Either',
  enabledGestures: {
    pinch: true,
    pinch_hold: true,
    two_finger: true,
    two_finger_move: true,
    swipe_up: true,
    swipe_down: true,
    swipe_left: true,
    swipe_right: true,
    thumbs_up: true,
    thumbs_down: true,
    open_palm: true,
    fist: true,
  },
};

/**
 * Convert a backend (snake_case) calibration record — as returned by
 * GET /personalization/me/gesture-mapping — into engine calibration keys.
 * Unknown keys are ignored; numeric guards keep malformed values out.
 */
export function engineCalibrationFromBackend(
  raw: Record<string, any> | null | undefined
): Partial<EngineCalibration> {
  if (!raw || typeof raw !== 'object') return {};
  const num = (v: any): number | undefined =>
    typeof v === 'number' && Number.isFinite(v) ? v : undefined;
  const fields: Array<[keyof EngineCalibration, string]> = [
    ['dwellTimeMs', 'dwell_time_ms'],
    ['clickDebounceMs', 'click_debounce_ms'],
    ['doubleClickWindowMs', 'double_click_window_ms'],
    ['pinchClickMaxMs', 'pinch_click_max_ms'],
    ['pinchSelectMinMs', 'pinch_select_min_ms'],
    ['pinchDragMinMs', 'pinch_drag_min_ms'],
    ['pointerSensitivity', 'cursor_sensitivity'],
    ['scrollSensitivity', 'scroll_sensitivity'],
    ['scrollThrottleMs', 'scroll_throttle_ms'],
    ['smoothingAlpha', 'smoothing_alpha'],
    ['jitterThreshold', 'jitter_threshold'],
  ];
  const patch: Partial<EngineCalibration> = {};
  for (const [camel, snake] of fields) {
    const v = num(raw[snake]);
    if (v !== undefined) (patch as Record<string, any>)[camel] = v;
  }
  if (raw.handedness === 'Left' || raw.handedness === 'Right' || raw.handedness === 'Either') {
    patch.handedness = raw.handedness;
  }
  if (raw.enabled_gestures && typeof raw.enabled_gestures === 'object') {
    patch.enabledGestures = { ...raw.enabled_gestures };
  }
  return patch;
}

/**
 * Convert engine calibration back into the backend (snake_case) record shape
 * persisted in worker_personalizations.calibration.
 */
export function engineCalibrationToBackend(
  cal: Partial<EngineCalibration> | Record<string, any> | null | undefined
): Record<string, any> {
  if (!cal || typeof cal !== 'object') return {};
  const out: Record<string, any> = {};
  if (cal.dwellTimeMs !== undefined) out.dwell_time_ms = cal.dwellTimeMs;
  if (cal.clickDebounceMs !== undefined) out.click_debounce_ms = cal.clickDebounceMs;
  if (cal.doubleClickWindowMs !== undefined) out.double_click_window_ms = cal.doubleClickWindowMs;
  if (cal.pinchClickMaxMs !== undefined) out.pinch_click_max_ms = cal.pinchClickMaxMs;
  if (cal.pinchSelectMinMs !== undefined) out.pinch_select_min_ms = cal.pinchSelectMinMs;
  if (cal.pinchDragMinMs !== undefined) out.pinch_drag_min_ms = cal.pinchDragMinMs;
  if (cal.pointerSensitivity !== undefined) out.cursor_sensitivity = cal.pointerSensitivity;
  if (cal.scrollSensitivity !== undefined) out.scroll_sensitivity = cal.scrollSensitivity;
  if (cal.scrollThrottleMs !== undefined) out.scroll_throttle_ms = cal.scrollThrottleMs;
  if (cal.smoothingAlpha !== undefined) out.smoothing_alpha = cal.smoothingAlpha;
  if (cal.jitterThreshold !== undefined) out.jitter_threshold = cal.jitterThreshold;
  if (cal.handedness !== undefined) out.handedness = cal.handedness;
  if (cal.enabledGestures !== undefined) out.enabled_gestures = { ...cal.enabledGestures };
  return out;
}

export interface PointerPosition {
  /** Viewport-space coordinates in pixels. */
  x: number;
  y: number;
}

export type EngineEvent =
  | {
      type: 'pointer';
      position: PointerPosition;
      state: InteractionState;
      pose: HandPose;
    }
  | {
      type: 'action';
      action: string;
      gesture: string;
      confidence: number;
      position: PointerPosition | null;
      state: InteractionState;
      /** Extra context forwarded to the action resolver / audit trail. */
      context?: Record<string, unknown>;
    }
  | {
      type: 'scroll';
      direction: 'up' | 'down' | 'left' | 'right';
      amountPx: number;
      position: PointerPosition;
      source: 'two_finger' | 'swipe';
    }
  | {
      type: 'drag';
      phase: 'start' | 'move' | 'end';
      position: PointerPosition;
      pathLengthPx: number;
      durationMs: number;
      source: 'pinch' | 'voice';
    }
  | { type: 'state'; state: InteractionState; pose: HandPose }
  | { type: 'feedback'; level: 'info' | 'warn' | 'error'; message: string };

// ---------------------------------------------------------------------------
// Engine
// ---------------------------------------------------------------------------

export class WorkerGestureEngine {
  private calibration: EngineCalibration;
  private gestureActionMap: Record<string, string>;

  /** Viewport size for normalized->pixel mapping. */
  private viewportWidth = 1280;
  private viewportHeight = 720;

  private state: InteractionState = 'IDLE';
  private pose: HandPose = 'NONE';

  /** Smoothed pointer position in normalized user-frame coordinates [0..1]. */
  private pointerNorm: { x: number; y: number } | null = null;
  private hasPointer = false;

  /** Timestamps of the last processed frame. */
  private lastFrameTs = 0;

  /** Pinch tracking. */
  private pinchStartTs = 0;
  private pinchStartPos: PointerPosition | null = null;
  private dragging = false;
  private dragPathPx = 0;
  private dragSource: 'pinch' | 'voice' = 'pinch';

  /** Two-finger scroll tracking. */
  private twoFingerStartPos: PointerPosition | null = null;
  private twoFingerTotalDisp = 0;
  private twoFingerLastScrollTs = 0;

  /** Discrete action debounce. */
  private lastClickTs = 0;
  private lastClickAction = '';
  private lastSwipeTs = 0;

  /** Palm-center history for swipe detection: {ts, x, y} in raw image space. */
  private palmHistory: { ts: number; x: number; y: number }[] = [];
  private swipeArmed = true;

  /** Double click detection. */
  private lastTapTs = 0;

  /** Paused / emergency lock. */
  private paused = false;
  private emergencyStopped = false;

  /** Voice-initiated drag pending (drag armed by voice, released by pinch/drop). */
  private voiceDragPending = false;

  constructor(
    calibration?: Partial<EngineCalibration>,
    gestureActionMap?: Record<string, string>,
    viewport?: { width: number; height: number }
  ) {
    this.calibration = { ...DEFAULT_ENGINE_CALIBRATION, ...(calibration || {}) };
    this.gestureActionMap = gestureActionMap || {};
    if (viewport) {
      this.viewportWidth = viewport.width;
      this.viewportHeight = viewport.height;
    }
  }

  // ------------------------------------------------------------------
  // Configuration
  // ------------------------------------------------------------------

  setViewport(width: number, height: number): void {
    this.viewportWidth = Math.max(1, width);
    this.viewportHeight = Math.max(1, height);
  }

  updateCalibration(patch: Partial<EngineCalibration>): void {
    this.calibration = { ...this.calibration, ...patch };
  }

  getCalibration(): EngineCalibration {
    return { ...this.calibration };
  }

  setGestureActionMap(map: Record<string, string>): void {
    this.gestureActionMap = { ...(map || {}) };
  }

  setPaused(paused: boolean): EngineEvent[] {
    this.paused = paused;
    if (paused) {
      this.resetTransientTracking();
      this.setState('PAUSED');
    } else {
      this.setState(this.hasPointer ? 'HOVER' : 'IDLE');
    }
    return [
      {
        type: 'feedback',
        level: 'info',
        message: paused ? 'Interaction paused.' : 'Interaction resumed.',
      },
    ];
  }

  setEmergencyStopped(stopped: boolean): EngineEvent[] {
    this.emergencyStopped = stopped;
    if (stopped) {
      this.resetTransientTracking();
      this.setState('EMERGENCY_STOPPED');
      return [
        {
          type: 'feedback',
          level: 'error',
          message: 'EMERGENCY STOP: gesture interaction halted immediately.',
        },
      ];
    }
    this.setState(this.hasPointer ? 'HOVER' : 'IDLE');
    return [];
  }

  getState(): InteractionState {
    return this.state;
  }

  getPointer(): PointerPosition | null {
    return this.pointerNorm ? this.toPixels(this.pointerNorm) : null;
  }

  /** Begin a drag from a non-gesture source (e.g. voice "move this"). */
  beginExternalDrag(source: 'voice' = 'voice'): EngineEvent[] {
    if (this.emergencyStopped || !this.pointerNorm) return [];
    this.dragging = true;
    this.dragSource = source;
    this.dragPathPx = 0;
    this.pinchStartTs = this.now();
    this.pinchStartPos = this.toPixels(this.pointerNorm);
    this.setState('DRAGGING');
    return [
      {
        type: 'drag',
        phase: 'start',
        position: this.pinchStartPos,
        pathLengthPx: 0,
        durationMs: 0,
        source,
      },
    ];
  }

  /** End an externally-initiated drag (e.g. voice "drop"). */
  endExternalDrag(): EngineEvent[] {
    if (!this.dragging || this.dragSource !== 'voice') return [];
    const end = this.toPixels(this.pointerNorm || { x: 0.5, y: 0.5 });
    const events: EngineEvent[] = [
      {
        type: 'drag',
        phase: 'end',
        position: end,
        pathLengthPx: Math.round(this.dragPathPx),
        durationMs: Math.round(this.now() - this.pinchStartTs),
        source: 'voice',
      },
    ];
    this.dragging = false;
    this.voiceDragPending = false;
    this.setState('HOVER');
    return events;
  }

  // ------------------------------------------------------------------
  // Frame processing
  // ------------------------------------------------------------------

  /**
   * Process one tracked-hand frame.
   * @param hands landmark arrays (one per detected hand)
   * @param labels handedness labels ('Left' | 'Right') per hand
   * @param tsMs client timestamp in milliseconds
   */
  processFrame(hands: Landmark3D[][], labels: string[], tsMs: number): EngineEvent[] {
    if (this.emergencyStopped) {
      return [];
    }

    if (!hands || hands.length === 0) {
      return this.handleNoHand();
    }

    const dt = this.lastFrameTs ? Math.max(1, tsMs - this.lastFrameTs) : 16;
    this.lastFrameTs = tsMs;

    const hand = this.selectHand(hands, labels);
    if (!hand || hand.length < 21) {
      return this.handleNoHand();
    }

    const events: EngineEvent[] = [];
    const result = classifyHandPose(hand);
    const prevPose = this.pose;
    this.pose = result.pose;

    // --- 1. FIST: immediate emergency stop (bypasses pause & debounce) ---
    if (result.pose === 'FIST') {
      if (this.gestureEnabled('fist')) {
        // De-duplicate: fire only on pose entry
        if (prevPose !== 'FIST') {
          events.push(this.makeActionEvent('fist', result.confidence, tsMs, events));
          this.setState('TRIGGERED');
        }
        // While fist is held, no other interaction is processed.
        return events;
      }
    }

    // --- 2. Pointer tracking (index fingertip, mirrored to user frame) ---
    const indexTip = hand[8];
    const rawX = 1 - indexTip.x; // mirror: user's right = screen right
    const rawY = indexTip.y;

    // Sensitivity amplification around screen center
    const sens = this.calibration.pointerSensitivity;
    const targetX = clamp01(0.5 + (rawX - 0.5) * sens);
    const targetY = clamp01(0.5 + (rawY - 0.5) * sens);

    if (!this.hasPointer) {
      this.pointerNorm = { x: targetX, y: targetY };
      this.hasPointer = true;
    } else {
      const alpha = clamp01(this.calibration.smoothingAlpha);
      this.pointerNorm = {
        x: this.pointerNorm!.x * (1 - alpha) + targetX * alpha,
        y: this.pointerNorm!.y * (1 - alpha) + targetY * alpha,
      };
    }

    const pointer = this.toPixels(this.pointerNorm);

    // Jitter deadband: only emit pointer moves above the threshold
    const lastEmitted = this.lastEmittedPointer;
    const dxPx = lastEmitted ? Math.abs(pointer.x - lastEmitted.x) : Infinity;
    const dyPx = lastEmitted ? Math.abs(pointer.y - lastEmitted.y) : Infinity;
    const jitterPx = this.calibration.jitterThreshold * this.viewportWidth;
    if (!lastEmitted || dxPx > jitterPx || dyPx > jitterPx) {
      this.lastEmittedPointer = pointer;
      events.push({
        type: 'pointer',
        position: pointer,
        state: this.state,
        pose: this.pose,
      });
    }

    // --- 3. Pose-transition logic ---
    if (this.paused) {
      // While paused the pointer stays live (worker must reach Resume), but
      // task-level gestures are suppressed.
      this.setState('PAUSED');
      return events;
    }

    // PINCH lifecycle
    if (result.pose === 'PINCH') {
      if (prevPose !== 'PINCH') {
        // Pinch begins
        this.pinchStartTs = tsMs;
        this.pinchStartPos = pointer;
        this.dragPathPx = 0;
        if (this.voiceDragPending) {
          // Voice armed a drag; the pinch grabs the element under the pointer.
          this.voiceDragPending = false;
          this.dragging = true;
          this.dragSource = 'voice';
          this.setState('DRAGGING');
          events.push({
            type: 'drag',
            phase: 'start',
            position: pointer,
            pathLengthPx: 0,
            durationMs: 0,
            source: 'voice',
          });
        } else if (this.gestureEnabled('pinch')) {
          this.setState('ARMED');
        }
      } else {
        // Pinch continues
        const elapsed = tsMs - this.pinchStartTs;
        if (this.dragging) {
          // Continuous drag movement
          if (this.pinchStartPos) {
            this.dragPathPx += Math.hypot(
              pointer.x - (this.lastDragPointer?.x ?? this.pinchStartPos.x),
              pointer.y - (this.lastDragPointer?.y ?? this.pinchStartPos.y)
            );
          }
          this.lastDragPointer = pointer;
          this.setState('DRAGGING');
          events.push({
            type: 'drag',
            phase: 'move',
            position: pointer,
            pathLengthPx: Math.round(this.dragPathPx),
            durationMs: Math.round(elapsed),
            source: this.dragSource,
          });
        } else if (
          this.gestureEnabled('pinch') &&
          elapsed >= this.calibration.pinchDragMinMs &&
          this.movedBeyond(pointer, this.pinchStartPos, 0.05)
        ) {
          // Pinch + sustained movement = DRAG start
          this.dragging = true;
          this.dragSource = 'pinch';
          this.lastDragPointer = pointer;
          this.setState('DRAGGING');
          events.push({
            type: 'drag',
            phase: 'start',
            position: this.pinchStartPos || pointer,
            pathLengthPx: 0,
            durationMs: Math.round(elapsed),
            source: 'pinch',
          });
        } else if (
          this.gestureEnabled('pinch_hold') &&
          elapsed >= this.calibration.pinchSelectMinMs &&
          !this.movedBeyond(pointer, this.pinchStartPos, 0.05)
        ) {
          // Sustained stationary pinch = SELECT (fires once)
          if (!this.selectFired) {
            this.selectFired = true;
            events.push(this.makeActionEvent('pinch_hold', result.confidence, tsMs, events, pointer));
            this.setState('TRIGGERED');
          } else {
            this.setState('HELD');
          }
        } else {
          this.setState('ARMED');
        }
      }
    } else if (prevPose === 'PINCH') {
      // Pinch released -> click / select / drag end
      const elapsed = tsMs - this.pinchStartTs;
      if (this.dragging) {
        events.push({
          type: 'drag',
          phase: 'end',
          position: pointer,
          pathLengthPx: Math.round(this.dragPathPx),
          durationMs: Math.round(elapsed),
          source: this.dragSource,
        });
        this.dragging = false;
        this.lastDragPointer = null;
        this.setState('RELEASED');
      } else if (this.selectFired) {
        // Select already fired during the hold
        this.selectFired = false;
        this.setState('RELEASED');
      } else if (this.gestureEnabled('pinch')) {
        this.selectFired = false;
        if (elapsed < this.pinchClickMaxMs()) {
          // Quick tap -> click (with double-click combination)
          const clickEvents = this.registerTap(pointer, tsMs, result.confidence);
          events.push(...clickEvents);
        } else if (
          elapsed >= this.calibration.pinchSelectMinMs &&
          !this.movedBeyond(pointer, this.pinchStartPos, 0.05) &&
          this.gestureEnabled('pinch_hold')
        ) {
          // Released after select threshold without the select having fired
          // (e.g. slightly moving hand) -> still honor as select.
          events.push(this.makeActionEvent('pinch_hold', result.confidence, tsMs, events, pointer));
          this.setState('TRIGGERED');
        } else {
          // Ambiguous duration -> conservative click fallback with feedback
          events.push(this.registerTap(pointer, tsMs, result.confidence, true)[0]);
        }
      } else {
        this.setState('HOVER');
      }
      this.pinchStartPos = null;
    } else if (result.pose === 'TWO_FINGER') {
      // Two-finger: scroll when moving, right click when released still
      if (prevPose !== 'TWO_FINGER') {
        this.twoFingerStartPos = pointer;
        this.twoFingerTotalDisp = 0;
        if (this.gestureEnabled('two_finger')) this.setState('ARMED');
      } else {
        const disp = this.twoFingerStartPos
          ? Math.hypot(pointer.x - this.twoFingerStartPos.x, pointer.y - this.twoFingerStartPos.y)
          : 0;
        this.twoFingerTotalDisp = disp;
        const scrollThresholdPx = 0.035 * this.viewportWidth;
        if (disp > scrollThresholdPx && this.gestureEnabled('two_finger_move')) {
          const scrollEvents = this.emitTwoFingerScroll(pointer, tsMs);
          events.push(...scrollEvents);
        }
      }
    } else if (prevPose === 'TWO_FINGER') {
      // Two-finger released
      if (this.twoFingerTotalDisp < 0.035 * this.viewportWidth && this.gestureEnabled('two_finger')) {
        events.push(this.registerDiscreteClick('right_click', 'two_finger', pointer, tsMs, 0.9));
      }
      this.twoFingerStartPos = null;
      this.twoFingerTotalDisp = 0;
      this.setState('RELEASED');
    } else if (result.pose === 'POINTING') {
      // Pointing drives the pointer; flicks (swipes) trigger discrete actions.
      this.palmHistory.push({ ts: tsMs, x: hand[9].x, y: hand[9].y });
      this.palmHistory = this.palmHistory.filter((p) => tsMs - p.ts <= 400);
      const swipe = this.detectSwipeFromHistory(tsMs);
      if (swipe) {
        events.push(swipe);
      } else {
        this.setState('HOVER');
      }
    } else {
      // OPEN_PALM / THUMBS / NONE poses: handled by the dwell pipeline or idle.
      this.palmHistory = [];
      if (this.state !== 'DRAGGING' && this.state !== 'PAUSED') {
        this.setState(result.pose === 'NONE' ? 'HOVER' : 'HOVER');
      }
    }

    return events;
  }

  // ------------------------------------------------------------------
  // Internal helpers
  // ------------------------------------------------------------------

  private lastEmittedPointer: PointerPosition | null = null;
  private lastDragPointer: PointerPosition | null = null;
  private selectFired = false;

  private now(): number {
    return Date.now();
  }

  private pinchClickMaxMs(): number {
    return this.calibration.pinchClickMaxMs;
  }

  private gestureEnabled(gestureKey: string): boolean {
    const enabled = this.calibration.enabledGestures;
    if (enabled && gestureKey in enabled) {
      return Boolean(enabled[gestureKey]);
    }
    return true;
  }

  private selectHand(hands: Landmark3D[][], labels: string[]): Landmark3D[] | null {
    if (hands.length === 1) return hands[0];
    const pref = this.calibration.handedness;
    if (pref !== 'Either') {
      const idx = labels.findIndex((l) => l === pref);
      if (idx >= 0) return hands[idx];
    }
    // Prefer the right hand as the dominant interaction hand by convention
    const rightIdx = labels.findIndex((l) => l === 'Right');
    return hands[rightIdx >= 0 ? rightIdx : 0];
  }

  private toPixels(norm: { x: number; y: number }): PointerPosition {
    return {
      x: Math.round(norm.x * this.viewportWidth),
      y: Math.round(norm.y * this.viewportHeight),
    };
  }

  private movedBeyond(
    current: PointerPosition,
    origin: PointerPosition | null,
  thresholdNorm: number
  ): boolean {
    if (!origin) return false;
    const thresholdPx = thresholdNorm * this.viewportWidth;
    return Math.hypot(current.x - origin.x, current.y - origin.y) > thresholdPx;
  }

  private setState(next: InteractionState): void {
    if (this.state === 'EMERGENCY_STOPPED' && next !== 'HOVER' && next !== 'IDLE' && next !== 'PAUSED') {
      // Emergency lock can only be cleared explicitly.
      return;
    }
    this.state = next;
  }

  /**
   * Register a quick pinch tap: combines two taps within the double-click
   * window into a double_click, otherwise a left_click. Debounced.
   */
  private registerTap(
    pointer: PointerPosition,
    tsMs: number,
    confidence: number,
    forceSingle = false
  ): EngineEvent[] {
    const isDouble =
      !forceSingle &&
      this.lastTapTs > 0 &&
      tsMs - this.lastTapTs <= this.calibration.doubleClickWindowMs;
    this.lastTapTs = tsMs;
    if (isDouble) {
      this.lastTapTs = 0; // consume the pair
      return [this.registerDiscreteClick('double_click', 'pinch', pointer, tsMs, confidence)];
    }
    return [this.registerDiscreteClick('left_click', 'pinch', pointer, tsMs, confidence)];
  }

  /**
   * Emit a discrete click action with debounce protection so one gesture
   * cannot generate dozens of clicks.
   */
  private registerDiscreteClick(
    action: string,
    gesture: string,
    pointer: PointerPosition,
    tsMs: number,
    confidence: number
  ): EngineEvent {
    const debounced =
      this.lastClickTs > 0 &&
      tsMs - this.lastClickTs < this.calibration.clickDebounceMs &&
      this.lastClickAction === action;
    if (debounced) {
      return {
        type: 'feedback',
        level: 'warn',
        message: 'Click debounced (too soon after previous click).',
      };
    }
    this.lastClickTs = tsMs;
    this.lastClickAction = action;
    this.setState('TRIGGERED');
    // double_click is a timing-derived action (two quick taps), not a single
    // gesture decision — it must NOT be remapped through the gesture map
    // (otherwise a pinch->left_click mapping would swallow it).
    const mapped =
      action === 'double_click' ? action : this.resolveAction(gesture, action);
    return {
      type: 'action',
      action: mapped,
      gesture,
      confidence,
      position: pointer,
      state: 'TRIGGERED',
      context: { spatial_x: pointer.x, spatial_y: pointer.y, discrete: true },
    };
  }

  private makeActionEvent(
    gestureKey: string,
    confidence: number,
    tsMs: number,
    _events: EngineEvent[],
    pointer?: PointerPosition
  ): EngineEvent {
    const action = this.resolveAction(gestureKey, null);
    const pos = pointer || (this.pointerNorm ? this.toPixels(this.pointerNorm) : null);
    this.lastClickTs = tsMs;
    this.lastClickAction = action;
    return {
      type: 'action',
      action,
      gesture: gestureKey,
      confidence,
      position: pos,
      state: 'TRIGGERED',
      context: pos ? { spatial_x: pos.x, spatial_y: pos.y } : {},
    };
  }

  /** Resolve a gesture to its action via the worker's personalized map. */
  private resolveAction(gestureKey: string, fallbackAction: string | null): string {
    const mapped = this.gestureActionMap[gestureKey];
    if (mapped) return mapped;
    return fallbackAction || gestureKey;
  }

  private emitTwoFingerScroll(pointer: PointerPosition, tsMs: number): EngineEvent[] {
    const events: EngineEvent[] = [];
    if (tsMs - this.twoFingerLastScrollTs < this.calibration.scrollThrottleMs) {
      return events;
    }
    this.twoFingerLastScrollTs = tsMs;
    const origin = this.twoFingerStartPos!;
    const dx = pointer.x - origin.x;
    const dy = pointer.y - origin.y;
    // Dominant axis decides direction; inverted like a trackpad
    // (hand moves down -> content scrolls up i.e. "scroll up" page movement).
    let direction: 'up' | 'down' | 'left' | 'right';
    if (Math.abs(dy) >= Math.abs(dx)) {
      direction = dy < 0 ? 'down' : 'up';
    } else {
      direction = dx < 0 ? 'right' : 'left';
    }
    const amount = Math.round(
      Math.hypot(dx, dy) * (this.calibration.scrollSensitivity / this.viewportWidth)
    );
    events.push({
      type: 'scroll',
      direction,
      amountPx: Math.max(40, Math.min(1200, amount)),
      position: pointer,
      source: 'two_finger',
    });
    return events;
  }

  private detectSwipeFromHistory(tsMs: number): EngineEvent | null {
    // Re-arm once the cooldown since the last swipe has fully elapsed, so
    // repeated flicks work without the hand having to leave the frame.
    if (!this.swipeArmed && tsMs - this.lastSwipeTs >= 600) {
      this.swipeArmed = true;
    }
    if (!this.swipeArmed || this.palmHistory.length < 3) return null;
    const newest = this.palmHistory[this.palmHistory.length - 1];
    const oldest = this.palmHistory[0];
    const dtMs = newest.ts - oldest.ts;
    if (dtMs < 60 || dtMs > 400) return null;

    // Mirror x so swipes match the user's frame of reference
    const dx = (1 - newest.x) - (1 - oldest.x);
    const dy = newest.y - oldest.y;
    const thresholdX = 0.12;
    const thresholdY = 0.1;
    const swipe = detectSwipe({ dx, dy }, thresholdX, thresholdY);
    if (!swipe) return null;
    if (!this.gestureEnabled(swipe)) return null;

    // Cooldown: one swipe per gesture, re-arm after brief pause
    if (tsMs - this.lastSwipeTs < 600) return null;
    this.lastSwipeTs = tsMs;
    this.swipeArmed = false;
    this.palmHistory = [];

    const action = this.resolveAction(swipe, null);
    const pos = this.pointerNorm ? this.toPixels(this.pointerNorm) : null;
    this.setState('TRIGGERED');
    return {
      type: 'action',
      action,
      gesture: swipe,
      confidence: 0.88,
      position: pos,
      state: 'TRIGGERED',
      context: {
        swipe: true,
        direction: swipe.replace('swipe_', ''),
        ...(pos ? { spatial_x: pos.x, spatial_y: pos.y } : {}),
      },
    };
  }

  /** Arm a voice-initiated drag: the next pinch grabs instead of clicking. */
  armVoiceDrag(): void {
    this.voiceDragPending = true;
  }

  isVoiceDragArmed(): boolean {
    return this.voiceDragPending;
  }

  private handleNoHand(): EngineEvent[] {
    const events: EngineEvent[] = [];
    if (this.dragging) {
      // Hand lost mid-drag: end the drag safely
      const pos = this.pointerNorm ? this.toPixels(this.pointerNorm) : { x: 0, y: 0 };
      events.push({
        type: 'drag',
        phase: 'end',
        position: pos,
        pathLengthPx: Math.round(this.dragPathPx),
        durationMs: Math.round(this.lastFrameTs - this.pinchStartTs),
        source: this.dragSource,
      });
      this.dragging = false;
    }
    this.resetTransientTracking();
    this.hasPointer = false;
    this.pointerNorm = null;
    this.pose = 'NONE';
    if (this.emergencyStopped) {
      this.setState('EMERGENCY_STOPPED');
    } else if (this.paused) {
      this.setState('PAUSED');
    } else {
      this.setState('IDLE');
    }
    events.push({ type: 'state', state: this.state, pose: 'NONE' });
    return events;
  }

  private resetTransientTracking(): void {
    this.pinchStartTs = 0;
    this.pinchStartPos = null;
    this.lastDragPointer = null;
    this.dragPathPx = 0;
    this.dragging = false;
    this.selectFired = false;
    this.twoFingerStartPos = null;
    this.twoFingerTotalDisp = 0;
    this.palmHistory = [];
    this.swipeArmed = true;
    this.lastEmittedPointer = null;
  }
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}
