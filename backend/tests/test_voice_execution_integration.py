"""
Phase 2 End-to-End Voice Integration Test:
Voice Transcription -> Intent Parsing -> Action Authorization Gateway -> Step Persistence.

Verifies the architectural invariant:
Recognition != Intent != Authorization != Execution
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_active_worker, get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from routes.actions import get_action_execution_service, get_execution_events_repo
from routes.tasks import get_task_service
from services.action_execution_service import ActionExecutionService


@pytest.fixture
def mock_worker():
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    worker_id = uuid.uuid4()
    return AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="voice.worker@amap.org",
        full_name="Voice Test Worker",
        status="active",
        roles=["worker"],
        permissions=["session:read", "session:write"],
        worker_profile_id=worker_id,
    )


def test_voice_end_to_end_authorized_action_and_persistence(mock_worker):
    """
    TASK 8-J PROOF:
    1. A finalized streaming transcript (recognition boundary — real Vosk
       coverage lives in tests/test_vosk_streaming.py and
       tests/test_phase11_voice_e2e.py) is forwarded to /voice/process-command
       -> yields canonical candidate 'next_step'.
    2. Candidate dispatched to /actions/execute -> passes backend safety gate & logs execution event.
    3. Workflow step execution is recorded -> persists completed status.
    """
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: mock_worker
    app.dependency_overrides[get_current_active_worker] = lambda: mock_worker

    # Recognition boundary: finalized transcript as delivered by the
    # /voice/stream WebSocket (Vosk final event).
    stt_data = {
        "transcript": "next step",
        "detected_language": "en",
        "confidence": 0.95,
        "success": True,
    }

    # Track execution events and task step persistence without mocking away the business logic
    mock_events_repo = type("MockEventsRepo", (), {
        "events": [],
        "create": lambda self, **kwargs: (self.events.append(kwargs), {"id": uuid.uuid4(), **kwargs})[-1],
    })()
    app.dependency_overrides[get_execution_events_repo] = lambda: mock_events_repo

    mock_actions_repo = type("MockActionsRepo", (), {
        "get_by_name": lambda self, name: {
            "id": uuid.uuid4(),
            "name": name,
            "display_name": name.replace("_", " ").title(),
            "status": "active",
        },
    })()

    mock_requirements_repo = type("MockReqsRepo", (), {
        "list_by_action_id": lambda self, action_id: [],
    })()
    mock_step_actions_repo = type("MockStepActionsRepo", (), {
        "get_by_ids": lambda self, **kw: None,
        "list_by_workflow_step_id": lambda self, sid: [],
    })()
    mock_task_actions_repo = type("MockTaskActionsRepo", (), {
        "get_by_ids": lambda self, **kw: None,
        "list_by_task_id": lambda self, tid: [],
    })()

    real_action_service = ActionExecutionService(
        actions_repo=mock_actions_repo,
        action_requirements_repo=mock_requirements_repo,
        workflow_step_actions_repo=mock_step_actions_repo,
        task_actions_repo=mock_task_actions_repo,
        execution_events_repo=mock_events_repo,
    )
    app.dependency_overrides[get_action_execution_service] = lambda: real_action_service

    # Mock task service for step persistence
    persisted_steps = []
    mock_task_service = type("MockTaskService", (), {
        "record_step_execution": lambda self, workflow_assignment_id, workflow_step_id, worker_profile_id, status, execution_data: (
            persisted_steps.append({
                "workflow_assignment_id": workflow_assignment_id,
                "workflow_step_id": workflow_step_id,
                "status": status,
            }),
            {"id": uuid.uuid4(), "status": status, "workflow_step_id": workflow_step_id},
        )[-1],
    })()
    app.dependency_overrides[get_task_service] = lambda: mock_task_service

    try:
        # Step A: finalized transcript (from /voice/stream final event)
        raw_transcript = stt_data["transcript"]
        assert raw_transcript == "next step"

        # Step B: POST /voice/process-command
        cmd_resp = client.post(
            "/api/v1/voice/process-command",
            json={
                "raw_transcript": raw_transcript,
                "confidence": stt_data["confidence"],
                "language": stt_data["detected_language"],
            },
        )
        assert cmd_resp.status_code == 200
        cmd_data = cmd_resp.json()
        assert cmd_data["validation_status"] == "valid"
        assert cmd_data["action_mapping"] == "next_step"
        assert cmd_data["requires_confirmation"] is False

        # Step C: POST /actions/execute (Authoritative Execution Gateway)
        workflow_step_id = uuid.uuid4()
        task_id = uuid.uuid4()
        exec_resp = client.post(
            "/api/v1/actions/execute",
            json={
                "action_name": cmd_data["action_mapping"],
                "workflow_step_id": str(workflow_step_id),
                "task_id": str(task_id),
                "parameters": {"from_step": 1, "to_step": 2},
            },
        )
        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()
        assert exec_data["success"] is True
        assert exec_data["action_name"] == "next_step"

        # Verify audit execution event was written
        assert len(mock_events_repo.events) == 1
        assert mock_events_repo.events[0]["event_type"] == "action.next_step.executed"
        assert mock_events_repo.events[0]["worker_profile_id"] == mock_worker.worker_profile_id

        # Step D: Persist workflow step execution
        wf_assign_id = uuid.uuid4()
        persist_resp = client.post(
            f"/api/v1/tasks/workflows/assignments/{wf_assign_id}/steps/{workflow_step_id}/execute",
            json={"status": "completed", "execution_data": {"step_number": 1, "source": "voice"}},
        )
        assert persist_resp.status_code == 201
        assert len(persisted_steps) == 1
        assert persisted_steps[0]["status"] == "completed"

    finally:
        app.dependency_overrides.clear()


def test_voice_hinglish_to_authorized_action_execution(mock_worker):
    """
    Verifies Romanized Hinglish 'agla' correctly resolves to 'next_step'
    and executes through /actions/execute.
    """
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: mock_worker
    app.dependency_overrides[get_current_active_worker] = lambda: mock_worker

    mock_events_repo = type("MockEventsRepo", (), {
        "events": [],
        "create": lambda self, **kwargs: (self.events.append(kwargs), {"id": uuid.uuid4(), **kwargs})[-1],
    })()
    app.dependency_overrides[get_execution_events_repo] = lambda: mock_events_repo

    mock_actions_repo = type("MockActionsRepo", (), {
        "get_by_name": lambda self, name: {
            "id": uuid.uuid4(),
            "name": name,
            "display_name": name.replace("_", " ").title(),
            "status": "active",
        },
    })()

    mock_step_actions_repo = type("MockStepActionsRepo", (), {
        "get_by_ids": lambda self, **kw: None,
        "list_by_workflow_step_id": lambda self, sid: [],
    })()
    mock_task_actions_repo = type("MockTaskActionsRepo", (), {
        "get_by_ids": lambda self, **kw: None,
        "list_by_task_id": lambda self, tid: [],
    })()

    real_action_service = ActionExecutionService(
        actions_repo=mock_actions_repo,
        action_requirements_repo=type("MockReqsRepo", (), {"list_by_action_id": lambda self, aid: []})(),
        workflow_step_actions_repo=mock_step_actions_repo,
        task_actions_repo=mock_task_actions_repo,
        execution_events_repo=mock_events_repo,
    )
    app.dependency_overrides[get_action_execution_service] = lambda: real_action_service

    try:
        # Hinglish command
        cmd_resp = client.post(
            "/api/v1/voice/process-command",
            json={
                "raw_transcript": "agla",
                "confidence": 0.90,
                "language": "hi",
            },
        )
        assert cmd_resp.status_code == 200
        cmd_data = cmd_resp.json()
        assert cmd_data["action_mapping"] == "next_step"

        # Authorized execution
        exec_resp = client.post(
            "/api/v1/actions/execute",
            json={"action_name": cmd_data["action_mapping"]},
        )
        assert exec_resp.status_code == 200
        assert exec_resp.json()["success"] is True
        assert len(mock_events_repo.events) == 1
    finally:
        app.dependency_overrides.clear()


def test_voice_command_requires_confirmation_flow(mock_worker):
    """
    Verifies that medium-confidence speech returns requires_confirmation=True,
    enforcing that the action must NOT be executed until confirmation is obtained.
    """
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: mock_worker

    try:
        # Medium confidence yields requires_confirmation = True
        cmd_resp = client.post(
            "/api/v1/voice/process-command",
            json={
                "raw_transcript": "continue",
                "confidence": 0.65,
                "language": "en",
            },
        )
        assert cmd_resp.status_code == 200
        cmd_data = cmd_resp.json()
        assert cmd_data["action_mapping"] == "next_step"
        assert cmd_data["requires_confirmation"] is True
    finally:
        app.dependency_overrides.clear()
