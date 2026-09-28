"""
Work session API routes for AMAP.

Provides endpoints for managing worker work session lifecycles:
- POST /sessions/start: Start a new active work session.
- GET /sessions/active: Get the currently active/paused work session.
- POST /sessions/{session_id}/pause: Pause active session.
- POST /sessions/{session_id}/resume: Resume paused session.
- POST /sessions/{session_id}/end: End work session.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_active_worker
from models.auth import AuthenticatedUserContext
from models.base import StrictInputModel
from models.session import WorkSessionRead
from services.base import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from services.work_session_service import WorkSessionService

router = APIRouter(prefix="/sessions", tags=["Work Sessions"])


def get_work_session_service() -> WorkSessionService:
    """Dependency provider for WorkSessionService."""
    return WorkSessionService()


class HeartbeatPayload(StrictInputModel):
    """Optional payload identifying which session to heartbeat."""
    work_session_id: Optional[UUID] = None


@router.post(
    "/start",
    response_model=WorkSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new work session",
)
def start_session(
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: WorkSessionService = Depends(get_work_session_service),
) -> WorkSessionRead:
    """Start a new work session for the authenticated worker."""
    try:
        return service.start_session(worker_profile_id=current_worker.worker_profile_id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/active",
    response_model=Optional[WorkSessionRead],
    status_code=status.HTTP_200_OK,
    summary="Get active work session",
)
def get_active_session(
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: WorkSessionService = Depends(get_work_session_service),
) -> Optional[WorkSessionRead]:
    """Retrieve the current active or paused session for the authenticated worker."""
    return service.get_active_session(worker_profile_id=current_worker.worker_profile_id)


@router.post(
    "/heartbeat",
    response_model=Optional[WorkSessionRead],
    status_code=status.HTTP_200_OK,
    summary="Refresh worker session liveness heartbeat",
)
def heartbeat_session(
    payload: Optional[HeartbeatPayload] = None,
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: WorkSessionService = Depends(get_work_session_service),
) -> Optional[WorkSessionRead]:
    """
    Refresh the liveness heartbeat for the worker's active work session.

    The supervisor live worker monitor uses `last_heartbeat_at` to distinguish
    genuinely online workers from stale session rows. Accepts an optional
    `work_session_id`; when omitted, the worker's current active/paused session
    is used. Returns the session, or None when no live session exists.
    """
    session_id = payload.work_session_id if payload and payload.work_session_id else None
    if session_id is None:
        active = service.get_active_session(worker_profile_id=current_worker.worker_profile_id)
        if active is None:
            return None
        session_id = active.id
    return service.heartbeat(
        work_session_id=session_id,
        worker_profile_id=current_worker.worker_profile_id,
    )


@router.post(
    "/{session_id}/pause",
    response_model=WorkSessionRead,
    status_code=status.HTTP_200_OK,
    summary="Pause active work session",
)
def pause_session(
    session_id: UUID,
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: WorkSessionService = Depends(get_work_session_service),
) -> WorkSessionRead:
    """Pause an active work session."""
    try:
        return service.pause_session(
            work_session_id=session_id,
            worker_profile_id=current_worker.worker_profile_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/{session_id}/resume",
    response_model=WorkSessionRead,
    status_code=status.HTTP_200_OK,
    summary="Resume paused work session",
)
def resume_session(
    session_id: UUID,
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: WorkSessionService = Depends(get_work_session_service),
) -> WorkSessionRead:
    """Resume a paused work session."""
    try:
        return service.resume_session(
            work_session_id=session_id,
            worker_profile_id=current_worker.worker_profile_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/{session_id}/end",
    response_model=WorkSessionRead,
    status_code=status.HTTP_200_OK,
    summary="End work session",
)
def end_session(
    session_id: UUID,
    status_param: str = Query("completed", alias="status", pattern="^(completed|cancelled)$"),
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: WorkSessionService = Depends(get_work_session_service),
) -> WorkSessionRead:
    """End a work session as completed or cancelled."""
    try:
        return service.end_session(
            work_session_id=session_id,
            worker_profile_id=current_worker.worker_profile_id,
            status=status_param,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
