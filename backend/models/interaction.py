"""
Interaction configurations and event schemas for AMAP multimodal pipeline.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel, EntityStatus, InteractionMode


class InteractionConfigurationCreate(StrictInputModel):
    organization_id: UUID = Field(..., description="Organization UUID")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    config_data: Dict[str, Any] = Field(default_factory=dict)
    status: EntityStatus = Field(default=EntityStatus.ACTIVE)


class InteractionConfigurationUpdate(StrictInputModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    config_data: Optional[Dict[str, Any]] = None
    status: Optional[EntityStatus] = None


class InteractionConfigurationRead(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: Optional[str] = None
    config_data: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class GestureConfigurationCreate(StrictInputModel):
    interaction_configuration_id: UUID
    gesture_name: str = Field(..., min_length=1, max_length=100)
    gesture_data: Dict[str, Any] = Field(default_factory=dict)
    status: EntityStatus = Field(default=EntityStatus.ACTIVE)


class GestureConfigurationUpdate(StrictInputModel):
    gesture_name: Optional[str] = Field(None, min_length=1, max_length=100)
    gesture_data: Optional[Dict[str, Any]] = None
    status: Optional[EntityStatus] = None


class GestureConfigurationRead(AMAPBaseModel):
    id: UUID
    interaction_configuration_id: UUID
    gesture_name: str
    gesture_data: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class VoiceConfigurationCreate(StrictInputModel):
    interaction_configuration_id: UUID
    command_phrase: str = Field(..., min_length=1, max_length=255)
    voice_data: Dict[str, Any] = Field(default_factory=dict)
    status: EntityStatus = Field(default=EntityStatus.ACTIVE)


class VoiceConfigurationUpdate(StrictInputModel):
    command_phrase: Optional[str] = Field(None, min_length=1, max_length=255)
    voice_data: Optional[Dict[str, Any]] = None
    status: Optional[EntityStatus] = None


class VoiceConfigurationRead(AMAPBaseModel):
    id: UUID
    interaction_configuration_id: UUID
    command_phrase: str
    voice_data: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class InteractionEventCreate(StrictInputModel):
    organization_id: UUID
    worker_profile_id: UUID
    work_session_id: Optional[UUID] = None
    action_id: Optional[UUID] = None
    interaction_mode: InteractionMode
    event_type: str = Field(..., min_length=1, max_length=100)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    interaction_data: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: Optional[datetime] = None


class InteractionEventRead(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    worker_profile_id: UUID
    work_session_id: Optional[UUID] = None
    action_id: Optional[UUID] = None
    interaction_mode: str
    event_type: str
    confidence: Optional[float] = None
    interaction_data: Dict[str, Any]
    occurred_at: datetime
    created_at: datetime


class MultimodalIntentPayload(StrictInputModel):
    """
    Incoming raw recognized multimodal event payload from worker client.
    Processed by intent recognition and server-side safety checks before execution.
    """
    mode: InteractionMode
    raw_intent: str = Field(..., min_length=1, max_length=255)
    confidence: float = Field(..., ge=0.0, le=1.0)
    context_data: Dict[str, Any] = Field(default_factory=dict)


class MultimodalProcessingResult(AMAPBaseModel):
    """
    Result of multimodal intent mapping and safety validation.
    """
    recognized: bool
    action_name: Optional[str] = None
    confidence: float
    requires_confirmation: bool = False
    validation_status: str = "valid"
    message: Optional[str] = None
