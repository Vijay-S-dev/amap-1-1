"""
Assistance Request and Notification schemas for AMAP.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import Field, model_validator

from models.base import AMAPBaseModel, StrictInputModel, AssistancePriority, AssistanceStatus


class NotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class AssistanceRequestCreate(StrictInputModel):
    organization_id: UUID
    worker_profile_id: UUID
    work_session_id: Optional[UUID] = None
    workflow_assignment_id: Optional[UUID] = None
    worker_task_assignment_id: Optional[UUID] = None
    status: AssistanceStatus = Field(default=AssistanceStatus.OPEN)
    priority: AssistancePriority = Field(default=AssistancePriority.NORMAL)
    reason: Optional[str] = Field(None, max_length=1000)
    request_data: Dict[str, Any] = Field(default_factory=dict)


class AssistanceRequestUpdate(StrictInputModel):
    status: Optional[AssistanceStatus] = None
    priority: Optional[AssistancePriority] = None
    reason: Optional[str] = Field(None, max_length=1000)
    request_data: Optional[Dict[str, Any]] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class AssistanceRequestRead(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    worker_profile_id: UUID
    work_session_id: Optional[UUID] = None
    workflow_assignment_id: Optional[UUID] = None
    worker_task_assignment_id: Optional[UUID] = None
    status: str
    priority: str
    reason: Optional[str] = None
    request_data: Dict[str, Any]
    requested_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_assistance_dates(self) -> "AssistanceRequestRead":
        if self.acknowledged_at and self.acknowledged_at < self.requested_at:
            raise ValueError("acknowledged_at must be greater than or equal to requested_at")
        if self.resolved_at and self.resolved_at < self.requested_at:
            raise ValueError("resolved_at must be greater than or equal to requested_at")
        return self


class NotificationCreate(StrictInputModel):
    organization_id: UUID
    recipient_user_id: UUID
    notification_type: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=2000)
    notification_data: Dict[str, Any] = Field(default_factory=dict)
    status: NotificationStatus = Field(default=NotificationStatus.UNREAD)


class NotificationUpdate(StrictInputModel):
    status: Optional[NotificationStatus] = None
    read_at: Optional[datetime] = None


class NotificationRead(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    recipient_user_id: UUID
    notification_type: str
    title: str
    message: str
    notification_data: Dict[str, Any]
    status: str
    created_at: datetime
    read_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_notification_dates(self) -> "NotificationRead":
        if self.read_at and self.read_at < self.created_at:
            raise ValueError("read_at must be greater than or equal to created_at")
        return self
