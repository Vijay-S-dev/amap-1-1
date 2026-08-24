"""
Job and Responsibility schemas for AMAP.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel, EntityStatus


class JobCreate(StrictInputModel):
    organization_id: UUID = Field(..., description="Organization UUID")
    name: str = Field(..., min_length=1, max_length=255, description="Job title / name")
    description: Optional[str] = Field(None, max_length=2000, description="Job description")
    status: EntityStatus = Field(default=EntityStatus.ACTIVE, description="Job status")


class JobUpdate(StrictInputModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[EntityStatus] = None


class JobRead(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class ResponsibilityCreate(StrictInputModel):
    organization_id: UUID = Field(..., description="Organization UUID")
    name: str = Field(..., min_length=1, max_length=255, description="Responsibility name")
    description: Optional[str] = Field(None, max_length=2000, description="Description")
    status: EntityStatus = Field(default=EntityStatus.ACTIVE, description="Status")


class ResponsibilityUpdate(StrictInputModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[EntityStatus] = None


class ResponsibilityRead(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
