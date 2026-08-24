"""
Work session and Execution event schemas for AMAP.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import Field, model_validator

from models.base import AMAPBaseModel, StrictInputModel, WorkSessionStatus


class WorkSessionCreate(StrictInputModel):
    worker_profile_id: UUID
    status: WorkSessionStatus = Field(default=WorkSessionStatus.ACTIVE)
    started_at: Optional[datetime] = None


class WorkSessionUpdate(StrictInputModel):
    status: Optional[WorkSessionStatus] = None
    ended_at: Optional[datetime] = None


class WorkSessionRead(AMAPBaseModel):
    id: UUID
    worker_profile_id: UUID
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_session_dates(self) -> "WorkSessionRead":
        if self.ended_at and self.ended_at < self.started_at:
            raise ValueError("ended_at must be greater than or equal to started_at")
        return self


class ExecutionEventCreate(StrictInputModel):
    organization_id: UUID
    worker_profile_id: Optional[UUID] = None
    workflow_assignment_id: Optional[UUID] = None
    worker_task_assignment_id: Optional[UUID] = None
    event_type: str = Field(..., min_length=1, max_length=100)
    event_data: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: Optional[datetime] = None


class ExecutionEventRead(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    worker_profile_id: Optional[UUID] = None
    workflow_assignment_id: Optional[UUID] = None
    worker_task_assignment_id: Optional[UUID] = None
    event_type: str
    event_data: Dict[str, Any]
    occurred_at: datetime
    created_at: datetime
