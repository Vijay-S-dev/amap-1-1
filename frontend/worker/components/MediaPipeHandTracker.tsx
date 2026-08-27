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
  | 'ERROR';

export interface HandTrackerProps {
  onGestureDetected?: (gesture: string, confidence: number) => void;
  onLandmarksDetected?: (landmarks: Landmark3D[]) => void;
  onHandPresenceChange?: (hasHand: boolean) => void;
  width?: string | number;
  height?: string | number;
  showLabels?: boolean;
  requiredDwellMs?: number;
  onGestureConfirmed?: (gesture: string) => void;
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
    onCameraStateChange,
    requiredDwellMs,
  });

  useEffect(() => {
    callbacksRef.current = {
      onGestureDetected,
      onLandmarksDetected,
      onHandPresenceChange,
      onGestureConfirmed,
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

  // Temporal Stability & Execution Release Latch
  const stabilityBufferRef = useRef<string[]>([]);
  const dwellStartTimeRef = useRef<number | null>(null);
  const isActionExecutedRef = useRef<boolean>(false);
  const currentConfirmedGestureRef = useRef<string | null>(null);

  // Real Geometric Classification for an Individual Hand
  const classifySingleHand = useCallback((landmarks: Landmark3D[]): { gesture: string | null; confidence: number } => {
    if (!landmarks || landmarks.length < 21) {
      return { gesture: null, confidence: 0 };
    }

    const wrist = landmarks[0];
    const thumbTip = landmarks[4];
    const thumbIp = landmarks[3];
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

    // Vertical extension metrics
    const isIndexExtended = indexTip.y < indexPip.y && indexTip.y < indexMcp.y;
    const isMiddleExtended = middleTip.y < middlePip.y && middleTip.y < middleMcp.y;
    const isRingExtended = ringTip.y < ringPip.y && ringTip.y < ringMcp.y;
    const isPinkyExtended = pinkyTip.y < pinkyPip.y && pinkyTip.y < pinkyMcp.y;
    const isThumbUp = thumbTip.y < thumbIp.y && thumbTip.y < indexMcp.y;

    const dist = (p1: Landmark3D, p2: Landmark3D) =>
      Math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2);

    const palmSize = dist(wrist, middleMcp);
    if (palmSize < 0.04) {
      return { gesture: null, confidence: 0 };
    }

    // 1. THUMBS UP
    if (isThumbUp && !isIndexExtended && !isMiddleExtended && !isRingExtended && !isPinkyExtended) {
      const extensionScore = Math.min(1.0, (indexPip.y - thumbTip.y) / (palmSize * 0.8));
      const confidence = Math.max(0.78, Math.min(0.99, 0.78 + extensionScore * 0.21));
      return { gesture: 'THUMBS_UP', confidence: parseFloat(confidence.toFixed(2)) };
    }

    // 2. POINTING
    if (isIndexExtended && !isMiddleExtended && !isRingExtended && !isPinkyExtended) {
      const pointDist = dist(indexTip, indexMcp);
      const confidence = Math.max(0.78, Math.min(0.98, 0.78 + (pointDist / palmSize) * 0.2));
      return { gesture: 'POINTING', confidence: parseFloat(confidence.toFixed(2)) };
    }

    // 3. OPEN PALM
    if (isIndexExtended && isMiddleExtended && isRingExtended && isPinkyExtended) {
      const spread = dist(thumbTip, pinkyTip);
      const confidence = Math.max(0.82, Math.min(0.99, 0.82 + (spread / (palmSize * 2)) * 0.17));
      return { gesture: 'OPEN_PALM', confidence: parseFloat(confidence.toFixed(2)) };
    }

    // 4. FIST
    if (!isIndexExtended && !isMiddleExtended && !isRingExtended && !isPinkyExtended && !isThumbUp) {
      const maxFingertipDist = Math.max(
        dist(indexTip, indexMcp),
        dist(middleTip, middleMcp),
        dist(ringTip, ringMcp),
        dist(pinkyTip, pinkyMcp)
      );
      if (maxFingertipDist < palmSize * 0.65) {
        return { gesture: 'FIST', confidence: 0.92 };
      }
    }

    return { gesture: 'UNKNOWN', confidence: 0.5 };
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
          'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
        );

        if (!isComponentMounted) return;

        // 2. Initialize Dual-Hand Landmarker (numHands: 2)
        handLandmarkerInstance = await HandLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
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
            if (multiHands.length === 0) {
              ctx.clearRect(0, 0, canvas.width, canvas.height);
              setHandCount(0);
              setActiveGesture(null);
              setRealConfidence(0.0);
              setDwellProgress(0);

              // Reset temporal and execution release states
              stabilityBufferRef.current = [];
              dwellStartTimeRef.current = null;
              isActionExecutedRef.current = false;
              currentConfirmedGestureRef.current = null;

              setPipelineStatus('SEARCHING_FOR_HAND');

              const cb = callbacksRef.current;
              if (cb.onHandPresenceChange) cb.onHandPresenceChange(false);
              if (cb.onGestureDetected) cb.onGestureDetected('NONE', 0.0);
            } else {
              // =========================================================================
              // LAYER 1 PASSED: 1 OR 2 HANDS DETECTED!
              // =========================================================================
              setHandCount(multiHands.length);

              const cb = callbacksRef.current;
              if (cb.onHandPresenceChange) cb.onHandPresenceChange(true);
              if (cb.onLandmarksDetected) cb.onLandmarksDetected(multiHands[0]);

              // =========================================================================
              // STRICT LAYER 2: "WHAT ARE THE HANDS DOING?"
              // =========================================================================
              // Classify primary active hand gesture
              let dominantGesture: string | null = null;
              let highestConfidence = 0;

              multiHands.forEach((handLandmarks) => {
                const { gesture, confidence } = classifySingleHand(handLandmarks);
                if (gesture && gesture !== 'UNKNOWN' && confidence > highestConfidence) {
                  dominantGesture = gesture;
                  highestConfidence = confidence;
                }
              });

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

              if (!dominantGesture) {
                // Hand(s) present, but no recognized gesture pose
                setActiveGesture(null);
                setRealConfidence(0.5);
                setDwellProgress(0);
                stabilityBufferRef.current = [];
                dwellStartTimeRef.current = null;
                isActionExecutedRef.current = false;
                setPipelineStatus('HAND_DETECTED');

                if (cb.onGestureDetected) cb.onGestureDetected('UNKNOWN', 0.5);
              } else {
                // Recognized gesture on at least one hand
                setActiveGesture(dominantGesture);
                setRealConfidence(highestConfidence);
                if (cb.onGestureDetected) cb.onGestureDetected(dominantGesture, highestConfidence);

                // --- Temporal Stability Buffer (Must persist for >= 3 frames) ---
                const buffer = stabilityBufferRef.current;
                buffer.push(dominantGesture);
                if (buffer.length > 5) buffer.shift();

                const isTemporallyStable =
                  buffer.length >= 3 && buffer.every((g) => g === dominantGesture);

                if (!isTemporallyStable) {
                  setPipelineStatus('CLASSIFYING');
                  setDwellProgress(0);
                  dwellStartTimeRef.current = null;
                } else {
                  // Temporal stability satisfied
                  if (isActionExecutedRef.current && currentConfirmedGestureRef.current === dominantGesture) {
                    // --- Release Latch: Hand still held after execution ---
                    setPipelineStatus('WAIT_FOR_RELEASE');
                    setDwellProgress(100);
                  } else {
                    setPipelineStatus('GESTURE_CANDIDATE');

                    // --- Dwell Time Accumulator ---
                    if (!dwellStartTimeRef.current) {
                      dwellStartTimeRef.current = now;
                    }

                    const elapsedDwell = now - dwellStartTimeRef.current;
                    const reqDwell = cb.requiredDwellMs || 500;
                    const pct = Math.min(100, Math.round((elapsedDwell / reqDwell) * 100));
                    setDwellProgress(pct);

                    if (pct >= 100 && !isActionExecutedRef.current) {
                      // --- GESTURE CONFIRMED & EXECUTED ONCE ---
                      setPipelineStatus('GESTURE_CONFIRMED');
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
          style={{
            position: 'absolute',
            bottom: '1rem',
            left: '1.5rem',
            right: '1.5rem',
            height: '8px',
            borderRadius: '4px',
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
            {handCount > 0 && !activeGesture && '🖐️'}
            {activeGesture === 'THUMBS_UP' && '👍'}
            {activeGesture === 'POINTING' && '👉'}
            {activeGesture === 'OPEN_PALM' && '✋'}
            {activeGesture === 'FIST' && '✊'}
          </span>
          <strong style={{ color: handCount > 0 && activeGesture ? 'var(--worker-cyan)' : '#fff' }}>
            {pipelineStatus === 'SEARCHING_FOR_HAND' && 'Searching for Hand(s)...'}
            {pipelineStatus === 'HAND_DETECTED' && `Hand(s) Tracked (${handCount}) • Unknown Pose`}
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
