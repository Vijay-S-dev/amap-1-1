"""
Voice Processing API routes for AMAP.

- POST /voice/process-command: Process a transcribed speech command (unchanged
  semantics; the single command-matching authority for AMAP).
- GET  /voice/stt-health: Local Vosk model status.
- WS   /voice/stream: Streaming speech recognition over WebSocket.

The streaming endpoint implements AMAP's single speech-recognition engine:

    browser mic -> PCM frames over WS -> Vosk streaming recognizer
    -> Kaldi end-of-speech endpointer -> FINAL transcript
    -> existing VoiceService (parser + safety validation) -> client

Safety invariants:
- FREE-FORM recognition only (no grammar constraints — grammar mode was
  measured to force-map out-of-vocabulary speech onto valid commands).
- Partials are display-only and never carry a command payload.
- Only endpointer-finalized transcripts reach VoiceService; one final
  produces at most one command execution.
- Every connection is authenticated with the same JWT used by the REST API;
  each connection gets an isolated recognizer (no state shared between users).
- No raw audio is stored.
"""

import json
import time
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status

from app.dependencies import get_current_user, get_auth_service
from models.auth import AuthenticatedUserContext
from models.voice import (
    STTHealthStatus,
    VoiceCommandPayload,
    VoiceCommandResult,
)
from services.auth_service import AuthService
from services.base import UnauthorizedError
from services.vosk_stt_service import (
    SUPPORTED_LANGUAGES,
    VoskModelRegistry,
    VoskModelUnavailableError,
    get_vosk_registry,
)
from services.voice_service import VoiceService

router = APIRouter(prefix="/voice", tags=["Voice"])

# Close codes (4xxx = application-defined, no WebSocket-protocol clash).
WS_CLOSE_UNAUTHENTICATED = 4401
WS_CLOSE_FORBIDDEN = 4403
WS_CLOSE_MODEL_UNAVAILABLE = 4503
WS_CLOSE_BAD_MESSAGE = 4400

# One PCM frame must be 16-bit mono samples; allow up to ~1 second of audio
# per frame (32000 bytes at 16 kHz) — the browser worklet sends ~32 ms frames.
MAX_FRAME_BYTES = 32000


def get_voice_service() -> VoiceService:
    """Dependency provider for VoiceService (singleton instance in memory)."""
    if not hasattr(get_voice_service, "_instance"):
        get_voice_service._instance = VoiceService()
    return get_voice_service._instance


@router.get(
    "/stt-health",
    response_model=STTHealthStatus,
    status_code=status.HTTP_200_OK,
    summary="Get local Vosk speech-to-text model status",
)
def stt_health(
    service: VoskModelRegistry = Depends(get_vosk_registry),
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


# ---------------------------------------------------------------------------
# Streaming recognition (WebSocket)
# ---------------------------------------------------------------------------


def _normalize_language(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower().replace("_", "-").split("-")[0]
    return normalized if normalized in SUPPORTED_LANGUAGES else None


def _authenticate_websocket(
    websocket: WebSocket,
    auth_service: AuthService,
) -> Optional[AuthenticatedUserContext]:
    """Authenticate a WebSocket with the same JWT as the REST API.

    Browsers cannot set the Authorization header on WebSocket connections, so
    the token may arrive as a `token` query parameter. Non-browser clients may
    use the standard Bearer header. Returns None when authentication fails.
    """
    token = websocket.query_params.get("token")
    if not token:
        header = websocket.headers.get("authorization")
        if header and header.lower().startswith("bearer "):
            token = header[7:].strip()
    if not token:
        return None
    try:
        return auth_service.verify_token(token)
    except UnauthorizedError:
        return None
    except Exception:  # noqa: BLE001 - any failure means "not authenticated"
        return None


async def _run_voice_stream(
    websocket: WebSocket,
    user: AuthenticatedUserContext,
    language: str,
    registry: VoskModelRegistry,
    voice_service: VoiceService,
) -> None:
    """Core streaming loop for one authenticated connection."""
    await websocket.accept()
    try:
        session = registry.new_session(language)
    except VoskModelUnavailableError as exc:
        await websocket.send_json(
            {"type": "error", "code": "model_unavailable", "message": str(exc)}
        )
        await websocket.close(code=WS_CLOSE_MODEL_UNAVAILABLE, reason="voice-model-unavailable")
        return

    await websocket.send_json(
        {"type": "ready", "language": language, "engine": "vosk", "sample_rate": session.sample_rate}
    )

    voice_service_local = voice_service
    worker_profile_id: Optional[UUID] = getattr(user, "worker_profile_id", None)

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                session.finish()
                return

            text_data = message.get("text")
            if text_data is not None:
                # Control messages are JSON text frames only.
                try:
                    control = json.loads(text_data)
                except (TypeError, ValueError):
                    await websocket.send_json(
                        {"type": "error", "code": "bad_message", "message": "Malformed control message."}
                    )
                    continue
                if not isinstance(control, dict) or "type" not in control:
                    await websocket.send_json(
                        {"type": "error", "code": "bad_message", "message": "Malformed control message."}
                    )
                    continue
                if control.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                await websocket.send_json(
                    {"type": "error", "code": "bad_message", "message": "Unsupported control message."}
                )
                continue

            pcm = message.get("bytes")
            if pcm is None:
                await websocket.send_json(
                    {"type": "error", "code": "bad_message", "message": "Binary PCM frames required."}
                )
                continue
            if len(pcm) > MAX_FRAME_BYTES:
                await websocket.send_json(
                    {"type": "error", "code": "unsupported_audio_format",
                     "message": "Audio frame exceeds maximum size."}
                )
                continue
            try:
                event = session.feed(pcm)
            except ValueError as exc:
                await websocket.send_json(
                    {"type": "error", "code": "unsupported_audio_format", "message": str(exc)}
                )
                continue

            if event is None:
                continue
            if event["type"] == "partial":
                # Display-only feedback. No command payload by construction.
                await websocket.send_json({"type": "partial", "text": event["text"]})
                continue

            if event["type"] == "final":
                transcript = event["transcript"]
                started = time.perf_counter()
                if not transcript:
                    # Endpointer fired on non-speech: report, never execute.
                    await websocket.send_json(
                        {"type": "final", "transcript": "", "detected_language": language,
                         "confidence": 0.0, "processing_time_ms": event["processing_time_ms"],
                         "utterance": event["utterance"], "speech_end_s": event.get("speech_end_s"),
                         "command": None}
                    )
                    continue
                # ONLY finalized transcripts reach the command parser.
                command_result: VoiceCommandResult = voice_service_local.process_command(
                    payload=VoiceCommandPayload(
                        raw_transcript=transcript,
                        confidence=event["confidence"],
                        language=language,
                    ),
                    worker_profile_id=worker_profile_id,
                )
                parse_ms = round((time.perf_counter() - started) * 1000, 2)
                await websocket.send_json(
                    {
                        "type": "final",
                        "transcript": transcript,
                        "detected_language": language,
                        "confidence": event["confidence"],
                        "processing_time_ms": event["processing_time_ms"],
                        "command_parse_ms": parse_ms,
                        "utterance": event["utterance"],
                        "speech_end_s": event.get("speech_end_s"),
                        "command": command_result.model_dump(),
                    }
                )
    except WebSocketDisconnect:
        session.finish()
        return
    except Exception as exc:  # noqa: BLE001 - never let a failure execute anything
        try:
            await websocket.send_json(
                {"type": "error", "code": "recognition_failure", "message": str(exc)}
            )
            await websocket.close(code=1011, reason="recognition-failure")
        except Exception:  # noqa: BLE001
            pass


@router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
    language: Optional[str] = Query(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    registry: VoskModelRegistry = Depends(get_vosk_registry),
    voice_service: VoiceService = Depends(get_voice_service),
) -> None:
    """Streaming voice recognition (Vosk) with automatic end-of-speech.

    Protocol:
      client -> server: binary frames of 16-bit LE mono PCM (16 kHz);
                       text frames of JSON control messages ({"type":"ping"}).
      server -> client: {"type":"ready", ...}
                       {"type":"partial","text":...}   (display-only)
                       {"type":"final","transcript":..., "command":{...}} (executable)
                       {"type":"error","code":...,"message":...}

    Authentication: same JWT as the REST API, via `token` query parameter
    (browsers) or Authorization: Bearer header (other clients).
    """
    user = _authenticate_websocket(websocket, auth_service)
    if user is None:
        await websocket.accept()
        await websocket.send_json(
            {"type": "error", "code": "unauthenticated", "message": "Valid authentication token required."}
        )
        await websocket.close(code=WS_CLOSE_UNAUTHENTICATED, reason="unauthenticated")
        return
    if getattr(user, "status", "active") != "active":
        await websocket.accept()
        await websocket.send_json(
            {"type": "error", "code": "forbidden", "message": "User account is not active."}
        )
        await websocket.close(code=WS_CLOSE_FORBIDDEN, reason="inactive-user")
        return

    normalized = _normalize_language(language)
    if language is not None and normalized is None:
        await websocket.accept()
        await websocket.send_json(
            {"type": "error", "code": "unsupported_language",
             "message": "Only English (en) and Hindi (hi) are supported."}
        )
        await websocket.close(code=WS_CLOSE_BAD_MESSAGE, reason="unsupported-language")
        return
    selected_language = normalized or "en"

    await _run_voice_stream(websocket, user, selected_language, registry, voice_service)
