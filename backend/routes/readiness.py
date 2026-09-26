"""
Worker Readiness and Onboarding Lifecycle API Routes for AMAP (§ 4, § 13, § 18).

Provides:
- GET /workers/{id}/readiness: Evaluates whether a worker is ready based on interaction mode and completed milestones.
- POST /workers/{id}/readiness/certify: Marks onboarding and simulated task training as certified.

All state is persisted in PostgreSQL (worker_readiness, migration 042) so it
survives backend restarts. There is no in-memory store.
"""

from typing import Any, Dict, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field

from app.dependencies import get_current_user
from models.auth import AuthenticatedUserContext
from models.base import AMAPBaseModel, StrictInputModel
from repositories.worker_profiles import WorkerProfilesRepository
from repositories.worker_readiness import WorkerReadinessRepository

router = APIRouter(prefix="/workers", tags=["Worker Readiness"])


class WorkerReadinessResponse(AMAPBaseModel):
    worker_id: UUID
    is_fresher: bool = Field(..., description="True if worker has not yet completed initial onboarding")
    onboarding_completed: bool
    readiness_status: str = Field(..., description="'ready' or 'incomplete'")
    interaction_mode: str = Field(default="multimodal", description="'gesture', 'voice', or 'multimodal'")
    gesture_ready: bool = Field(default=False)
    voice_ready: bool = Field(default=False)
    multimodal_ready: bool = Field(default=False)
    task_training_complete: bool = Field(default=False)
    overall_ready: bool = Field(default=False)
    completed_stages: List[str] = Field(default_factory=list)
    active_preferences: Dict[str, Any] = Field(default_factory=dict)


class CertifyReadinessRequest(StrictInputModel):
    selected_language: str = "en"
    selected_modality: str = "multimodal"
    calibrated_dwell_ms: int = 500
    training_order_id: str = "Order #1042 Level 1"
    gesture_ready: bool = False
    voice_ready: bool = False
    multimodal_ready: bool = False
    task_training_complete: bool = False


def _compute_readiness(
    interaction_mode: str,
    gesture_ready: bool,
    voice_ready: bool,
    multimodal_ready: bool,
    task_training_complete: bool,
) -> bool:
    """Calculate overall worker readiness according to interaction mode requirements (§ 8)."""
    if not task_training_complete:
        return False

    mode = interaction_mode.lower()
    if mode == "gesture":
        return gesture_ready
    elif mode == "voice":
        return voice_ready
    elif mode in ("both", "multimodal"):
        return gesture_ready and voice_ready and multimodal_ready
    return task_training_complete


def _require_worker_profile(worker_id: UUID) -> None:
    """Raise 404 when the worker profile does not exist in PostgreSQL."""
    profile = WorkerProfilesRepository().get_by_id(worker_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker profile {worker_id} not found.",
        )


def _row_to_response(worker_id: UUID, row: Dict[str, Any]) -> WorkerReadinessResponse:
    return WorkerReadinessResponse(
        worker_id=worker_id,
        is_fresher=row["is_fresher"],
        onboarding_completed=row["onboarding_completed"],
        readiness_status=row["readiness_status"],
        interaction_mode=row["interaction_mode"],
        gesture_ready=row["gesture_ready"],
        voice_ready=row["voice_ready"],
        multimodal_ready=row["multimodal_ready"],
        task_training_complete=row["task_training_complete"],
        overall_ready=row["overall_ready"],
        completed_stages=list(row["completed_stages"] or []),
        active_preferences=dict(row["active_preferences"] or {}),
    )


@router.get(
    "/{worker_id}/readiness",
    response_model=WorkerReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get worker onboarding readiness and fresher status",
)
def get_worker_readiness(
    worker_id: UUID,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> WorkerReadinessResponse:
    """
    Check if the worker is a new hire/fresher requiring onboarding or a certified existing employee.
    Creates and persists the default readiness record on first access.
    """
    _require_worker_profile(worker_id)

    readiness_repo = WorkerReadinessRepository()
    row = readiness_repo.get(worker_id)
    if not row:
        row = readiness_repo.create_default(worker_id)

    return _row_to_response(worker_id, row)


@router.post(
    "/{worker_id}/readiness/certify",
    response_model=WorkerReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Certify worker onboarding and simulated training completion",
)
def certify_worker_readiness(
    worker_id: UUID,
    payload: CertifyReadinessRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> WorkerReadinessResponse:
    """
    Mark worker onboarding as complete, calculating overall readiness based on
    the selected interaction mode. The result is persisted to PostgreSQL.
    """
    _require_worker_profile(worker_id)

    overall_ready = _compute_readiness(
        interaction_mode=payload.selected_modality,
        gesture_ready=payload.gesture_ready,
        voice_ready=payload.voice_ready,
        multimodal_ready=payload.multimodal_ready,
        task_training_complete=payload.task_training_complete,
    )

    completed_stages = ["language", "accessibility"]
    if payload.gesture_ready:
        completed_stages.append("gesture_calibration")
    if payload.voice_ready:
        completed_stages.append("voice_setup")
    if payload.task_training_complete:
        completed_stages.append("training")

    state = {
        "is_fresher": not overall_ready,
        "onboarding_completed": overall_ready,
        "readiness_status": "ready" if overall_ready else "incomplete",
        "interaction_mode": payload.selected_modality,
        "gesture_ready": payload.gesture_ready,
        "voice_ready": payload.voice_ready,
        "multimodal_ready": payload.multimodal_ready,
        "task_training_complete": payload.task_training_complete,
        "overall_ready": overall_ready,
        "completed_stages": completed_stages,
        "active_preferences": {
            "language": payload.selected_language,
            "modality": payload.selected_modality,
            "dwell_time_ms": payload.calibrated_dwell_ms,
            "training_order": payload.training_order_id,
        },
    }

    row = WorkerReadinessRepository().upsert(worker_id, state)
    return _row_to_response(worker_id, row)
