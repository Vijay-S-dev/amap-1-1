/**
 * Camera display transform helpers (frontend/worker/lib/cameraTransform.ts)
 *
 * The live camera <video> uses `object-fit: contain` (letterboxed, never
 * cropped) so the worker's hand is always fully visible at any container
 * size. These helpers map video-frame normalized landmark coordinates onto
 * the display container using the SAME letterbox math CSS applies, so the
 * skeleton overlay aligns exactly with the visible hand.
 */

export interface ContainTransform {
  /** Uniform scale applied to the video to fit the container. */
  scale: number;
  /** Horizontal centering offset in container pixels. */
  offsetX: number;
  /** Vertical centering offset in container pixels. */
  offsetY: number;
}

export function computeContainTransform(
  videoWidth: number,
  videoHeight: number,
  containerWidth: number,
  containerHeight: number
): ContainTransform {
  const vw = Math.max(1, videoWidth || 640);
  const vh = Math.max(1, videoHeight || 480);
  const cw = Math.max(1, containerWidth);
  const ch = Math.max(1, containerHeight);
  const scale = Math.min(cw / vw, ch / vh);
  return {
    scale,
    offsetX: (cw - vw * scale) / 2,
    offsetY: (ch - vh * scale) / 2,
  };
}
