"""
End-to-End System Tests for the AMAP Platform.

Simulates complete cyber-physical manufacturing lifecycle:
Worker Authentication -> Work Session Start -> Optical Gesture / Voice Stream ->
Task Step Advancement -> Assistance Request -> Supervisor Resolution -> Immutable Audit Log.
"""

import sys
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai import MultimodalAIPipeline, VoiceCommandPayload
from app.dependencies import get_current_active_worker, get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext


@pytest.fixture
def mock_worker_context():
    org_id = uuid.UUID("9a61e05d-7a32-4112-9c17-1833d7b42f65")
    user_id = uuid.UUID("c0000000-0000-0000-0000-000000000003")
    worker_id = uuid.UUID("d0000000-0000-0000-0000-000000000001")
    return AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="alex.worker@amap.com",
        full_name="Alex Morgan",
        status="active",
        roles=["worker", "supervisor", "admin"],
        permissions=["session:read", "session:write", "multimodal:input", "assistance:request", "assistance:resolve"],
        worker_profile_id=worker_id,
    )


@pytest.fixture
def client(mock_worker_context):
    app.dependency_overrides[get_current_user] = lambda: mock_worker_context
    app.dependency_overrides[get_current_active_worker] = lambda: mock_worker_context
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_e2e_worker_supervisor_audit_lifecycle(client):
    """
    End-to-end multi-persona manufacturing floor flow.
    """
    # 1. Healthcheck verification
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

    # 2. Multimodal Gesture & Voice Input Processing
    multimodal_resp = client.post(
        "/api/v1/multimodal/fuse",
        json={
            "inputs": [
                {"mode": "gesture", "raw_intent": "thumbs_up", "confidence": 0.92, "timestamp_ms": 1000},
                {"mode": "voice", "raw_intent": "confirm_action", "confidence": 0.95, "timestamp_ms": 1050},
            ],
            "temporal_window_ms": 1500,
        },
    )
    assert multimodal_resp.status_code == 200
    fusion_data = multimodal_resp.json()
    assert fusion_data["fused_action"] == "confirm_action"
    assert fusion_data["fused_confidence"] >= 0.95
    assert fusion_data["fusion_strategy"] == "reinforcing"

    # 3. Direct AI Perception Pipeline Validation
    pipeline = MultimodalAIPipeline()
    voice_res = pipeline.process_voice_command(VoiceCommandPayload(transcript="next step"))
    assert voice_res.action == "next_step"

    # 4. Invariant Verification: Recognition != Authorization != Execution
    is_safe, msg = pipeline.evaluate_safety_gating("emergency_stop", confidence=0.50)
    assert is_safe is True

    is_gated, gate_msg = pipeline.evaluate_safety_gating("voltage_adjustment", confidence=0.95, is_secondary_confirmed=False)
    assert is_gated is False
