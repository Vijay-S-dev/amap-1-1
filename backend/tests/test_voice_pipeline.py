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

    # 2. Spanish commands
    cmd_es, act_es, _, _ = service.match_command("siguiente")
    assert cmd_es == "next_step"
    assert act_es == "next_step"

    cmd_es2, act_es2, _, _ = service.match_command("confirmar")
    assert cmd_es2 == "confirm_action"
    assert act_es2 == "confirm_action"

    cmd_es3, act_es3, _, is_crit = service.match_command("detener")
    assert cmd_es3 == "emergency_stop"
    assert is_crit is True

    # 3. German commands
    cmd_de, act_de, _, _ = service.match_command("weiter")
    assert cmd_de == "next_step"

    cmd_de2, act_de2, _, _ = service.match_command("bestätigen")
    assert cmd_de2 == "confirm_action"

    # 4. Hindi commands
    cmd_hi, act_hi, _, _ = service.match_command("अगला")
    assert cmd_hi == "next_step"

    cmd_hi2, act_hi2, _, _ = service.match_command("पुष्टि")
    assert cmd_hi2 == "confirm_action"

    # 5. Tamil commands
    cmd_ta, act_ta, _, _ = service.match_command("அடுத்து")
    assert cmd_ta == "next_step"

    cmd_ta2, act_ta2, _, _ = service.match_command("உறுதி")
    assert cmd_ta2 == "confirm_action"


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
# /voice/transcribe Endpoint Hardening Tests (Step 1 & 8)
# =====================================================================

def test_voice_transcribe_unauthenticated_rejected():
    """POST /api/v1/voice/transcribe must reject unauthenticated requests with HTTP 401."""
    client = TestClient(app)
    app.dependency_overrides.clear()

    resp = client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("audio.webm", b"fake-audio-content-under-100", "audio/webm")},
    )
    assert resp.status_code in (401, 403)


def test_voice_transcribe_payload_too_large_rejected():
    """POST /api/v1/voice/transcribe must reject payloads > 10MB with HTTP 413."""
    client = TestClient(app)
    mock_user = AuthenticatedUserContext(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email="worker@amap.org",
        full_name="Worker",
        status="active",
        roles=["worker"],
        permissions=[],
        worker_profile_id=uuid.uuid4(),
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    try:
        # Create a payload exceeding 10 MB (10 * 1024 * 1024 + 1 bytes)
        oversized_data = b"0" * (10 * 1024 * 1024 + 1024)
        resp = client.post(
            "/api/v1/voice/transcribe",
            files={"audio": ("large_audio.webm", oversized_data, "audio/webm")},
        )
        assert resp.status_code == 413
        err_msg = resp.json().get("error") or resp.json().get("detail") or ""
        assert "10MB" in err_msg
    finally:
        app.dependency_overrides.clear()


def test_voice_transcribe_unsupported_language_rejected():
    """POST /api/v1/voice/transcribe with language=de must return HTTP 422."""
    client = TestClient(app)
    mock_user = AuthenticatedUserContext(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email="worker@amap.org",
        full_name="Worker",
        status="active",
        roles=["worker"],
        permissions=[],
        worker_profile_id=uuid.uuid4(),
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    try:
        resp = client.post(
            "/api/v1/voice/transcribe",
            data={"language": "de"},
            files={"audio": ("audio.webm", b"x" * 200, "audio/webm")},
        )
        assert resp.status_code == 422
        err_msg = resp.json().get("error") or resp.json().get("detail") or ""
        assert "Only English (en) and Hindi (hi) are supported" in err_msg
    finally:
        app.dependency_overrides.clear()


def test_voice_transcribe_empty_or_small_audio_rejected():
    """POST /api/v1/voice/transcribe with < 100 bytes must return HTTP 422."""
    client = TestClient(app)
    mock_user = AuthenticatedUserContext(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email="worker@amap.org",
        full_name="Worker",
        status="active",
        roles=["worker"],
        permissions=[],
        worker_profile_id=uuid.uuid4(),
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    try:
        resp = client.post(
            "/api/v1/voice/transcribe",
            files={"audio": ("audio.webm", b"too small", "audio/webm")},
        )
        assert resp.status_code == 422
        err_msg = resp.json().get("error") or resp.json().get("detail") or ""
        assert "too small" in err_msg.lower()
    finally:
        app.dependency_overrides.clear()


def test_voice_transcribe_mocked_success():
    """POST /api/v1/voice/transcribe returns valid TranscriptionResult contract."""
    client = TestClient(app)
    mock_user = AuthenticatedUserContext(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email="worker@amap.org",
        full_name="Worker",
        status="active",
        roles=["worker"],
        permissions=[],
        worker_profile_id=uuid.uuid4(),
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    from models.voice import TranscriptionResult
    from routes.voice import get_speech_to_text_service

    class MockSTTService:
        def validate_language(self, lang):
            return "en"

        def transcribe(self, audio_bytes, language=None, filename=None):
            return TranscriptionResult(
                transcript="next step",
                detected_language="en",
                confidence=0.92,
                processing_time_ms=120.5,
                success=True,
            )

    app.dependency_overrides[get_speech_to_text_service] = lambda: MockSTTService()

    try:
        resp = client.post(
            "/api/v1/voice/transcribe",
            data={"language": "en"},
            files={"audio": ("audio.webm", b"x" * 500, "audio/webm")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["transcript"] == "next step"
        assert data["detected_language"] == "en"
        assert data["confidence"] == 0.92
        assert data["processing_time_ms"] == 120.5
    finally:
        app.dependency_overrides.clear()
