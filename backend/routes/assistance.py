"""
Assistance and Notification API routes for AMAP.

Provides endpoints for worker assistance requests and user notifications:
- POST /assistance/requests: Create an assistance request.
- POST /assistance/requests/{request_id}/acknowledge: Acknowledge request.
- POST /assistance/requests/{request_id}/resolve: Resolve request.
- POST /assistance/notifications: Send notification.
- POST /assistance/notifications/{notification_id}/read: Mark notification as read.
"""

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field

from app.dependencies import (
    get_current_active_worker,
    get_current_user,
    require_roles,
)
from models.assistance import (
    AssistancePriority,
    AssistanceRequestCreate,
    AssistanceRequestRead,
    NotificationCreate,
    NotificationRead,
)
from models.auth import AuthenticatedUserContext
from models.base import StrictInputModel
from services.assistance_service import AssistanceService
from services.base import NotFoundError, UnauthorizedError

router = APIRouter(prefix="/assistance", tags=["Assistance & Notifications"])


def get_assistance_service() -> AssistanceService:
    """Dependency provider for AssistanceService."""
    return AssistanceService()


class CreateAssistancePayload(StrictInputModel):
    """Payload for worker creating an assistance request."""
    reason: Optional[str] = Field(default=None, max_length=1000)
    priority: AssistancePriority = Field(default=AssistancePriority.NORMAL)
    work_session_id: Optional[UUID] = None
    workflow_assignment_id: Optional[UUID] = None
    worker_task_assignment_id: Optional[UUID] = None
    request_data: Optional[Dict[str, Any]] = None


@router.post(
    "/requests",
    response_model=AssistanceRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a worker assistance request",
)
def create_request(
    payload: CreateAssistancePayload,
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: AssistanceService = Depends(get_assistance_service),
) -> AssistanceRequestRead:
    """Create a new assistance request for the current worker."""
    req_create = AssistanceRequestCreate(
        organization_id=current_worker.organization_id,
        worker_profile_id=current_worker.worker_profile_id,
        work_session_id=payload.work_session_id,
        workflow_assignment_id=payload.workflow_assignment_id,
        worker_task_assignment_id=payload.worker_task_assignment_id,
        priority=payload.priority,
        reason=payload.reason,
        request_data=payload.request_data or {},
    )
    return service.create_assistance_request(req_create)


@router.post(
    "/requests/{request_id}/acknowledge",
    response_model=AssistanceRequestRead,
    status_code=status.HTTP_200_OK,
    summary="Acknowledge an assistance request",
    dependencies=[Depends(require_roles("supervisor", "manager", "admin", "organization_admin"))],
)
def acknowledge_request(
    request_id: UUID,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: AssistanceService = Depends(get_assistance_service),
) -> AssistanceRequestRead:
    """Supervisor acknowledges an open assistance request."""
    try:
        return service.acknowledge_request(
            request_id=request_id,
            organization_id=current_user.organization_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post(
    "/requests/{request_id}/resolve",
    response_model=AssistanceRequestRead,
    status_code=status.HTTP_200_OK,
    summary="Resolve an assistance request",
    dependencies=[Depends(require_roles("supervisor", "manager", "admin", "organization_admin"))],
)
def resolve_request(
    request_id: UUID,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: AssistanceService = Depends(get_assistance_service),
) -> AssistanceRequestRead:
    """Supervisor marks an assistance request as resolved."""
    try:
        return service.resolve_request(
            request_id=request_id,
            organization_id=current_user.organization_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post(
    "/notifications",
    response_model=NotificationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send a user notification",
)
def send_notification(
    payload: NotificationCreate,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: AssistanceService = Depends(get_assistance_service),
) -> NotificationRead:
    """Send a notification to a specific user within the organization."""
    return service.send_notification(payload)


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationRead,
    status_code=status.HTTP_200_OK,
    summary="Mark notification as read",
)
def mark_notification_read(
    notification_id: UUID,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: AssistanceService = Depends(get_assistance_service),
) -> NotificationRead:
    """Mark a received notification as read."""
    try:
        return service.mark_notification_as_read(
            notification_id=notification_id,
            recipient_user_id=current_user.user_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
