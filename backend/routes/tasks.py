"""
Task and Workflow API routes for AMAP.

Provides endpoints for worker task execution, assignment progression,
and workflow step tracking.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.dependencies import get_current_active_worker, get_current_user
from models.auth import AuthenticatedUserContext
from models.base import StrictInputModel
from models.worker import WorkerTaskAssignmentRead
from services.base import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks & Workflows"])


def get_task_service() -> TaskService:
    """Dependency provider for TaskService."""
    return TaskService()


class TaskCompletionPayload(StrictInputModel):
    """Payload for completing a task assignment."""
    outcome: str = Field(default="completed", pattern="^(completed|failed|partial|cancelled)$")
    result_data: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class StepExecutionPayload(StrictInputModel):
    """Payload for recording a workflow step execution."""
    status: str = Field(default="in_progress", pattern="^(in_progress|completed|failed|skipped)$")
    execution_data: Optional[Dict[str, Any]] = None


@router.get(
    "/assigned",
    response_model=List[WorkerTaskAssignmentRead],
    status_code=status.HTTP_200_OK,
    summary="Get assigned tasks for the authenticated worker",
)
def get_assigned_tasks(
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: TaskService = Depends(get_task_service),
) -> List[WorkerTaskAssignmentRead]:
    """Return all task assignments for the authenticated worker profile."""
    return service.get_worker_assignments(worker_profile_id=current_worker.worker_profile_id)


@router.post(
    "/assignments/{assignment_id}/start",
    response_model=WorkerTaskAssignmentRead,
    status_code=status.HTTP_200_OK,
    summary="Start a task assignment",
)
def start_task(
    assignment_id: UUID,
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: TaskService = Depends(get_task_service),
) -> WorkerTaskAssignmentRead:
    """Start working on an assigned task."""
    try:
        return service.start_task_assignment(
            assignment_id=assignment_id,
            worker_profile_id=current_worker.worker_profile_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/assignments/{assignment_id}/complete",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Complete a task assignment and record results",
)
def complete_task(
    assignment_id: UUID,
    payload: TaskCompletionPayload,
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: TaskService = Depends(get_task_service),
) -> Dict[str, Any]:
    """Complete a task assignment with outcome and optional result data."""
    try:
        return service.complete_task_assignment(
            assignment_id=assignment_id,
            worker_profile_id=current_worker.worker_profile_id,
            outcome=payload.outcome,
            result_data=payload.result_data,
            notes=payload.notes,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/workflows/{workflow_id}/steps",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get ordered workflow steps",
)
def get_workflow_steps(
    workflow_id: UUID,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> List[Dict[str, Any]]:
    """Return ordered steps for a workflow."""
    try:
        return service.get_workflow_steps(workflow_id=workflow_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/workflows/assignments/{assignment_id}/steps/{step_id}/execute",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Record a workflow step execution",
)
def execute_workflow_step(
    assignment_id: UUID,
    step_id: UUID,
    payload: StepExecutionPayload,
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: TaskService = Depends(get_task_service),
) -> Dict[str, Any]:
    """Record execution details of a workflow step."""
    try:
        return service.record_step_execution(
            workflow_assignment_id=assignment_id,
            workflow_step_id=step_id,
            worker_profile_id=current_worker.worker_profile_id,
            status=payload.status,
            execution_data=payload.execution_data,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
