"""
Voice Processing API routes for AMAP.

Provides real-time speech command parsing, fuzzy keyword matching, and safety confidence evaluation:
- POST /voice/process-command: Process a transcribed speech command.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from typing import Optional

from app.dependencies import get_current_user
from models.auth import AuthenticatedUserContext
from models.voice import STTHealthStatus, TranscriptionResult, VoiceCommandPayload, VoiceCommandResult
from services.speech_to_text_service import SpeechToTextService
from services.voice_service import VoiceService

router = APIRouter(prefix="/voice", tags=["Voice"])

MAX_AUDIO_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
CHUNK_SIZE_BYTES = 64 * 1024  # 64 KB read buffer


def get_voice_service() -> VoiceService:
    """Dependency provider for VoiceService (singleton instance in memory)."""
    if not hasattr(get_voice_service, "_instance"):
        get_voice_service._instance = VoiceService()
    return get_voice_service._instance


def get_speech_to_text_service() -> SpeechToTextService:
    """Dependency provider for the lazy local STT singleton."""
    if not hasattr(get_speech_to_text_service, "_instance"):
        get_speech_to_text_service._instance = SpeechToTextService()
    return get_speech_to_text_service._instance


@router.post(
    "/transcribe",
    response_model=TranscriptionResult,
    status_code=status.HTTP_200_OK,
    summary="Transcribe browser audio with local faster-whisper",
)
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(default=None),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: SpeechToTextService = Depends(get_speech_to_text_service),
) -> TranscriptionResult:
    """Decode a short browser recording and return text only.

    Requires authentication. This endpoint never processes or executes an AMAP
    command. Callers must submit the returned transcript separately to
    ``/process-command``.
    """
    try:
        service.validate_language(language)

        # Enforce maximum 10 MB payload without buffering unbounded input into memory
        audio_chunks = []
        total_bytes = 0
        while True:
            chunk = await audio.read(CHUNK_SIZE_BYTES)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > MAX_AUDIO_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Audio payload exceeds maximum limit of 10MB",
                )
            audio_chunks.append(chunk)

        audio_bytes = b"".join(audio_chunks)
        if not audio_bytes or len(audio_bytes) < 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Audio payload is empty or too small to contain speech",
            )
        result = await run_in_threadpool(service.transcribe, audio_bytes, language=language, filename=audio.filename)
        # Fail-closed gate: reject empty, invalid, or unsupported transcriptions
        # before they can be forwarded to process-command.
        if not result.success or not result.transcript.strip():
            result.success = False
            result.transcript = ""
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get(
    "/stt-health",
    response_model=STTHealthStatus,
    status_code=status.HTTP_200_OK,
    summary="Get local speech-to-text model status",
)
def stt_health(
    service: SpeechToTextService = Depends(get_speech_to_text_service),
) -> STTHealthStatus:
    return service.health()


@router.post(
    "/process-command",
    response_model=VoiceCommandResult,
    status_code=status.HTTP_200_OK,
    summary="Process speech command transcript with fuzzy keyword matching",
)
def process_command(
    payload: VoiceCommandPayload,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
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
