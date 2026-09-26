"""PostgreSQL persistence tests for worker readiness (Phase 1).

Verifies that readiness writes go to the `worker_readiness` table, survive
repeated reads, and that a missing worker profile returns HTTP 404 instead of
fabricating state.
"""

from uuid import uuid4

import pytest
from fastapi import status
from starlette.testclient import TestClient

from app.database import get_db_connection
from app.dependencies import get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.worker_profiles import WorkerProfilesRepository
from repositories.worker_readiness import WorkerReadinessRepository


@pytest.fixture
def client():
    """Test client with authenticated user context (readiness routes only need auth)."""
    auth_context = AuthenticatedUserContext(
        user_id=uuid4(),
        organization_id=uuid4(),
        email="readiness-pg@example.com",
        full_name="Readiness PG Tester",
        status="active",
        roles=["admin"],
        permissions=[],
        worker_profile_id=None,
    )
    app.dependency_overrides[get_current_user] = lambda: auth_context
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def readiness_worker():
    """Create a real worker profile (org -> user -> profile) for readiness tests."""
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()

    organization = organizations.create(f"readiness-pg-org-{uuid4()}")
    user = users.create(
        organization["id"],
        f"readiness-pg-{uuid4()}@example.com",
        "Readiness PG Worker",
        "test-password-hash",
    )
    profile = worker_profiles.create(user["id"])

    try:
        yield profile["id"]
    finally:
        worker_profiles.delete_by_id(profile["id"])
        users.delete_by_id(user["id"])
        organizations.delete_by_id(organization["id"])


def _fetch_raw(worker_id):
    """Read the readiness row with an independent SQL query (bypasses repository)."""
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT readiness_status, interaction_mode,
                       gesture_ready, voice_ready, multimodal_ready,
                       active_preferences
                FROM worker_readiness
                WHERE worker_profile_id = %s
                """,
                (worker_id,),
            )
            return cursor.fetchone()


def test_readiness_certify_persists_to_postgres(client, readiness_worker):
    """Certify writes a durable row readable via a fresh repository session."""
    worker_id = readiness_worker
    response = client.post(
        f"/api/v1/workers/{worker_id}/readiness/certify",
        json={
            "selected_language": "en",
            "selected_modality": "multimodal",
            "calibrated_dwell_ms": 480,
            "training_order_id": "Order #9001 Level 1",
            "gesture_ready": True,
            "voice_ready": True,
            "multimodal_ready": True,
            "task_training_complete": True,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["worker_id"] == str(worker_id)
    assert payload["readiness_status"] == "ready"
    assert payload["overall_ready"] is True
    assert payload["active_preferences"]["dwell_time_ms"] == 480

    # Fresh repository read = independent PostgreSQL verification
    row = WorkerReadinessRepository().get(worker_id)
    assert row is not None, "certified readiness row missing from PostgreSQL"
    assert row["readiness_status"] == "ready"
    assert row["voice_ready"] is True
    assert row["active_preferences"]["dwell_time_ms"] == 480

    # Raw SQL verification, independent of repository logic
    raw = _fetch_raw(worker_id)
    assert raw is not None, "worker_readiness row not found by raw SQL"
    assert raw[0] == "ready"
    assert raw[1] == "multimodal"
    assert raw[2] is True and raw[3] is True and raw[4] is True
    assert raw[5]["language"] == "en"


def test_readiness_get_returns_and_creates_persisted_default(client, readiness_worker):
    """GET for an uncertified worker returns defaults AND persists them."""
    worker_id = readiness_worker
    response = client.get(f"/api/v1/workers/{worker_id}/readiness")
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["readiness_status"] == "incomplete"
    assert payload["is_fresher"] is True

    # The default must have been persisted (no in-memory-only response)
    raw = _fetch_raw(worker_id)
    assert raw is not None, "GET did not persist a readiness row"
    assert raw[0] == "incomplete"

    # Second GET returns the same persisted state
    second = client.get(f"/api/v1/workers/{worker_id}/readiness")
    assert second.status_code == status.HTTP_200_OK
    assert second.json()["readiness_status"] == "incomplete"
    assert second.json()["is_fresher"] is True


def test_readiness_unknown_profile_returns_404(client):
    """A non-existent worker profile yields 404, not fabricated defaults."""
    response = client.get(f"/api/v1/workers/{uuid4()}/readiness")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    certify = client.post(
        f"/api/v1/workers/{uuid4()}/readiness/certify",
        json={
            "selected_language": "en",
            "selected_modality": "gesture",
            "calibrated_dwell_ms": 500,
            "training_order_id": "Order #1",
            "gesture_ready": True,
            "task_training_complete": True,
        },
    )
    assert certify.status_code == status.HTTP_404_NOT_FOUND


def test_readiness_repo_upsert_overwrites_existing_row(readiness_worker):
    """Repository upsert replaces values instead of duplicating rows."""
    worker_id = readiness_worker
    repo = WorkerReadinessRepository()

    repo.upsert(
        worker_id,
        {
            "is_fresher": False,
            "onboarding_completed": True,
            "readiness_status": "ready",
            "interaction_mode": "gesture",
            "gesture_ready": True,
            "voice_ready": False,
            "multimodal_ready": False,
            "task_training_complete": True,
            "overall_ready": True,
            "completed_stages": ["language", "accessibility", "gesture_calibration"],
            "active_preferences": {"language": "en", "modality": "gesture"},
        },
    )
    repo.upsert(
        worker_id,
        {
            "is_fresher": False,
            "onboarding_completed": True,
            "readiness_status": "ready",
            "interaction_mode": "voice",
            "gesture_ready": False,
            "voice_ready": True,
            "multimodal_ready": False,
            "task_training_complete": True,
            "overall_ready": True,
            "completed_stages": ["language", "accessibility", "voice_setup"],
            "active_preferences": {"language": "hi", "modality": "voice"},
        },
    )

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM worker_readiness WHERE worker_profile_id = %s",
                (worker_id,),
            )
            count = cursor.fetchone()[0]
    assert count == 1, "upsert created duplicate readiness rows"

    row = repo.get(worker_id)
    assert row["interaction_mode"] == "voice"
    assert row["voice_ready"] is True
    assert row["gesture_ready"] is False
    assert row["active_preferences"]["language"] == "hi"
