"""
Organization and Department schemas for AMAP.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel, EntityStatus


class OrganizationCreate(StrictInputModel):
    name: str = Field(..., min_length=1, max_length=255, description="Organization name")
    status: EntityStatus = Field(default=EntityStatus.ACTIVE, description="Organization status")


class OrganizationUpdate(StrictInputModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Organization name")
    status: Optional[EntityStatus] = Field(None, description="Organization status")


class OrganizationRead(AMAPBaseModel):
    id: UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class DepartmentCreate(StrictInputModel):
    organization_id: UUID = Field(..., description="Organization UUID")
    name: str = Field(..., min_length=1, max_length=255, description="Department name")
    status: EntityStatus = Field(default=EntityStatus.ACTIVE, description="Department status")


class DepartmentUpdate(StrictInputModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Department name")
    status: Optional[EntityStatus] = Field(None, description="Department status")


class DepartmentRead(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
