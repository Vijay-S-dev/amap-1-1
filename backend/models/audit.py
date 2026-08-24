"""
Audit event schemas for AMAP system and user action tracking.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel


class AuditEventCreate(StrictInputModel):
    organization_id: UUID
    actor_user_id: Optional[UUID] = None
    event_type: str = Field(..., min_length=1, max_length=100)
    resource_type: Optional[str] = Field(None, max_length=100)
    resource_id: Optional[UUID] = None
    event_data: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: Optional[datetime] = None


class AuditEventRead(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    actor_user_id: Optional[UUID] = None
    event_type: str
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    event_data: Dict[str, Any]
    occurred_at: datetime
    created_at: datetime
