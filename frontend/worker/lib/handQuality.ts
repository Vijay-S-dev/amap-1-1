/**
 * Hand-quality gate for the MediaPipe hand pipeline.
 *
 * Drops partial / too-distant / low-visibility hands BEFORE any
 * classification, so poorly visible frames can never produce gestures or
 * drive the interaction engine.
 *
 * Extracted verbatim from MediaPipeHandTracker.tsx so it is unit-testable
 * with the same realistic landmark shapes @mediapipe/tasks-vision produces.
 *
 * Rules:
 *   - a hand must have all 21 landmarks;
 *   - palm size (wrist -> middle MCP) must exceed MIN_PALM_SIZE: a tiny
 *     distant hand yields noisy landmarks and accidental gestures;
 *   - when the model reports per-landmark visibility, the average must
 *     clear MIN_AVG_VISIBILITY (occluded/partial hands are rejected).
 *
 * IMPORTANT — visibility semantics (root cause of an earlier gesture
 * blackout): @mediapipe/tasks-vision ALWAYS materializes `visibility` as a
 * number for every landmark. For models that do not emit per-landmark
 * visibility scores — which includes the hand_landmarker models, whose
 * output tensor carries only x/y/z — the JS converter writes a literal `0`
 * (landmark_result.ts: `visibility: proto.getVisibility() ?? 0`). A `0`
 * therefore means "NOT REPORTED", not "invisible". Treating a numeric `0`
 * as a real score rejected every detected hand every frame. A visibility
 * value is only treated as reported when it is a number strictly greater
 * than zero; genuine scores are sigmoid outputs in (0, 1].
 */

/** Landmark shape produced by @mediapipe/tasks-vision (visibility optional). */
export interface QualityLandmark {
  x: number;
  y: number;
  z?: number;
  /** Materialized as 0 by tasks-vision when the model emits no score. */
  visibility?: number;
}

export interface QualityHandResult {
  hands: QualityLandmark[][];
  labels: string[];
}

/**
 * Minimum palm size (wrist -> middle MCP), normalized units.
 * 0.035 (~3.5% of frame width) accepts hands on wide-FOV laptop webcams and
 * at arm's length while still rejecting degenerate/noise detections —
 * MediaPipe's own detection confidence remains the primary noise filter.
 * Verified against real webcam-synthetic feeds: hands at ~30% frame width
 * pass with margin; hands MediaPipe can no longer detect (~18%) never
 * reach this gate at all.
 */
export const MIN_PALM_SIZE = 0.035;
/** Minimum average per-landmark visibility when the model reports scores. */
export const MIN_AVG_VISIBILITY = 0.55;

/**
 * Filters raw MediaPipe hands down to quality hands, preserving the
 * handedness label alignment (defaults to 'Right' when absent).
 */
export function filterHandsByQuality(
  rawHands: QualityLandmark[][],
  rawLabels: string[]
): QualityHandResult {
  const hands: QualityLandmark[][] = [];
  const labels: string[] = [];
  rawHands.forEach((hand, handIdx) => {
    if (!hand || hand.length < 21) return;
    const palmSize = Math.hypot(hand[0].x - hand[9].x, hand[0].y - hand[9].y);
    if (palmSize < MIN_PALM_SIZE) return;
    const visibilities = hand
      .map((pt) =>
        typeof pt?.visibility === 'number' && pt.visibility > 0 ? pt.visibility : null
      )
      .filter((v: number | null): v is number => v !== null);
    if (visibilities.length === hand.length) {
      const avgVisibility = visibilities.reduce((a, b) => a + b, 0) / visibilities.length;
      if (avgVisibility < MIN_AVG_VISIBILITY) return;
    }
    hands.push(hand);
    labels.push(rawLabels[handIdx] || 'Right');
  });
  return { hands, labels };
}
