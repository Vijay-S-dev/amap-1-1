"""
FastAPI security, authentication, and authorization dependencies for AMAP.

Provides:
- get_current_user: Resolves AuthenticatedUserContext from Bearer JWT.
- get_current_active_worker: Ensures user is linked to an active worker profile.
- require_permissions: Dependency factory enforcing required RBAC permissions.
- require_roles: Dependency factory enforcing required user roles.
- require_organization_access: Enforces tenant isolation (caller org == resource org).
- require_worker_self_or_admin: Enforces worker self-access or manager/admin override.
"""

from typing import Callable, List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from models.auth import AuthenticatedUserContext
from services.auth_service import AuthService
from services.authorization_service import AuthorizationService
from services.base import UnauthorizedError

bearer_scheme = HTTPBearer(auto_error=True)


def get_auth_service() -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthenticatedUserContext:
    """
    Validate the incoming Bearer JWT access token and return the AuthenticatedUserContext.
    Raises HTTP 401 Unauthorized if invalid or expired.
    """
    token = credentials.credentials
    try:
        user_context = auth_service.verify_token(token)
        return user_context
    except UnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_active_worker(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AuthenticatedUserContext:
    """
    Ensure the authenticated user has an active worker profile associated with their account.
    Raises HTTP 403 Forbidden if the user is not configured as a worker.
    """
    if not current_user.worker_profile_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user does not have an active worker profile.",
        )
    return current_user


def require_permissions(*required_permissions: str) -> Callable[[AuthenticatedUserContext], AuthenticatedUserContext]:
    """
    FastAPI dependency factory enforcing that the caller holds all specified permissions
    (or possesses the admin/superadmin role).
    """
    def _permission_dependency(
        current_user: AuthenticatedUserContext = Depends(get_current_user),
    ) -> AuthenticatedUserContext:
        if not AuthorizationService.has_all_permissions(current_user, list(required_permissions)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Missing required permission(s): {list(required_permissions)}",
            )
        return current_user

    return _permission_dependency


def require_roles(*required_roles: str) -> Callable[[AuthenticatedUserContext], AuthenticatedUserContext]:
    """
    FastAPI dependency factory enforcing that the caller holds at least one of the specified roles
    (or possesses the superadmin role).
    """
    def _role_dependency(
        current_user: AuthenticatedUserContext = Depends(get_current_user),
    ) -> AuthenticatedUserContext:
        if not AuthorizationService.has_any_role(current_user, list(required_roles)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Requires at least one role in {list(required_roles)}",
            )
        return current_user

    return _role_dependency


def validate_organization_access(
    organization_id: UUID,
    current_user: AuthenticatedUserContext,
) -> None:
    """
    Validate that caller belongs to the target organization.
    Raises HTTP 403 Forbidden on tenant boundary violation.
    """
    try:
        AuthorizationService.assert_same_organization(current_user, organization_id)
    except UnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


def validate_worker_access(
    worker_profile_id: UUID,
    current_user: AuthenticatedUserContext,
) -> None:
    """
    Validate that caller can access the target worker profile.
    Raises HTTP 403 Forbidden if not self and not an authorized manager/admin.
    """
    if not AuthorizationService.can_access_worker(current_user, worker_profile_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have permission to access worker profile {worker_profile_id}.",
        )
