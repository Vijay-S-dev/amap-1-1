"""
Enterprise Organization Management API Routes for AMAP (§ 1-38).

Provides authenticated REST endpoints for enterprise administration:
- Dashboard KPIs & real operational metrics
- Organization profile & accessibility defaults
- Department CRUD & supervisor assignments
- Supervisor & Worker invitations & rosters
- Approved workflow templates & step checklists
- Assistance overview, emergency alerts, analytics & audit streams

Guarded strictly by RBAC `admin` / `super_admin` role checks and server-side tenant isolation.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import require_roles
from models.auth import AuthenticatedUserContext
from models.enterprise_organization import (
    DepartmentCreatePayload,
    DepartmentItem,
    DepartmentUpdatePayload,
    EnterpriseWorkerItem,
    OrganizationAnalyticsSummary,
    OrganizationAuditEventItem,
    OrganizationDashboardKPIs,
    OrganizationProfileRead,
    OrganizationProfileUpdate,
    SupervisorInvitePayload,
    SupervisorItem,
    SupervisorUpdatePayload,
    WorkerInvitePayload,
    WorkflowCreatePayload,
    WorkflowTemplate,
    WorkflowUpdatePayload,
)
from services.base import NotFoundError, ValidationError
from services.organization_management_service import OrganizationManagementService

router = APIRouter(prefix="/organizations/manage", tags=["Enterprise Organization Management"])


def get_org_management_service() -> OrganizationManagementService:
    """Dependency provider for OrganizationManagementService."""
    return OrganizationManagementService()


# =====================================================================
# 1. Organization Dashboard KPIs (§ 5, § 34)
# =====================================================================

@router.get(
    "/dashboard",
    response_model=OrganizationDashboardKPIs,
    status_code=status.HTTP_200_OK,
    summary="Get organization dashboard KPIs",
)
def get_organization_dashboard(
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> OrganizationDashboardKPIs:
    """Retrieve summarized real database metrics for the organization operational dashboard."""
    return service.get_organization_dashboard(organization_id=admin_user.organization_id)


# =====================================================================
# 2. Organization Profile & Settings (§ 6, § 28)
# =====================================================================

@router.get(
    "/profile",
    response_model=OrganizationProfileRead,
    status_code=status.HTTP_200_OK,
    summary="Get organization profile and accessibility defaults",
)
def get_organization_profile(
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> OrganizationProfileRead:
    """Retrieve tenant profile and configured accessibility defaults."""
    try:
        return service.get_organization_profile(organization_id=admin_user.organization_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/profile",
    response_model=OrganizationProfileRead,
    status_code=status.HTTP_200_OK,
    summary="Update organization profile and settings",
)
def update_organization_profile(
    payload: OrganizationProfileUpdate,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> OrganizationProfileRead:
    """Update organization settings and append immutable audit log."""
    try:
        return service.update_organization_profile(
            organization_id=admin_user.organization_id,
            payload=payload,
            actor_id=admin_user.user_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# =====================================================================
# 3. Department Management (§ 7, § 8)
# =====================================================================

@router.get(
    "/departments",
    response_model=List[DepartmentItem],
    status_code=status.HTTP_200_OK,
    summary="List organization departments",
)
def list_departments(
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> List[DepartmentItem]:
    """List all departments belonging to the administrator's organization."""
    return service.list_departments(organization_id=admin_user.organization_id)


@router.post(
    "/departments",
    response_model=DepartmentItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create department",
)
def create_department(
    payload: DepartmentCreatePayload,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> DepartmentItem:
    """Create a new department within the tenant boundary."""
    try:
        return service.create_department(
            organization_id=admin_user.organization_id,
            payload=payload,
            actor_id=admin_user.user_id,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put(
    "/departments/{department_id}",
    response_model=DepartmentItem,
    status_code=status.HTTP_200_OK,
    summary="Update department",
)
def update_department(
    department_id: UUID,
    payload: DepartmentUpdatePayload,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> DepartmentItem:
    """Update department properties enforcing organization ownership."""
    try:
        return service.update_department(
            organization_id=admin_user.organization_id,
            department_id=department_id,
            payload=payload,
            actor_id=admin_user.user_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/departments/{department_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Deactivate department",
)
def deactivate_department(
    department_id: UUID,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> Dict[str, Any]:
    """Deactivate department with organization isolation."""
    try:
        return service.deactivate_department(
            organization_id=admin_user.organization_id,
            department_id=department_id,
            actor_id=admin_user.user_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# =====================================================================
# 4. Supervisor Management (§ 9, § 13)
# =====================================================================

@router.get(
    "/supervisors",
    response_model=List[SupervisorItem],
    status_code=status.HTTP_200_OK,
    summary="List organization supervisors",
)
def list_supervisors(
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> List[SupervisorItem]:
    """List all floor supervisors in the organization."""
    return service.list_supervisors(organization_id=admin_user.organization_id)


@router.post(
    "/supervisors/invite",
    response_model=SupervisorItem,
    status_code=status.HTTP_201_CREATED,
    summary="Invite supervisor",
)
def invite_supervisor(
    payload: SupervisorInvitePayload,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> SupervisorItem:
    """Invite a new supervisor to the organization."""
    return service.invite_supervisor(
        organization_id=admin_user.organization_id,
        payload=payload,
        actor_id=admin_user.user_id,
    )


@router.put(
    "/supervisors/{user_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Update supervisor",
)
def update_supervisor(
    user_id: UUID,
    payload: SupervisorUpdatePayload,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> Dict[str, Any]:
    """Update supervisor department assignment or status."""
    return service.update_supervisor(
        organization_id=admin_user.organization_id,
        user_id=user_id,
        payload=payload,
        actor_id=admin_user.user_id,
    )


# =====================================================================
# 5. Worker Management (§ 10, § 11, § 13)
# =====================================================================

@router.get(
    "/workers",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List organization workers",
)
def list_workers(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    dept_filter: Optional[UUID] = Query(None, alias="department_id"),
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> Dict[str, Any]:
    """List workers with real operational state and pagination."""
    return service.list_workers(
        organization_id=admin_user.organization_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        dept_filter=dept_filter,
    )


@router.post(
    "/workers/invite",
    response_model=EnterpriseWorkerItem,
    status_code=status.HTTP_201_CREATED,
    summary="Invite worker",
)
def invite_worker(
    payload: WorkerInvitePayload,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> EnterpriseWorkerItem:
    """Generate accessible worker invitation for AMAP onboarding."""
    return service.invite_worker(
        organization_id=admin_user.organization_id,
        payload=payload,
        actor_id=admin_user.user_id,
    )


# =====================================================================
# 6. Enterprise Workflows & Task Templates (§ 14, § 16)
# =====================================================================

@router.get(
    "/workflows",
    response_model=List[WorkflowTemplate],
    status_code=status.HTTP_200_OK,
    summary="List organization workflows",
)
def list_workflows(
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> List[WorkflowTemplate]:
    """List approved assembly workflow templates."""
    return service.list_workflows(organization_id=admin_user.organization_id)


@router.post(
    "/workflows",
    response_model=WorkflowTemplate,
    status_code=status.HTTP_201_CREATED,
    summary="Create workflow template",
)
def create_workflow(
    payload: WorkflowCreatePayload,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> WorkflowTemplate:
    """Create approved workflow template with step sequences."""
    return service.create_workflow(
        organization_id=admin_user.organization_id,
        payload=payload,
        actor_id=admin_user.user_id,
    )


@router.put(
    "/workflows/{workflow_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Update workflow template",
)
def update_workflow(
    workflow_id: UUID,
    payload: WorkflowUpdatePayload,
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> Dict[str, Any]:
    """Update workflow template definition."""
    return service.update_workflow(
        organization_id=admin_user.organization_id,
        workflow_id=workflow_id,
        payload=payload,
        actor_id=admin_user.user_id,
    )


# =====================================================================
# 7. Assistance Overview, Emergency Events, Analytics & Audit Stream (§ 19, § 20, § 21, § 23)
# =====================================================================

@router.get(
    "/assistance",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get organization assistance overview",
)
def get_assistance_overview(
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> List[Dict[str, Any]]:
    """Retrieve organization-wide assistance requests."""
    return service.get_assistance_overview(organization_id=admin_user.organization_id)


@router.get(
    "/emergencies",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get organization emergency events",
)
def get_emergency_events(
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> List[Dict[str, Any]]:
    """Retrieve active emergency stop safety halts."""
    return service.get_emergency_events(organization_id=admin_user.organization_id)


@router.get(
    "/analytics",
    response_model=OrganizationAnalyticsSummary,
    status_code=status.HTTP_200_OK,
    summary="Get organization operational & accessibility analytics",
)
def get_organization_analytics(
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> OrganizationAnalyticsSummary:
    """Retrieve aggregate non-medical operational and accessibility readiness analytics."""
    return service.get_organization_analytics(organization_id=admin_user.organization_id)


@router.get(
    "/audit",
    response_model=List[OrganizationAuditEventItem],
    status_code=status.HTTP_200_OK,
    summary="Query organization audit trail",
)
def query_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    admin_user: AuthenticatedUserContext = Depends(require_roles("admin", "organization_admin", "super_admin")),
    service: OrganizationManagementService = Depends(get_org_management_service),
) -> List[OrganizationAuditEventItem]:
    """Query immutable audit events for the organization."""
    return service.query_audit_logs(organization_id=admin_user.organization_id, limit=limit)
