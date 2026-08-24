"""
User, Role, Permission, and Assignment schemas for AMAP.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel, EntityStatus

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


class UserCreate(StrictInputModel):
    organization_id: UUID = Field(..., description="Organization UUID")
    email: str = Field(..., pattern=EMAIL_REGEX, min_length=3, max_length=255, description="User email address")
    full_name: str = Field(..., min_length=1, max_length=255, description="Full name of the user")
    password: str = Field(..., min_length=8, max_length=128, description="Plaintext password")
    status: EntityStatus = Field(default=EntityStatus.ACTIVE, description="User status")


class UserUpdate(StrictInputModel):
    email: Optional[str] = Field(None, pattern=EMAIL_REGEX, min_length=3, max_length=255, description="User email address")
    full_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Full name")
    status: Optional[EntityStatus] = None


class UserPasswordUpdate(StrictInputModel):
    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class UserRead(AMAPBaseModel):
    id: UUID
    organization_id: UUID
    email: str
    full_name: str
    status: str
    created_at: datetime
    updated_at: datetime


class UserInDB(UserRead):
    password_hash: str


class RoleRead(AMAPBaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PermissionRead(AMAPBaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class UserRoleAssignmentCreate(StrictInputModel):
    user_id: UUID
    role_id: UUID


class UserRoleAssignmentRead(AMAPBaseModel):
    id: UUID
    user_id: UUID
    role_id: UUID
    created_at: datetime


class RolePermissionAssignmentCreate(StrictInputModel):
    role_id: UUID
    permission_id: UUID


class RolePermissionAssignmentRead(AMAPBaseModel):
    id: UUID
    role_id: UUID
    permission_id: UUID
    created_at: datetime


class UserDepartmentAssignmentCreate(StrictInputModel):
    user_id: UUID
    department_id: UUID


class UserDepartmentAssignmentRead(AMAPBaseModel):
    id: UUID
    user_id: UUID
    department_id: UUID
    created_at: datetime
