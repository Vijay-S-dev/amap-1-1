"""
Multimodal Processing and Cross-Modal Fusion API routes for AMAP.

Provides real-time cross-modal intent fusion, spatial-action binding, and conflict arbitration:
- POST /multimodal/fuse: Arbitrate and fuse multi-input streams within a temporal window.

The fusion service itself stays a pure computation (no database access); the
route layer resolves the worker's effective gesture mapping from PostgreSQL
(worker personalization override -> organization preset -> canonical default)
and injects it so personalized mappings apply to fusion.
"""

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user, require_permissions
from models.auth import AuthenticatedUserContext
from models.multimodal import MultimodalFusionPayload, MultimodalFusionResult
from services.multimodal_service import MultimodalService
from services.worker_interaction_service import WorkerInteractionService

router = APIRouter(prefix="/multimodal", tags=["Multimodal"])


def get_multimodal_service() -> MultimodalService:
    """Dependency provider for MultimodalService (singleton instance in memory)."""
    if not hasattr(get_multimodal_service, "_instance"):
        get_multimodal_service._instance = MultimodalService()
    return get_multimodal_service._instance


def get_worker_interaction_service() -> WorkerInteractionService:
    """Dependency provider for WorkerInteractionService (singleton, cached mapping)."""
    if not hasattr(get_worker_interaction_service, "_instance"):
        get_worker_interaction_service._instance = WorkerInteractionService()
    return get_worker_interaction_service._instance


@router.post(
    "/fuse",
    response_model=MultimodalFusionResult,
    status_code=status.HTTP_200_OK,
    summary="Arbitrate and fuse multimodal inputs across modalities",
    dependencies=[Depends(require_permissions("multimodal:input"))],
)
def fuse_multimodal_inputs(
    payload: MultimodalFusionPayload,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: MultimodalService = Depends(get_multimodal_service),
    interaction_service: WorkerInteractionService = Depends(get_worker_interaction_service),
) -> MultimodalFusionResult:
    """
    Correlates multiple inputs across modalities (gesture, voice, UI) within a temporal window,
    performs probabilistic confidence reinforcement or complementary binding, and resolves conflicts.
    Gesture intents are resolved through the worker's personalized gesture mapping.
    """
    gesture_action_map = None
    if current_user.worker_profile_id:
        try:
            gesture_action_map = interaction_service.get_effective_gesture_mapping(
                current_user.worker_profile_id
            ).get("gesture_action_map")
        except Exception:
            gesture_action_map = None  # fall back to canonical mapping

    return service.fuse_inputs(
        payload=payload,
        worker_profile_id=current_user.worker_profile_id,
        gesture_action_map=gesture_action_map,
    )
