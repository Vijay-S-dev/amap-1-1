"""
Accessibility preferences API routes for AMAP.

Persists the signed-in user's accessibility + onboarding preferences in
PostgreSQL (never localStorage-authoritative):
- GET /accessibility/preferences: read current user's preferences.
- PUT /accessibility/preferences: validate and persist (full replace).
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from models.auth import AuthenticatedUserContext
from models.base import StrictInputModel
from pydantic import Field
from services.accessibility_service import AccessibilityService
from services.base import ValidationError

router = APIRouter(prefix="/accessibility", tags=["Accessibility"])


def get_accessibility_service() -> AccessibilityService:
    """Dependency provider for AccessibilityService."""
    return AccessibilityService()


class AccessibilityPreferencesPayload(StrictInputModel):
    """Full-replace preferences payload from the client state engine."""

    preferences: Dict[str, Any] = Field(
        ..., description="Accessibility + onboarding preference key/values"
    )


@router.get(
    "/preferences",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get current user accessibility preferences",
)
def get_my_preferences(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: AccessibilityService = Depends(get_accessibility_service),
) -> Dict[str, Any]:
    """Read the authenticated user's persisted accessibility preferences."""
    return service.get_preferences(user_id=current_user.user_id)


@router.put(
    "/preferences",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Persist current user accessibility preferences",
)
def put_my_preferences(
    payload: AccessibilityPreferencesPayload,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: AccessibilityService = Depends(get_accessibility_service),
) -> Dict[str, Any]:
    """Validate and persist preferences; refresh/login/restart preserve them."""
    try:
        return service.update_preferences(
            user_id=current_user.user_id, preferences=payload.preferences
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
