"""
Permission matrix API routes for AMAP.

Provides organization-scoped RBAC governance endpoints:
- GET  /permissions/matrix: full permission catalog + role grants for caller's org.
- PUT  /permissions/matrix: grant/revoke one permission for one role (audited).
"""

from fastapi import APIRouter, Depends, status

from app.dependencies import require_permissions, require_roles
from models.auth import AuthenticatedUserContext
from models.permissions import PermissionMatrixResponse, PermissionMatrixUpdate
from services.base import ConflictError, NotFoundError
from services.permission_service import PermissionService

router = APIRouter(prefix="/permissions", tags=["Permissions"])


def get_permission_service() -> PermissionService:
    """Dependency provider for PermissionService."""
    return PermissionService()


@router.get(
    "/matrix",
    response_model=PermissionMatrixResponse,
    status_code=status.HTTP_200_OK,
    summary="Get organization permission matrix",
)
def get_permission_matrix(
    admin_user: AuthenticatedUserContext = Depends(
        require_roles("admin", "organization_admin")
    ),
    _perm: AuthenticatedUserContext = Depends(require_permissions("admin:config")),
    service: PermissionService = Depends(get_permission_service),
) -> PermissionMatrixResponse:
    """Return the permission catalog with this organization's role grants."""
    return service.get_matrix(organization_id=admin_user.organization_id)


@router.put(
    "/matrix",
    response_model=PermissionMatrixResponse,
    status_code=status.HTTP_200_OK,
    summary="Grant or revoke one role permission",
)
def update_permission_matrix(
    payload: PermissionMatrixUpdate,
    admin_user: AuthenticatedUserContext = Depends(
        require_roles("admin", "organization_admin")
    ),
    _perm: AuthenticatedUserContext = Depends(require_permissions("admin:config")),
    service: PermissionService = Depends(get_permission_service),
) -> PermissionMatrixResponse:
    """Apply a single matrix toggle, validated and audit-logged."""
    try:
        return service.set_grant(
            organization_id=admin_user.organization_id,
            role_name=payload.role_name,
            permission_name=payload.permission_name,
            granted=payload.granted,
            actor_id=admin_user.user_id,
        )
    except NotFoundError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConflictError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
