"""
Tests for AMAP Voice Input Pipeline (Phase 10).
Covers speech command normalization, phonetic/fuzzy keyword matching, confidence thresholding,
safety confirmation gating, and the voice API endpoint.
"""

from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from models.voice import VoiceCommandPayload
from services.voice_service import VoiceService


# =====================================================================
# Exact & Vocabulary Match Tests
# =====================================================================

def test_voice_exact_matches():
    service = VoiceService()

    # Next step
    cmd, action, score, is_crit = service.match_command("next step")
    assert cmd == "next_step"
    assert action == "next_step"
    assert score == 1.0
    assert is_crit is False

    # Confirm action
    cmd, action, score, is_crit = service.match_command("confirm")
    assert cmd == "confirm_action"
    assert action == "confirm_action"
    assert score == 1.0

    # Cancel action (safety critical)
    cmd, action, score, is_crit = service.match_command("cancel")
    assert cmd == "cancel_action"
    assert action == "cancel_action"
    assert score == 1.0
    assert is_crit is True

    # Emergency stop (safety critical)
    cmd, action, score, is_crit = service.match_command("emergency stop")
    assert cmd == "emergency_stop"
    assert is_crit is True

    # Assistance
    cmd, action, score, is_crit = service.match_command("call supervisor")
    assert cmd == "request_assistance"
    assert action == "request_assistance"


# =====================================================================
# Fuzzy Matching & Noise Tolerance Tests
# =====================================================================

def test_voice_fuzzy_matching():
    service = VoiceService()

    # Slurred/abbreviated "nxt stp"
    cmd, action, score, _ = service.match_command("nxt stp")
    assert cmd == "next_step"
    assert score >= 0.85

    # Conversational phrasing "please pause session now"
    cmd, action, score, _ = service.match_command("please pause session now")
    assert cmd == "pause_session"
    assert score >= 0.60

    # Minor typo "approv"
    cmd, action, score, _ = service.match_command("approv")
    assert cmd == "confirm_action"
    assert score >= 0.80


# =====================================================================
# Confidence Tiering & Safety Gating Tests
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

    # 4. Unrecognized background chatter
    p4 = VoiceCommandPayload(raw_transcript="what is the weather in London today", confidence=0.90)
    r4 = service.process_command(p4)
    assert r4.matched_command is None
    assert r4.validation_status == "unmatched"


# =====================================================================
# Voice API Endpoint Tests
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

    finally:
        app.dependency_overrides.clear()
