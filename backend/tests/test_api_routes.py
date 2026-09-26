"""
Comprehensive API route integration tests for AMAP (Phase 7).
Tests all endpoints in /api/v1 (Sessions, Tasks, Actions, Interactions, Personalization, Assistance).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_active_worker, get_current_user
from app.main import app
from models.action import ActionExecutionResponse
from models.assistance import AssistancePriority, AssistanceRequestRead, NotificationRead
from models.auth import AuthenticatedUserContext
from models.interaction import MultimodalProcessingResult
from models.session import WorkSessionRead
from models.worker import WorkerPersonalizationRead, WorkerTaskAssignmentRead
from routes.actions import get_action_execution_service
from routes.assistance import get_assistance_service
from routes.interactions import get_interaction_service
from routes.personalization import get_personalization_service
from routes.sessions import get_work_session_service
from routes.tasks import get_task_service
from services.base import ConflictError, SafetyViolationError


@pytest.fixture
def mock_worker_context():
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    worker_id = uuid.uuid4()
    return AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="worker@amap.org",
        full_name="AMAP Worker",
        status="active",
        roles=["worker", "supervisor"],
        permissions=[
            "session:read",
            "session:write",
            "multimodal:input",
            "assistance:request",
            "assistance:resolve",
            "tasks:read",
            "tasks:write",
        ],
        worker_profile_id=worker_id,
    )


@pytest.fixture
def client(mock_worker_context):
    app.dependency_overrides[get_current_user] = lambda: mock_worker_context
    app.dependency_overrides[get_current_active_worker] = lambda: mock_worker_context
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# =====================================================================
# Work Sessions Endpoint Tests
# =====================================================================

def test_sessions_lifecycle_endpoints(client, mock_worker_context):
    mock_service = MagicMock()
    app.dependency_overrides[get_work_session_service] = lambda: mock_service

    session_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    sample_session = WorkSessionRead(
        id=session_id,
        worker_profile_id=mock_worker_context.worker_profile_id,
        status="active",
        started_at=now,
        ended_at=None,
        created_at=now,
        updated_at=now,
    )

    # 1. Start session
    mock_service.start_session.return_value = sample_session
    resp = client.post("/api/v1/sessions/start")
    assert resp.status_code == 201
    assert resp.json()["id"] == str(session_id)

    # 2. Get active session
    mock_service.get_active_session.return_value = sample_session
    resp = client.get("/api/v1/sessions/active")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    # 3. Pause session
    sample_session.status = "paused"
    mock_service.pause_session.return_value = sample_session
    resp = client.post(f"/api/v1/sessions/{session_id}/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"

    # 4. Resume session
    sample_session.status = "active"
    mock_service.resume_session.return_value = sample_session
    resp = client.post(f"/api/v1/sessions/{session_id}/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    # 5. End session
    sample_session.status = "completed"
    sample_session.ended_at = now
    mock_service.end_session.return_value = sample_session
    resp = client.post(f"/api/v1/sessions/{session_id}/end?status=completed")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


# =====================================================================
# Tasks & Workflows Endpoint Tests
# =====================================================================

def test_tasks_and_workflows_endpoints(client, mock_worker_context):
    mock_service = MagicMock()
    app.dependency_overrides[get_task_service] = lambda: mock_service

    assignment_id = uuid.uuid4()
    task_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    assignment = WorkerTaskAssignmentRead(
        id=assignment_id,
        task_id=task_id,
        worker_profile_id=mock_worker_context.worker_profile_id,
        status="active",
        assigned_at=now,
        started_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )

    # 1. Get assigned tasks
    mock_service.get_worker_assignments.return_value = [assignment]
    resp = client.get("/api/v1/tasks/assigned")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 2. Start task assignment
    mock_service.start_task_assignment.return_value = assignment
    resp = client.post(f"/api/v1/tasks/assignments/{assignment_id}/start")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(assignment_id)

    # 3. Complete task assignment
    mock_service.complete_task_assignment.return_value = {
        "id": str(uuid.uuid4()),
        "outcome": "completed",
        "result_data": {"barcode": "ABC"},
    }
    resp = client.post(
        f"/api/v1/tasks/assignments/{assignment_id}/complete",
        json={"outcome": "completed", "result_data": {"barcode": "ABC"}},
    )
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "completed"


# =====================================================================
# Action Execution Gateway Endpoint Tests
# =====================================================================

def test_action_execution_endpoint(client):
    mock_service = MagicMock()
    app.dependency_overrides[get_action_execution_service] = lambda: mock_service

    action_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Success execution
    mock_service.execute_action.return_value = ActionExecutionResponse(
        success=True,
        action_id=action_id,
        action_name="next_step",
        executed_at=now,
        result_data={"status": "executed"},
        feedback_message="Action executed",
    )

    resp = client.post(
        "/api/v1/actions/execute",
        json={"action_name": "next_step", "parameters": {"step": 2}},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Safety violation
    mock_service.execute_action.side_effect = SafetyViolationError("Missing prerequisite")
    err_resp = client.post(
        "/api/v1/actions/execute",
        json={"action_name": "next_step", "parameters": {}},
    )
    assert err_resp.status_code == 422
    assert "Safety Gate Violation" in err_resp.json()["error"]


# =====================================================================
# Multimodal Interaction Endpoint Tests
# =====================================================================

def test_interaction_process_intent_endpoint(client):
    mock_service = MagicMock()
    app.dependency_overrides[get_interaction_service] = lambda: mock_service

    mock_service.process_multimodal_intent.return_value = MultimodalProcessingResult(
        recognized=True,
        action_name="confirm_action",
        confidence=0.88,
        requires_confirmation=False,
        validation_status="valid",
        message="Action recognized",
    )

    resp = client.post(
        "/api/v1/interactions/process-intent",
        json={"mode": "gesture", "raw_intent": "confirm", "confidence": 0.88},
    )
    assert resp.status_code == 200
    assert resp.json()["recognized"] is True
    assert resp.json()["action_name"] == "confirm_action"


# =====================================================================
# Personalization Endpoint Tests
# =====================================================================

def test_personalization_endpoints(client, mock_worker_context):
    mock_service = MagicMock()
    app.dependency_overrides[get_personalization_service] = lambda: mock_service

    pers_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    pers = WorkerPersonalizationRead(
        id=pers_id,
        worker_profile_id=mock_worker_context.worker_profile_id,
        interaction_configuration_id=None,
        personalization_data={"dwell_time": 400},
        status="active",
        created_at=now,
        updated_at=now,
    )

    # 1. Get personalization
    mock_service.get_personalization.return_value = pers
    resp = client.get("/api/v1/personalization/me")
    assert resp.status_code == 200
    assert resp.json()["personalization_data"]["dwell_time"] == 400

    # 2. Evidence analysis
    mock_service.analyze_interaction_evidence.return_value = {
        "status": "evaluated",
        "recommendations": ["Consider voice mode"],
    }
    resp = client.get("/api/v1/personalization/me/evidence")
    assert resp.status_code == 200
    assert resp.json()["status"] == "evaluated"


# =====================================================================
# Assistance and Notification Endpoint Tests
# =====================================================================

def test_assistance_endpoints(client, mock_worker_context):
    mock_service = MagicMock()
    app.dependency_overrides[get_assistance_service] = lambda: mock_service

    req_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    sample_request = AssistanceRequestRead(
        id=req_id,
        organization_id=mock_worker_context.organization_id,
        worker_profile_id=mock_worker_context.worker_profile_id,
        work_session_id=None,
        workflow_assignment_id=None,
        worker_task_assignment_id=None,
        status="open",
        priority=AssistancePriority.NORMAL,
        reason="Help needed",
        request_data={},
        requested_at=now,
        acknowledged_at=None,
        resolved_at=None,
        created_at=now,
        updated_at=now,
    )

    # 1. Create request
    mock_service.create_assistance_request.return_value = sample_request
    resp = client.post(
        "/api/v1/assistance/requests",
        json={"reason": "Help needed", "priority": "normal"},
    )
    assert resp.status_code == 201
    assert resp.json()["reason"] == "Help needed"

    # 2. Acknowledge request
    sample_request.status = "acknowledged"
    sample_request.acknowledged_at = now
    mock_service.acknowledge_request.return_value = sample_request
    resp = client.post(f"/api/v1/assistance/requests/{req_id}/acknowledge")
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"
