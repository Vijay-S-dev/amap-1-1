"""
Personalization API routes for AMAP.

Provides endpoints for managing worker accessibility preferences, capability profiles,
audit change history, and evaluating evidence-based adaptation recommendations:
- GET /personalization/me: Retrieve current worker's personalization settings.
- PUT /personalization/me: Update worker personalization settings (with history tracking).
- GET /personalization/me/evidence: Analyze interaction difficulty patterns.
- POST /personalization/me/evaluate-adapt: Run multi-signal adaptation evaluation.
- GET /personalization/me/capabilities: Get worker capability profile.
- PUT /personalization/me/capabilities: Update worker capability profile.
- GET /personalization/me/history: Get personalization history audit trail.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import Field

from app.dependencies import get_current_active_worker
from models.auth import AuthenticatedUserContext
from models.base import StrictInputModel
from models.worker import (
    AdaptationEvaluationResult,
    PersonalizationHistoryRead,
    WorkerCapabilityProfileRead,
    WorkerPersonalizationRead,
)
from services.personalization_service import PersonalizationService

router = APIRouter(prefix="/personalization", tags=["Personalization"])


def get_personalization_service() -> PersonalizationService:
    """Dependency provider for PersonalizationService."""
    return PersonalizationService()


class PersonalizationUpdatePayload(StrictInputModel):
    """Payload for updating worker personalization preferences."""
    personalization_data: Dict[str, Any] = Field(..., description="Key-value customization parameters")
    change_reason: str = Field(default="User preference update", min_length=1, max_length=500)
    interaction_configuration_id: Optional[UUID] = None


class CapabilityProfileUpdatePayload(StrictInputModel):
    """Payload for updating worker physical/cognitive capability profiles."""
    capability_data: Dict[str, Any] = Field(..., description="Worker capability descriptors")
    status: str = Field(default="active", pattern="^(active|archived|suspended)$")


@router.get(
    "/me",
    response_model=Optional[WorkerPersonalizationRead],
    status_code=status.HTTP_200_OK,
    summary="Get current worker personalization profile",
)
def get_my_personalization(
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: PersonalizationService = Depends(get_personalization_service),
) -> Optional[WorkerPersonalizationRead]:
    """Return the personalization settings for the authenticated worker."""
    return service.get_personalization(worker_profile_id=current_worker.worker_profile_id)


@router.put(
    "/me",
    response_model=WorkerPersonalizationRead,
    status_code=status.HTTP_200_OK,
    summary="Update current worker personalization profile",
)
def update_my_personalization(
    payload: PersonalizationUpdatePayload,
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: PersonalizationService = Depends(get_personalization_service),
) -> WorkerPersonalizationRead:
    """Update personalization preferences and record change history."""
    return service.update_personalization(
        worker_profile_id=current_worker.worker_profile_id,
        new_data=payload.personalization_data,
        change_reason=payload.change_reason,
        interaction_configuration_id=payload.interaction_configuration_id,
    )


@router.get(
    "/me/evidence",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Evaluate interaction difficulty evidence for adaptation",
)
def get_adaptation_evidence(
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: PersonalizationService = Depends(get_personalization_service),
) -> Dict[str, Any]:
    """
    Analyze recent interaction logs to identify recurring difficulty patterns
    and return evidence-based recommendations.
    """
    return service.analyze_interaction_evidence(
        worker_profile_id=current_worker.worker_profile_id
    )


@router.post(
    "/me/evaluate-adapt",
    response_model=AdaptationEvaluationResult,
    status_code=status.HTTP_200_OK,
    summary="Run evidence-based adaptation evaluation engine",
)
def evaluate_and_adapt(
    auto_apply: bool = Query(False, description="Whether to auto-apply safe recommendations"),
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: PersonalizationService = Depends(get_personalization_service),
) -> AdaptationEvaluationResult:
    """
    Evaluates multi-event interaction evidence across modalities and formulates or auto-applies adaptations.
    """
    return service.evaluate_and_adapt(
        worker_profile_id=current_worker.worker_profile_id,
        auto_apply=auto_apply,
    )


@router.get(
    "/me/capabilities",
    response_model=Optional[WorkerCapabilityProfileRead],
    status_code=status.HTTP_200_OK,
    summary="Get worker physical and cognitive capability profile",
)
def get_my_capabilities(
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: PersonalizationService = Depends(get_personalization_service),
) -> Optional[WorkerCapabilityProfileRead]:
    """Return capability profile descriptors for the authenticated worker."""
    return service.get_worker_capabilities(worker_profile_id=current_worker.worker_profile_id)


@router.put(
    "/me/capabilities",
    response_model=WorkerCapabilityProfileRead,
    status_code=status.HTTP_200_OK,
    summary="Update worker capability profile",
)
def update_my_capabilities(
    payload: CapabilityProfileUpdatePayload,
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: PersonalizationService = Depends(get_personalization_service),
) -> WorkerCapabilityProfileRead:
    """Create or update capability profile descriptors for the worker."""
    return service.update_worker_capabilities(
        worker_profile_id=current_worker.worker_profile_id,
        capability_data=payload.capability_data,
        status=payload.status,
    )


@router.get(
    "/me/history",
    response_model=List[PersonalizationHistoryRead],
    status_code=status.HTTP_200_OK,
    summary="Get worker personalization audit history",
)
def get_my_personalization_history(
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: PersonalizationService = Depends(get_personalization_service),
) -> List[PersonalizationHistoryRead]:
    """Return complete audit trail of personalization configuration changes."""
    return service.get_personalization_history(worker_profile_id=current_worker.worker_profile_id)
