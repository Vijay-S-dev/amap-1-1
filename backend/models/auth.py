"""
Authentication schemas for AMAP.

Defines schemas for login requests, token responses, token payloads,
and authenticated user security context.
"""

from typing import List, Optional
from uuid import UUID
from pydantic import Field

from models.base import AMAPBaseModel, StrictInputModel

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


class LoginRequest(StrictInputModel):
    """Worker / Admin login request schema."""
    organization_id: UUID = Field(..., description="Organization UUID")
    email: str = Field(..., pattern=EMAIL_REGEX, min_length=3, max_length=255, description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User plaintext password")


class TokenResponse(AMAPBaseModel):
    """OAuth2 / JWT Token response schema."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(AMAPBaseModel):
    """Decoded JWT payload structure."""
    sub: str = Field(..., description="User UUID")
    organization_id: str = Field(..., description="Organization UUID")
    email: str
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    exp: Optional[int] = None


class AuthenticatedUserContext(AMAPBaseModel):
    """
    Authenticated user context injected into request handlers.
    Used for authorization and multi-tenant scoping.
    """
    user_id: UUID
    organization_id: UUID
    email: str
    full_name: str
    status: str
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    worker_profile_id: Optional[UUID] = None
