'use client';

/**
 * Dual-Hand Real-Time 21-Landmark Vision Pipeline (§ 9, § 19, § 20)
 * 
 * Features:
 * - Simultaneous Dual-Hand Detection (Left & Right Hands, numHands: 2)
 * - Rock-Solid Camera Lifecycle (No flickering/restarting on parent re-renders)
 * - High-FPS Real-Time MediaPipe Tasks Vision Inference
 * - Strict Two-Layer Invariant: Hand Presence Gate -> Geometric Classification
 * - One-Shot Dwell & Execution Release Latch
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';
import { classifyHandPose } from '@/worker/lib/handPoses';
import { computeContainTransform } from '@/worker/lib/cameraTransform';
import { filterHandsByQuality, MIN_AVG_VISIBILITY, MIN_PALM_SIZE } from '@/worker/lib/handQuality';
import { t } from '@/shared/i18n/languages';

// MediaPipe 21 3D Joint Connection Topology
export const HAND_CONNECTIONS: [number, number][] = [
  // Thumb
  [0, 1], [1, 2], [2, 3], [3, 4],
  // Index finger
  [0, 5], [5, 6], [6, 7], [7, 8],
  // Middle finger
  [0, 9], [9, 10], [10, 11], [11, 12],
  // Ring finger
  [0, 13], [13, 14], [14, 15], [15, 16],
  // Pinky
  [0, 17], [17, 18], [18, 19], [19, 20],
  // Palm base
  [5, 9], [9, 13], [13, 17],
];

export interface Landmark3D {
  x: number;
  y: number;
  z?: number;
}

export type CameraLifecycleState =
  | 'CAMERA_IDLE'
  | 'CAMERA_REQUESTING_PERMISSION'
  | 'CAMERA_READY'
  | 'CAMERA_ACTIVE'
  | 'CAMERA_ERROR'
  | 'CAMERA_STOPPED';

export type GesturePipelineStatus =
  | 'CAMERA_INITIALIZING'
  | 'SEARCHING_FOR_HAND'
  | 'HAND_DETECTED'
  | 'CLASSIFYING'
  | 'GESTURE_CANDIDATE'
  | 'GESTURE_CONFIRMED'
  | 'WAIT_FOR_RELEASE'
  | 'CONFLICT'
  | 'ERROR';

export interface MultiHandResolution {
  dominantGesture: string | null;
  confidence: number;
  isConflicting: boolean;
  statusMessage?: string;
}

/**
 * Geometric Classification for an Individual Hand.
 * Delegates to the shared canonical classifier in worker/lib/handPoses.ts so
 * the dwell pipeline and the real-time interaction engine classify poses
 * identically. Kept as a named export for existing consumers/tests.
 */
export function classifySingleHand(landmarks: Landmark3D[]): { gesture: string | null; confidence: number } {
  const result = classifyHandPose(landmarks);
  if (result.pose === 'NONE') {
    return { gesture: null, confidence: 0 };
  }
  return { gesture: result.pose, confidence: result.confidence };
}

/**
 * Multi-Hand Gesture Resolution (Phase 4 Hardened)
 * Enforces:
 * 1. FIST Emergency Stop Priority: Any visible hand with FIST overrides all other normal gestures immediately.
 * 2. Multi-Hand Normal Conflict: If two hands display different normal gestures, marks conflict and suppresses action.
 * 3. Multi-Hand Agreement: If both hands agree on the same gesture, reinforces confidence.
 */
export function resolveMultiHandGestures(
  multiHands: Landmark3D[][],
  classifier: (landmarks: Landmark3D[]) => { gesture: string | null; confidence: number } = classifySingleHand
): MultiHandResolution {
  if (!multiHands || multiHands.length === 0) {
    return { dominantGesture: null, confidence: 0.0, isConflicting: false };
  }

  const classified = multiHands.map((hand, idx) => ({
    handIdx: idx,
    ...classifier(hand),
  }));

  // 1. Emergency Stop Priority (MUST IMPLEMENT #1)
  // If ANY visible hand is classified as FIST (conf >= 0.75), FIST takes absolute priority!
  const fistHand = classified.find((c) => c.gesture === 'FIST' && c.confidence >= 0.75);
  if (fistHand) {
    return {
      dominantGesture: 'FIST',
      confidence: fistHand.confidence,
      isConflicting: false,
      statusMessage: 'Emergency Stop Priority Active (Fist Detected)',
    };
  }

  // Filter for recognized active gestures (excluding null, NONE, UNKNOWN)
  const activeGestures = classified.filter(
    (c) => c.gesture !== null && c.gesture !== 'UNKNOWN' && c.gesture !== 'NONE'
  );

  if (activeGestures.length === 0) {
    return { dominantGesture: null, confidence: 0.50, isConflicting: false };
  }

  if (activeGestures.length === 1) {
    return {
      dominantGesture: activeGestures[0].gesture,
      confidence: activeGestures[0].confidence,
      isConflicting: false,
    };
  }

  // 2. Multi-Hand Normal Conflict (MUST IMPLEMENT #3)
  const distinctGestures = Array.from(new Set(activeGestures.map((c) => c.gesture)));

  if (distinctGestures.length === 1) {
    const highestConf = Math.max(...activeGestures.map((c) => c.confidence));
    return {
      dominantGesture: distinctGestures[0],
      confidence: highestConf,
      isConflicting: false,
    };
  }

  // Opposing gestures detected across visible hands
  return {
    dominantGesture: null,
    confidence: 0.50,
    isConflicting: true,
    statusMessage: `Multi-Hand Conflict: Opposing gestures (${distinctGestures.join(' vs ')}) detected across hands. Action suspended for safety.`,
  };
}

export interface HandTrackerProps {
  onGestureDetected?: (gesture: string, confidence: number) => void;
  onLandmarksDetected?: (landmarks: Landmark3D[]) => void;
  onHandPresenceChange?: (hasHand: boolean) => void;
  width?: string | number;
  height?: string | number;
  showLabels?: boolean;
  requiredDwellMs?: number;
  onGestureConfirmed?: (gesture: string) => void;
  onHandFrame?: (hands: Landmark3D[][], labels: string[]) => void;
  enabled?: boolean;
  onCameraStateChange?: (state: CameraLifecycleState, error?: string) => void;
  /**
   * Poses eligible for dwell-confirmed one-shot execution. Poses outside this
   * set are still classified and displayed, but their actions are owned by the
   * real-time interaction engine (pointer / pinch clicks / two-finger / swipes)
   * which has its own state machine — double execution is prevented.
   */
  dwellGestures?: string[];
}

/**
 * Default dwell-confirmed gesture set for the workstation: discrete workflow
 * poses only. PINCH / TWO_FINGER / POINTING are engine-managed (clicks,
 * right-click/scroll, pointer aiming).
 */
export const DEFAULT_DWELL_GESTURES = ['THUMBS_UP', 'THUMBS_DOWN', 'OPEN_PALM', 'FIST'];

/**
 * RUNTIME DIAGNOSTICS (observation build): snapshot of read-only counters
 * displayed in the plain-text panel rendered directly above the camera area.
 * NOTHING here influences detection, classification, quality gating, or
 * MediaPipe configuration — it only records what already happened.
 */
export interface RuntimeDiagSnapshot {
  videoWidth: number;
  videoHeight: number;
  readyState: number;
  paused: boolean;
  rafCount: number;
  detectForVideoCount: number;
  rawHandsCount: number;
  lastDetectError: string;
  acceptedHandsCount: number;
  lastGesture: string;
  /** DIAG: landmark count of the first raw hand (pre-gate). */
  rawLmCount: number;
  /** DIAG: palm size of the first raw hand (wrist -> middle MCP, normalized). */
  palmSize: number | null;
  /** DIAG: how many landmarks report a real (> 0) visibility score. */
  visCount: number | null;
  /** DIAG: average of the reported visibility scores (null when none). */
  visAvg: number | null;
}

const INITIAL_RUNTIME_DIAG: RuntimeDiagSnapshot = {
  videoWidth: 0,
  videoHeight: 0,
  readyState: 0,
  paused: false,
  rafCount: 0,
  detectForVideoCount: 0,
  rawHandsCount: 0,
  lastDetectError: '(none)',
  acceptedHandsCount: 0,
  lastGesture: 'none',
  rawLmCount: 0,
  palmSize: null,
  visCount: null,
  visAvg: null,
};



export function MediaPipeHandTracker({
  onGestureDetected,
  onLandmarksDetected,
  onHandPresenceChange,
  width = '100%',
  height = '360px',
  showLabels = true,
  requiredDwellMs = 500,
  onGestureConfirmed,
  onHandFrame,
  enabled = true,
  onCameraStateChange,
  dwellGestures = DEFAULT_DWELL_GESTURES,
}: HandTrackerProps) {
  let accessibilityContext: any = null;
  try {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    accessibilityContext = useAccessibility();
  } catch {
    // Context fallback
  }
  const language = accessibilityContext?.language || 'en';

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Camera Lifecycle and Permission State (FR-01)
  const [cameraState, setCameraState] = useState<CameraLifecycleState>(
    enabled ? 'CAMERA_REQUESTING_PERMISSION' : 'CAMERA_STOPPED'
  );
  const [permissionDenied, setPermissionDenied] = useState<boolean>(false);
  const [retryTrigger, setRetryTrigger] = useState<number>(0);

  // Store latest callbacks in ref to avoid re-triggering camera lifecycle on parent state changes
  const callbacksRef = useRef({
    onGestureDetected,
    onLandmarksDetected,
    onHandPresenceChange,
    onGestureConfirmed,
    onHandFrame,
    onCameraStateChange,
    requiredDwellMs,
    dwellGestures,
  });

  useEffect(() => {
    callbacksRef.current = {
      onGestureDetected,
      onLandmarksDetected,
      onHandPresenceChange,
      onGestureConfirmed,
      onHandFrame,
      onCameraStateChange,
      requiredDwellMs,
      dwellGestures,
    };
  });

  // Diagnostic State Machine
  const [pipelineStatus, setPipelineStatus] = useState<GesturePipelineStatus>('CAMERA_INITIALIZING');
  const [handCount, setHandCount] = useState<number>(0);
  const [activeGesture, setActiveGesture] = useState<string | null>(null);
  const [realConfidence, setRealConfidence] = useState<number>(0);
  const [fps, setFps] = useState<number>(0);
  const [dwellProgress, setDwellProgress] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string>('');

  // Temporal Stability & Execution Release Latch (Phase 4 Hardened)
  const stabilityBufferRef = useRef<string[]>([]);
  const dwellStartTimeRef = useRef<number | null>(null);
  const isActionExecutedRef = useRef<boolean>(false);
  const currentConfirmedGestureRef = useRef<string | null>(null);
  const neutralStartTimeRef = useRef<number | null>(null);

  // High-frequency UI update throttling refs (Phase 4 Hardening)
  const prevHandCountRef = useRef<number>(0);
  const prevActiveGestureRef = useRef<string | null>(null);
  const prevConfidenceRef = useRef<number>(0);
  const prevDwellProgressRef = useRef<number>(0);
  const prevPipelineStatusRef = useRef<GesturePipelineStatus>('CAMERA_INITIALIZING');

  // =========================================================================
  // RUNTIME DIAGNOSTICS (observation build) — see RuntimeDiagSnapshot above.
  // The frame loop writes counters into diagRef (pure ref writes, no
  // re-renders, zero behavioral impact); a 4 Hz interval copies them into
  // state for the always-visible panel above the camera. Camera element
  // fields are read HERE (not in the loop) so they keep updating even if the
  // frame loop stalls — a stalled loop is itself visible as "RAF count 0".
  // =========================================================================
  const diagRef = useRef<RuntimeDiagSnapshot>({ ...INITIAL_RUNTIME_DIAG });
  const [diagSnapshot, setDiagSnapshot] = useState<RuntimeDiagSnapshot>({ ...INITIAL_RUNTIME_DIAG });

  useEffect(() => {
    const diagFlushTimer = window.setInterval(() => {
      const videoEl = videoRef.current;
      if (videoEl) {
        diagRef.current.videoWidth = videoEl.videoWidth;
        diagRef.current.videoHeight = videoEl.videoHeight;
        diagRef.current.readyState = videoEl.readyState;
        diagRef.current.paused = videoEl.paused;
      }
      setDiagSnapshot({ ...diagRef.current });
    }, 250);
    return () => window.clearInterval(diagFlushTimer);
  }, []);

  // Draw Dual-Hand Skeletal Meshes on Canvas
  const drawAllHandsMesh = useCallback((
    ctx: CanvasRenderingContext2D,
    allHandsLandmarks: Landmark3D[][],
    canvasWidth: number,
    canvasHeight: number,
    handLabels: string[],
    activeGesture: string | null,
    confidence: number
  ) => {
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);

    if (!allHandsLandmarks || allHandsLandmarks.length === 0) return;

    // The <video> is object-fit: CONTAIN (never cropped). Map landmark
    // coordinates through the same letterbox transform so the skeleton
    // overlay aligns exactly with the visible hand at any container size.
    const videoEl = videoRef.current;
    const { scale, offsetX, offsetY } = computeContainTransform(
      videoEl?.videoWidth || 640,
      videoEl?.videoHeight || 480,
      canvasWidth,
      canvasHeight
    );
    const toCanvasX = (nx: number) => offsetX + (1 - nx) * (videoEl?.videoWidth || 640) * scale; // mirrored
    const toCanvasY = (ny: number) => offsetY + ny * (videoEl?.videoHeight || 480) * scale;

    allHandsLandmarks.forEach((landmarks, handIdx) => {
      if (!landmarks || landmarks.length < 21) return;

      // Compute bounding box around joints
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      landmarks.forEach((pt) => {
        const px = toCanvasX(pt.x);
        const py = toCanvasY(pt.y);
        if (px < minX) minX = px;
        if (py < minY) minY = py;
        if (px > maxX) maxX = px;
        if (py > maxY) maxY = py;
      });

      const pad = 16;
      minX = Math.max(0, minX - pad);
      minY = Math.max(0, minY - pad);
      maxX = Math.min(canvasWidth, maxX + pad);
      maxY = Math.min(canvasHeight, maxY + pad);

      const isLeft = handLabels[handIdx]?.includes('Left') || handIdx === 1;
      const primaryColor = isLeft ? '#38bdf8' : '#00f2fe';

      // 1. Draw Bounding Box
      ctx.save();
      ctx.strokeStyle = activeGesture && activeGesture !== 'UNKNOWN' ? primaryColor : '#f59e0b';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.strokeRect(minX, minY, maxX - minX, maxY - minY);
      ctx.restore();

      // Bounding Box Tag
      const handTitle = isLeft ? 'Left Hand' : 'Right Hand';
      const labelText = activeGesture && activeGesture !== 'UNKNOWN'
        ? `${handTitle}: ${activeGesture} • ${(confidence * 100).toFixed(0)}%`
        : `${handTitle} • 21 Joints`;

      ctx.fillStyle = activeGesture && activeGesture !== 'UNKNOWN' ? 'rgba(0, 242, 254, 0.9)' : 'rgba(245, 158, 11, 0.9)';
      ctx.fillRect(minX, Math.max(0, minY - 24), Math.max(170, labelText.length * 7.5), 22);
      ctx.fillStyle = '#0b0f19';
      ctx.font = 'bold 11px sans-serif';
      ctx.fillText(labelText, minX + 8, Math.max(0, minY - 9));

      // 2. Draw Skeletal Connections (Bones)
      HAND_CONNECTIONS.forEach(([startIdx, endIdx]) => {
        const p1 = landmarks[startIdx];
        const p2 = landmarks[endIdx];
        if (!p1 || !p2) return;

        const x1 = toCanvasX(p1.x);
        const y1 = toCanvasY(p1.y);
        const x2 = toCanvasX(p2.x);
        const y2 = toCanvasY(p2.y);

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);

        if (startIdx >= 1 && endIdx <= 4) {
          ctx.strokeStyle = isLeft ? '#38bdf8' : '#00f2fe'; // Thumb
        } else if (startIdx >= 5 && endIdx <= 8) {
          ctx.strokeStyle = '#10b981'; // Index
        } else if (startIdx >= 9 && endIdx <= 12) {
          ctx.strokeStyle = '#6366f1'; // Middle
        } else if (startIdx >= 13 && endIdx <= 16) {
          ctx.strokeStyle = '#a855f7'; // Ring
        } else if (startIdx >= 17 && endIdx <= 20) {
          ctx.strokeStyle = '#f59e0b'; // Pinky
        } else {
          ctx.strokeStyle = '#ec4899'; // Palm
        }

        ctx.lineWidth = 3;
        ctx.shadowColor = ctx.strokeStyle;
        ctx.shadowBlur = 6;
        ctx.stroke();
      });

      // 3. Draw 21 Joint Nodes
      landmarks.forEach((pt, idx) => {
        const px = toCanvasX(pt.x);
        const py = toCanvasY(pt.y);

        ctx.beginPath();
        ctx.arc(px, py, idx === 4 || idx === 8 || idx === 12 || idx === 16 || idx === 20 ? 6 : 4, 0, 2 * Math.PI);
        ctx.fillStyle = idx === 0 ? '#f43f5e' : idx % 4 === 0 ? '#10b981' : '#ffffff';
        ctx.shadowColor = primaryColor;
        ctx.shadowBlur = 8;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(px, py, 2, 0, 2 * Math.PI);
        ctx.fillStyle = '#ffffff';
        ctx.fill();

        if (showLabels) {
          ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
          ctx.font = '8px monospace';
          ctx.fillText(`${idx}`, px + 6, py - 4);
        }
      });
    });
  }, [showLabels]);

  // Main Persistent Vision Worker & Camera Lifecycle (Zero-Flicker Initialization + FR-01 Input Capture)
  useEffect(() => {
    let isComponentMounted = true;
    let handLandmarkerInstance: HandLandmarker | null = null;
    let cameraStream: MediaStream | null = null;
    let animationFrameId: number;
    let lastTime = performance.now();
    let frameCount = 0;
    // Inference resilience state: which delegate is live, and how many
    // consecutive detectForVideo() calls have thrown (GPU context loss etc.).
    let usingDelegate: 'GPU' | 'CPU' = 'GPU';
    let detectErrorStreak = 0;

    // Hardware isolation: If disabled, ensure camera is stopped and never requested
    if (!enabled) {
      setCameraState('CAMERA_STOPPED');
      setPipelineStatus('CAMERA_INITIALIZING');
      setErrorMessage('');
      callbacksRef.current.onCameraStateChange?.('CAMERA_STOPPED');
      if (callbacksRef.current.onHandPresenceChange) callbacksRef.current.onHandPresenceChange(false);
      return () => {};
    }

    async function initDualHandVisionPipeline() {
      try {
        setCameraState('CAMERA_REQUESTING_PERMISSION');
        setPipelineStatus('CAMERA_INITIALIZING');
        setErrorMessage('');
        setPermissionDenied(false);
        callbacksRef.current.onCameraStateChange?.('CAMERA_REQUESTING_PERMISSION');

        // 1. Initialize WebAssembly Tasks Vision Resolver
        const vision = await FilesetResolver.forVisionTasks(
          '/mediapipe/wasm'
        );

        if (!isComponentMounted) return;

        // 2. Initialize Dual-Hand Landmarker (numHands: 2).
        // GPU delegate first; fall back to the CPU delegate automatically when
        // the GPU path is unavailable on this machine (driver/WebGL issues) so
        // gesture tracking never silently dies on exotic GPU setups.
        const createLandmarker = (delegate: 'GPU' | 'CPU') =>
          HandLandmarker.createFromOptions(vision, {
            baseOptions: {
              modelAssetPath: '/mediapipe/hand_landmarker.task',
              delegate,
            },
            runningMode: 'VIDEO',
            numHands: 2, // DETECT BOTH HANDS SIMULTANEOUSLY
            minHandDetectionConfidence: 0.45,
            minHandPresenceConfidence: 0.45,
            minTrackingConfidence: 0.45,
          });
        try {
          handLandmarkerInstance = await createLandmarker('GPU');
        } catch (gpuErr) {
          console.warn('[AMAP Camera] GPU delegate unavailable — retrying with CPU delegate:', gpuErr);
          usingDelegate = 'CPU';
          handLandmarkerInstance = await createLandmarker('CPU');
        }

        if (!isComponentMounted) return;

        // 3. Start Camera Stream (FR-01 User Input Capture)
        if (typeof navigator !== 'undefined' && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
          try {
            cameraStream = await navigator.mediaDevices.getUserMedia({
              video: {
                // Prefer a high-resolution 4:3 mode: more landmark detail for
                // distant/small hands; the browser negotiates down (640x480)
                // when the camera does not support it.
                width: { ideal: 1280 },
                height: { ideal: 960 },
                facingMode: 'user',
              },
              audio: false,
            });
          } catch (mediaErr: any) {
            console.error('Camera getUserMedia error:', mediaErr);
            if (mediaErr?.name === 'NotAllowedError' || mediaErr?.name === 'PermissionDeniedError') {
              setPermissionDenied(true);
              const deniedMsg = t('camera_access_denied', language);
              setErrorMessage(deniedMsg);
              setCameraState('CAMERA_ERROR');
              setPipelineStatus('ERROR');
              callbacksRef.current.onCameraStateChange?.('CAMERA_ERROR', deniedMsg);
              return;
            } else if (
              mediaErr?.name === 'NotFoundError' ||
              mediaErr?.name === 'DevicesNotFoundError' ||
              mediaErr?.name === 'NotReadableError' ||
              mediaErr?.name === 'TrackStartError'
            ) {
              const unavailMsg = t('camera_unavailable', language);
              setErrorMessage(unavailMsg);
              setCameraState('CAMERA_ERROR');
              setPipelineStatus('ERROR');
              callbacksRef.current.onCameraStateChange?.('CAMERA_ERROR', unavailMsg);
              return;
            } else {
              const genericMsg = t('camera_unavailable', language);
              setErrorMessage(genericMsg);
              setCameraState('CAMERA_ERROR');
              setPipelineStatus('ERROR');
              callbacksRef.current.onCameraStateChange?.('CAMERA_ERROR', genericMsg);
              return;
            }
          }

          if (videoRef.current && isComponentMounted && cameraStream) {
            videoRef.current.srcObject = cameraStream;
            try {
              // FIX (stuck 'Initializing Dual-Hand Camera...' / 0 FPS):
              // video.play() can stay PENDING indefinitely (autoplay policy
              // hold, track interruption). A bare `await` stalled init forever
              // BEFORE the pipeline state advanced and BEFORE the
              // requestAnimationFrame loop was ever scheduled — while the
              // <video> kept painting camera frames. Race play() with a
              // timeout and proceed: the frame loop already guards on
              // video.readyState >= 2, so proceeding is always safe.
              await Promise.race([
                videoRef.current.play(),
                new Promise<void>((resolve) =>
                  window.setTimeout(() => {
                    console.warn('[AMAP Camera] video.play() still pending after 2.5s — proceeding (frame loop guards on readyState)');
                    resolve();
                  }, 2500)
                ),
              ]);
            } catch (playErr) {
              console.warn('Video play interrupted or muted:', playErr);
            }
            setCameraState('CAMERA_ACTIVE');
            setPipelineStatus('SEARCHING_FOR_HAND');
            callbacksRef.current.onCameraStateChange?.('CAMERA_ACTIVE');
          } else {
            // FIX: this branch previously fell through SILENTLY (no else) and
            // scheduled the frame loop anyway — with no video attached the
            // loop could never detect anything. Distinguish a dead closure
            // (StrictMode remount race: do nothing) from a genuinely missing
            // video element (surface a real error).
            if (!isComponentMounted) return;
            console.error('[AMAP CAMERA] video element missing at attach time — aborting init');
            const attachMsg = t('camera_unavailable', language);
            setErrorMessage(attachMsg);
            setCameraState('CAMERA_ERROR');
            setPipelineStatus('ERROR');
            callbacksRef.current.onCameraStateChange?.('CAMERA_ERROR', attachMsg);
            return;
          }
        } else {
          const noSupportMsg = t('camera_unavailable', language);
          setErrorMessage(noSupportMsg);
          setCameraState('CAMERA_ERROR');
          setPipelineStatus('ERROR');
          callbacksRef.current.onCameraStateChange?.('CAMERA_ERROR', noSupportMsg);
          return;
        }
      } catch (err: any) {
        console.error('Dual-Hand MediaPipe initialization error:', err);
        const errMsg = t('camera_unavailable', language);
        setErrorMessage(errMsg);
        setCameraState('CAMERA_ERROR');
        setPipelineStatus('ERROR');
        callbacksRef.current.onCameraStateChange?.('CAMERA_ERROR', errMsg);
      }

      // 4. Stable 60 FPS Video Frame Detection Loop
      const processVideoFrame = () => {
        if (!isComponentMounted) return;

        // DIAG (observation only): cumulative requestAnimationFrame counter.
        diagRef.current.rafCount += 1;

        frameCount++;
        const now = performance.now();
        if (now - lastTime >= 1000) {
          setFps(frameCount);
          frameCount = 0;
          lastTime = now;
        }

        const video = videoRef.current;
        const canvas = canvasRef.current;

        if (video && canvas && handLandmarkerInstance && video.readyState >= 2 && video.videoWidth > 0) {
          // Keep the canvas backing store matched to the DISPLAYED size so the
          // skeleton overlay is pixel-exact on the enlarged camera area (a
          // fixed 640x480 buffer would be CSS-stretched and distorted).
          if (
            canvas.clientWidth > 0 &&
            canvas.clientHeight > 0 &&
            (canvas.width !== canvas.clientWidth || canvas.height !== canvas.clientHeight)
          ) {
            canvas.width = canvas.clientWidth;
            canvas.height = canvas.clientHeight;
          }
          const ctx = canvas.getContext('2d');
          if (ctx) {
            let results: any = null;
            try {
              // DIAG (observation only): count every detectForVideo() call.
              diagRef.current.detectForVideoCount += 1;
              results = handLandmarkerInstance.detectForVideo(video, now);
              detectErrorStreak = 0;
              diagRef.current.lastDetectError = '(none)';
            } catch (detectErr) {
              // DIAG (observation only): surface the real per-frame error.
              diagRef.current.lastDetectError = String((detectErr as any)?.message ?? detectErr).slice(0, 160);
              // Inference resilience: a GPU delegate can fail per-frame (lost
              // WebGL context, driver hiccups). Instead of silently treating
              // it as "no hand" forever, fall back to the CPU delegate after
              // a sustained failure streak so tracking recovers on its own.
              results = null;
              detectErrorStreak++;
              if (detectErrorStreak === 20) {
                console.error('[AMAP Camera] detectForVideo failing repeatedly:', detectErr);
                if (usingDelegate === 'GPU' && isComponentMounted) {
                  usingDelegate = 'CPU';
                  detectErrorStreak = 0;
                  void (async () => {
                    try {
                      handLandmarkerInstance?.close();
                    } catch {}
                    try {
                      const vision = await FilesetResolver.forVisionTasks('/mediapipe/wasm');
                      handLandmarkerInstance = await HandLandmarker.createFromOptions(vision, {
                        baseOptions: {
                          modelAssetPath: '/mediapipe/hand_landmarker.task',
                          delegate: 'CPU',
                        },
                        runningMode: 'VIDEO',
                        numHands: 2,
                        minHandDetectionConfidence: 0.45,
                        minHandPresenceConfidence: 0.45,
                        minTrackingConfidence: 0.45,
                      });
                      console.warn('[AMAP Camera] recovered: switched to CPU delegate after repeated detect failures');
                    } catch (cpuErr) {
                      console.error('[AMAP Camera] CPU fallback failed:', cpuErr);
                    }
                  })();
                }
              }
            }

            const rawHands: Landmark3D[][] = results?.landmarks || [];
            // DIAG (observation only): raw landmark arrays returned by MediaPipe,
            // BEFORE any quality filtering.
            diagRef.current.rawHandsCount = rawHands.length;
            // DIAG (observation only): gate inputs for the FIRST raw hand —
            // landmark count, palm size (wrist -> middle MCP, normalized) and
            // reported-visibility count/average — mirroring the gate's own
            // math for display only. No filtering happens here.
            const diagRaw0 = rawHands[0] as Landmark3D[] | undefined;
            diagRef.current.rawLmCount = diagRaw0?.length ?? 0;
            diagRef.current.palmSize =
              diagRaw0 && diagRaw0.length > 9
                ? Math.hypot(diagRaw0[0].x - diagRaw0[9].x, diagRaw0[0].y - diagRaw0[9].y)
                : null;
            const diagVis: number[] = (diagRaw0 ?? [])
              .map((pt: any) => (typeof pt?.visibility === 'number' && pt.visibility > 0 ? pt.visibility : null))
              .filter((v: number | null): v is number => v !== null);
            diagRef.current.visCount = diagVis.length;
            diagRef.current.visAvg =
              diagVis.length > 0
                ? Math.round((diagVis.reduce((a, b) => a + b, 0) / diagVis.length) * 100) / 100
                : null;
            // `handednesses` is the deprecated alias; prefer the modern
            // `handedness` field when the installed tasks-vision provides it.
            const rawLabels: string[] =
              (results?.handedness ?? results?.handednesses)?.map((h: any) => h[0]?.categoryName) || [];

            // =========================================================================
            // HAND QUALITY GATE: drop partial / too-distant / low-visibility hands
            // BEFORE any classification, so poorly visible frames can never
            // produce gestures or drive the interaction engine.
            // Exact rules (and the tasks-vision visibility caveat) live in
            // worker/lib/handQuality.ts, where they are unit-tested.
            // =========================================================================
            const { hands: multiHands, labels: multiHandLabels } = filterHandsByQuality(
              rawHands,
              rawLabels
            );
            // DIAG (observation only): hands that passed the quality gate.
            diagRef.current.acceptedHandsCount = multiHands.length;

            // =========================================================================
            // STRICT LAYER 1: "IS THERE A HAND?" (NO HAND = 0 GESTURE, NO INTENT)
            // =========================================================================
            // State Throttling Helpers (MUST IMPLEMENT #7)
            const safeSetHandCount = (count: number) => {
              if (prevHandCountRef.current !== count) {
                prevHandCountRef.current = count;
                setHandCount(count);
              }
            };
            const safeSetActiveGesture = (gesture: string | null) => {
              if (prevActiveGestureRef.current !== gesture) {
                prevActiveGestureRef.current = gesture;
                setActiveGesture(gesture);
              }
            };
            const safeSetConfidence = (conf: number) => {
              if (Math.abs(prevConfidenceRef.current - conf) >= 0.05 || (conf === 0 && prevConfidenceRef.current !== 0)) {
                prevConfidenceRef.current = conf;
                setRealConfidence(conf);
              }
            };
            const safeSetDwellProgress = (pct: number) => {
              const quantized = Math.floor(pct / 5) * 5;
              if (prevDwellProgressRef.current !== quantized) {
                prevDwellProgressRef.current = quantized;
                setDwellProgress(quantized);
              }
            };
            const safeSetPipelineStatus = (status: GesturePipelineStatus) => {
              if (prevPipelineStatusRef.current !== status) {
                prevPipelineStatusRef.current = status;
                setPipelineStatus(status);
              }
            };

            // =========================================================================
            // STRICT LAYER 1: "IS THERE A HAND?" (NO HAND = 0 GESTURE, NO INTENT)
            // =========================================================================
            if (multiHands.length === 0) {
              ctx.clearRect(0, 0, canvas.width, canvas.height);
              // DIAG (observation only): no hand passed the gate — classifier output is none.
              diagRef.current.lastGesture = 'none';
              safeSetHandCount(0);
              safeSetActiveGesture(null);
              safeSetConfidence(0.0);
              safeSetDwellProgress(0);

              // Temporal stability buffer and dwell timer reset
              stabilityBufferRef.current = [];
              dwellStartTimeRef.current = null;

              // Release-Latch Hysteresis (MUST IMPLEMENT #2):
              // Latch only re-arms after sustained neutral/no-hand behavior (>= 350ms)
              if (isActionExecutedRef.current) {
                if (!neutralStartTimeRef.current) {
                  neutralStartTimeRef.current = now;
                }
                if (now - neutralStartTimeRef.current >= 350) {
                  isActionExecutedRef.current = false;
                  currentConfirmedGestureRef.current = null;
                  neutralStartTimeRef.current = null;
                }
              } else {
                neutralStartTimeRef.current = null;
              }

              safeSetPipelineStatus('SEARCHING_FOR_HAND');

              const cb = callbacksRef.current;
              if (cb.onHandPresenceChange) cb.onHandPresenceChange(false);
              if (cb.onGestureDetected) cb.onGestureDetected('NONE', 0.0);
            } else {
              // =========================================================================
              // LAYER 1 PASSED: 1 OR 2 HANDS DETECTED!
              // =========================================================================
              safeSetHandCount(multiHands.length);

              const cb = callbacksRef.current;
              if (cb.onHandPresenceChange) cb.onHandPresenceChange(true);
              if (cb.onLandmarksDetected) cb.onLandmarksDetected(multiHands[0]);
              if (cb.onHandFrame) cb.onHandFrame(multiHands, multiHandLabels);

              // =========================================================================
              // STRICT LAYER 2: "WHAT ARE THE HANDS DOING?" (PHASE 4 HARDENED)
              // Evaluates FIST Emergency Stop Priority (#1) and Multi-Hand Normal Conflict (#3)
              // =========================================================================
              const {
                dominantGesture,
                confidence: highestConfidence,
                isConflicting,
              } = resolveMultiHandGestures(multiHands, classifySingleHand);
              // DIAG (observation only): last classifier resolution.
              diagRef.current.lastGesture = dominantGesture
                ? `${dominantGesture} (${Math.round(highestConfidence * 100)}%)`
                : isConflicting
                  ? 'CONFLICT'
                  : 'none';

              // Draw all detected hands (Left & Right) on the canvas
              drawAllHandsMesh(
                ctx,
                multiHands,
                canvas.width,
                canvas.height,
                multiHandLabels,
                dominantGesture,
                highestConfidence
              );

              if (isConflicting) {
                // Multi-Hand Normal Conflict: Suppress normal action emission for safety
                safeSetActiveGesture(null);
                safeSetConfidence(0.5);
                safeSetDwellProgress(0);
                stabilityBufferRef.current = [];
                dwellStartTimeRef.current = null;
                safeSetPipelineStatus('CONFLICT');

                if (cb.onGestureDetected) cb.onGestureDetected('UNKNOWN', 0.5);
              } else if (!dominantGesture) {
                // Hand(s) present, but no recognized gesture pose (neutral / unknown)
                safeSetActiveGesture(null);
                safeSetConfidence(0.5);
                safeSetDwellProgress(0);
                stabilityBufferRef.current = [];
                dwellStartTimeRef.current = null;

                // Release-Latch Hysteresis on Neutral Hand Pose (>= 350ms)
                if (isActionExecutedRef.current) {
                  if (!neutralStartTimeRef.current) {
                    neutralStartTimeRef.current = now;
                  }
                  if (now - neutralStartTimeRef.current >= 350) {
                    isActionExecutedRef.current = false;
                    currentConfirmedGestureRef.current = null;
                    neutralStartTimeRef.current = null;
                  }
                } else {
                  neutralStartTimeRef.current = null;
                }

                safeSetPipelineStatus('HAND_DETECTED');

                if (cb.onGestureDetected) cb.onGestureDetected('UNKNOWN', 0.5);
              } else {
                // Dominant gesture recognized on at least one hand
                safeSetActiveGesture(dominantGesture);
                safeSetConfidence(highestConfidence);
                if (cb.onGestureDetected) cb.onGestureDetected(dominantGesture, highestConfidence);

                // Engine-managed poses (pinch/two-finger/pointing) are owned
                // by the real-time interaction engine: display them, but do
                // NOT dwell-confirm them here (prevents double execution).
                if (!(cb.dwellGestures || []).includes(dominantGesture)) {
                  safeSetDwellProgress(0);
                  stabilityBufferRef.current = [];
                  dwellStartTimeRef.current = null;
                  if (isActionExecutedRef.current) {
                    isActionExecutedRef.current = false;
                    currentConfirmedGestureRef.current = null;
                  }
                  neutralStartTimeRef.current = null;
                  safeSetPipelineStatus('HAND_DETECTED');
                } else {
                // Check for Valid Gesture Transition (MUST IMPLEMENT #4):
                // If transitioning from Gesture A to Gesture B, reset execution latch so Gesture B can fire
                if (
                  currentConfirmedGestureRef.current !== null &&
                  dominantGesture !== currentConfirmedGestureRef.current
                ) {
                  isActionExecutedRef.current = false;
                  currentConfirmedGestureRef.current = null;
                  dwellStartTimeRef.current = null;
                  stabilityBufferRef.current = [];
                  neutralStartTimeRef.current = null;
                }

                // If currently matching the already-executed gesture, keep latch locked (jitter immunity)
                if (isActionExecutedRef.current && currentConfirmedGestureRef.current === dominantGesture) {
                  neutralStartTimeRef.current = null;
                  safeSetPipelineStatus('WAIT_FOR_RELEASE');
                  safeSetDwellProgress(100);
                } else {
                  neutralStartTimeRef.current = null;

                  // --- Temporal Stability Buffer (Must persist for >= 3 consecutive frames) ---
                  const buffer = stabilityBufferRef.current;
                  buffer.push(dominantGesture);
                  if (buffer.length > 5) buffer.shift();

                  const isTemporallyStable =
                    buffer.length >= 3 && buffer.every((g) => g === dominantGesture);

                  if (!isTemporallyStable) {
                    safeSetPipelineStatus('CLASSIFYING');
                    safeSetDwellProgress(0);
                    dwellStartTimeRef.current = null;
                  } else {
                    // Temporal stability satisfied
                    safeSetPipelineStatus('GESTURE_CANDIDATE');

                    // --- Dwell Time Accumulator ---
                    if (!dwellStartTimeRef.current) {
                      dwellStartTimeRef.current = now;
                    }

                    const elapsedDwell = now - dwellStartTimeRef.current;
                    const reqDwell = cb.requiredDwellMs || 500;
                    const pct = Math.min(100, Math.round((elapsedDwell / reqDwell) * 100));
                    safeSetDwellProgress(pct);

                    if (pct >= 100 && !isActionExecutedRef.current) {
                      // --- GESTURE CONFIRMED & EXECUTED ONCE ---
                      safeSetPipelineStatus('GESTURE_CONFIRMED');
                      isActionExecutedRef.current = true;
                      currentConfirmedGestureRef.current = dominantGesture;

                      if (cb.onGestureConfirmed) {
                        cb.onGestureConfirmed(dominantGesture);
                      }
                    }
                  }
                }
                }
              }
            }
          }
        }

        animationFrameId = requestAnimationFrame(processVideoFrame);
      };

      animationFrameId = requestAnimationFrame(processVideoFrame);
    }

    initDualHandVisionPipeline();

    return () => {
      isComponentMounted = false;
      cancelAnimationFrame(animationFrameId);
      if (handLandmarkerInstance && handLandmarkerInstance.close) {
        try {
          handLandmarkerInstance.close();
        } catch {}
      }
      if (cameraStream) {
        cameraStream.getTracks().forEach((t) => t.stop());
      }
      if (videoRef.current && videoRef.current.srcObject) {
        const s = videoRef.current.srcObject as MediaStream;
        s.getTracks().forEach((t) => t.stop());
        videoRef.current.srcObject = null;
      }
    };
  }, [enabled, retryTrigger, classifySingleHand, drawAllHandsMesh, language]);

  const handleRetryCamera = () => {
    setErrorMessage('');
    setPermissionDenied(false);
    setRetryTrigger((prev) => prev + 1);
  };

  // If camera is explicitly disabled by worker input mode (e.g. Voice Only mode)
  if (!enabled) {
    return (
      <div
        role="region"
        aria-label="Camera Hardware Inactive"
        style={{
          position: 'relative',
          width: width,
          height: height,
          borderRadius: '20px',
          background: 'rgba(11, 15, 25, 0.6)',
          border: '2px dashed var(--surface-glass-border)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '1rem',
          padding: '1.5rem',
          textAlign: 'center',
        }}
      >
        <span style={{ fontSize: '2.5rem', opacity: 0.6 }}>📷</span>
        <div>
          <strong style={{ color: 'var(--text-secondary)', display: 'block', fontSize: '1rem' }}>
            {t('camera_label', language)}: {t('camera_status_idle', language)}
          </strong>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            {t('input_mode_label', language)}: Voice Only (Camera hardware inactive for privacy & performance)
          </span>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* RUNTIME DIAGNOSTICS PANEL (observation build) — plain visible text,
          always rendered, NOT collapsible, directly ABOVE the camera/video
          area. Read-only display of counters written by the frame loop; it
          never alters detection, classification, quality gating, or
          MediaPipe configuration. */}
      <div
        data-testid="amap-runtime-diagnostics"
        style={{
          width: '100%',
          boxSizing: 'border-box',
          background: '#000000',
          border: '3px solid #facc15',
          borderRadius: '10px',
          padding: '0.85rem 1.1rem',
          marginBottom: '0.75rem',
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace',
          fontSize: '14px',
          lineHeight: '1.55',
          fontWeight: 700,
          color: '#4ade80',
          zIndex: 50,
        }}
      >
        <div style={{ color: '#facc15', fontSize: '15px', marginBottom: '0.4rem' }}>
          AMAP RUNTIME DIAGNOSTICS
        </div>

        <div style={{ color: '#facc15' }}>CAMERA</div>
        <div>{diagSnapshot.videoWidth} × {diagSnapshot.videoHeight}</div>
        <div>readyState {diagSnapshot.readyState}</div>
        <div>paused {String(diagSnapshot.paused)}</div>

        <div style={{ color: '#facc15', marginTop: '0.4rem' }}>LOOP</div>
        <div>RAF count {diagSnapshot.rafCount}</div>

        <div style={{ color: '#facc15', marginTop: '0.4rem' }}>MEDIAPIPE</div>
        <div>detectForVideo count {diagSnapshot.detectForVideoCount}</div>
        <div>raw hands count {diagSnapshot.rawHandsCount}</div>
        <div style={{ color: diagSnapshot.lastDetectError !== '(none)' ? '#f87171' : '#4ade80' }}>
          last detection error {diagSnapshot.lastDetectError}
        </div>

        <div style={{ color: '#facc15', marginTop: '0.4rem' }}>QUALITY</div>
        <div>first raw hand LMs {diagSnapshot.rawLmCount}</div>
        <div>palm {diagSnapshot.palmSize !== null ? diagSnapshot.palmSize.toFixed(3) : 'n/a'} (floor {MIN_PALM_SIZE})</div>
        <div>vis {diagSnapshot.visCount !== null ? `${diagSnapshot.visCount}/21 reported` : 'n/a'} avg {diagSnapshot.visAvg !== null ? diagSnapshot.visAvg.toFixed(2) : 'n/a'} (floor {MIN_AVG_VISIBILITY})</div>
        <div>accepted hands count {diagSnapshot.acceptedHandsCount}</div>

        <div style={{ color: '#facc15', marginTop: '0.4rem' }}>CLASSIFIER</div>
        <div>last gesture {diagSnapshot.lastGesture}</div>

        <div style={{ color: '#facc15', marginTop: '0.4rem' }}>UI</div>
        <div>pipeline {pipelineStatus}</div>
        <div>hand count {handCount}</div>
      </div>

      <div
      role="region"
      aria-label="Camera Live Gesture Input"
      style={{
        position: 'relative',
        width: width,
        height: height,
        borderRadius: '20px',
        background: '#090d16',
        border: '2px solid var(--surface-glass-border)',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {/* Real Live Video Element */}
      <video
        ref={videoRef}
        playsInline
        muted
        style={{
          position: 'absolute',
          width: '100%',
          height: '100%',
          objectFit: 'contain', // Letterboxed: the whole camera frame (and
          // hand) stays visible at any container size; the skeleton overlay
          // uses the same contain transform so it aligns exactly.
          transform: 'scaleX(-1)', // Mirror user reflection
          opacity: 0.88,
          background: '#05070d',
        }}
      />

      {/* Overlaid Dual-Hand Skeletal Mesh Canvas */}
      <canvas
        ref={canvasRef}
        width={640}
        height={480}
        style={{
          position: 'absolute',
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          pointerEvents: 'none',
        }}
      />

      {/* Dwell / Release Progress Bar */}
      {handCount > 0 && activeGesture && (
        <div
          role="progressbar"
          aria-label={`Gesture dwell activation progress: ${Math.round(dwellProgress)}%`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(dwellProgress)}
          style={{
            position: 'absolute',
            bottom: '1rem',
            left: '1.5rem',
            right: '1.5rem',
            height: '10px',
            borderRadius: '5px',
            background: 'rgba(0, 0, 0, 0.75)',
            overflow: 'hidden',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            zIndex: 10,
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${dwellProgress}%`,
              background:
                pipelineStatus === 'WAIT_FOR_RELEASE'
                  ? 'var(--org-emerald)'
                  : 'linear-gradient(90deg, var(--worker-cyan), var(--org-emerald))',
              transition: 'width 0.05s linear',
            }}
          />
        </div>
      )}

      {/* Diagnostic Telemetry Overlay (§ 19, Strict Debug Mode) */}
      <div
        style={{
          position: 'absolute',
          top: '1rem',
          left: '1rem',
          background: 'rgba(11, 15, 25, 0.9)',
          backdropFilter: 'blur(8px)',
          border: '1px solid var(--surface-glass-border)',
          padding: '0.5rem 0.85rem',
          borderRadius: '12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.2rem',
          zIndex: 5,
          fontSize: '0.78rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1rem' }}>
            {handCount === 0 && '🔍'}
            {handCount > 0 && !activeGesture && pipelineStatus !== 'CONFLICT' && '🖐️'}
            {pipelineStatus === 'CONFLICT' && '⚠️'}
            {activeGesture === 'THUMBS_UP' && '👍'}
            {activeGesture === 'THUMBS_DOWN' && '👎'}
            {activeGesture === 'POINTING' && '👉'}
            {activeGesture === 'OPEN_PALM' && '✋'}
            {activeGesture === 'FIST' && '✊'}
            {activeGesture === 'PINCH' && '🤏'}
            {activeGesture === 'TWO_FINGER' && '✌️'}
          </span>
          <strong style={{ color: handCount > 0 && activeGesture ? 'var(--worker-cyan)' : pipelineStatus === 'CONFLICT' ? 'var(--accent-amber)' : '#fff' }}>
            {pipelineStatus === 'SEARCHING_FOR_HAND' && 'Searching for Hand(s)...'}
            {pipelineStatus === 'HAND_DETECTED' && `Hand(s) Tracked (${handCount}) • Unknown Pose`}
            {pipelineStatus === 'CONFLICT' && '⚠️ Multi-Hand Conflict • Action Suspended'}
            {pipelineStatus === 'CLASSIFYING' && `Analyzing ${activeGesture}...`}
            {pipelineStatus === 'GESTURE_CANDIDATE' && `Holding ${activeGesture} (${dwellProgress}%)`}
            {pipelineStatus === 'GESTURE_CONFIRMED' && `✓ ${activeGesture} Confirmed!`}
            {pipelineStatus === 'WAIT_FOR_RELEASE' && `✓ ${activeGesture} Executed • Release Hand`}
            {pipelineStatus === 'CAMERA_INITIALIZING' && 'Initializing Dual-Hand Camera...'}
            {pipelineStatus === 'ERROR' && 'Vision Error'}
          </strong>
        </div>

        <div style={{ color: 'var(--text-secondary)', fontSize: '0.72rem' }}>
          Hands Tracked: <span style={{ color: handCount > 0 ? 'var(--org-emerald)' : 'var(--text-muted)' }}>{handCount > 0 ? `${handCount} Active (21 LMs/hand)` : 'NONE'}</span> •{' '}
          Confidence: <span style={{ color: realConfidence > 0 ? 'var(--worker-cyan)' : 'var(--text-muted)' }}>{(realConfidence * 100).toFixed(0)}%</span>
        </div>
      </div>

      {/* Top Right: Pipeline Telemetry (FPS + Dual-Hand Landmarker Status) */}
      <div
        style={{
          position: 'absolute',
          top: '1rem',
          right: '1rem',
          background: 'rgba(11, 15, 25, 0.9)',
          backdropFilter: 'blur(8px)',
          border: '1px solid var(--surface-glass-border)',
          padding: '0.35rem 0.75rem',
          borderRadius: '10px',
          fontSize: '0.75rem',
          color: handCount > 0 ? 'var(--org-emerald)' : 'var(--text-muted)',
          fontWeight: 700,
          zIndex: 5,
        }}
      >
        ● Dual-Hand 21-LM Active ({fps} FPS)
      </div>

      {/* Camera Permission / Error Overlay (FR-01) */}
      {(errorMessage || permissionDenied || cameraState === 'CAMERA_ERROR') && (
        <div
          role="alert"
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(9, 13, 22, 0.95)',
            backdropFilter: 'blur(12px)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '2rem',
            textAlign: 'center',
            zIndex: 30,
            gap: '1rem',
          }}
        >
          <span style={{ fontSize: '3rem' }}>📷⚠️</span>
          <div>
            <h4 style={{ color: 'var(--accent-rose)', fontSize: '1.15rem', fontWeight: 800, marginBottom: '0.4rem' }}>
              {permissionDenied ? t('camera_access_denied', language) : t('camera_unavailable', language)}
            </h4>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', maxWidth: '400px', margin: '0 auto' }}>
              {permissionDenied
                ? t('camera_access_required', language)
                : errorMessage || t('camera_unavailable', language)}
            </p>
          </div>
          <button
            type="button"
            onClick={handleRetryCamera}
            className="btn btn-primary"
            style={{
              minHeight: '48px',
              minWidth: '160px',
              padding: '0.75rem 1.5rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
            }}
          >
            🔄 {t('try_again_btn', language)}
          </button>
        </div>
      )}
      </div>
    </>
  );
}

export default MediaPipeHandTracker;
