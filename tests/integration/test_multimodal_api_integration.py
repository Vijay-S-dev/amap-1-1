"""
Integration Tests for Cross-Modal API and Multi-Tenant Repositories.
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
        roles=["worker", "admin"],
        permissions=["session:read", "session:write", "multimodal:input"],
        worker_profile_id=worker_id,
    )


@pytest.fixture
def client(mock_worker_context):
    app.dependency_overrides[get_current_user] = lambda: mock_worker_context
    app.dependency_overrides[get_current_active_worker] = lambda: mock_worker_context
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_multimodal_spatial_voice_integration(client):
    """
    Test combining spatial gesture pointer target with voice confirmation command.
    """
    resp = client.post(
        "/api/v1/multimodal/fuse",
        json={
            "inputs": [
                {
                    "mode": "gesture",
                    "raw_intent": "pointing",
                    "confidence": 0.88,
                    "timestamp_ms": 1000,
                },
                {
                    "mode": "voice",
                    "raw_intent": "confirm_action",
                    "confidence": 0.94,
                    "timestamp_ms": 1050,
                },
            ],
            "temporal_window_ms": 1500,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fused_action"] == "confirm_action"
    assert data["validation_status"] == "valid"


def test_multimodal_single_gesture_frame_processing(client):
    """
    Test processing standalone optical hand gesture frame via /gestures/process-frame.
    """
    resp = client.post(
        "/api/v1/gestures/process-frame",
        json={
            "landmarks": [{"x": 0.5, "y": 0.5, "z": 0.0} for _ in range(21)],
            "handedness": "Right",
            "timestamp_ms": 1000,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "detected_gesture" in data
    assert "confidence" in data
