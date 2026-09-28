/**
 * AMAP Shared Hand Pose Classification (frontend/worker/lib/handPoses.ts)
 *
 * Single source of truth for geometric 21-landmark hand pose classification
 * used by BOTH:
 *  - MediaPipeHandTracker (dwell-confirmed workflow gestures)
 *  - WorkerGestureEngine (real-time interaction: pointer, click, drag, scroll)
 *
 * Poses:
 *  - NONE          hand present but pose not recognized
 *  - POINTING      index extended, others curled (pointer aiming pose)
 *  - PINCH         thumb tip + index tip touching (click / drag pose)
 *  - TWO_FINGER    index + middle extended (right click / scroll pose)
 *  - OPEN_PALM     all fingers extended (pause)
 *  - FIST          all fingers curled (emergency stop)
 *  - THUMBS_UP     thumb up, fingers curled (confirm)
 *  - THUMBS_DOWN   thumb down, fingers curled (cancel)
 *
 * Kept behaviorally compatible with backend/services/gesture_service.py.
 */

export interface Landmark3D {
  x: number;
  y: number;
  z?: number;
}

export type HandPose =
  | 'NONE'
  | 'POINTING'
  | 'PINCH'
  | 'TWO_FINGER'
  | 'OPEN_PALM'
  | 'FIST'
  | 'THUMBS_UP'
  | 'THUMBS_DOWN';

export interface PoseMetrics {
  /** Normalized distance between thumb tip and index tip (pinch tightness). */
  pinchDistance: number;
  /** Palm size used as normalization scale. */
  palmSize: number;
}

export interface HandPoseResult {
  pose: HandPose;
  confidence: number;
  metrics: PoseMetrics;
}

const dist2d = (p1: Landmark3D, p2: Landmark3D): number =>
  Math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2);

const dist3d = (p1: Landmark3D, p2: Landmark3D): number => {
  const dz = (p1.z || 0) - (p2.z || 0);
  return Math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + dz * dz);
};

/** Pinch distance thresholds (normalized by palm size), with hysteresis:
 *  a pose ENTERS pinch below PINCH_ENTER_THRESHOLD and only EXITS above
 *  PINCH_EXIT_THRESHOLD, so a hand hovering near the boundary cannot
 *  flicker PINCH <-> NONE (which the engine would read as repeated clicks). */
export const PINCH_ENTER_THRESHOLD = 0.45;
export const PINCH_EXIT_THRESHOLD = 0.56;

export interface ClassifyOptions {
  /** True when the previous committed pose was PINCH (enables exit hysteresis). */
  pinchActive?: boolean;
}

/**
 * Classify a single 21-landmark hand into a canonical AMAP pose.
 * Returns pose NONE with confidence 0 when the hand skeleton is invalid.
 */
export function classifyHandPose(landmarks: Landmark3D[], options?: ClassifyOptions): HandPoseResult {
  const none = (pinch = 1): HandPoseResult => ({
    pose: 'NONE',
    confidence: 0,
    metrics: { pinchDistance: pinch, palmSize: 0 },
  });

  if (!landmarks || landmarks.length < 21) return none();

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

  const palmSize = dist2d(wrist, middleMcp);
  const pinchDistance = dist2d(thumbTip, indexTip);

  if (palmSize < 0.04) return none(pinchDistance);

  const metrics: PoseMetrics = {
    pinchDistance: pinchDistance / palmSize,
    palmSize,
  };

  // Robust extension: vertical OR 3D radial extension
  const isExtended = (tip: Landmark3D, pip: Landmark3D, mcp: Landmark3D): boolean => {
    const verticalExt = tip.y < pip.y && tip.y < mcp.y;
    const radialExt = dist3d(tip, wrist) > dist3d(pip, wrist) * 1.15 && dist3d(tip, mcp) > palmSize * 0.7;
    return verticalExt || radialExt;
  };

  const isCurled = (tip: Landmark3D, mcp: Landmark3D): boolean =>
    dist3d(tip, mcp) < palmSize * 0.75;

  const isIndexExtended = isExtended(indexTip, indexPip, indexMcp);
  const isMiddleExtended = isExtended(middleTip, middlePip, middleMcp);
  const isRingExtended = isExtended(ringTip, ringPip, ringMcp);
  const isPinkyExtended = isExtended(pinkyTip, pinkyPip, pinkyMcp);

  const isMiddleCurled = isCurled(middleTip, middleMcp);
  const isRingCurled = isCurled(ringTip, ringMcp);
  const isPinkyCurled = isCurled(pinkyTip, pinkyMcp);

  const isThumbUp = thumbTip.y < thumbIp.y && thumbTip.y < indexMcp.y;
  const isThumbDown = thumbTip.y > thumbIp.y && thumbTip.y > wrist.y;

  // 1. THUMBS UP
  if (isThumbUp && !isIndexExtended && !isMiddleExtended && !isRingExtended && !isPinkyExtended) {
    const extensionScore = Math.min(1.0, (indexPip.y - thumbTip.y) / (palmSize * 0.8));
    const confidence = Math.max(0.78, Math.min(0.99, 0.78 + extensionScore * 0.21));
    return { pose: 'THUMBS_UP', confidence: round2(confidence), metrics };
  }

  // 2. THUMBS DOWN
  if (isThumbDown && !isIndexExtended && !isMiddleExtended && !isRingExtended && !isPinkyExtended) {
    const extensionScore = Math.min(1.0, (thumbTip.y - wrist.y) / (palmSize * 0.8));
    const confidence = Math.max(0.78, Math.min(0.99, 0.78 + extensionScore * 0.21));
    return { pose: 'THUMBS_DOWN', confidence: round2(confidence), metrics };
  }

  // 3. PINCH: thumb tip meets index tip while middle/ring/pinky are curled.
  //    (pinchDistance normalized by palm size for depth robustness)
  //    Hysteresis: entering requires a tight pinch; releasing requires
  //    clearly opening past the exit threshold.
  const pinchThreshold = options?.pinchActive
    ? PINCH_EXIT_THRESHOLD
    : PINCH_ENTER_THRESHOLD;
  if (metrics.pinchDistance < pinchThreshold) {
    if (isMiddleCurled && isRingCurled && isPinkyCurled) {
      const tightness = 1 - Math.min(1, metrics.pinchDistance / 0.45);
      const confidence = Math.max(0.82, Math.min(0.98, 0.82 + tightness * 0.16));
      return { pose: 'PINCH', confidence: round2(confidence), metrics };
    }
  }

  // 4. FIST: all four fingers curled, thumb not pointing up or down
  if (
    !isIndexExtended &&
    !isMiddleExtended &&
    !isRingExtended &&
    !isPinkyExtended &&
    !isThumbUp &&
    !isThumbDown
  ) {
    const maxFingertipDist = Math.max(
      dist3d(indexTip, indexMcp),
      dist3d(middleTip, middleMcp),
      dist3d(ringTip, ringMcp),
      dist3d(pinkyTip, pinkyMcp)
    );
    if (maxFingertipDist < palmSize * 0.7) {
      return { pose: 'FIST', confidence: 0.92, metrics };
    }
  }

  // 5. TWO_FINGER: index + middle extended, ring + pinky curled (right click / scroll)
  if (isIndexExtended && isMiddleExtended && !isRingExtended && !isPinkyExtended) {
    const pointDist = dist3d(indexTip, indexMcp);
    const confidence = Math.max(0.8, Math.min(0.97, 0.8 + (pointDist / palmSize) * 0.17));
    return { pose: 'TWO_FINGER', confidence: round2(confidence), metrics };
  }

  // 6. POINTING: index extended, middle/ring/pinky curled
  if (isIndexExtended && isMiddleCurled && isRingCurled && isPinkyCurled && !isThumbUp && !isThumbDown) {
    const pointDist = dist3d(indexTip, indexMcp);
    const confidence = Math.max(0.78, Math.min(0.98, 0.78 + (pointDist / palmSize) * 0.2));
    return { pose: 'POINTING', confidence: round2(confidence), metrics };
  }

  // 7. OPEN_PALM: all four fingers extended
  if (isIndexExtended && isMiddleExtended && isRingExtended && isPinkyExtended) {
    const spread = dist2d(thumbTip, pinkyTip);
    const confidence = Math.max(0.82, Math.min(0.99, 0.82 + (spread / (palmSize * 2)) * 0.17));
    return { pose: 'OPEN_PALM', confidence: round2(confidence), metrics };
  }

  return { pose: 'NONE', confidence: 0.5, metrics };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

/** Map a pose to the lowercase gesture key used in worker gesture mappings. */
export function poseToGestureKey(pose: HandPose): string {
  switch (pose) {
    case 'THUMBS_UP':
      return 'thumbs_up';
    case 'THUMBS_DOWN':
      return 'thumbs_down';
    case 'OPEN_PALM':
      return 'open_palm';
    case 'FIST':
      return 'fist';
    case 'POINTING':
      return 'pointing';
    case 'PINCH':
      return 'pinch';
    case 'TWO_FINGER':
      return 'two_finger';
    default:
      return 'none';
  }
}

/**
 * Detect a swipe direction from accumulated palm-center motion.
 * Returns null when the motion is below threshold (no swipe).
 */
export type SwipeDirection = 'swipe_left' | 'swipe_right' | 'swipe_up' | 'swipe_down';

export function detectSwipe(
  displacement: { dx: number; dy: number },
  thresholdX: number,
  thresholdY: number
): SwipeDirection | null {
  const { dx, dy } = displacement;
  const ax = Math.abs(dx);
  const ay = Math.abs(dy);
  if (ax < thresholdX && ay < thresholdY) return null;
  if (ax >= ay) {
    return dx > 0 ? 'swipe_right' : 'swipe_left';
  }
  return dy > 0 ? 'swipe_down' : 'swipe_up';
}
