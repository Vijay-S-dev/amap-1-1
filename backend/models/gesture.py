"""
Gesture pipeline domain schemas for AMAP.

Defines schemas for hand landmarks, video frame payloads, standard recognition results,
and worker-specific custom gesture training, persistence, and classification.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel, EntityStatus


class LandmarkPoint(AMAPBaseModel):
    """Normalized 3D hand landmark coordinate point (e.g. MediaPipe)."""
    x: float = Field(..., description="Normalized X coordinate [0.0, 1.0]")
    y: float = Field(..., description="Normalized Y coordinate [0.0, 1.0]")
    z: float = Field(default=0.0, description="Normalized Z coordinate (depth)")


class GestureFramePayload(StrictInputModel):
    """
    Client payload representing a single video frame of tracked hand landmarks.
    """
    landmarks: List[LandmarkPoint] = Field(
        ...,
        min_length=21,
        max_length=21,
        description="21 MediaPipe hand landmark points",
    )
    handedness: str = Field(default="Right", pattern="^(Right|Left)$")
    timestamp_ms: int = Field(..., ge=0, description="Frame timestamp in milliseconds")
    dwell_time_ms: Optional[int] = Field(
        default=500,
        ge=100,
        le=3000,
        description="Required dwell time threshold in milliseconds",
    )
    client_context: Dict[str, Any] = Field(default_factory=dict)


class GestureRecognitionResult(AMAPBaseModel):
    """
    Result of landmark classification (standard or custom) and temporal dwell-time filtering.
    """
    detected_gesture: Optional[str] = Field(
        None,
        description="Classified gesture name (e.g. thumbs_up, custom_confirm, open_palm)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Recognition confidence score",
    )
    is_triggered: bool = Field(
        ...,
        description="True if the gesture has been sustained for the required dwell time threshold",
    )
    dwell_progress: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Progress towards fulfilling the dwell threshold [0.0, 1.0]",
    )
    action_mapping: Optional[str] = Field(
        None,
        description="Candidate AMAP action mapping associated with this gesture",
    )
    is_custom: bool = Field(
        default=False,
        description="True if the recognized gesture originated from a worker custom gesture profile",
    )
    custom_gesture_id: Optional[UUID] = None
    message: Optional[str] = None


# =============================================================================
# Custom Gesture Profiles (§ 24, § 25, § 26, § 27)
# =============================================================================

class CustomGestureTrainPayload(StrictInputModel):
    """
    Payload sent to train and certify a worker-specific custom gesture.
    Requires at least 5 complete 21-landmark real physical hand samples.
    """
    gesture_name: str = Field(..., min_length=2, max_length=64, description="Human-readable gesture label")
    intent: str = Field(..., description="Approved AMAP intent (e.g. CONFIRM, NEXT_STEP, PAUSE, HELP)")
    samples: List[List[LandmarkPoint]] = Field(
        ...,
        min_length=5,
        description="At least 5 distinct physical landmark samples (each containing 21 points)",
    )
    handedness: str = Field(default="Right", pattern="^(Right|Left|Both)$")
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CustomGestureProfileRead(AMAPBaseModel):
    """
    Worker-specific custom gesture profile representation stored in database.
    """
    id: UUID
    worker_id: UUID
    organization_id: UUID
    gesture_name: str
    intent: str
    action_mapping: str
    handedness: str
    sample_count: int
    stability_score: float
    feature_template: List[float] = Field(
        ...,
        description="Normalized 60-float geometric reference vector derived from wrist-relative landmarks",
    )
    version: int = 1
    status: str = EntityStatus.ACTIVE.value
    created_at: datetime
    updated_at: datetime


class CustomGestureTestPayload(StrictInputModel):
    """
    Payload to test live landmark frame against worker's custom profiles.
    """
    landmarks: List[LandmarkPoint] = Field(
        ...,
        min_length=21,
        max_length=21,
        description="21 MediaPipe hand landmarks from live camera frame",
    )
    handedness: str = Field(default="Right", pattern="^(Right|Left)$")
