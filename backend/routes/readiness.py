"""
Worker Readiness and Onboarding Lifecycle API Routes for AMAP (§ 4, § 13, § 18).

Provides:
- GET /workers/{id}/readiness: Evaluates whether a worker is ready based on interaction mode and completed milestones.
- POST /workers/{id}/readiness/certify: Marks onboarding and simulated task training as certified.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field

from app.dependencies import get_current_user
from models.auth import AuthenticatedUserContext
from models.base import AMAPBaseModel, StrictInputModel

router = APIRouter(prefix="/workers", tags=["Worker Readiness"])

# In-memory readiness state registry (backed by worker profile UUID)
_WORKER_READINESS_STORE: Dict[str, Dict[str, Any]] = {
    # Alex Morgan (Certified Existing Employee)
    "d0000000-0000-0000-0000-000000000001": {
        "is_fresher": False,
        "onboarding_completed": True,
        "readiness_status": "ready",
        "interaction_mode": "multimodal",
        "gesture_ready": True,
        "voice_ready": True,
        "multimodal_ready": True,
        "task_training_complete": True,
        "overall_ready": True,
        "completed_stages": ["language", "accessibility", "gesture_calibration", "voice_setup", "training"],
        "active_preferences": {
            "language": "en",
            "modality": "multimodal",
            "dwell_time_ms": 500,
            "high_contrast": False,
            "text_scale": 1.0,
        },
    },
    # Maria Rodriguez (Fresher / New Hire)
    "d0000000-0000-0000-0000-000000000002": {
        "is_fresher": True,
        "onboarding_completed": False,
        "readiness_status": "incomplete",
        "interaction_mode": "multimodal",
        "gesture_ready": False,
        "voice_ready": False,
        "multimodal_ready": False,
        "task_training_complete": False,
        "overall_ready": False,
        "completed_stages": [],
        "active_preferences": {
            "language": "es",
            "modality": "multimodal",
            "dwell_time_ms": 500,
            "high_contrast": False,
            "text_scale": 1.0,
        },
    },
}


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
    """
    str_id = str(worker_id)
    state = _WORKER_READINESS_STORE.get(str_id)

    if not state:
        state = {
            "is_fresher": True,
            "onboarding_completed": False,
            "readiness_status": "incomplete",
            "interaction_mode": "multimodal",
            "gesture_ready": False,
            "voice_ready": False,
            "multimodal_ready": False,
            "task_training_complete": False,
            "overall_ready": False,
            "completed_stages": [],
            "active_preferences": {
                "language": "en",
                "modality": "multimodal",
                "dwell_time_ms": 500,
                "high_contrast": False,
                "text_scale": 1.0,
            },
        }
        _WORKER_READINESS_STORE[str_id] = state

    return WorkerReadinessResponse(
        worker_id=worker_id,
        is_fresher=state.get("is_fresher", True),
        onboarding_completed=state.get("onboarding_completed", False),
        readiness_status=state.get("readiness_status", "incomplete"),
        interaction_mode=state.get("interaction_mode", "multimodal"),
        gesture_ready=state.get("gesture_ready", False),
        voice_ready=state.get("voice_ready", False),
        multimodal_ready=state.get("multimodal_ready", False),
        task_training_complete=state.get("task_training_complete", False),
        overall_ready=state.get("overall_ready", False),
        completed_stages=state.get("completed_stages", []),
        active_preferences=state.get("active_preferences", {}),
    )


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
    Mark worker onboarding as complete, calculating overall readiness based on the selected interaction mode.
    """
    str_id = str(worker_id)
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
    _WORKER_READINESS_STORE[str_id] = state

    return WorkerReadinessResponse(
        worker_id=worker_id,
        is_fresher=state["is_fresher"],
        onboarding_completed=state["onboarding_completed"],
        readiness_status=state["readiness_status"],
        interaction_mode=state["interaction_mode"],
        gesture_ready=state["gesture_ready"],
        voice_ready=state["voice_ready"],
        multimodal_ready=state["multimodal_ready"],
        task_training_complete=state["task_training_complete"],
        overall_ready=state["overall_ready"],
        completed_stages=state["completed_stages"],
        active_preferences=state["active_preferences"],
    )
