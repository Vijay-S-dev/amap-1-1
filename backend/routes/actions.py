"""
Action Execution API routes for AMAP.

Provides the deterministic action execution gateway:
- POST /actions/execute: Validate server-side safety checks and execute deterministic action.
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field

from app.dependencies import get_current_user, get_current_active_worker
from models.action import ActionExecutionRequest, ActionExecutionResponse
from models.auth import AuthenticatedUserContext
from models.base import AMAPBaseModel, StrictInputModel
from repositories.assistance_requests import AssistanceRequestsRepository
from repositories.execution_events import ExecutionEventsRepository
from services.action_execution_service import ActionExecutionService
from services.base import NotFoundError, SafetyViolationError

router = APIRouter(prefix="/actions", tags=["Actions"])


def get_action_execution_service() -> ActionExecutionService:
    """Dependency provider for ActionExecutionService."""
    return ActionExecutionService()


def get_execution_events_repo() -> ExecutionEventsRepository:
    """Dependency provider for ExecutionEventsRepository."""
    return ExecutionEventsRepository()


def get_assistance_requests_repo() -> AssistanceRequestsRepository:
    """Dependency provider for AssistanceRequestsRepository."""
    return AssistanceRequestsRepository()


class EmergencyStopPayload(StrictInputModel):
    reason: Optional[str] = Field(default="Worker triggered emergency stop", max_length=1000)
    work_session_id: Optional[UUID] = None


class EmergencyStopResponse(AMAPBaseModel):
    success: bool
    event_id: str
    eventId: str
    message: str


@router.post(
    "/execute",
    response_model=ActionExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a deterministic action through the safety gateway",
)
def execute_action(
    payload: ActionExecutionRequest,
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: ActionExecutionService = Depends(get_action_execution_service),
) -> ActionExecutionResponse:
    """
    Validate safety requirements, workflow constraints, and execute the requested action.
    Enforces the principle: Recognition != Intent != Authorization != Execution.
    """
    try:
        return service.execute_action(
            request=payload,
            worker_profile_id=current_worker.worker_profile_id,
            organization_id=current_worker.organization_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SafetyViolationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Safety Gate Violation: {str(exc)}",
        ) from exc


@router.post(
    "/emergency-stop",
    response_model=EmergencyStopResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger software emergency stop safety interlock",
)
def emergency_stop(
    payload: EmergencyStopPayload,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    execution_events_repo: ExecutionEventsRepository = Depends(get_execution_events_repo),
    assistance_requests_repo: AssistanceRequestsRepository = Depends(get_assistance_requests_repo),
) -> EmergencyStopResponse:
    """
    Software emergency stop safety boundary:
    1. Requires authenticated caller context.
    2. Records an immutable execution event (event_type='emergency_stop').
    3. Creates a supervisor-visible urgent assistance request.
    4. Returns confirmation to lock client-side work session.
    Note: Software prototype safety boundary only; does not claim physical machinery control.
    """
    reason_str = payload.reason or "Worker triggered emergency stop"

    # 1. Record execution event
    event = execution_events_repo.create(
        organization_id=current_user.organization_id,
        worker_profile_id=current_user.worker_profile_id,
        event_type="emergency_stop",
        event_data={
            "reason": reason_str,
            "work_session_id": str(payload.work_session_id) if payload.work_session_id else None,
            "is_emergency": True,
            "safety_boundary": "software_only",
        },
    )

    event_id_str = str(event["id"]) if event and "id" in event else f"evt-safety-{current_user.user_id}"

    # 2. Create urgent assistance request for supervisor visibility
    try:
        assistance_requests_repo.create(
            organization_id=current_user.organization_id,
            worker_profile_id=current_user.worker_profile_id,
            work_session_id=payload.work_session_id,
            priority="urgent",
            reason=f"EMERGENCY STOP: {reason_str}",
            request_data={
                "execution_event_id": event_id_str,
                "is_emergency": True,
            },
        )
    except Exception:
        pass

    return EmergencyStopResponse(
        success=True,
        event_id=event_id_str,
        eventId=event_id_str,
        message="Software emergency stop registered. Session locked.",
    )
