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
 * Geometric Classification for an Individual Hand (Phase 4 Hardened)
 * Evaluates 21 3D landmarks for canonical AMAP gestures:
 * - THUMBS_UP (confirm_action)
 * - THUMBS_DOWN (cancel_action)
 * - FIST (emergency_stop)
 * - POINTING (orientation-robust next_step / point_focus)
 * - OPEN_PALM (pause_session)
 * - UNKNOWN (safely rejected)
 */
export function classifySingleHand(landmarks: Landmark3D[]): { gesture: string | null; confidence: number } {
  if (!landmarks || landmarks.length < 21) {
    return { gesture: null, confidence: 0 };
  }

  const wrist = landmarks[0];
  const thumbIp = landmarks[3];
  const thumbTip = landmarks[4];
  const indexMcp = landmarks[5];
  const indexPip = landmarks[6];
  const indexTip = landmarks[8];
  const middleMcp = landmarks[9];
  const middlePip = landmarks[10];
  const middleTip = landmarks[12];
  const ringMcp = landmarks[13];
  const ringPip = landmarks[14];
  const ringTip = landmarks[16];
  const pinkyMcp = landmarks[17];
  const pinkyPip = landmarks[18];
  const pinkyTip = landmarks[20];

  const dist2d = (p1: Landmark3D, p2: Landmark3D) =>
    Math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2);

  const dist3d = (p1: Landmark3D, p2: Landmark3D) => {
    const dz = (p1.z || 0) - (p2.z || 0);
    return Math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + dz * dz);
  };

  const palmSize = dist2d(wrist, middleMcp);
  if (palmSize < 0.04) {
    return { gesture: null, confidence: 0 };
  }

  // Robust Extension Metrics: supports both vertical extension and 3D radial extension
  const isExtended = (tip: Landmark3D, pip: Landmark3D, mcp: Landmark3D): boolean => {
    const verticalExt = tip.y < pip.y && tip.y < mcp.y;
    const radialExt = dist3d(tip, wrist) > dist3d(pip, wrist) * 1.15 && dist3d(tip, mcp) > palmSize * 0.70;
    return verticalExt || radialExt;
  };

  const isCurled = (tip: Landmark3D, mcp: Landmark3D): boolean => {
    return dist3d(tip, mcp) < palmSize * 0.75;
  };

  const isIndexExtended = isExtended(indexTip, indexPip, indexMcp);
  const isMiddleExtended = isExtended(middleTip, middlePip, middleMcp);
  const isRingExtended = isExtended(ringTip, ringPip, ringMcp);
  const isPinkyExtended = isExtended(pinkyTip, pinkyPip, pinkyMcp);

  const isMiddleCurled = isCurled(middleTip, middleMcp);
  const isRingCurled = isCurled(ringTip, ringMcp);
  const isPinkyCurled = isCurled(pinkyTip, pinkyMcp);

  // Thumb vertical directions
  const isThumbUp = thumbTip.y < thumbIp.y && thumbTip.y < indexMcp.y;
  const isThumbDown = thumbTip.y > thumbIp.y && thumbTip.y > wrist.y;

  // 1. THUMBS UP: Thumb pointing up, other 4 fingers curled
  if (isThumbUp && !isIndexExtended && !isMiddleExtended && !isRingExtended && !isPinkyExtended) {
    const extensionScore = Math.min(1.0, (indexPip.y - thumbTip.y) / (palmSize * 0.8));
    const confidence = Math.max(0.78, Math.min(0.99, 0.78 + extensionScore * 0.21));
    return { gesture: 'THUMBS_UP', confidence: parseFloat(confidence.toFixed(2)) };
  }

  // 2. THUMBS DOWN: Thumb pointing down, other 4 fingers curled (Phase 4 Hardened)
  if (isThumbDown && !isIndexExtended && !isMiddleExtended && !isRingExtended && !isPinkyExtended) {
    const extensionScore = Math.min(1.0, (thumbTip.y - wrist.y) / (palmSize * 0.8));
    const confidence = Math.max(0.78, Math.min(0.99, 0.78 + extensionScore * 0.21));
    return { gesture: 'THUMBS_DOWN', confidence: parseFloat(confidence.toFixed(2)) };
  }

  // 3. FIST: All 4 fingers curled, thumb not pointing up or down
  if (!isIndexExtended && !isMiddleExtended && !isRingExtended && !isPinkyExtended && !isThumbUp && !isThumbDown) {
    const maxFingertipDist = Math.max(
      dist3d(indexTip, indexMcp),
      dist3d(middleTip, middleMcp),
      dist3d(ringTip, ringMcp),
      dist3d(pinkyTip, pinkyMcp)
    );
    if (maxFingertipDist < palmSize * 0.70) {
      return { gesture: 'FIST', confidence: 0.92 };
    }
  }

  // 4. POINTING (Orientation-Robust):
  // Index finger extended (upwards, horizontal, or forward), while middle, ring, pinky are curled
  if (isIndexExtended && isMiddleCurled && isRingCurled && isPinkyCurled && !isThumbUp && !isThumbDown) {
    const pointDist = dist3d(indexTip, indexMcp);
    const confidence = Math.max(0.78, Math.min(0.98, 0.78 + (pointDist / palmSize) * 0.2));
    return { gesture: 'POINTING', confidence: parseFloat(confidence.toFixed(2)) };
  }

  // 5. OPEN PALM: All 4 fingers extended + spread
  if (isIndexExtended && isMiddleExtended && isRingExtended && isPinkyExtended) {
    const spread = dist3d(thumbTip, pinkyTip);
    const confidence = Math.max(0.82, Math.min(0.99, 0.82 + (spread / (palmSize * 2)) * 0.17));
    return { gesture: 'OPEN_PALM', confidence: parseFloat(confidence.toFixed(2)) };
  }

  return { gesture: 'UNKNOWN', confidence: 0.50 };
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
}

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

    allHandsLandmarks.forEach((landmarks, handIdx) => {
      if (!landmarks || landmarks.length < 21) return;

      // Compute bounding box around joints
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      landmarks.forEach((pt) => {
        const px = (1 - pt.x) * canvasWidth; // Mirrored
        const py = pt.y * canvasHeight;
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

        const x1 = (1 - p1.x) * canvasWidth;
        const y1 = p1.y * canvasHeight;
        const x2 = (1 - p2.x) * canvasWidth;
        const y2 = p2.y * canvasHeight;

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
        const px = (1 - pt.x) * canvasWidth;
        const py = pt.y * canvasHeight;

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

        // 2. Initialize Dual-Hand Landmarker (numHands: 2)
        handLandmarkerInstance = await HandLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: '/mediapipe/hand_landmarker.task',
            delegate: 'GPU',
          },
          runningMode: 'VIDEO',
          numHands: 2, // DETECT BOTH HANDS SIMULTANEOUSLY
          minHandDetectionConfidence: 0.45,
          minHandPresenceConfidence: 0.45,
          minTrackingConfidence: 0.45,
        });

        if (!isComponentMounted) return;

        // 3. Start Camera Stream (FR-01 User Input Capture)
        if (typeof navigator !== 'undefined' && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
          try {
            cameraStream = await navigator.mediaDevices.getUserMedia({
              video: {
                width: { ideal: 640 },
                height: { ideal: 480 },
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
              await videoRef.current.play();
            } catch (playErr) {
              console.warn('Video play interrupted or muted:', playErr);
            }
            setCameraState('CAMERA_ACTIVE');
            setPipelineStatus('SEARCHING_FOR_HAND');
            callbacksRef.current.onCameraStateChange?.('CAMERA_ACTIVE');
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

        frameCount++;
        const now = performance.now();
        if (now - lastTime >= 1000) {
          setFps(frameCount);
          frameCount = 0;
          lastTime = now;
        }

        const video = videoRef.current;
        const canvas = canvasRef.current;

        if (video && canvas && handLandmarkerInstance && video.readyState >= 2) {
          const ctx = canvas.getContext('2d');
          if (ctx) {
            let results: any = null;
            try {
              results = handLandmarkerInstance.detectForVideo(video, now);
            } catch {
              results = null;
            }

            const multiHands: Landmark3D[][] = results?.landmarks || [];
            const multiHandLabels: string[] = results?.handednesses?.map((h: any) => h[0]?.categoryName) || [];

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
          objectFit: 'cover',
          transform: 'scaleX(-1)', // Mirror user reflection
          opacity: 0.88,
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
  );
}

export default MediaPipeHandTracker;
