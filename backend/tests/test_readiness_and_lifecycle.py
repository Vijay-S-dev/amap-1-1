"""
Unit & Integration Tests for Worker Readiness, State Machine, Fresher vs. Existing Employee Lifecycle,
and Mode-Specific Certification Persistence (Master Spec § 12, § 13, § 38 & Training State Machine § 1 - § 25).
"""

import sys
import uuid
from pathlib import Path
import pytest
from starlette.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.dependencies import get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.worker_profiles import WorkerProfilesRepository
from repositories.worker_readiness import WorkerReadinessRepository

# Seed-equivalent readiness states (must match database/seed/seed.sql section 16)
_ALEX_READINESS = {
    "is_fresher": False,
    "onboarding_completed": True,
    "readiness_status": "ready",
    "interaction_mode": "multimodal",
    "gesture_ready": True,
    "voice_ready": True,
    "multimodal_ready": True,
    "task_training_complete": True,
    "overall_ready": True,
    "completed_stages": [
        "language",
        "accessibility",
        "gesture_calibration",
        "voice_setup",
        "training",
    ],
    "active_preferences": {
        "language": "en",
        "modality": "multimodal",
        "dwell_time_ms": 500,
        "high_contrast": False,
        "text_scale": 1.0,
    },
}

_MARIA_READINESS = {
    "is_fresher": True,
    "onboarding_completed": False,
    "readiness_status": "incomplete",
    "interaction_mode": "multimodal",
    "gesture_ready": False,
    "voice_ready": False,
    "multimodal_ready": False,
    "task_training_complete": False,
    "overall_ready": False,
    "completed_stages": [],
    "active_preferences": {
        "language": "en",
        "modality": "multimodal",
        "dwell_time_ms": 500,
        "high_contrast": False,
        "text_scale": 1.0,
    },
}


@pytest.fixture(autouse=True)
def reset_seeded_readiness():
    """
    Restore the two seeded readiness rows to their seed state before every test.
    Readiness is persisted in PostgreSQL, so certification in one test run would
    otherwise leak into subsequent runs/tests.
    """
    repo = WorkerReadinessRepository()
    repo.upsert(uuid.UUID("d0000000-0000-0000-0000-000000000001"), _ALEX_READINESS)
    repo.upsert(uuid.UUID("d0000000-0000-0000-0000-000000000002"), _MARIA_READINESS)
    yield


@pytest.fixture
def new_worker_profile():
    """Create a real worker profile (org -> user -> profile) for readiness certification tests."""
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()

    organization = organizations.create(f"readiness-test-org-{uuid.uuid4()}")
    user = users.create(
        organization["id"],
        f"readiness-{uuid.uuid4()}@example.com",
        "Readiness Tester",
        "test-password-hash",
    )
    profile = worker_profiles.create(user["id"])

    yield profile["id"]

    worker_profiles.delete_by_id(profile["id"])
    users.delete_by_id(user["id"])
    organizations.delete_by_id(organization["id"])


@pytest.fixture
def mock_auth_context():
    org_id = uuid.UUID("9a61e05d-7a32-4112-9c17-1833d7b42f65")
    user_id = uuid.UUID("c0000000-0000-0000-0000-000000000003")
    worker_id = uuid.UUID("d0000000-0000-0000-0000-000000000001")
    return AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="alex.worker@amap.com",
        full_name="Alex Morgan",
        status="active",
        roles=["worker"],
        permissions=["session:read", "session:write"],
        worker_profile_id=worker_id,
    )


@pytest.fixture
def client(mock_auth_context):
    app.dependency_overrides[get_current_user] = lambda: mock_auth_context
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_existing_worker_readiness_state(client):
    """Verify existing worker (Alex Morgan) is recognized as certified existing employee."""
    alex_id = "d0000000-0000-0000-0000-000000000001"
    resp = client.get(f"/api/v1/workers/{alex_id}/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_fresher"] is False
    assert data["onboarding_completed"] is True
    assert data["readiness_status"] == "ready"
    assert data["overall_ready"] is True
    assert "training" in data["completed_stages"]


def test_fresher_worker_readiness_and_certification(client):
    """Verify fresher (Maria Rodriguez) starts incomplete and can be certified."""
    maria_id = "d0000000-0000-0000-0000-000000000002"
    
    # 1. Initial State: Fresher
    get_resp = client.get(f"/api/v1/workers/{maria_id}/readiness")
    assert get_resp.status_code == 200
    fresher_data = get_resp.json()
    assert fresher_data["is_fresher"] is True
    assert fresher_data["onboarding_completed"] is False
    assert fresher_data["readiness_status"] == "incomplete"

    # 2. Certify Readiness after training completion
    cert_resp = client.post(
        f"/api/v1/workers/{maria_id}/readiness/certify",
        json={
            "selected_language": "hi",
            "selected_modality": "multimodal",
            "calibrated_dwell_ms": 550,
            "training_order_id": "Order #1042 Level 1",
            "gesture_ready": True,
            "voice_ready": True,
            "multimodal_ready": True,
            "task_training_complete": True,
        },
    )
    assert cert_resp.status_code == 200
    cert_data = cert_resp.json()
    assert cert_data["is_fresher"] is False
    assert cert_data["onboarding_completed"] is True
    assert cert_data["readiness_status"] == "ready"
    assert cert_data["overall_ready"] is True
    assert cert_data["active_preferences"]["language"] == "hi"


def test_gesture_only_readiness_does_not_require_voice(client, new_worker_profile):
    """Verify gesture-only training certifies worker without voice readiness (§ 3, § 7, § 8)."""
    worker_id = str(new_worker_profile)
    
    cert_resp = client.post(
        f"/api/v1/workers/{worker_id}/readiness/certify",
        json={
            "selected_language": "en",
            "selected_modality": "gesture",
            "calibrated_dwell_ms": 500,
            "training_order_id": "Order #1042 Level 1",
            "gesture_ready": True,
            "voice_ready": False,  # Voice not completed
            "multimodal_ready": False,
            "task_training_complete": True,
        },
    )
    assert cert_resp.status_code == 200
    data = cert_resp.json()
    assert data["interaction_mode"] == "gesture"
    assert data["gesture_ready"] is True
    assert data["voice_ready"] is False
    assert data["overall_ready"] is True
    assert data["readiness_status"] == "ready"


def test_voice_only_readiness_does_not_require_gesture(client, new_worker_profile):
    """Verify voice-only training certifies worker without gesture readiness (§ 4, § 7, § 8)."""
    worker_id = str(new_worker_profile)
    
    cert_resp = client.post(
        f"/api/v1/workers/{worker_id}/readiness/certify",
        json={
            "selected_language": "hi",
            "selected_modality": "voice",
            "calibrated_dwell_ms": 500,
            "training_order_id": "Order #1042 Level 1",
            "gesture_ready": False,  # Gesture not completed
            "voice_ready": True,
            "multimodal_ready": False,
            "task_training_complete": True,
        },
    )
    assert cert_resp.status_code == 200
    data = cert_resp.json()
    assert data["interaction_mode"] == "voice"
    assert data["gesture_ready"] is False
    assert data["voice_ready"] is True
    assert data["overall_ready"] is True
    assert data["readiness_status"] == "ready"


def test_multimodal_requires_both_and_fusion(client, new_worker_profile):
    """Verify multimodal/both training strictly requires gesture, voice, and fusion (§ 5, § 7, § 8)."""
    worker_id = str(new_worker_profile)
    
    # Missing voice -> not ready
    cert_resp1 = client.post(
        f"/api/v1/workers/{worker_id}/readiness/certify",
        json={
            "selected_language": "en",
            "selected_modality": "multimodal",
            "calibrated_dwell_ms": 500,
            "training_order_id": "Order #1042 Level 1",
            "gesture_ready": True,
            "voice_ready": False,
            "multimodal_ready": False,
            "task_training_complete": True,
        },
    )
    assert cert_resp1.status_code == 200
    assert cert_resp1.json()["overall_ready"] is False

    # All three passed -> ready
    cert_resp2 = client.post(
        f"/api/v1/workers/{worker_id}/readiness/certify",
        json={
            "selected_language": "en",
            "selected_modality": "multimodal",
            "calibrated_dwell_ms": 500,
            "training_order_id": "Order #1042 Level 1",
            "gesture_ready": True,
            "voice_ready": True,
            "multimodal_ready": True,
            "task_training_complete": True,
        },
    )
    assert cert_resp2.status_code == 200
    assert cert_resp2.json()["overall_ready"] is True
    assert cert_resp2.json()["readiness_status"] == "ready"
