"""
Multimodal fusion and cross-modal processing domain schemas for AMAP.

Defines schemas for multi-input payloads (simultaneous gesture, voice, and UI inputs)
and fused arbitration results.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, InteractionMode, StrictInputModel


class MultimodalInputItem(StrictInputModel):
    """A single modality input item within a multimodal event window."""
    mode: InteractionMode
    raw_intent: str = Field(..., min_length=1, max_length=255)
    confidence: float = Field(..., ge=0.0, le=1.0)
    timestamp_ms: int = Field(..., ge=0)
    context_data: Dict[str, Any] = Field(default_factory=dict)


class MultimodalFusionPayload(StrictInputModel):
    """
    Incoming multimodal bundle containing inputs across modalities within a temporal window.
    """
    inputs: List[MultimodalInputItem] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of multimodal inputs to fuse",
    )
    temporal_window_ms: int = Field(
        default=1500,
        ge=100,
        le=5000,
        description="Maximum temporal divergence window for cross-modal association",
    )
    work_session_id: Optional[UUID] = None
    client_context: Dict[str, Any] = Field(default_factory=dict)


class MultimodalFusionResult(AMAPBaseModel):
    """
    Arbitrated result of multimodal fusion and conflict resolution.
    """
    fused_action: Optional[str] = Field(
        None,
        description="Arbitrated AMAP candidate action name",
    )
    fused_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fused multi-modal confidence score",
    )
    fusion_strategy: str = Field(
        ...,
        description="Strategy applied: single_mode, reinforcing, complementary, conflict_resolved, conflict_ambiguous",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="True if arbitration detected ambiguity or safety-critical action",
    )
    contributing_modes: List[str] = Field(
        default_factory=list,
        description="List of interaction modes that contributed to the fused intent",
    )
    target_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Merged parameters, spatial targets, or item references",
    )
    validation_status: str = Field(
        default="valid",
        description="Validation outcome: valid, ambiguous, or rejected",
    )
    message: Optional[str] = None
