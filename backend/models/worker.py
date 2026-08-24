"""
Worker profile, capability, assignment, and personalization schemas for AMAP.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel, EntityStatus, TaskStatus


class WorkerProfileCreate(StrictInputModel):
    user_id: UUID = Field(..., description="User UUID")


class WorkerProfileRead(AMAPBaseModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class WorkerJobAssignmentCreate(StrictInputModel):
    worker_profile_id: UUID
    job_id: UUID
    status: EntityStatus = Field(default=EntityStatus.ACTIVE)


class WorkerJobAssignmentRead(AMAPBaseModel):
    id: UUID
    worker_profile_id: UUID
    job_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime


class WorkerTaskAssignmentCreate(StrictInputModel):
    worker_profile_id: UUID
    task_id: UUID
    workflow_assignment_id: Optional[UUID] = None
    status: TaskStatus = Field(default=TaskStatus.ACTIVE)


class WorkerTaskAssignmentUpdate(StrictInputModel):
    status: Optional[TaskStatus] = None


class WorkerTaskAssignmentRead(AMAPBaseModel):
    id: UUID
    worker_profile_id: UUID
    task_id: UUID
    workflow_assignment_id: Optional[UUID] = None
    status: str
    created_at: datetime
    updated_at: datetime


class WorkerCapabilityProfileCreate(StrictInputModel):
    worker_profile_id: UUID
    capability_data: Dict[str, Any] = Field(default_factory=dict)
    status: EntityStatus = Field(default=EntityStatus.ACTIVE)


class WorkerCapabilityProfileUpdate(StrictInputModel):
    capability_data: Optional[Dict[str, Any]] = None
    status: Optional[EntityStatus] = None


class WorkerCapabilityProfileRead(AMAPBaseModel):
    id: UUID
    worker_profile_id: UUID
    capability_data: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class WorkerPersonalizationCreate(StrictInputModel):
    worker_profile_id: UUID
    interaction_configuration_id: Optional[UUID] = None
    personalization_data: Dict[str, Any] = Field(default_factory=dict)
    status: EntityStatus = Field(default=EntityStatus.ACTIVE)


class WorkerPersonalizationUpdate(StrictInputModel):
    interaction_configuration_id: Optional[UUID] = None
    personalization_data: Optional[Dict[str, Any]] = None
    status: Optional[EntityStatus] = None


class WorkerPersonalizationRead(AMAPBaseModel):
    id: UUID
    worker_profile_id: UUID
    interaction_configuration_id: Optional[UUID] = None
    personalization_data: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class PersonalizationHistoryCreate(StrictInputModel):
    worker_personalization_id: UUID
    change_reason: Optional[str] = Field(None, max_length=500)
    previous_state: Dict[str, Any] = Field(default_factory=dict)
    new_state: Dict[str, Any] = Field(default_factory=dict)


class PersonalizationHistoryRead(AMAPBaseModel):
    id: UUID
    worker_personalization_id: UUID
    change_reason: Optional[str] = None
    previous_state: Dict[str, Any]
    new_state: Dict[str, Any]
    created_at: datetime


class AdaptationRecommendation(AMAPBaseModel):
    """Specific adaptation recommendation derived from evidence."""
    recommendation_type: str = Field(..., description="e.g. dwell_time_adjustment, modality_switch, voice_threshold")
    current_value: Any = None
    suggested_value: Any = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    auto_applicable: bool = False


class AdaptationEvaluationResult(AMAPBaseModel):
    """Outcome of multi-event evidence evaluation and adaptation."""
    worker_profile_id: UUID
    status: str
    evidence_count: int
    recommendations: List[AdaptationRecommendation] = Field(default_factory=list)
    auto_applied_changes: List[str] = Field(default_factory=list)
    message: Optional[str] = None


class ApplyAdaptationRequest(StrictInputModel):
    """Explicit request to apply a recommended or custom adaptation."""
    adaptation_type: str = Field(..., min_length=1, max_length=100)
    new_settings: Dict[str, Any] = Field(..., description="Updated personalization key-values")
    reason: str = Field(default="Evidence-based worker adaptation", min_length=1, max_length=500)

