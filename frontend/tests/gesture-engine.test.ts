/**
 * WorkerGestureEngine + hand pose classifier unit tests.
 *
 * Pure-logic tests (no React, no DOM, no camera) for the real-time gesture
 * interaction engine: pointer movement, smoothing, jitter deadband, pinch
 * click/double-click/debounce/select/drag, two-finger scroll/right-click,
 * swipes, FIST emergency stop, pause semantics, personalized mapping, and
 * calibration conversion.
 *
 * Run via: node scripts/run-engine-tests.mjs  (compiles with tsc first)
 */

import {
  WorkerGestureEngine,
  EngineEvent,
  engineCalibrationFromBackend,
  engineCalibrationToBackend,
} from '../worker/lib/gestureEngine';
import { classifyHandPose, detectSwipe, poseToGestureKey } from '../worker/lib/handPoses';
import { computeContainTransform } from '../worker/lib/cameraTransform';

// ---------------------------------------------------------------------------
// Tiny test harness (no external runner available in this repo)
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;
const failures: string[] = [];

function test(name: string, fn: () => void | Promise<void>): void {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    failed++;
    const msg = err instanceof Error ? `${err.message}` : String(err);
    failures.push(`${name}: ${msg}`);
    console.error(`  ✗ ${name}\n      ${msg}`);
  }
}

function assert(cond: boolean, message?: string): void {
  if (!cond) throw new Error(message || 'assertion failed');
}

function assertEqual<T>(actual: T, expected: T, message?: string): void {
  if (actual !== expected) {
    throw new Error(`${message || 'assertEqual'}: expected ${String(expected)}, got ${String(actual)}`);
  }
}

// ---------------------------------------------------------------------------
// Synthetic hand factory (21 landmarks, classifiable by the shared classifier)
// ---------------------------------------------------------------------------

interface Pt {
  x: number;
  y: number;
}

const WRIST: Pt = { x: 0.5, y: 0.6 };
const THUMB = [{ x: 0.46, y: 0.58 }, { x: 0.45, y: 0.55 }, { x: 0.45, y: 0.52 }] as const;

/** Finger base positions: mcp, pip, dip-ish, tip per finger. */
function fingerPoints(mcpX: number, extended: boolean): [Pt, Pt, Pt, Pt] {
  const mcp: Pt = { x: mcpX, y: 0.55 };
  if (extended) {
    return [mcp, { x: mcpX + 0.01, y: 0.48 }, { x: mcpX + 0.015, y: 0.44 }, { x: mcpX + 0.02, y: 0.4 }];
  }
  return [mcp, { x: mcpX + 0.01, y: 0.52 }, { x: mcpX + 0.01, y: 0.53 }, { x: mcpX + 0.005, y: 0.53 }];
}

type HandSpec = {
  pointing?: boolean;
  pinch?: boolean;
  twoFinger?: boolean;
  fist?: boolean;
  openPalm?: boolean;
  thumbsUp?: boolean;
  thumbsDown?: boolean;
};

function buildHand(spec: HandSpec, shift: Pt = { x: 0, y: 0 }): { x: number; y: number; z: number }[] {
  const lm: Pt[] = new Array(21).fill(null).map(() => ({ x: 0.5, y: 0.6 }));

  lm[0] = { ...WRIST };
  lm[1] = { ...THUMB[0] };
  lm[2] = { ...THUMB[1] };
  lm[3] = { ...THUMB[2] };

  const idx = spec.pinch;
  const pointIdx = spec.pointing || spec.twoFinger || spec.openPalm;
  const midExt = spec.twoFinger || spec.openPalm || false;
  const ringExt = spec.openPalm || false;
  const pinkyExt = spec.openPalm || false;

  // index
  const [iMcp, iPip, iDip, iTip] = fingerPoints(0.52, pointIdx === true);
  lm[5] = iMcp;
  lm[6] = iPip;
  lm[7] = iDip;
  lm[8] = iTip;
  // middle
  const [mMcp, mPip, mDip, mTip] = fingerPoints(0.56, midExt);
  lm[9] = mMcp;
  lm[10] = mPip;
  lm[11] = mDip;
  lm[12] = mTip;
  // ring
  const [rMcp, rPip, rDip, rTip] = fingerPoints(0.6, ringExt);
  lm[13] = rMcp;
  lm[14] = rPip;
  lm[15] = rDip;
  lm[16] = rTip;
  // pinky
  const [pMcp, pPip, pDip, pTip] = fingerPoints(0.63, pinkyExt);
  lm[17] = pMcp;
  lm[18] = pPip;
  lm[19] = pDip;
  lm[20] = pTip;

  if (spec.pinch) {
    // thumb tip meets index tip (both near the index tip location)
    lm[4] = { x: 0.51, y: 0.505 };
    lm[8] = { x: 0.515, y: 0.5 };
  } else if (spec.fist) {
    lm[4] = { x: 0.47, y: 0.54 };
    lm[8] = { x: 0.53, y: 0.52 };
  } else if (spec.thumbsUp) {
    lm[4] = { x: 0.46, y: 0.42 };
  } else if (spec.thumbsDown) {
    lm[4] = { x: 0.46, y: 0.68 };
  } else {
    lm[4] = { x: 0.46, y: 0.56 }; // thumb resting beside the palm (no thumbs-up)
  }

  // Apply a global spatial shift (hand translation) to every landmark.
  return lm.map((p) => ({ x: p.x + shift.x, y: p.y + shift.y, z: 0 }));
}

const HANDS = {
  pointing: () => buildHand({ pointing: true }),
  pinch: (shift?: Pt) => buildHand({ pinch: true }, shift),
  twoFinger: (shift?: Pt) => buildHand({ twoFinger: true }, shift),
  fist: () => buildHand({ fist: true }),
  openPalm: () => buildHand({ openPalm: true }),
  thumbsUp: () => buildHand({ thumbsUp: true }),
  thumbsDown: () => buildHand({ thumbsDown: true }),
};

const CANONICAL_MAP: Record<string, string> = {
  pinch: 'left_click',
  pinch_hold: 'select_item',
  two_finger: 'right_click',
  fist: 'emergency_stop',
  swipe_right: 'next_step',
  swipe_left: 'previous_step',
  swipe_up: 'scroll_up',
  swipe_down: 'scroll_down',
  thumbs_up: 'confirm_action',
  thumbs_down: 'cancel_action',
  open_palm: 'pause_session',
};

function newEngine(map: Record<string, string> = CANONICAL_MAP): WorkerGestureEngine {
  return new WorkerGestureEngine({}, map, { width: 1280, height: 720 });
}

/**
 * Feed a pose for `frames` consecutive frames (50ms apart) starting at t0 —
 * mirrors a real camera stream where a pose persists across many frames and
 * must clear the engine's temporal stability buffer (poseStabilityFrames).
 * Returns all emitted events.
 */
function feed(
  engine: WorkerGestureEngine,
  makeHand: () => { x: number; y: number; z: number }[],
  t0: number,
  frames = 4,
  stepMs = 50
): EngineEvent[] {
  const all: EngineEvent[] = [];
  for (let i = 0; i < frames; i++) {
    all.push(...engine.processFrame([makeHand()], ['Right'], t0 + i * stepMs));
  }
  return all;
}

/** Timestamp just after feeding (next frame time). */
const afterFeed = (t0: number, frames = 4, stepMs = 50) => t0 + frames * stepMs;

function actionsOf(events: EngineEvent[]): EngineEvent[] {
  return events.filter((e) => e.type === 'action');
}

function countBy<T>(items: T[], pred: (t: T) => boolean): number {
  return items.filter(pred).length;
}

// ---------------------------------------------------------------------------
// 1. Hand pose classifier
// ---------------------------------------------------------------------------

console.log('\n— handPoses classifier —');

test('PINCH hand classifies as PINCH', () => {
  const r = classifyHandPose(HANDS.pinch());
  assertEqual(r.pose, 'PINCH');
  assert(r.confidence >= 0.8, 'pinch confidence should be >= 0.8');
});

test('POINTING hand classifies as POINTING', () => {
  const r = classifyHandPose(HANDS.pointing());
  assertEqual(r.pose, 'POINTING');
});

test('TWO_FINGER hand classifies as TWO_FINGER', () => {
  const r = classifyHandPose(HANDS.twoFinger());
  assertEqual(r.pose, 'TWO_FINGER');
});

test('FIST hand classifies as FIST', () => {
  const r = classifyHandPose(HANDS.fist());
  assertEqual(r.pose, 'FIST');
});

test('OPEN_PALM hand classifies as OPEN_PALM', () => {
  const r = classifyHandPose(HANDS.openPalm());
  assertEqual(r.pose, 'OPEN_PALM');
});

test('THUMBS_UP / THUMBS_DOWN classify correctly', () => {
  assertEqual(classifyHandPose(HANDS.thumbsUp()).pose, 'THUMBS_UP');
  assertEqual(classifyHandPose(HANDS.thumbsDown()).pose, 'THUMBS_DOWN');
});

test('poseToGestureKey maps poses to mapping keys', () => {
  assertEqual(poseToGestureKey('THUMBS_UP'), 'thumbs_up');
  assertEqual(poseToGestureKey('PINCH'), 'pinch');
  assertEqual(poseToGestureKey('FIST'), 'fist');
});

test('detectSwipe thresholds', () => {
  assertEqual(detectSwipe({ dx: 0.2, dy: 0 }, 0.12, 0.1), 'swipe_right');
  assertEqual(detectSwipe({ dx: -0.2, dy: 0 }, 0.12, 0.1), 'swipe_left');
  assertEqual(detectSwipe({ dx: 0, dy: -0.15 }, 0.12, 0.1), 'swipe_up');
  assertEqual(detectSwipe({ dx: 0, dy: 0.15 }, 0.12, 0.1), 'swipe_down');
  assertEqual(detectSwipe({ dx: 0.05, dy: 0.03 }, 0.12, 0.1), null);
});

// ---------------------------------------------------------------------------
// 2. Pointer movement: sensitivity, mirror, smoothing, jitter deadband
// ---------------------------------------------------------------------------

console.log('\n— pointer movement —');

test('pointing hand drives the pointer (mirrored, sensitivity-amplified)', () => {
  const engine = newEngine();
  // index tip at x=0.54 (camera) -> mirrored rawX = 0.46
  const events = engine.processFrame([HANDS.pointing()], ['Right'], 1000);
  const ptr = events.find((e) => e.type === 'pointer');
  assert(!!ptr, 'first frame must emit a pointer event');
  if (ptr && ptr.type === 'pointer') {
    // target = 0.5 + (0.46 - 0.5) * 1.4 = 0.444 -> x = 568 px (viewport 1280)
    assert(Math.abs(ptr.position.x - 568) <= 2, `pointer x ~568 expected, got ${ptr.position.x}`);
    assert(ptr.position.y >= 0 && ptr.position.y <= 720, 'pointer y within viewport');
  }
  const viaGetter = engine.getPointer();
  assert(!!viaGetter, 'getPointer returns a position');
});

test('jitter deadband suppresses micro-movements', () => {
  const engine = newEngine();
  engine.processFrame([HANDS.pointing()], ['Right'], 1000);
  // 0.003 normalized shift -> ~4 px after amplification: below the 15 px deadband
  const jittered = engine.processFrame(
    [buildHand({ pointing: true }, { x: 0.003, y: 0 })],
    ['Right'],
    1050
  );
  assertEqual(
    countBy(jittered, (e) => e.type === 'pointer'),
    0,
    'micro-movement must not emit a pointer event'
  );
  // A large movement does emit.
  const moved = engine.processFrame(
    [buildHand({ pointing: true }, { x: -0.15, y: 0.1 })],
    ['Right'],
    1100
  );
  assert(countBy(moved, (e) => e.type === 'pointer') === 1, 'large movement emits a pointer event');
});

test('EMA smoothing: pointer converges gradually, not teleports', () => {
  const engine = newEngine();
  engine.processFrame([HANDS.pointing()], ['Right'], 1000);
  const before = engine.getPointer()!;
  // Large jump of the hand
  const events = engine.processFrame(
    [buildHand({ pointing: true }, { x: -0.2, y: 0 })],
    ['Right'],
    1060
  );
  const ptr = events.find((e) => e.type === 'pointer');
  assert(!!ptr && ptr.type === 'pointer', 'pointer event emitted');
  if (ptr && ptr.type === 'pointer') {
    const jump = Math.abs(ptr.position.x - before.x);
    // Full jump would be ~0.2*1.4*1280 = 358 px; EMA(0.35) must land well below
    assert(jump > 40 && jump < 300, `smoothed jump expected between 40 and 300 px, got ${jump}`);
  }
});

test('updateCalibration changes pointer sensitivity live', () => {
  const engine = newEngine();
  engine.processFrame([HANDS.pointing()], ['Right'], 1000);
  engine.updateCalibration({ pointerSensitivity: 1.0 });
  const events = engine.processFrame(
    [buildHand({ pointing: true }, { x: -0.2, y: 0 })],
    ['Right'],
    2000
  );
  const ptr = events.find((e) => e.type === 'pointer');
  assert(!!ptr && ptr.type === 'pointer', 'pointer emitted after sensitivity change');
  if (ptr && ptr.type === 'pointer') {
    // With sensitivity 1.0 the mirrored jump is 0.2 * 1280 = 256 px pre-smoothing
    assert(ptr.position.x > 600, 'sensitivity 1.0 moves pointer less than 1.4 did');
  }
});

// ---------------------------------------------------------------------------
// 3. Pinch lifecycle: click, double click, debounce, select, drag
// ---------------------------------------------------------------------------

console.log('\n— pinch click / select / drag —');

test('quick pinch tap = left_click', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4); // establish pointer (stable)
  feed(engine, HANDS.pinch, 1200, 4); // pinch commits after stability buffer
  const events = feed(engine, HANDS.pointing, 1400, 4); // released
  const acts = actionsOf(events);
  assertEqual(acts.length, 1, 'exactly one action on release');
  if (acts[0] && acts[0].type === 'action') {
    assertEqual(acts[0].action, 'left_click');
    assertEqual(acts[0].gesture, 'pinch');
    assert(!!acts[0].position, 'click carries the pointer position (spatial context)');
    if (acts[0].context) {
      assert('spatial_x' in acts[0].context, 'spatial_x present for multimodal fusion');
    }
  }
});

test('two quick taps within the double-click window = double_click', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  feed(engine, HANDS.pinch, 1200, 4); // tap 1 pinch
  let events = feed(engine, HANDS.pointing, 1400, 4); // tap 1 release
  assertEqual(actionsOf(events)[0]?.type === 'action' && (actionsOf(events)[0] as any).action, 'left_click');
  feed(engine, HANDS.pinch, 1450, 4); // tap 2 pinch (within double-click window of the release)
  events = feed(engine, HANDS.pointing, 1650, 4); // tap 2 release
  const acts = actionsOf(events);
  assertEqual(acts.length, 1);
  if (acts[0] && acts[0].type === 'action') {
    assertEqual(acts[0].action, 'double_click');
  }
});

test('click debounce suppresses a third rapid click', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  feed(engine, HANDS.pinch, 1200, 4);
  // tap 1 release action fires when POINTING re-commits (3rd frame, t=1500)
  const tap1 = feed(engine, HANDS.pointing, 1400, 4);
  assertEqual(actionsOf(tap1).length, 1);
  // tap 2 release fires at t=1950: 450ms after tap 1 — OUTSIDE the 400ms
  // double-click window, INSIDE the 700ms debounce window.
  feed(engine, HANDS.pinch, 1650, 4);
  const events = feed(engine, HANDS.pointing, 1850, 4);
  const acts = actionsOf(events);
  assertEqual(acts.length, 0, 'debounced click must not emit an action');
  const warn = events.find((e) => e.type === 'feedback');
  assert(!!warn, 'debounce produces user feedback');
});

test('sustained stationary pinch = select_item, fires exactly once', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  const committed = feed(engine, HANDS.pinch, 1200, 4); // pinch begins (commits ~1300)
  assertEqual(actionsOf(committed).length, 0);
  // hold stationary well past the select threshold (650ms)
  const hold: EngineEvent[] = [];
  for (let t = 1400; t <= 2600; t += 50) hold.push(...engine.processFrame([HANDS.pinch()], ['Right'], t));
  const acts = actionsOf(hold);
  assertEqual(acts.length, 1, 'select fires once during the hold');
  if (acts[0] && acts[0].type === 'action') {
    assertEqual(acts[0].action, 'select_item');
    assertEqual(acts[0].gesture, 'pinch_hold');
  }
  // further holding must not fire again
  const more: EngineEvent[] = [];
  for (let t = 2650; t <= 3000; t += 50) more.push(...engine.processFrame([HANDS.pinch()], ['Right'], t));
  assertEqual(actionsOf(more).length, 0, 'select must not repeat while held');
  // release after select: no additional action
  const rel = feed(engine, HANDS.pointing, 3100, 4);
  assertEqual(actionsOf(rel).length, 0, 'release after select is silent');
});

test('pinch + movement = continuous drag (start/move/end)', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  feed(engine, HANDS.pinch, 1200, 4); // pinch commits ~1300
  // Move the pinched hand (shift whole hand left in camera = pointer right)
  // Feed several frames: EMA-smoothed pointer must converge past the drag
  // movement threshold (0.05 normalized) after the 350ms drag arm time.
  const startEvents: EngineEvent[] = [];
  for (let i = 0; i < 10; i++) {
    startEvents.push(
      ...engine.processFrame([buildHand({ pinch: true }, { x: -0.1 - i * 0.005, y: 0.05 })], ['Right'], 1400 + i * 50)
    );
  }
  const start = startEvents.find((e) => e.type === 'drag' && e.phase === 'start');
  assert(!!start, 'drag start must fire after sustained pinch + movement');
  const moveEvents = engine.processFrame([buildHand({ pinch: true }, { x: -0.14, y: 0.07 })], ['Right'], 1950);
  const move = moveEvents.find((e) => e.type === 'drag' && e.phase === 'move');
  assert(!!move, 'drag move events stream while dragging');
  if (move && move.type === 'drag') {
    assert(move.pathLengthPx > 0, 'drag accumulates path length');
    assertEqual(move.source, 'pinch');
  }
  const endEvents = feed(engine, HANDS.pointing, 2000, 4);
  const end = endEvents.find((e) => e.type === 'drag' && e.phase === 'end');
  assert(!!end, 'drag end fires on pinch release');
  if (end && end.type === 'drag') {
    assert(end.durationMs > 0, 'drag duration recorded');
  }
  assert(
    engine.getState() === 'RELEASED' || engine.getState() === 'HOVER',
    'engine settles to a non-dragging state after release'
  );
});

test('hand lost mid-drag ends the drag safely', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  feed(engine, HANDS.pinch, 1200, 4);
  for (let i = 0; i < 8; i++) {
    engine.processFrame([buildHand({ pinch: true }, { x: -0.1 - i * 0.005, y: 0.05 })], ['Right'], 1400 + i * 50);
  }
  const events = engine.processFrame([], [], 1850); // hand lost
  const end = events.find((e) => e.type === 'drag' && e.phase === 'end');
  assert(!!end, 'losing the hand must end the drag');
  assertEqual(engine.getState(), 'IDLE');
});

// ---------------------------------------------------------------------------
// 4. Two-finger: scroll + right click
// ---------------------------------------------------------------------------

console.log('\n— two-finger scroll / right click —');

test('two-finger held still then released = right_click', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  feed(engine, HANDS.twoFinger, 1200, 4);
  const events = feed(engine, HANDS.pointing, 1400, 4); // released still
  const acts = actionsOf(events);
  assertEqual(acts.length, 1);
  if (acts[0] && acts[0].type === 'action') {
    assertEqual(acts[0].action, 'right_click');
    assertEqual(acts[0].gesture, 'two_finger');
  }
});

test('two-finger movement emits throttled scroll events', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  feed(engine, HANDS.twoFinger, 1200, 4);
  // Move hand down in camera space (y +0.1) -> pointer y increases -> "up"
  // scroll. The pointer is EMA-smoothed, so feed a few frames at the new
  // position until it converges past the scroll threshold.
  const down = buildHand({ twoFinger: true }, { x: 0, y: 0.1 });
  let scroll: EngineEvent | undefined;
  for (const ts of [1400, 1450, 1500, 1550]) {
    const evts = engine.processFrame([down], ['Right'], ts);
    scroll = scroll || evts.find((e) => e.type === 'scroll');
  }
  assert(!!scroll, 'two-finger movement must emit a scroll event');
  if (scroll && scroll.type === 'scroll') {
    assertEqual(scroll.direction, 'up');
    assert(scroll.amountPx >= 40, 'scroll amount clamped to a minimum of 40px');
    assertEqual(scroll.source, 'two_finger');
  }
  // Within the throttle window (180ms) no second scroll is emitted
  const more = engine.processFrame([buildHand({ twoFinger: true }, { x: 0, y: 0.12 })], ['Right'], 1600);
  assertEqual(countBy(more, (e) => e.type === 'scroll'), 0, 'scroll throttle must suppress rapid repeats');
  // After the throttle window it scrolls again
  const later = engine.processFrame([buildHand({ twoFinger: true }, { x: 0, y: 0.14 })], ['Right'], 1850);
  assert(countBy(later, (e) => e.type === 'scroll') === 1, 'scroll resumes after throttle window');
});

test('vertical hand-up movement scrolls down', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  feed(engine, HANDS.twoFinger, 1200, 4);
  const up = buildHand({ twoFinger: true }, { x: 0, y: -0.1 });
  let scroll: EngineEvent | undefined;
  for (const ts of [1400, 1450, 1500, 1550]) {
    const evts = engine.processFrame([up], ['Right'], ts);
    scroll = scroll || evts.find((e) => e.type === 'scroll');
  }
  assert(!!scroll && scroll.type === 'scroll' && scroll.direction === 'down');
});

// ---------------------------------------------------------------------------
// 5. Swipes (pointing flicks)
// ---------------------------------------------------------------------------

console.log('\n— swipe navigation —');

test('fast pointing flick right = swipe_right action (next_step)', () => {
  const engine = newEngine();
  // A RIGHT flick in the user's frame of reference = camera x DECREASING
  // (the pointer is mirrored). Displacement 0.30 over ~250ms = 1.2 units/s:
  // well above the velocity gate (0.55/s) and distance threshold (0.16).
  let flick: EngineEvent | null = null;
  for (let i = 0; i < 6; i++) {
    const evts = engine.processFrame(
      [buildHand({ pointing: true }, { x: -0.06 * i, y: 0 })],
      ['Right'],
      1000 + i * 50
    );
    const act = actionsOf(evts)[0];
    if (act) flick = act;
  }
  assert(!!flick, 'swipe must fire an action');
  if (flick && flick.type === 'action') {
    assertEqual(flick.action, 'next_step');
    assertEqual(flick.gesture, 'swipe_right');
  }
});

test('slow pointing drift does NOT fire a swipe (velocity gate)', () => {
  const engine = newEngine();
  // Same 0.30 displacement but over 1500ms = 0.2 units/s: natural aiming
  // movement, not a deliberate flick.
  let fired = 0;
  for (let i = 0; i < 10; i++) {
    const evts = engine.processFrame(
      [buildHand({ pointing: true }, { x: -0.033 * i, y: 0 })],
      ['Right'],
      1000 + i * 150
    );
    fired += countBy(evts, (e) => e.type === 'action');
  }
  assertEqual(fired, 0, 'slow drift must not trigger swipe actions');
});

test('swipe cooldown prevents double firing', () => {
  const engine = newEngine();
  const runFlick = (t0: number) => {
    let fired = 0;
    for (let i = 0; i < 6; i++) {
      const evts = engine.processFrame(
        [buildHand({ pointing: true }, { x: -0.06 * i, y: 0 })],
        ['Right'],
        t0 + i * 50
      );
      fired += countBy(evts, (e) => e.type === 'action');
    }
    return fired;
  };
  const first = runFlick(1000);
  assert(first >= 1, 'first flick fires');
  // Immediate second flick within the 600ms cooldown: no new action
  const second = runFlick(1300);
  assertEqual(second, 0, 'cooldown must suppress an immediate second swipe');
});

// ---------------------------------------------------------------------------
// 6. FIST emergency stop + engine lockout semantics
// ---------------------------------------------------------------------------

console.log('\n— emergency stop —');

test('FIST maps to emergency_stop immediately', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  // FIST commits on the FIRST frame (safety latency) — no stability delay.
  const events = engine.processFrame([HANDS.fist()], ['Right'], 1250);
  const acts = actionsOf(events);
  assertEqual(acts.length, 1);
  if (acts[0] && acts[0].type === 'action') {
    assertEqual(acts[0].action, 'emergency_stop');
    assertEqual(acts[0].gesture, 'fist');
  }
});

test('setEmergencyStopped blocks all frames until cleared', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  engine.setEmergencyStopped(true);
  assertEqual(engine.getState(), 'EMERGENCY_STOPPED');
  const blocked = engine.processFrame([HANDS.pinch()], ['Right'], 1300);
  assertEqual(blocked.length, 0, 'no events while emergency-stopped');
  engine.setEmergencyStopped(false);
  const resumed = engine.processFrame([HANDS.pointing()], ['Right'], 1400);
  assert(resumed.length > 0, 'engine processes frames again after clearing');
});

// ---------------------------------------------------------------------------
// 7. Pause semantics
// ---------------------------------------------------------------------------

console.log('\n— pause / resume —');

test('paused engine suppresses task gestures but keeps the pointer live', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  engine.setPaused(true);
  assertEqual(engine.getState(), 'PAUSED');
  // pointer still tracks
  const ev1 = engine.processFrame([buildHand({ pointing: true }, { x: -0.1, y: 0 })], ['Right'], 1300);
  assert(countBy(ev1, (e) => e.type === 'pointer') >= 1, 'pointer stays live while paused');
  // pinch click suppressed (feed full stable sequences)
  feed(engine, HANDS.pinch, 1400, 4);
  const ev2 = feed(engine, HANDS.pointing, 1600, 4);
  assertEqual(actionsOf(ev2).length, 0, 'no click actions while paused');
  // resume restores interaction
  engine.setPaused(false);
  feed(engine, HANDS.pinch, 2000, 4);
  const ev3 = feed(engine, HANDS.pointing, 2200, 4);
  assertEqual(actionsOf(ev3).length, 1, 'click works after resume');
  const resumed = actionsOf(ev3)[0];
  if (resumed && resumed.type === 'action') {
    assertEqual(resumed.action, 'left_click');
  }
});

// ---------------------------------------------------------------------------
// 8. Personalized mapping + gesture enable switches
// ---------------------------------------------------------------------------

console.log('\n— personalized mapping —');

test('worker-personalized mapping overrides the default action', () => {
  const engine = newEngine({ ...CANONICAL_MAP, pinch: 'double_click' });
  feed(engine, HANDS.pointing, 1000, 4);
  feed(engine, HANDS.pinch, 1200, 4);
  const events = feed(engine, HANDS.pointing, 1400, 4);
  const acts = actionsOf(events);
  assertEqual(acts.length, 1);
  if (acts[0] && acts[0].type === 'action') {
    assertEqual(acts[0].action, 'double_click', 'remapped pinch must resolve to double_click');
  }
});

test('disabled gesture produces no action', () => {
  const engine = new WorkerGestureEngine(
    { enabledGestures: { ...CANONICAL_MAP, pinch: false } as any },
    CANONICAL_MAP,
    { width: 1280, height: 720 }
  );
  // properly disable via calibration API
  engine.updateCalibration({ enabledGestures: { pinch: false, pinch_hold: false } });
  feed(engine, HANDS.pointing, 1000, 4);
  feed(engine, HANDS.pinch, 1200, 4);
  const events = feed(engine, HANDS.pointing, 1400, 4);
  assertEqual(actionsOf(events).length, 0, 'disabled pinch must not click');
});

test('handedness preference selects the right hand when two are present', () => {
  const engine = newEngine();
  engine.updateCalibration({ handedness: 'Left' });
  const leftHand = buildHand({ pointing: true }, { x: 0.2, y: 0 }); // x shifted far left
  const rightHand = buildHand({ pointing: true }, { x: -0.2, y: 0 });
  const events = engine.processFrame([rightHand, leftHand], ['Right', 'Left'], 1000);
  const ptr = events.find((e) => e.type === 'pointer');
  assert(!!ptr && ptr.type === 'pointer');
  if (ptr && ptr.type === 'pointer') {
    // left hand x=0.7 camera -> mirrored 0.3 -> amplified 0.5+(0.3-0.5)*1.4=0.22 -> ~282px
    assert(ptr.position.x < 400, 'preferred Left hand must drive the pointer');
  }
});

// ---------------------------------------------------------------------------
// 9. Voice-armed drag
// ---------------------------------------------------------------------------

console.log('\n— voice-armed drag —');

test('armVoiceDrag + pinch grabs instead of clicking', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  engine.armVoiceDrag();
  assertEqual(engine.isVoiceDragArmed(), true);
  // Feed the pinch long enough to commit through the stability buffer; the
  // grab happens on the committed PINCH entry edge.
  const startEvents: EngineEvent[] = [];
  let grabbed = false;
  for (let t = 1200; t < 1500 && !grabbed; t += 50) {
    const evts = engine.processFrame([HANDS.pinch()], ['Right'], t);
    startEvents.push(...evts);
    grabbed = evts.some((e) => e.type === 'drag' && e.phase === 'start');
  }
  const start = startEvents.find((e) => e.type === 'drag' && e.phase === 'start');
  assert(!!start, 'pinch after voice-arm must start a drag (not a click)');
  if (start && start.type === 'drag') assertEqual(start.source, 'voice');
  assertEqual(actionsOf(startEvents).length, 0, 'no click action when grabbing for voice drag');
  // move
  const moveEvents = engine.processFrame([buildHand({ pinch: true }, { x: -0.08, y: 0 })], ['Right'], 1550);
  assert(!!moveEvents.find((e) => e.type === 'drag' && e.phase === 'move'));
  // voice "drop" ends the drag
  const endEvents = engine.endExternalDrag();
  const end = endEvents.find((e) => e.type === 'drag' && e.phase === 'end');
  assert(!!end && end.type === 'drag' && end.source === 'voice');
});

test('beginExternalDrag starts a voice drag at the current pointer', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  const pos = engine.getPointer();
  const events = engine.beginExternalDrag('voice');
  const start = events.find((e) => e.type === 'drag' && e.phase === 'start');
  assert(!!start, 'external drag starts');
  if (start && start.type === 'drag' && pos) {
    assertEqual(start.position.x, pos.x);
  }
  assertEqual(engine.getState(), 'DRAGGING');
});

// ---------------------------------------------------------------------------
// 10. Calibration conversion (backend <-> engine)
// ---------------------------------------------------------------------------

console.log('\n— calibration conversion —');

test('engineCalibrationFromBackend maps snake_case keys', () => {
  const patch = engineCalibrationFromBackend({
    dwell_time_ms: 800,
    cursor_sensitivity: 2.2,
    scroll_sensitivity: 300,
    smoothing_alpha: 0.5,
    jitter_threshold: 0.02,
    handedness: 'Left',
    enabled_gestures: { pinch: true, fist: true },
    garbage_key: 'ignored',
  });
  assertEqual(patch.dwellTimeMs, 800);
  assertEqual(patch.pointerSensitivity, 2.2);
  assertEqual(patch.scrollSensitivity, 300);
  assertEqual(patch.smoothingAlpha, 0.5);
  assertEqual(patch.jitterThreshold, 0.02);
  assertEqual(patch.handedness, 'Left');
  assertEqual(patch.enabledGestures?.fist, true);
  assert(!('garbage_key' in (patch as object)), 'unknown keys ignored');
});

test('engineCalibrationToBackend round-trips', () => {
  const backend = engineCalibrationToBackend({
    dwellTimeMs: 900,
    pointerSensitivity: 1.8,
    scrollThrottleMs: 200,
    handedness: 'Right',
    enabledGestures: { pinch: false },
  });
  assertEqual(backend.dwell_time_ms, 900);
  assertEqual(backend.cursor_sensitivity, 1.8);
  assertEqual(backend.scroll_throttle_ms, 200);
  assertEqual(backend.handedness, 'Right');
  assertEqual(backend.enabled_gestures.pinch, false);
  const back = engineCalibrationFromBackend(backend);
  assertEqual(back.pointerSensitivity, 1.8);
  assertEqual(back.enabledGestures?.pinch, false);
});

test('engine adopts backend calibration (cursor_sensitivity honored)', () => {
  const engine = newEngine();
  engine.updateCalibration(engineCalibrationFromBackend({ cursor_sensitivity: 1.0 }));
  const cal = engine.getCalibration();
  assertEqual(cal.pointerSensitivity, 1.0);
});

// ---------------------------------------------------------------------------
// 11. Robustness & accuracy (negative cases)
// ---------------------------------------------------------------------------

console.log('\n— robustness / negative cases —');

test('pose flutter (single stray PINCH frames) produces NO clicks', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 6);
  // Stray single-frame pinch blips (landmark flutter near the threshold):
  // the stability buffer must not commit them, so no click ever fires.
  let actions = 0;
  let t = 1400;
  for (let blip = 0; blip < 5; blip++) {
    engine.processFrame([HANDS.pinch()], ['Right'], t); t += 50; // 1 stray frame
    actions += countBy(
      feed(engine, HANDS.pointing, t, 5),
      (e) => e.type === 'action'
    );
    t += 300;
  }
  assertEqual(actions, 0, 'single-frame pinch blips must never click');
});

test('pinch hysteresis: hovering near the pinch threshold does not flicker', () => {
  // Directly on the classifier: once PINCH is active, a thumb-index gap up to
  // the EXIT threshold still classifies as PINCH (no PINCH->NONE flutter).
  const tight = classifyHandPose(HANDS.pinch());
  assertEqual(tight.pose, 'PINCH');
  // Open the gap slightly (still below the exit threshold ~0.56):
  // build a pinch hand with the thumb tip pulled a little away.
  const loosePinch = buildHand({ pinch: true });
  loosePinch[4] = { x: loosePinch[4].x - 0.03, y: loosePinch[4].y - 0.03, z: 0 };
  const withoutHysteresis = classifyHandPose(loosePinch);
  const withHysteresis = classifyHandPose(loosePinch, { pinchActive: true });
  // The gap may now be past the ENTER threshold (so cold classify -> not pinch)
  // but hysteresis must keep the active pinch alive.
  if (withoutHysteresis.pose !== 'PINCH') {
    assertEqual(withHysteresis.pose, 'PINCH', 'exit hysteresis must hold an active pinch');
  } else {
    assertEqual(withHysteresis.pose, 'PINCH');
  }
});

test('hand too small / too far away is ignored (no pointer, no actions)', () => {
  const engine = newEngine();
  // Shrink the whole hand toward the frame center -> tiny palm size.
  const tiny = () => {
    const hand = HANDS.pointing();
    return hand.map((pt) => ({
      x: 0.5 + (pt.x - 0.5) * 0.22,
      y: 0.6 + (pt.y - 0.6) * 0.22,
      z: 0,
    }));
  };
  const events = feed(engine, tiny, 1000, 8);
  assertEqual(countBy(events, (e) => e.type === 'pointer'), 0, 'no pointer tracking for a tiny hand');
  assertEqual(countBy(events, (e) => e.type === 'action'), 0, 'no actions for a tiny hand');
  // A tiny FIST must not trigger the emergency stop either (unreliable input).
  const tinyFist = () => {
    const hand = HANDS.fist();
    return hand.map((pt) => ({
      x: 0.5 + (pt.x - 0.5) * 0.22,
      y: 0.6 + (pt.y - 0.6) * 0.22,
      z: 0,
    }));
  };
  const fistEvents = feed(engine, tinyFist, 1500, 6);
  assertEqual(countBy(fistEvents, (e) => e.type === 'action'), 0, 'distant FIST must not fire e-stop');
});

test('noisy landmarks: jittered PINCH hold still fires exactly one select', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  // Pinch held stationary with per-frame landmark noise (±0.006).
  const jitter = (amp: number) => () => {
    const hand = HANDS.pinch();
    return hand.map((pt) => ({
      x: pt.x + (Math.random() - 0.5) * amp,
      y: pt.y + (Math.random() - 0.5) * amp,
      z: 0,
    }));
  };
  const held: EngineEvent[] = [];
  for (let t = 1200; t <= 3000; t += 50) {
    held.push(...engine.processFrame([jitter(0.012)()], ['Right'], t));
  }
  const selects = held.filter((e) => e.type === 'action' && e.action === 'select_item');
  assertEqual(selects.length, 1, 'noisy stationary pinch fires exactly one select');
  // and no spurious clicks mixed in
  const clicks = held.filter((e) => e.type === 'action' && (e.action === 'left_click' || e.action === 'double_click'));
  assertEqual(clicks.length, 0, 'no spurious clicks from noise');
});

test('rapid repeated taps: exactly one action, extras debounced', () => {
  const engine = newEngine();
  feed(engine, HANDS.pointing, 1000, 4);
  let actions = 0;
  let feedbacks = 0;
  let t = 1200;
  // Four taps in quick succession (~200ms between releases)
  for (let tap = 0; tap < 4; tap++) {
    feed(engine, HANDS.pinch, t, 4); t += 200;
    const release = feed(engine, HANDS.pointing, t, 4); t += 300;
    actions += countBy(release, (e) => e.type === 'action');
    feedbacks += countBy(release, (e) => e.type === 'feedback');
  }
  assert(actions <= 2, `at most click+double-click from a rapid burst (got ${actions})`);
  assert(feedbacks >= 1, 'debounce feedback is emitted for suppressed repeats');
});

test('similar poses do not confuse the classifier', () => {
  // POINTING vs TWO_FINGER vs OPEN_PALM discrimination on the shared classifier
  assertEqual(classifyHandPose(HANDS.pointing()).pose, 'POINTING');
  assertEqual(classifyHandPose(HANDS.twoFinger()).pose, 'TWO_FINGER');
  assertEqual(classifyHandPose(HANDS.openPalm()).pose, 'OPEN_PALM');
  assertEqual(classifyHandPose(HANDS.fist()).pose, 'FIST');
  assertEqual(classifyHandPose(HANDS.thumbsUp()).pose, 'THUMBS_UP');
  assertEqual(classifyHandPose(HANDS.thumbsDown()).pose, 'THUMBS_DOWN');
  // Invalid skeletons are NONE, never a random gesture
  assertEqual(classifyHandPose([]).pose, 'NONE');
  assertEqual(classifyHandPose(new Array(21).fill({ x: 0.5, y: 0.5 })).pose, 'NONE');
});

test('dwell-owned poses stay silent in the engine (no double execution)', () => {
  // OPEN_PALM / THUMBS_UP / THUMBS_DOWN are confirmed by the tracker's dwell
  // pipeline (HUD onGestureConfirmed) — the engine must NOT also fire them,
  // or one physical gesture would execute twice.
  const engine = newEngine({ ...CANONICAL_MAP, open_palm: 'pause_session' });
  feed(engine, HANDS.pointing, 1000, 4);
  const palm: EngineEvent[] = [];
  for (let t = 1200; t <= 2400; t += 50) {
    palm.push(...engine.processFrame([HANDS.openPalm()], ['Right'], t));
  }
  assertEqual(
    countBy(palm, (e) => e.type === 'action'),
    0,
    'engine leaves dwell-owned poses to the dwell pipeline'
  );
});

test('contain transform: overlay maps letterboxed video exactly (camera enlargement)', () => {
  // 4:3 video in a wide 16:9 container: scale limited by height, centered
  const t = computeContainTransform(640, 480, 1280, 720);
  assert(Math.abs(t.scale - 1.5) < 1e-9, 'scale = 720/480');
  assertEqual(t.offsetY, 0);
  assert(Math.abs(t.offsetX - 160) < 1e-9, 'horizontal letterbox 160px each side');
  // Landmark at video center maps to container center
  const cx = t.offsetX + 0.5 * 640 * t.scale;
  assert(Math.abs(cx - 640) < 1e-9, 'center maps to center');
  // Tall narrow container: scale limited by width
  const t2 = computeContainTransform(640, 480, 400, 700);
  assert(Math.abs(t2.scale - 400 / 640) < 1e-9);
  assertEqual(t2.offsetX, 0);
  assert(t2.offsetY > 0, 'vertical letterbox');
});

// ---------------------------------------------------------------------------
// Hand-quality gate (worker/lib/handQuality.ts)
//
// Regression suite for the gesture blackout: @mediapipe/tasks-vision
// materializes `visibility: 0` for hand landmarks (the hand model emits
// x/y/z only), and the gate used to treat any numeric visibility as a real
// score — rejecting every detected hand, every frame.
// ---------------------------------------------------------------------------
import {
  filterHandsByQuality,
  MIN_AVG_VISIBILITY,
  MIN_PALM_SIZE,
} from '../worker/lib/handQuality';

/** Builds a synthetic 21-landmark hand. Wrist at index 0, middle MCP at 9. */
function gateHand(opts: { visibility?: number; yStep?: number; count?: number } = {}) {
  const { visibility, yStep = 0.01, count = 21 } = opts;
  const hand: { x: number; y: number; z?: number; visibility?: number }[] = [];
  for (let i = 0; i < count; i++) {
    const pt: { x: number; y: number; z?: number; visibility?: number } = {
      x: 0.5,
      y: 0.7 - i * yStep,
    };
    if (visibility !== undefined) pt.visibility = visibility;
    hand.push(pt);
  }
  return hand;
}

test('quality gate passes the exact tasks-vision hand shape (all visibility === 0)', () => {
  // THE regression: hand_landmarker output has visibility materialized as 0
  // for every landmark. This hand MUST pass the gate.
  const { hands } = filterHandsByQuality([gateHand({ visibility: 0 })], ['Left']);
  assertEqual(hands.length, 1, 'visibility:0 hand must NOT be rejected');
});

test('quality gate passes hands with no visibility field at all', () => {
  const { hands } = filterHandsByQuality([gateHand()], []);
  assertEqual(hands.length, 1);
});

test('quality gate passes hands whose model reports good visibility', () => {
  const { hands } = filterHandsByQuality([gateHand({ visibility: 0.8 })], ['Left']);
  assertEqual(hands.length, 1);
});

test('quality gate rejects occluded hands when visibility is genuinely reported low', () => {
  const { hands } = filterHandsByQuality([gateHand({ visibility: 0.3 })], ['Left']);
  assertEqual(hands.length, 0, 'avg visibility 0.3 < floor must be rejected');
  assert(MIN_AVG_VISIBILITY > 0.3 && MIN_AVG_VISIBILITY <= 0.55, 'floor unchanged');
});

test('quality gate rejects a distant hand (palm size below minimum)', () => {
  // yStep 0.002 -> wrist->MCP distance 0.018, far below the 0.035 floor
  const { hands } = filterHandsByQuality([gateHand({ yStep: 0.002 })], ['Left']);
  assertEqual(hands.length, 0);
  assert(MIN_PALM_SIZE === 0.035, 'palm threshold = 0.035 (wide-FOV/distance tolerant)');
});

test('quality gate accepts small-but-real hands in the 0.035-0.045 band (wide-FOV cameras)', () => {
  // yStep 0.0045 -> wrist->MCP distance 0.0405: a real hand that the old
  // 0.045 floor rejected on wide-FOV webcams. Must be accepted now.
  const { hands } = filterHandsByQuality([gateHand({ yStep: 0.0045 })], ['Left']);
  assertEqual(hands.length, 1, 'palm 0.0405 >= 0.035 floor must be accepted');
});

test('quality gate rejects partial hands (fewer than 21 landmarks)', () => {
  const { hands } = filterHandsByQuality([gateHand({ count: 20 })], ['Left']);
  assertEqual(hands.length, 0);
});

test('quality gate keeps label alignment and applies the Right default', () => {
  const { hands, labels } = filterHandsByQuality(
    [gateHand({ visibility: 0 }), gateHand({ visibility: 0.2 })],
    ['Left']
  );
  assertEqual(hands.length, 1, 'visibility:0 hand passes, genuinely-occluded hand drops');
  assertEqual(labels.length, 1);
  assertEqual(labels[0], 'Left', 'label of the surviving hand is preserved');
  assertEqual(filterHandsByQuality([gateHand({ visibility: 0 })], []).labels[0], 'Right');
});

test('quality gate handles an empty detection result', () => {
  const { hands, labels } = filterHandsByQuality([], []);
  assertEqual(hands.length, 0);
  assertEqual(labels.length, 0);
});

test('quality gate accepts mixed visibility (sentinel zeros + real scores)', () => {
  // tasks-vision materializes visibility: 0 for hand landmarks (the hand model
  // emits x/y/z only). If a future model build reported REAL scores for only
  // SOME landmarks, the hand must still pass: the average check only applies
  // when EVERY landmark reports a real (> 0) score. Locks in the sentinel
  // semantics that caused the original full blackout.
  const hand = gateHand({ visibility: 0 });
  hand[0].visibility = 0.9;
  hand[9].visibility = 0.85;
  const { hands } = filterHandsByQuality([hand], ['Left']);
  assertEqual(hands.length, 1, 'mixed sentinel/real visibility must not blackout');
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

console.log(`\n=========================================================`);
console.log(`  gesture engine tests: ${passed} passed, ${failed} failed`);
console.log(`=========================================================`);
if (failed > 0) {
  console.error('\nFailures:');
  for (const f of failures) console.error(`  - ${f}`);
  process.exit(1);
}
process.exit(0);
