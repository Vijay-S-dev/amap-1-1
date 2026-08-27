"""
Optical Hand Gesture Recognizer and Interaction Pipeline.
"""

from typing import Dict, List, Optional

from ai.config import CONFIDENCE_THRESHOLD_GESTURE, GESTURE_TO_ACTION
from ai.gesture.dwell import DwellAccumulator
from ai.gesture.landmarks import compute_palm_center
from ai.gesture.spatial import SpatialTargetDetector
from ai.models.classifier import BaseClassifier
from ai.models.registry import ModelRegistry
from ai.models.types import (
    BoundingBox,
    DwellStatus,
    GestureFramePayload,
    GestureRecognitionResult,
    GestureType,
    Handedness,
    LandmarkPoint,
)


class GestureRecognizer:
    """
    Main optical perception engine for gesture classification, spatial tracking,
    dwell accumulation, and involuntary tremor filtering.
    """

    def __init__(
        self,
        classifier: Optional[BaseClassifier] = None,
        default_dwell_ms: int = 600,
    ) -> None:
        self.classifier = classifier or ModelRegistry.get("geometric")
        self.default_dwell_ms = default_dwell_ms
        self.spatial_detector = SpatialTargetDetector()

        # In-memory dwell accumulators per worker: {worker_id: DwellAccumulator}
        self._accumulators: Dict[str, DwellAccumulator] = {}

    def _get_accumulator(self, worker_id: Optional[str]) -> DwellAccumulator:
        key = worker_id or "default_worker"
        if key not in self._accumulators:
            self._accumulators[key] = DwellAccumulator(dwell_time_ms=self.default_dwell_ms)
        return self._accumulators[key]

    def set_worker_dwell_time(self, worker_id: str, dwell_time_ms: int) -> None:
        """Dynamically adapt dwell time for a specific worker."""
        acc = self._get_accumulator(worker_id)
        acc.dwell_time_ms = dwell_time_ms

    def process_frame(self, payload: GestureFramePayload) -> GestureRecognitionResult:
        """
        Process a single optical video/landmark frame.
        """
        landmarks = payload.landmarks
        if not landmarks or len(landmarks) < 21:
            return GestureRecognitionResult(
                gesture=GestureType.IDLE,
                confidence=0.0,
                dwell_status=DwellStatus.IDLE,
                dwell_progress=0.0,
                action=None,
                message="Insufficient hand landmarks detected (need 21 points).",
            )

        # 1. Optical classification
        gesture, confidence = self.classifier.predict(landmarks, payload.handedness)

        # 2. Determine spatial pointer (index tip or palm center)
        if gesture == GestureType.POINTING:
            raw_pointer = landmarks[8]  # Index fingertip
        else:
            raw_pointer = compute_palm_center(landmarks)

        # 3. Feed to Dwell Accumulator & Tremor Filter
        accumulator = self._get_accumulator(payload.worker_id)
        dwell_status, dwell_progress = accumulator.update(
            gesture=gesture if confidence >= CONFIDENCE_THRESHOLD_GESTURE else GestureType.IDLE,
            raw_point=raw_pointer,
            timestamp_ms=payload.timestamp_ms,
        )

        smoothed_pointer = accumulator.smoothed_pointer or raw_pointer

        # 4. Spatial Target Hit Testing
        target_hit: Optional[BoundingBox] = None
        if payload.target_hitboxes:
            target_hit = self.spatial_detector.find_intersecting_target(
                pointer=smoothed_pointer,
                targets=payload.target_hitboxes,
            )

        # 5. Action Resolution
        action: Optional[str] = None
        if dwell_status == DwellStatus.TRIGGERED:
            action = GESTURE_TO_ACTION.get(gesture.value)

        return GestureRecognitionResult(
            gesture=gesture,
            confidence=confidence,
            dwell_status=dwell_status,
            dwell_progress=dwell_progress,
            action=action,
            target_hit=target_hit,
            is_tremor_detected=accumulator.is_tremor_detected,
            smoothed_pointer=smoothed_pointer,
            message=f"Gesture {gesture.value} ({confidence:.2f}) - Dwell: {dwell_status.value} ({dwell_progress:.0%})",
        )
