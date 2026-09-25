"""
Tests for AMAP Phase 0 Emergency Stop Endpoint and Safety Guarantees (§ Phase 0).

Validates:
- Emergency stop requires authenticated context (fails closed).
- Software prototype safety boundary records execution events and urgent assistance requests.
- Never reports false success when unauthenticated or rejected.
- Software-only safety scope (does not claim physical machinery control).
"""

from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from routes.actions import get_assistance_requests_repo, get_execution_events_repo


@pytest.fixture
def mock_worker_context():
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    worker_id = uuid.uuid4()
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


def test_emergency_stop_unauthenticated_rejected():
    """
    TASK 4 PROOF: Unauthenticated emergency stop request must be rejected.
    Must NOT return success=true without valid authentication.
    """
    client = TestClient(app)
    app.dependency_overrides.clear()

    resp = client.post(
        "/api/v1/actions/emergency-stop",
        json={"reason": "Test emergency stop attempt"},
    )
    assert resp.status_code in (401, 403)
    assert resp.status_code != 200


def test_emergency_stop_authenticated_success(mock_worker_context):
    """
    TASK 4 PROOF: Authenticated emergency stop records execution event,
    creates urgent supervisor assistance request, and returns success=True.
    """
    client = TestClient(app)
    mock_exec_repo = MagicMock()
    mock_assist_repo = MagicMock()

    event_id = uuid.uuid4()
    mock_exec_repo.create.return_value = {
        "id": event_id,
        "organization_id": mock_worker_context.organization_id,
        "worker_profile_id": mock_worker_context.worker_profile_id,
        "event_type": "emergency_stop",
        "event_data": {"reason": "Manual operator stop", "is_emergency": True},
    }

    mock_assist_repo.create.return_value = {
        "id": uuid.uuid4(),
        "organization_id": mock_worker_context.organization_id,
        "worker_profile_id": mock_worker_context.worker_profile_id,
        "status": "open",
        "priority": "urgent",
        "reason": "EMERGENCY STOP: Manual operator stop",
    }

    app.dependency_overrides[get_current_user] = lambda: mock_worker_context
    app.dependency_overrides[get_execution_events_repo] = lambda: mock_exec_repo
    app.dependency_overrides[get_assistance_requests_repo] = lambda: mock_assist_repo

    try:
        resp = client.post(
            "/api/v1/actions/emergency-stop",
            json={
                "reason": "Manual operator stop",
                "work_session_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["event_id"] == str(event_id)
        assert data["eventId"] == str(event_id)
        assert "Software emergency stop" in data["message"]
        # Verify software boundary only - does not claim physical machinery shutdown
        assert "machinery" not in data["message"].lower()

        # Verify execution event recorded
        mock_exec_repo.create.assert_called_once()
        call_kwargs = mock_exec_repo.create.call_args[1]
        assert call_kwargs["event_type"] == "emergency_stop"
        assert call_kwargs["organization_id"] == mock_worker_context.organization_id

        # Verify urgent assistance request created for supervisor visibility
        mock_assist_repo.create.assert_called_once()
        assist_kwargs = mock_assist_repo.create.call_args[1]
        assert assist_kwargs["priority"] == "urgent"

    finally:
        app.dependency_overrides.clear()
