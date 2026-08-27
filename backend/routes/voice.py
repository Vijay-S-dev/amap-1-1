"""
Voice Processing API routes for AMAP.

Provides real-time speech command parsing, fuzzy keyword matching, and safety confidence evaluation:
- POST /voice/process-command: Process a transcribed speech command.
"""

from fastapi import APIRouter, Depends, status

from typing import Optional

from app.dependencies import get_current_user_optional
from models.auth import AuthenticatedUserContext
from models.voice import VoiceCommandPayload, VoiceCommandResult
from services.voice_service import VoiceService

router = APIRouter(prefix="/voice", tags=["Voice"])


def get_voice_service() -> VoiceService:
    """Dependency provider for VoiceService (singleton instance in memory)."""
    if not hasattr(get_voice_service, "_instance"):
        get_voice_service._instance = VoiceService()
    return get_voice_service._instance


@router.post(
    "/process-command",
    response_model=VoiceCommandResult,
    status_code=status.HTTP_200_OK,
    summary="Process speech command transcript with fuzzy keyword matching",
)
def process_command(
    payload: VoiceCommandPayload,
    current_user: Optional[AuthenticatedUserContext] = Depends(get_current_user_optional),
    service: VoiceService = Depends(get_voice_service),
) -> VoiceCommandResult:
    """
    Parse speech transcript into an AMAP candidate action with confidence tiering
    and safety confirmation gating.
    """
    worker_id = current_user.worker_profile_id if current_user else None
    return service.process_command(
        payload=payload,
        worker_profile_id=worker_id,
    )
