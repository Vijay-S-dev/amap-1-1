"""
Multimodal Processing and Cross-Modal Fusion API routes for AMAP.

Provides real-time cross-modal intent fusion, spatial-action binding, and conflict arbitration:
- POST /multimodal/fuse: Arbitrate and fuse multi-input streams within a temporal window.
"""

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user, require_permissions
from models.auth import AuthenticatedUserContext
from models.multimodal import MultimodalFusionPayload, MultimodalFusionResult
from services.multimodal_service import MultimodalService

router = APIRouter(prefix="/multimodal", tags=["Multimodal"])


def get_multimodal_service() -> MultimodalService:
    """Dependency provider for MultimodalService (singleton instance in memory)."""
    if not hasattr(get_multimodal_service, "_instance"):
        get_multimodal_service._instance = MultimodalService()
    return get_multimodal_service._instance


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
) -> MultimodalFusionResult:
    """
    Correlates multiple inputs across modalities (gesture, voice, UI) within a temporal window,
    performs probabilistic confidence reinforcement or complementary binding, and resolves conflicts.
    """
    return service.fuse_inputs(
        payload=payload,
        worker_profile_id=current_user.worker_profile_id,
    )
