"""
Supervisor and Fleet Operations API routes for AMAP.

Provides endpoints for supervisor fleet monitoring, worker telemetry inspection,
task dispatching, live assistance triage, operational performance analytics,
and immutable audit timelines.
All endpoints require supervisor/manager/admin roles and enforce strict organization tenancy.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, require_roles
from models.auth import AuthenticatedUserContext
from models.supervisor import (
    AssistanceResolvePayload,
    AssistanceResponsePayload,
    SupervisorAnalytics,
    SupervisorAuditEvent,
    SupervisorDashboardSummary,
    SupervisorWorkerDetail,
    SupervisorWorkerItem,
    TaskAssignmentPayload,
    TaskReassignmentPayload,
)
from services.base import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from services.supervisor_service import SupervisorService

router = APIRouter(
    prefix="/supervisor",
    tags=["Supervisor & Fleet Operations"],
    dependencies=[Depends(require_roles("supervisor", "manager", "admin", "superadmin"))],
)


def get_supervisor_service() -> SupervisorService:
    """Dependency provider for SupervisorService."""
    return SupervisorService()


@router.get(
    "/dashboard",
    response_model=SupervisorDashboardSummary,
    status_code=status.HTTP_200_OK,
    summary="Get real-time operational dashboard summary for supervisor organization",
)
def get_dashboard(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> SupervisorDashboardSummary:
    """Return live worker counts, active task volume, and capacity workload."""
    return service.get_dashboard_summary(organization_id=current_user.organization_id)


@router.get(
    "/workers",
    response_model=List[SupervisorWorkerItem],
    status_code=status.HTTP_200_OK,
    summary="List all workers in supervisor's organization with live telemetry",
)
def list_workers(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> List[SupervisorWorkerItem]:
    """Return all organization workers with live session, status, and interaction health."""
    return service.list_organization_workers(organization_id=current_user.organization_id)


@router.get(
    "/workers/{worker_id}",
    response_model=SupervisorWorkerDetail,
    status_code=status.HTTP_200_OK,
    summary="Get deep-dive inspection details for a worker",
)
def get_worker_detail(
    worker_id: UUID,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> SupervisorWorkerDetail:
    """Return detailed worker telemetry including active task steps and assistance history."""
    try:
        return service.get_worker_detail(
            organization_id=current_user.organization_id,
            worker_profile_id=worker_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/tasks",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="List active assignable tasks for the organization",
)
def list_tasks(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> List[Dict[str, Any]]:
    """Return tasks eligible for worker assignment."""
    return service.list_assignable_tasks(organization_id=current_user.organization_id)


@router.post(
    "/tasks/assign",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Assign a task to an eligible worker",
)
def assign_task(
    payload: TaskAssignmentPayload,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> Dict[str, Any]:
    """Assign an active assembly task to a worker and commit an audit log entry."""
    try:
        return service.assign_task(
            organization_id=current_user.organization_id,
            supervisor_user_id=current_user.user_id,
            payload=payload,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/tasks/{assignment_id}/reassign",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Reassign a task to another worker",
)
def reassign_task(
    assignment_id: UUID,
    payload: TaskReassignmentPayload,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> Dict[str, Any]:
    """Reassign an in-progress or assigned task to another worker."""
    try:
        return service.reassign_task(
            organization_id=current_user.organization_id,
            supervisor_user_id=current_user.user_id,
            assignment_id=assignment_id,
            payload=payload,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/assistance",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="List assistance requests for supervisor organization",
)
def list_assistance(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> List[Dict[str, Any]]:
    """Return priority-sorted assistance tickets."""
    return service.list_assistance_requests(
        organization_id=current_user.organization_id,
        status=status_filter,
        priority=priority_filter,
    )


@router.post(
    "/assistance/{request_id}/acknowledge",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Supervisor acknowledges assistance request",
)
def acknowledge_assistance(
    request_id: UUID,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> Dict[str, Any]:
    """Mark an open assistance request as acknowledged."""
    try:
        return service.acknowledge_assistance(
            organization_id=current_user.organization_id,
            supervisor_user_id=current_user.user_id,
            request_id=request_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post(
    "/assistance/{request_id}/respond",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Supervisor transmits guidance message to worker",
)
def respond_assistance(
    request_id: UUID,
    payload: AssistanceResponsePayload,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> Dict[str, Any]:
    """Send instructions or guidance to the worker requesting help."""
    try:
        return service.respond_to_assistance(
            organization_id=current_user.organization_id,
            supervisor_user_id=current_user.user_id,
            request_id=request_id,
            payload=payload,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post(
    "/assistance/{request_id}/resolve",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Supervisor resolves and closes assistance request",
)
def resolve_assistance(
    request_id: UUID,
    payload: Optional[AssistanceResolvePayload] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> Dict[str, Any]:
    """Mark an assistance request as resolved."""
    try:
        return service.resolve_assistance(
            organization_id=current_user.organization_id,
            supervisor_user_id=current_user.user_id,
            request_id=request_id,
            payload=payload,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/emergency-events",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="List active emergency stop events",
)
def list_emergency_events(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> List[Dict[str, Any]]:
    """Return active line halts and urgent emergency requests."""
    return service.list_emergency_events(organization_id=current_user.organization_id)


@router.get(
    "/analytics",
    response_model=SupervisorAnalytics,
    status_code=status.HTTP_200_OK,
    summary="Get operational support and performance analytics",
)
def get_analytics(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> SupervisorAnalytics:
    """Return aggregated operational completion and assistance resolution metrics."""
    return service.get_operational_analytics(organization_id=current_user.organization_id)


@router.get(
    "/audit",
    response_model=List[SupervisorAuditEvent],
    status_code=status.HTTP_200_OK,
    summary="Get immutable audit timeline for supervisor organization",
)
def get_audit_timeline(
    limit: int = Query(50, ge=1, le=200),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SupervisorService = Depends(get_supervisor_service),
) -> List[SupervisorAuditEvent]:
    """Return organization operational audit events."""
    return service.list_audit_timeline(
        organization_id=current_user.organization_id,
        limit=limit,
    )
