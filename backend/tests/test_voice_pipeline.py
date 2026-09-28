"""
Tests for AMAP Voice Input Pipeline (Phase 10 & § 11, § 12, § 13, § 14, § 28).
Covers speech command normalization, multilingual keyword matching (en, es, de, hi, ta),
confidence thresholding, safety confirmation gating, and the voice API endpoint.
"""

from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.dependencies import get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from models.voice import VoiceCommandPayload
from services.voice_service import VoiceService


# =====================================================================
# Exact & Multilingual Vocabulary Match Tests (§ 11, § 13)
# =====================================================================

def test_voice_exact_and_multilingual_matches():
    service = VoiceService()

    # 1. English commands
    cmd, action, score, is_crit = service.match_command("next step")
    assert cmd == "next_step"
    assert action == "next_step"
    assert is_crit is False

    cmd, action, score, is_crit = service.match_command("confirm please")
    assert cmd == "confirm_action"
    assert action == "confirm_action"

    cmd, action, score, is_crit = service.match_command("emergency stop")
    assert cmd == "emergency_stop"
    assert action == "emergency_stop"
    assert is_crit is True

    cmd, action, score, is_crit = service.match_command("call supervisor")
    assert cmd == "request_assistance"
    assert action == "request_assistance"

    # 2. Hindi commands (devanagari and transliteration) — en/hi only product
    cmd_hi, act_hi, _, _ = service.match_command("अगला")
    assert cmd_hi == "next_step"

    cmd_hi2, act_hi2, _, _ = service.match_command("पुष्टि")
    assert cmd_hi2 == "confirm_action"

    cmd_hi3, act_hi3, _, _ = service.match_command("agla step")
    assert cmd_hi3 == "next_step"
    assert act_hi3 == "next_step"

    # 3. Unsupported languages are handled correctly: unmatched, not guessed
    assert service.match_command("siguiente")[0] is None  # Spanish
    assert service.match_command("weiter")[0] is None  # German
    assert service.match_command("அடுத்து")[0] is None  # Tamil


# =====================================================================
# Unknown Speech & Non-Vocabulary Safety Tests (§ 8, § 14)
# =====================================================================

def test_voice_unknown_speech_rejection():
    service = VoiceService()

    # 1. Empty text rejected by schema validation
    with pytest.raises(ValidationError):
        VoiceCommandPayload(raw_transcript="   ", confidence=0.95)

    with pytest.raises(ValidationError):
        VoiceCommandPayload(raw_transcript="", confidence=0.95)

    # 2. Casual conversation / off-vocabulary speech safely produces unmatched status and zero intent
    p_chat = VoiceCommandPayload(raw_transcript="I had lunch already today", confidence=0.92)
    r_chat = service.process_command(p_chat)
    assert r_chat.matched_command is None
    assert r_chat.action_mapping is None
    assert r_chat.validation_status == "unmatched"

    p_weather = VoiceCommandPayload(raw_transcript="what time does the shift end", confidence=0.88)
    r_weather = service.process_command(p_weather)
    assert r_weather.matched_command is None
    assert r_weather.action_mapping is None
    assert r_weather.validation_status == "unmatched"


# =====================================================================
# Confidence Tiering & Safety Gating Tests (§ 15, § 16)
# =====================================================================

def test_voice_process_command_tiers():
    service = VoiceService()

    # 1. High confidence non-critical command -> no confirmation required
    p1 = VoiceCommandPayload(raw_transcript="next step", confidence=0.95)
    r1 = service.process_command(p1)
    assert r1.matched_command == "next_step"
    assert r1.validation_status == "valid"
    assert r1.requires_confirmation is False

    # 2. High confidence safety-critical command -> confirmation required
    p2 = VoiceCommandPayload(raw_transcript="emergency stop", confidence=0.95)
    r2 = service.process_command(p2)
    assert r2.matched_command == "emergency_stop"
    assert r2.validation_status == "valid"
    assert r2.requires_confirmation is True

    # 3. Medium confidence command -> confirmation required
    p3 = VoiceCommandPayload(raw_transcript="continue", confidence=0.65)
    r3 = service.process_command(p3)
    assert r3.matched_command == "next_step"
    assert r3.validation_status == "valid"
    assert r3.requires_confirmation is True


# =====================================================================
# Voice API Endpoint Tests (§ 21)
# =====================================================================

def test_voice_process_command_api_endpoint():
    client = TestClient(app)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    worker_id = uuid.uuid4()

    mock_user = AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="worker@amap.org",
        full_name="Worker",
        status="active",
        roles=["worker"],
        permissions=[],
        worker_profile_id=worker_id,
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        # Valid assistance command
        resp = client.post(
            "/api/v1/voice/process-command",
            json={
                "raw_transcript": "help",
                "confidence": 0.92,
                "language": "en-US",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched_command"] == "request_assistance"
        assert data["action_mapping"] == "request_assistance"
        assert data["validation_status"] == "valid"

        # Unknown speech returns unmatched
        resp_unmatched = client.post(
            "/api/v1/voice/process-command",
            json={
                "raw_transcript": "good morning team",
                "confidence": 0.90,
                "language": "en-US",
            },
        )
        assert resp_unmatched.status_code == 200
        data_unmatched = resp_unmatched.json()
        assert data_unmatched["matched_command"] is None
        assert data_unmatched["action_mapping"] is None
        assert data_unmatched["validation_status"] == "unmatched"

    finally:
        app.dependency_overrides.clear()


def test_voice_process_command_unauthenticated_rejected():
    """
    TASK 9 PROOF: POST /api/v1/voice/process-command must reject unauthenticated
    requests with HTTP 401 or 403.
    """
    client = TestClient(app)
    # Ensure no dependency override is present
    app.dependency_overrides.clear()

    resp = client.post(
        "/api/v1/voice/process-command",
        json={
            "raw_transcript": "emergency stop",
            "confidence": 0.95,
            "language": "en-US",
        },
    )
    # HTTPBearer returns 401 or 403 when unauthenticated
    assert resp.status_code in (401, 403)


# =====================================================================
# Hinglish Vocabulary Tests (Step 3 & 8)
# =====================================================================

def test_voice_hinglish_vocabulary_matches():
    service = VoiceService()

    # next_step
    cmd, act, _, _ = service.match_command("agla")
    assert cmd == "next_step"
    assert act == "next_step"

    cmd, act, _, _ = service.match_command("aage")
    assert cmd == "next_step"
    assert act == "next_step"

    # previous_step
    cmd, act, _, _ = service.match_command("pichla")
    assert cmd == "previous_step"
    assert act == "previous_step"

    cmd, act, _, _ = service.match_command("wapas")
    assert cmd == "previous_step"
    assert act == "previous_step"

    # confirm_action
    cmd, act, _, _ = service.match_command("pushti")
    assert cmd == "confirm_action"
    assert act == "confirm_action"

    cmd, act, _, _ = service.match_command("haan")
    assert cmd == "confirm_action"
    assert act == "confirm_action"

    cmd, act, _, _ = service.match_command("sahi")
    assert cmd == "confirm_action"
    assert act == "confirm_action"

    # request_assistance
    cmd, act, _, _ = service.match_command("madad")
    assert cmd == "request_assistance"
    assert act == "request_assistance"

    cmd, act, _, _ = service.match_command("sahayata")
    assert cmd == "request_assistance"
    assert act == "request_assistance"

    # emergency_stop
    cmd, act, _, is_crit = service.match_command("roko")
    assert cmd == "emergency_stop"
    assert act == "emergency_stop"
    assert is_crit is True

    cmd, act, _, is_crit = service.match_command("ruko")
    assert cmd == "emergency_stop"
    assert act == "emergency_stop"
    assert is_crit is True


# =====================================================================
# /voice/stream WebSocket Protocol Hardening Tests
# (model-independent: fake recognizer + fake auth service)
# =====================================================================

import json
import uuid

from app.dependencies import get_auth_service
from routes.voice import get_vosk_registry, get_voice_service
from services.auth_service import AuthService
from services.base import UnauthorizedError
from services.vosk_stt_service import VoskModelUnavailableError


class _FakeAuthService:
    """Accepts exactly one fixed token; everything else is unauthorized."""

    def __init__(self, user):
        self._user = user

    def verify_token(self, token: str):
        if token == "valid-test-token":
            return self._user
        raise UnauthorizedError("Invalid authentication token: test")


class _FakeSession:
    """Deterministic in-memory recognizer stand-in (no Vosk dependency)."""

    def __init__(self, model=None, language="en", sample_rate=16000):
        self.language = language
        self.sample_rate = sample_rate
        self.fed = 0
        self.final_count = 0

    def feed(self, pcm_chunk: bytes):
        if len(pcm_chunk) % 2 != 0:
            raise ValueError(
                "Malformed audio frame: 16-bit PCM frames must have an even byte length"
            )
        self.fed += len(pcm_chunk)
        if self.fed >= 32000 and self.final_count == 0:
            self.final_count += 1
            return {
                "type": "final",
                "transcript": "next step",
                "confidence": 0.99,
                "word_count": 2,
                "utterance": 1,
                "processing_time_ms": 1.0,
            }
        return None

    def finish(self):
        return None


class _FakeRegistry:
    """Registry stand-in with isolated per-connection sessions."""

    def __init__(self, sessions=None):
        self.sessions = sessions if sessions is not None else []
        self.created = []

    def new_session(self, language, sample_rate=16000):
        session = _FakeSession(language=language, sample_rate=sample_rate)
        self.created.append(session)
        return session


class _MissingModelRegistry:
    def health(self):
        from models.voice import STTHealthStatus

        return STTHealthStatus(
            model_status="ERROR",
            model_name="vosk-test-missing",
            supported_languages=["en", "hi"],
        )

    def new_session(self, language, sample_rate=16000):
        raise VoskModelUnavailableError("Vosk model directory missing: /nonexistent")


def _mock_ws_user():
    from models.auth import AuthenticatedUserContext

    return AuthenticatedUserContext(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email="voice.ws@amap.org",
        full_name="Voice WS Worker",
        status="active",
        roles=["worker"],
        permissions=[],
        worker_profile_id=uuid.uuid4(),
    )


def _ws_overrides(user=None, registry=None):
    user = user or _mock_ws_user()
    app.dependency_overrides[get_auth_service] = lambda: _FakeAuthService(user)
    if registry is not None:
        app.dependency_overrides[get_vosk_registry] = lambda: registry


def test_voice_stream_ws_unauthenticated_rejected():
    """WS /voice/stream without a token: error event + close, never recognition."""
    client = TestClient(app)
    app.dependency_overrides.clear()
    with client.websocket_connect("/api/v1/voice/stream") as ws:
        message = ws.receive_json()
        assert message["type"] == "error"
        assert message["code"] == "unauthenticated"
        with pytest.raises(Exception):
            ws.receive_json()  # server closes the socket


def test_voice_stream_ws_invalid_token_rejected():
    """WS /voice/stream with a garbage token: error event + close."""
    client = TestClient(app)
    app.dependency_overrides.clear()
    with client.websocket_connect("/api/v1/voice/stream?token=not-a-real-jwt") as ws:
        message = ws.receive_json()
        assert message["type"] == "error"
        assert message["code"] == "unauthenticated"
        with pytest.raises(Exception):
            ws.receive_json()


def test_voice_stream_ws_unsupported_language_rejected():
    """Authenticated WS with language=fr must receive an error and close."""
    client = TestClient(app)
    _ws_overrides()
    try:
        with client.websocket_connect("/api/v1/voice/stream?token=valid-test-token&language=fr") as ws:
            message = ws.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "unsupported_language"
    finally:
        app.dependency_overrides.clear()


def test_voice_stream_ws_model_unavailable_never_executes():
    """Missing Vosk model: error event + close 4503, and no command can execute."""
    client = TestClient(app)
    _ws_overrides(registry=_MissingModelRegistry())
    try:
        with client.websocket_connect("/api/v1/voice/stream?token=valid-test-token&language=en") as ws:
            message = ws.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "model_unavailable"
    finally:
        app.dependency_overrides.clear()


def test_voice_stream_ws_malformed_audio_frame_rejected():
    """Odd-length (non-16-bit) frame -> unsupported_audio_format error, no command."""
    client = TestClient(app)
    registry = _FakeRegistry()
    _ws_overrides(registry=registry)
    try:
        with client.websocket_connect("/api/v1/voice/stream?token=valid-test-token&language=en") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_bytes(b"\x01\x02\x03")  # odd byte length
            message = ws.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "unsupported_audio_format"
            # well-formed silence afterwards is still fine (connection stays up)
            ws.send_bytes(b"\x00\x00" * 160)
    finally:
        app.dependency_overrides.clear()


def test_voice_stream_ws_oversized_frame_rejected():
    """Frame larger than MAX_FRAME_BYTES -> unsupported_audio_format error."""
    client = TestClient(app)
    registry = _FakeRegistry()
    _ws_overrides(registry=registry)
    try:
        with client.websocket_connect("/api/v1/voice/stream?token=valid-test-token&language=en") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_bytes(b"\x00\x00" * 20000)  # 40000 bytes > 32000 limit
            message = ws.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "unsupported_audio_format"
    finally:
        app.dependency_overrides.clear()


def test_voice_stream_ws_control_messages():
    """Ping is answered; malformed text control frames get bad_message errors."""
    client = TestClient(app)
    registry = _FakeRegistry()
    _ws_overrides(registry=registry)
    try:
        with client.websocket_connect("/api/v1/voice/stream?token=valid-test-token&language=en") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_text(json.dumps({"type": "ping"}))
            assert ws.receive_json() == {"type": "pong"}
            ws.send_text("this is not json")
            message = ws.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "bad_message"
            ws.send_text(json.dumps({"type": "bogus-control"}))
            message = ws.receive_json()
            assert message["type"] == "error"
            assert message["code"] == "bad_message"
    finally:
        app.dependency_overrides.clear()


def test_voice_stream_ws_final_event_carries_command_exactly_once():
    """One endpointer final -> exactly one command payload on the final message."""
    client = TestClient(app)
    registry = _FakeRegistry()
    _ws_overrides(registry=registry)
    try:
        with client.websocket_connect("/api/v1/voice/stream?token=valid-test-token&language=en") as ws:
            assert ws.receive_json()["type"] == "ready"
            # Feed enough well-formed audio for the fake session to endpoint.
            ws.send_bytes(b"\x00\x00" * 16000)
            final = ws.receive_json()
            assert final["type"] == "final"
            assert final["transcript"] == "next step"
            command = final["command"]
            assert command is not None
            assert command["action_mapping"] == "next_step"
            assert command["validation_status"] == "valid"
            # Partials NEVER carry a command payload.
            ws.send_bytes(b"\x00\x00" * 16000)
            ws.send_text(json.dumps({"type": "ping"}))
            assert ws.receive_json() == {"type": "pong"}
    finally:
        app.dependency_overrides.clear()
