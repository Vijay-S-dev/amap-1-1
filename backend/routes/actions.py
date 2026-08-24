"""
Action Execution API routes for AMAP.

Provides the deterministic action execution gateway:
- POST /actions/execute: Validate server-side safety checks and execute deterministic action.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_active_worker
from models.action import ActionExecutionRequest, ActionExecutionResponse
from models.auth import AuthenticatedUserContext
from services.action_execution_service import ActionExecutionService
from services.base import NotFoundError, SafetyViolationError

router = APIRouter(prefix="/actions", tags=["Actions"])


def get_action_execution_service() -> ActionExecutionService:
    """Dependency provider for ActionExecutionService."""
    return ActionExecutionService()


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
