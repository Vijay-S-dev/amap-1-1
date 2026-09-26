"""Permission and RBAC matrix models for AMAP."""

from typing import Dict, List, Optional
from uuid import UUID

from models.base import AMAPBaseModel, StrictInputModel
from pydantic import Field


class PermissionRead(AMAPBaseModel):
    """A catalog permission row."""

    id: UUID
    name: str
    description: Optional[str] = None


class PermissionMatrixEntry(AMAPBaseModel):
    """One permission row with per-role grant flags for an organization."""

    permission: PermissionRead
    roles: Dict[str, bool]


class PermissionMatrixResponse(AMAPBaseModel):
    """Full organization-scoped permission matrix."""

    organization_id: UUID
    roles: List[str]
    permissions: List[PermissionMatrixEntry]


class PermissionMatrixUpdate(StrictInputModel):
    """Toggle one role/permission grant in the organization matrix."""

    role_name: str = Field(..., min_length=1, max_length=80)
    permission_name: str = Field(..., min_length=1, max_length=120)
    granted: bool
