"""
Authorization and RBAC domain service for AMAP.

Provides programmatic permission evaluation, role checking,
and organization isolation enforcement.
"""

from typing import List, Optional
from uuid import UUID

from models.auth import AuthenticatedUserContext
from services.base import UnauthorizedError


class AuthorizationService:
    """Business logic for authorization and multi-tenant isolation."""

    @staticmethod
    def has_permission(user: AuthenticatedUserContext, permission: str) -> bool:
        """Check if user has a specific permission or admin override."""
        if any(r in user.roles for r in ("admin", "organization_admin", "superadmin")):
            return True
        return permission in user.permissions

    @staticmethod
    def has_all_permissions(user: AuthenticatedUserContext, required_permissions: List[str]) -> bool:
        """Check if user has all required permissions or admin override."""
        if any(r in user.roles for r in ("admin", "organization_admin", "superadmin")):
            return True
        return all(p in user.permissions for p in required_permissions)

    @staticmethod
    def has_any_role(user: AuthenticatedUserContext, required_roles: List[str]) -> bool:
        """Check if user has at least one of the required roles."""
        if "superadmin" in user.roles:
            return True
        return any(r in user.roles for r in required_roles)

    @staticmethod
    def assert_same_organization(user: AuthenticatedUserContext, target_organization_id: UUID) -> None:
        """Enforce strict organization isolation."""
        if "superadmin" in user.roles:
            return
        if user.organization_id != target_organization_id:
            raise UnauthorizedError(
                f"Cross-organization access denied. Caller org ({user.organization_id}) != target org ({target_organization_id})."
            )

    @staticmethod
    def can_access_worker(user: AuthenticatedUserContext, target_worker_profile_id: UUID) -> bool:
        """Check if user can access worker profile (self or manager/supervisor/admin)."""
        if user.worker_profile_id and user.worker_profile_id == target_worker_profile_id:
            return True
        if any(
            role in user.roles
            for role in ("admin", "organization_admin", "superadmin", "supervisor", "manager")
        ):
            return True
        return False
