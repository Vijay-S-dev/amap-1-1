"""
Admin and System Configuration API routes for AMAP.

Provides administrative management for:
- Tenant-scoped interaction configurations CRUD.
- Organization settings and status updates.
- User management, account status toggling, and role assignment.
- Tenant audit log querying and inspection.

All endpoints are strictly guarded by RBAC role requirements (`admin` or `super_admin`)
and enforce organization boundary isolation.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import require_roles
from models.admin import (
    UserRoleAssignPayload,
    UserStatusUpdatePayload,
)
from models.audit import AuditEventRead
from models.auth import AuthenticatedUserContext
from models.interaction import (
    InteractionConfigurationCreate,
    InteractionConfigurationRead,
    InteractionConfigurationUpdate,
)
from models.organization import OrganizationRead, OrganizationUpdate
from models.user import UserRead
from services.admin_service import AdminService
from services.base import NotFoundError, ValidationError

router = APIRouter(prefix="/admin", tags=["Admin & System Configuration"])


def get_admin_service() -> AdminService:
    """Dependency provider for AdminService."""
    return AdminService()


# =====================================================================
# 1. Interaction Configurations CRUD
# =====================================================================

@router.get(
    "/configs",
    response_model=List[InteractionConfigurationRead],
    status_code=status.HTTP_200_OK,
    summary="List organization interaction configurations",
)
def list_interaction_configs(
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "super_admin")),
    service: AdminService = Depends(get_admin_service),
) -> List[InteractionConfigurationRead]:
    """Retrieve all interaction presets defined for the administrator's organization."""
    return service.list_configs(organization_id=admin_user.organization_id)


@router.post(
    "/configs",
    response_model=InteractionConfigurationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create interaction configuration",
)
def create_interaction_config(
    payload: InteractionConfigurationCreate,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "super_admin")),
    service: AdminService = Depends(get_admin_service),
) -> InteractionConfigurationRead:
    """Create a new interaction preset within the organization and emit an audit trail event."""
    return service.create_config(
        organization_id=admin_user.organization_id,
        payload=payload,
        actor_id=admin_user.user_id,
    )


@router.get(
    "/configs/{config_id}",
    response_model=InteractionConfigurationRead,
    status_code=status.HTTP_200_OK,
    summary="Get interaction configuration details",
)
def get_interaction_config(
    config_id: UUID,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "super_admin")),
    service: AdminService = Depends(get_admin_service),
) -> InteractionConfigurationRead:
    """Retrieve details for a specific interaction configuration."""
    try:
        return service.get_config(config_id=config_id, organization_id=admin_user.organization_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/configs/{config_id}",
    response_model=InteractionConfigurationRead,
    status_code=status.HTTP_200_OK,
    summary="Update interaction configuration",
)
def update_interaction_config(
    config_id: UUID,
    payload: InteractionConfigurationUpdate,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "super_admin")),
    service: AdminService = Depends(get_admin_service),
) -> InteractionConfigurationRead:
    """Update an existing interaction configuration and record the modification in the audit log."""
    try:
        return service.update_config(
            config_id=config_id,
            organization_id=admin_user.organization_id,
            payload=payload,
            actor_id=admin_user.user_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/configs/{config_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete interaction configuration",
)
def delete_interaction_config(
    config_id: UUID,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "super_admin")),
    service: AdminService = Depends(get_admin_service),
) -> Dict[str, Any]:
    """Delete an interaction configuration and record the deletion in the audit log."""
    try:
        deleted = service.delete_config(
            config_id=config_id,
            organization_id=admin_user.organization_id,
            actor_id=admin_user.user_id,
        )
        return {"success": deleted, "message": "Interaction configuration deleted successfully."}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# =====================================================================
# 2. Organization Management
# =====================================================================

@router.get(
    "/organization",
    response_model=OrganizationRead,
    status_code=status.HTTP_200_OK,
    summary="Get current organization settings",
)
def get_current_organization(
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "super_admin")),
    service: AdminService = Depends(get_admin_service),
) -> OrganizationRead:
    """Retrieve details and status of the administrator's organization."""
    try:
        return service.get_organization(organization_id=admin_user.organization_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/organization",
    response_model=OrganizationRead,
    status_code=status.HTTP_200_OK,
    summary="Update current organization settings",
)
def update_current_organization(
    payload: OrganizationUpdate,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "super_admin")),
    service: AdminService = Depends(get_admin_service),
) -> OrganizationRead:
    """Update organization settings and record audit log."""
    try:
        return service.update_organization(
            organization_id=admin_user.organization_id,
            payload=payload,
            actor_id=admin_user.user_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# =====================================================================
# 3. User & Role Management
# =====================================================================

@router.get(
    "/users",
    response_model=List[UserRead],
    status_code=status.HTTP_200_OK,
    summary="List organization users",
)
def list_organization_users(
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "super_admin")),
    service: AdminService = Depends(get_admin_service),
) -> List[UserRead]:
    """Retrieve all users associated with the administrator's organization."""
    return service.list_organization_users(organization_id=admin_user.organization_id)


@router.patch(
    "/users/{user_id}/status",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Update user account status",
)
def update_user_status(
    user_id: UUID,
    payload: UserStatusUpdatePayload,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "super_admin")),
    service: AdminService = Depends(get_admin_service),
) -> UserRead:
    """Update a user's status (active, suspended, archived) and record an audit log."""
    try:
        return service.update_user_status(
            user_id=user_id,
            organization_id=admin_user.organization_id,
            new_status=payload.status,
            actor_id=admin_user.user_id,
            reason=payload.reason,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/users/{user_id}/roles",
    status_code=status.HTTP_200_OK,
    summary="Assign role to user",
)
def assign_role_to_user(
    user_id: UUID,
    payload: UserRoleAssignPayload,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "super_admin")),
    service: AdminService = Depends(get_admin_service),
) -> Dict[str, Any]:
    """Assign a role to an organization user and record the assignment in the audit log."""
    try:
        assignment = service.assign_role(
            user_id=user_id,
            role_name=payload.role_name,
            organization_id=admin_user.organization_id,
            actor_id=admin_user.user_id,
        )
        return {"success": True, "assignment": assignment, "message": f"Role '{payload.role_name}' assigned."}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/users/{user_id}/roles/{role_name}",
    status_code=status.HTTP_200_OK,
    summary="Revoke role from user",
)
def revoke_role_from_user(
    user_id: UUID,
    role_name: str,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "super_admin")),
    service: AdminService = Depends(get_admin_service),
) -> Dict[str, Any]:
    """Revoke a role from an organization user and record the revocation in the audit log."""
    try:
        deleted = service.revoke_role(
            user_id=user_id,
            role_name=role_name,
            organization_id=admin_user.organization_id,
            actor_id=admin_user.user_id,
        )
        return {"success": deleted, "message": f"Role '{role_name}' revoked successfully."}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# =====================================================================
# 4. Audit Log Querying
# =====================================================================

@router.get(
    "/audit-logs",
    response_model=List[AuditEventRead],
    status_code=status.HTTP_200_OK,
    summary="Query organization audit logs",
)
def query_organization_audit_logs(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    actor_user_id: Optional[UUID] = Query(None, description="Filter by actor user ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "super_admin")),
    service: AdminService = Depends(get_admin_service),
) -> List[AuditEventRead]:
    """Query immutable audit events recorded for the administrator's organization."""
    return service.query_audit_logs(
        organization_id=admin_user.organization_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        resource_type=resource_type,
        limit=limit,
    )
