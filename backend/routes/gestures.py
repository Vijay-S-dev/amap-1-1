"""
Gesture Processing and Custom Gesture Training API routes for AMAP.

Provides:
- POST /gestures/process-frame: Process a tracked hand landmark frame with dwell-time accumulation.
- POST /gestures/custom/train: Train and persist a worker-specific custom gesture profile.
- GET /gestures/custom: List all active custom gestures for the authenticated worker.
- DELETE /gestures/custom/{gesture_id}: Delete/deactivate a worker's custom gesture.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from models.auth import AuthenticatedUserContext
from models.gesture import (
    CustomGestureProfileRead,
    CustomGestureTestPayload,
    CustomGestureTrainPayload,
    GestureFramePayload,
    GestureRecognitionResult,
)
from services.gesture_service import GestureService

router = APIRouter(prefix="/gestures", tags=["Gestures"])


def get_gesture_service() -> GestureService:
    """Dependency provider for GestureService (singleton instance in memory)."""
    if not hasattr(get_gesture_service, "_instance"):
        get_gesture_service._instance = GestureService()
    return get_gesture_service._instance


@router.post(
    "/process-frame",
    response_model=GestureRecognitionResult,
    status_code=status.HTTP_200_OK,
    summary="Process video frame landmarks with dwell-time accumulation (Standard + Custom Hybrid)",
)
def process_frame(
    payload: GestureFramePayload,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GestureService = Depends(get_gesture_service),
) -> GestureRecognitionResult:
    """
    Classify 21 hand landmark points into discrete gestures (standard or custom) and accumulate dwell progress.
    Returns recognition result and trigger status.
    """
    return service.process_frame(
        payload=payload,
        worker_profile_id=current_user.worker_profile_id,
    )


@router.post(
    "/custom/train",
    response_model=CustomGestureProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Train and persist a worker-specific custom gesture profile",
)
def train_custom_gesture(
    payload: CustomGestureTrainPayload,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GestureService = Depends(get_gesture_service),
) -> CustomGestureProfileRead:
    """
    Validates at least 5 physical landmark samples, computes normalized reference template,
    and persists the custom gesture profile for the authenticated worker.
    """
    if not current_user.worker_profile_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user does not have an active worker profile.",
        )

    try:
        profile = service.train_custom_gesture(
            payload=payload,
            worker_profile_id=current_user.worker_profile_id,
            organization_id=current_user.organization_id,
        )
        return profile
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err),
        )


@router.get(
    "/custom",
    response_model=List[CustomGestureProfileRead],
    status_code=status.HTTP_200_OK,
    summary="List all active custom gestures for the authenticated worker",
)
def get_custom_gestures(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GestureService = Depends(get_gesture_service),
) -> List[CustomGestureProfileRead]:
    """Retrieve all active custom gesture profiles belonging to the authenticated worker."""
    if not current_user.worker_profile_id:
        return []
    return service.get_worker_custom_gestures(current_user.worker_profile_id)


@router.delete(
    "/custom/{gesture_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete/deactivate a worker's custom gesture profile",
)
def delete_custom_gesture(
    gesture_id: UUID,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GestureService = Depends(get_gesture_service),
) -> dict:
    """Delete a custom gesture profile for the authenticated worker."""
    if not current_user.worker_profile_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have an active worker profile.",
        )
    deleted = service.delete_worker_custom_gesture(
        worker_profile_id=current_user.worker_profile_id,
        gesture_id=gesture_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom gesture profile not found.",
        )
    return {"status": "success", "message": "Custom gesture deleted."}
