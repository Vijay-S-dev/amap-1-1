"""
High-Level AI Service Layer for AMAP Backend and Edge Workstations.
"""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from ai.models.types import (
    AdaptationProposal,
    BoundingBox,
    GestureFramePayload,
    GestureRecognitionResult,
    GestureType,
    Handedness,
    InputModality,
    LandmarkPoint,
    MultimodalFusionResult,
    MultimodalInputItem,
    VoiceCommandPayload,
    VoiceCommandResult,
)
from ai.personalization.analyzer import InteractionEventRecord
from ai.pipeline import MultimodalAIPipeline


class AIService:
    """
    Singleton-friendly service wrapper exposing complete AI pipeline capabilities.
    """

    _instance: Optional["AIService"] = None

    def __init__(self) -> None:
        self.pipeline = MultimodalAIPipeline()

    @classmethod
    def get_instance(cls) -> "AIService":
        """Retrieve or create singleton AIService instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def recognize_gesture(
        self,
        landmarks: List[Dict[str, float]],
        handedness: str = "Right",
        worker_id: Optional[str] = None,
        target_hitboxes: Optional[List[Dict[str, Any]]] = None,
        timestamp_ms: Optional[int] = None,
    ) -> GestureRecognitionResult:
        """Process optical gesture landmarks dictionary."""
        pts = [
            LandmarkPoint(
                x=float(p.get("x", 0.0)),
                y=float(p.get("y", 0.0)),
                z=float(p.get("z", 0.0)),
                visibility=float(p.get("visibility", 1.0)),
            )
            for p in landmarks
        ]

        hitboxes: List[BoundingBox] = []
        if target_hitboxes:
            for b in target_hitboxes:
                hitboxes.append(
                    BoundingBox(
                        x_min=float(b.get("x_min", 0.0)),
                        y_min=float(b.get("y_min", 0.0)),
                        x_max=float(b.get("x_max", 1.0)),
                        y_max=float(b.get("y_max", 1.0)),
                        target_id=b.get("target_id"),
                        label=b.get("label"),
                    )
                )

        h_enum = Handedness.RIGHT if handedness.lower() == "right" else Handedness.LEFT
        payload = GestureFramePayload(
            landmarks=pts,
            handedness=h_enum,
            worker_id=worker_id,
            target_hitboxes=hitboxes,
        )
        if timestamp_ms:
            payload.timestamp_ms = timestamp_ms

        return self.pipeline.process_gesture_frame(payload)

    def process_voice_transcript(
        self,
        transcript: str,
        confidence: float = 1.0,
        worker_id: Optional[str] = None,
        timestamp_ms: Optional[int] = None,
    ) -> VoiceCommandResult:
        """Process speech transcript command."""
        payload = VoiceCommandPayload(
            transcript=transcript,
            confidence=confidence,
            worker_id=worker_id,
        )
        if timestamp_ms:
            payload.timestamp_ms = timestamp_ms

        return self.pipeline.process_voice_command(payload)

    def fuse_inputs(
        self,
        inputs: List[Dict[str, Any]],
        temporal_window_ms: Optional[int] = None,
    ) -> MultimodalFusionResult:
        """Fuse multiple input streams within temporal window."""
        items: List[MultimodalInputItem] = []
        for inp in inputs:
            mode_str = str(inp.get("mode", "gesture")).lower()
            mode_enum = (
                InputModality.GESTURE
                if mode_str == "gesture"
                else (InputModality.VOICE if mode_str == "voice" else InputModality.UI)
            )
            items.append(
                MultimodalInputItem(
                    mode=mode_enum,
                    raw_intent=str(inp.get("raw_intent", "")),
                    confidence=float(inp.get("confidence", 1.0)),
                    timestamp_ms=int(inp.get("timestamp_ms", 0)),
                    spatial_target=inp.get("spatial_target"),
                )
            )

        return self.pipeline.fuse_multimodal_inputs(items, temporal_window_ms)

    def record_interaction_telemetry(
        self,
        worker_id: str,
        mode: str,
        success: bool,
        is_tremor: bool = False,
        is_dwell_timeout: bool = False,
        is_low_snr: bool = False,
        confidence: float = 0.90,
    ) -> None:
        """Record worker telemetry for evidence-based adaptation."""
        record = InteractionEventRecord(
            mode=mode,
            success=success,
            is_tremor=is_tremor,
            is_dwell_timeout=is_dwell_timeout,
            is_low_snr=is_low_snr,
            confidence=confidence,
        )
        self.pipeline.adaptation_engine.record_interaction(worker_id, record)

    def get_adaptation_proposals(
        self,
        worker_id: str,
        current_dwell_ms: int = 600,
        current_hitbox_factor: float = 1.0,
    ) -> List[AdaptationProposal]:
        """Query active adaptation recommendations for worker."""
        return self.pipeline.evaluate_adaptations(
            worker_id=worker_id,
            current_dwell_ms=current_dwell_ms,
            current_hitbox_factor=current_hitbox_factor,
        )
