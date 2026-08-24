"""
Interaction and Multimodal API routes for AMAP.

Provides endpoints for multimodal intent evaluation and interaction audit event recording:
- POST /interactions/process-intent: Evaluate raw gesture/voice intents and confidence levels.
- POST /interactions/events: Log an interaction audit event.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_active_worker, get_current_user
from models.auth import AuthenticatedUserContext
from models.interaction import (
    InteractionEventCreate,
    InteractionEventRead,
    MultimodalIntentPayload,
    MultimodalProcessingResult,
)
from services.interaction_service import InteractionService

router = APIRouter(prefix="/interactions", tags=["Interactions & Multimodal"])


def get_interaction_service() -> InteractionService:
    """Dependency provider for InteractionService."""
    return InteractionService()


@router.post(
    "/process-intent",
    response_model=MultimodalProcessingResult,
    status_code=status.HTTP_200_OK,
    summary="Process raw multimodal gesture/voice intent",
)
def process_intent(
    payload: MultimodalIntentPayload,
    work_session_id: Optional[UUID] = Query(None, description="Optional active work session ID"),
    current_worker: AuthenticatedUserContext = Depends(get_current_active_worker),
    service: InteractionService = Depends(get_interaction_service),
) -> MultimodalProcessingResult:
    """
    Evaluate raw recognized gesture or voice intent against confidence thresholds.
    Determines if candidate action requires explicit user confirmation.
    """
    return service.process_multimodal_intent(
        payload=payload,
        worker_profile_id=current_worker.worker_profile_id,
        organization_id=current_worker.organization_id,
        work_session_id=work_session_id,
    )


@router.post(
    "/events",
    response_model=InteractionEventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record an interaction audit event",
)
def record_event(
    payload: InteractionEventCreate,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: InteractionService = Depends(get_interaction_service),
) -> InteractionEventRead:
    """Record an interaction event in the audit log."""
    return service.record_interaction_event(payload)
