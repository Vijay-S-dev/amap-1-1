"""
Gesture Processing API routes for AMAP.

Provides real-time landmark processing, geometric classification, and dwell-time filtering:
- POST /gestures/process-frame: Process a tracked hand landmark frame.
"""

from typing import Optional

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user
from models.auth import AuthenticatedUserContext
from models.gesture import GestureFramePayload, GestureRecognitionResult
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
    summary="Process video frame landmarks with dwell-time accumulation",
)
def process_frame(
    payload: GestureFramePayload,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: GestureService = Depends(get_gesture_service),
) -> GestureRecognitionResult:
    """
    Classify 21 hand landmark points into discrete gestures and accumulate dwell progress.
    Returns recognition result and trigger status.
    """
    return service.process_frame(
        payload=payload,
        worker_profile_id=current_user.worker_profile_id,
    )
