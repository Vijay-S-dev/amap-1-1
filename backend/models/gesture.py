"""
Gesture pipeline domain schemas for AMAP.

Defines schemas for hand landmarks, video frame payloads, and recognition results.
"""

from typing import Any, Dict, List, Optional
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel


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
    Result of landmark heuristic classification and temporal dwell-time filtering.
    """
    detected_gesture: Optional[str] = Field(
        None,
        description="Classified gesture name (e.g. thumbs_up, open_palm, fist, pointing, pinch)",
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
    message: Optional[str] = None
