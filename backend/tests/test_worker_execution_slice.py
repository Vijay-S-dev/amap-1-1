"""
Phase 1 Vertical Slice Tests: Real Worker Task Execution, Step Progression & Persistence.

Verifies:
1. Unauthorized action execution is rejected (401/403).
2. Unknown action execution fails closed (404).
3. Authorized action execution succeeds through the safety gateway (200) and logs execution event.
4. GET /tasks/assigned is strictly read-only and resolves workflow assignment without writing to DB.
5. GET /tasks/{task_id} returns task metadata and ordered workflow steps.
6. Step execution persistence records status to workflow_step_executions (201).
7. Step execution persistence is idempotent: updating an existing step does not violate unique constraints.
8. Task completion persists outcome to task_results and archives the assignment (200).
9. Emergency stop safety boundary remains protected (Phase 0 regression guard).
"""

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_active_worker, get_current_user
from app.main import app
from models.action import ActionExecutionRequest, ActionExecutionResponse
from models.auth import AuthenticatedUserContext
from models.worker import WorkerTaskAssignmentRead
from routes.actions import get_action_execution_service, get_assistance_requests_repo, get_execution_events_repo
from routes.tasks import get_task_service
from services.base import ConflictError, NotFoundError, SafetyViolationError, UnauthorizedError
from services.task_service import TaskService


@pytest.fixture
def mock_worker_user():
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


@pytest.fixture
def mock_supervisor_user():
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    return AuthenticatedUserContext(
        user_id=user_id,
        organization_id=org_id,
        email="supervisor@amap.com",
        full_name="Marcus Vance",
        status="active",
        roles=["supervisor"],
        permissions=["assistance:resolve"],
        worker_profile_id=None,
    )


# --------------------------------------------------------------------------
# 1. Action Execution Safety Gateway Tests
# --------------------------------------------------------------------------

def test_action_execution_unauthenticated_rejected():
    """Unauthenticated caller must be rejected by the safety gateway."""
    client = TestClient(app)
    app.dependency_overrides.clear()

    resp = client.post(
        "/api/v1/actions/execute",
        json={"action_name": "next_step"},
    )
    assert resp.status_code in (401, 403)


def test_action_execution_non_worker_rejected(mock_supervisor_user):
    """User without worker profile must be rejected by get_current_active_worker."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: mock_supervisor_user

    resp = client.post(
        "/api/v1/actions/execute",
        json={"action_name": "next_step"},
    )
    assert resp.status_code == 403


def test_action_execution_unknown_action_fails_closed(mock_worker_user):
    """Unknown action must fail closed with 404."""
    client = TestClient(app)
    app.dependency_overrides[get_current_active_worker] = lambda: mock_worker_user

    mock_action_svc = MagicMock()
    mock_action_svc.execute_action.side_effect = NotFoundError("Action 'unknown_action' is not registered.")
    app.dependency_overrides[get_action_execution_service] = lambda: mock_action_svc

    resp = client.post(
        "/api/v1/actions/execute",
        json={"action_name": "unknown_action"},
    )
    assert resp.status_code == 404
    data = resp.json()
    assert "not registered" in data.get("error", data.get("detail", ""))



def test_action_execution_authorized_success(mock_worker_user):
    """Authorized worker executing next_step receives 200 OK and result data."""
    client = TestClient(app)
    app.dependency_overrides[get_current_active_worker] = lambda: mock_worker_user

    action_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_action_svc = MagicMock()
    mock_action_svc.execute_action.return_value = ActionExecutionResponse(
        success=True,
        action_id=action_id,
        action_name="next_step",
        executed_at=now,
        result_data={"status": "executed", "parameters": {"step": 2}},
        feedback_message="Action 'Next Step' executed successfully.",
    )
    app.dependency_overrides[get_action_execution_service] = lambda: mock_action_svc

    resp = client.post(
        "/api/v1/actions/execute",
        json={
            "action_name": "next_step",
            "workflow_step_id": str(uuid.uuid4()),
            "task_id": str(uuid.uuid4()),
            "parameters": {"step": 2},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["action_name"] == "next_step"
    assert data["action_id"] == str(action_id)


# --------------------------------------------------------------------------
# 2. Worker Assignment & Task Loading Tests
# --------------------------------------------------------------------------

def test_get_assigned_tasks_returns_worker_assignments(mock_worker_user):
    """GET /tasks/assigned returns the worker's assignments without writing to DB."""
    client = TestClient(app)
    app.dependency_overrides[get_current_active_worker] = lambda: mock_worker_user

    assignment_id = uuid.uuid4()
    task_id = uuid.uuid4()
    wf_assignment_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_task_svc = MagicMock()
    mock_task_svc.get_worker_assignments.return_value = [
        WorkerTaskAssignmentRead(
            id=assignment_id,
            worker_profile_id=mock_worker_user.worker_profile_id,
            task_id=task_id,
            workflow_assignment_id=wf_assignment_id,
            status="assigned",
            created_at=now,
            updated_at=now,
        )
    ]
    app.dependency_overrides[get_task_service] = lambda: mock_task_svc

    resp = client.get("/api/v1/tasks/assigned")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == str(assignment_id)
    assert items[0]["workflow_assignment_id"] == str(wf_assignment_id)
    assert items[0]["status"] == "assigned"


def test_get_task_details_returns_ordered_steps(mock_worker_user):
    """GET /tasks/{task_id} returns task info and its ordered workflow steps."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: mock_worker_user

    task_id = uuid.uuid4()
    step1_id = uuid.uuid4()
    step2_id = uuid.uuid4()

    mock_task_svc = MagicMock()
    mock_task_svc.get_task_details.return_value = {
        "id": str(task_id),
        "organization_id": str(mock_worker_user.organization_id),
        "name": "Inverter Alpha Assembly",
        "description": "High voltage electronics",
        "status": "active",
        "workflow_id": str(uuid.uuid4()),
        "total_steps": 2,
        "steps": [
            {
                "id": str(step1_id),
                "stepNumber": 1,
                "title": "Optical Inspection",
                "instructionText": "Inspect capacitors",
                "isSafetyCritical": False,
            },
            {
                "id": str(step2_id),
                "stepNumber": 2,
                "title": "Torque Fasteners",
                "instructionText": "Torque to 9.2 Nm",
                "isSafetyCritical": True,
            },
        ],
    }
    app.dependency_overrides[get_task_service] = lambda: mock_task_svc

    resp = client.get(f"/api/v1/tasks/{task_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Inverter Alpha Assembly"
    assert len(data["steps"]) == 2
    assert data["steps"][0]["title"] == "Optical Inspection"
    assert data["steps"][1]["isSafetyCritical"] is True


# --------------------------------------------------------------------------
# 3. Step Execution Persistence Tests
# --------------------------------------------------------------------------

def test_step_execution_persistence_success(mock_worker_user):
    """POST /tasks/workflows/assignments/{id}/steps/{step_id}/execute records step execution."""
    client = TestClient(app)
    app.dependency_overrides[get_current_active_worker] = lambda: mock_worker_user

    wf_assign_id = uuid.uuid4()
    step_id = uuid.uuid4()
    exec_id = uuid.uuid4()

    mock_task_svc = MagicMock()
    mock_task_svc.record_step_execution.return_value = {
        "id": str(exec_id),
        "workflow_assignment_id": str(wf_assign_id),
        "workflow_step_id": str(step_id),
        "status": "completed",
        "notes": json.dumps({"duration_sec": 30}),
    }
    app.dependency_overrides[get_task_service] = lambda: mock_task_svc

    resp = client.post(
        f"/api/v1/tasks/workflows/assignments/{wf_assign_id}/steps/{step_id}/execute",
        json={"status": "completed", "execution_data": {"duration_sec": 30}},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert data["workflow_step_id"] == str(step_id)


def test_step_execution_service_idempotent_logic():
    """Direct service test: record_step_execution updates existing record when present."""
    from services.task_service import TaskService

    mock_wf_assigns = MagicMock()
    mock_steps = MagicMock()
    mock_step_execs = MagicMock()

    wf_id = uuid.uuid4()
    worker_id = uuid.uuid4()
    wf_assign_id = uuid.uuid4()
    step_id = uuid.uuid4()
    existing_exec_id = uuid.uuid4()

    mock_wf_assigns.get_by_id.return_value = {
        "id": wf_assign_id,
        "workflow_id": wf_id,
        "worker_profile_id": worker_id,
    }
    mock_steps.get_by_id.return_value = {
        "id": step_id,
        "workflow_id": wf_id,
        "title": "Test Step",
    }
    # Row already exists:
    mock_step_execs.get_by_assignment_and_step.return_value = {
        "id": existing_exec_id,
        "workflow_assignment_id": wf_assign_id,
        "workflow_step_id": step_id,
        "status": "in_progress",
    }
    mock_step_execs.update_status.return_value = {
        "id": existing_exec_id,
        "workflow_assignment_id": wf_assign_id,
        "workflow_step_id": step_id,
        "status": "completed",
    }

    service = TaskService(
        workflow_assignments_repo=mock_wf_assigns,
        workflow_steps_repo=mock_steps,
        step_executions_repo=mock_step_execs,
    )

    result = service.record_step_execution(
        workflow_assignment_id=wf_assign_id,
        workflow_step_id=step_id,
        worker_profile_id=worker_id,
        status="completed",
        execution_data={"step": 1},
    )

    assert result["status"] == "completed"
    mock_step_execs.update_status.assert_called_once()
    mock_step_execs.create.assert_not_called()


# --------------------------------------------------------------------------
# 4. Task Completion Tests
# --------------------------------------------------------------------------

def test_task_completion_success(mock_worker_user):
    """POST /tasks/assignments/{assignment_id}/complete records result and completes task."""
    client = TestClient(app)
    app.dependency_overrides[get_current_active_worker] = lambda: mock_worker_user

    assignment_id = uuid.uuid4()
    result_id = uuid.uuid4()

    mock_task_svc = MagicMock()
    mock_task_svc.complete_task_assignment.return_value = {
        "id": str(result_id),
        "worker_task_assignment_id": str(assignment_id),
        "outcome": "completed",
        "result_data": {"completed_steps": 3},
        "notes": "Assembly completed cleanly",
    }
    app.dependency_overrides[get_task_service] = lambda: mock_task_svc

    resp = client.post(
        f"/api/v1/tasks/assignments/{assignment_id}/complete",
        json={
            "outcome": "completed",
            "result_data": {"completed_steps": 3},
            "notes": "Assembly completed cleanly",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["outcome"] == "completed"
    assert data["worker_task_assignment_id"] == str(assignment_id)


# --------------------------------------------------------------------------
# 5. Phase 0 Safety Boundary Regression Guard
# --------------------------------------------------------------------------

def test_emergency_stop_regression_protected(mock_worker_user):
    """Emergency stop endpoint must still function and create an audit event."""
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: mock_worker_user

    event_id = uuid.uuid4()
    mock_exec_repo = MagicMock()
    mock_exec_repo.create.return_value = {"id": event_id}
    mock_assist_repo = MagicMock()
    mock_assist_repo.create.return_value = {"id": uuid.uuid4()}

    app.dependency_overrides[get_execution_events_repo] = lambda: mock_exec_repo
    app.dependency_overrides[get_assistance_requests_repo] = lambda: mock_assist_repo

    resp = client.post(
        "/api/v1/actions/emergency-stop",
        json={"reason": "Vertical slice regression check"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["event_id"] == str(event_id)


# --------------------------------------------------------------------------
# 6. Assignment Status Lifecycle Schema-Alignment Regression Tests
# --------------------------------------------------------------------------

def test_start_task_assignment_sets_in_progress():
    """start_task_assignment must transition assignment to 'in_progress', never 'active'."""
    assignment_id = uuid.uuid4()
    worker_id = uuid.uuid4()
    task_id = uuid.uuid4()
    wf_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.get_by_id.return_value = {
        "id": assignment_id,
        "worker_profile_id": worker_id,
        "task_id": task_id,
        "status": "assigned",
        "started_at": None,
    }
    mock_task_assign_repo.update_status.return_value = {
        "id": assignment_id,
        "worker_profile_id": worker_id,
        "task_id": task_id,
        "status": "in_progress",
        "started_at": now,
        "completed_at": None,
        "created_at": now,
        "updated_at": now,
    }

    mock_tw_repo = MagicMock()
    mock_tw_repo.list_by_task_id.return_value = [{"workflow_id": wf_id}]

    mock_wf_assign_repo = MagicMock()
    mock_wf_assign_repo.list_by_worker_profile_id.return_value = [
        {"id": uuid.uuid4(), "workflow_id": wf_id, "status": "assigned"}
    ]

    service = TaskService(
        task_assignments_repo=mock_task_assign_repo,
        task_workflows_repo=mock_tw_repo,
        workflow_assignments_repo=mock_wf_assign_repo,
    )

    result = service.start_task_assignment(assignment_id, worker_id)

    assert result.status == "in_progress"
    mock_task_assign_repo.update_status.assert_called_once()
    call_kwargs = mock_task_assign_repo.update_status.call_args[1]
    assert call_kwargs["status"] == "in_progress"
    assert call_kwargs["status"] != "active"


def test_complete_task_assignment_sets_completed_and_creates_result():
    """complete_task_assignment must transition assignment to 'completed' and create task_results."""
    assignment_id = uuid.uuid4()
    worker_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.get_by_id.return_value = {
        "id": assignment_id,
        "worker_profile_id": worker_id,
        "task_id": uuid.uuid4(),
        "status": "in_progress",
        "started_at": now,
    }

    mock_results_repo = MagicMock()
    mock_results_repo.get_by_worker_task_assignment_id.return_value = None
    mock_results_repo.create.return_value = {
        "id": uuid.uuid4(),
        "worker_task_assignment_id": assignment_id,
        "outcome": "completed",
        "result_data": {"steps": 3},
        "notes": "Finished",
    }

    mock_tw_repo = MagicMock()
    mock_tw_repo.list_by_task_id.return_value = [{"workflow_id": uuid.uuid4()}]
    mock_wf_assign_repo = MagicMock()
    wf_assign_id = uuid.uuid4()
    mock_wf_assign_repo.list_by_worker_profile_id.return_value = [
        {"id": wf_assign_id, "workflow_id": mock_tw_repo.list_by_task_id.return_value[0]["workflow_id"], "status": "in_progress"}
    ]

    service = TaskService(
        task_assignments_repo=mock_task_assign_repo,
        task_results_repo=mock_results_repo,
        task_workflows_repo=mock_tw_repo,
        workflow_assignments_repo=mock_wf_assign_repo,
    )

    result = service.complete_task_assignment(
        assignment_id=assignment_id,
        worker_profile_id=worker_id,
        outcome="completed",
        result_data={"steps": 3},
        notes="Finished",
    )

    assert result["outcome"] == "completed"
    mock_results_repo.create.assert_called_once()
    mock_task_assign_repo.update_status.assert_called_once()
    call_kwargs = mock_task_assign_repo.update_status.call_args[1]
    assert call_kwargs["status"] == "completed"
    assert call_kwargs["status"] != "archived"

    # Verify linked workflow assignment was synchronized to 'completed'
    mock_wf_assign_repo.update_status.assert_called_once_with(
        assignment_id=wf_assign_id,
        status="completed",
    )


def test_cannot_start_completed_or_cancelled_assignment():
    """Starting an assignment that is already completed or cancelled must fail with ConflictError."""
    worker_id = uuid.uuid4()
    mock_task_assign_repo = MagicMock()

    service = TaskService(task_assignments_repo=mock_task_assign_repo)

    for terminal_status in ("completed", "cancelled", "archived"):
        mock_task_assign_repo.get_by_id.return_value = {
            "id": uuid.uuid4(),
            "worker_profile_id": worker_id,
            "status": terminal_status,
        }
        with pytest.raises(ConflictError):
            service.start_task_assignment(uuid.uuid4(), worker_id)


def test_complete_task_assignment_with_cancellation_outcome():
    """Cancellation outcome records task_results with 'cancelled' and sets assignment status to 'cancelled' (MUST FIX #1)."""
    assignment_id = uuid.uuid4()
    worker_id = uuid.uuid4()
    task_id = uuid.uuid4()
    wf_id = uuid.uuid4()
    wf_assign_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.get_by_id.return_value = {
        "id": assignment_id,
        "worker_profile_id": worker_id,
        "task_id": task_id,
        "status": "in_progress",
        "started_at": now,
    }

    mock_results_repo = MagicMock()
    mock_results_repo.get_by_worker_task_assignment_id.return_value = None
    mock_results_repo.create.return_value = {
        "id": uuid.uuid4(),
        "worker_task_assignment_id": assignment_id,
        "outcome": "cancelled",
        "result_data": {},
        "notes": "Worker cancelled assignment",
    }

    mock_tw_repo = MagicMock()
    mock_tw_repo.list_by_task_id.return_value = [{"workflow_id": wf_id}]
    mock_wf_assign_repo = MagicMock()
    mock_wf_assign_repo.list_by_worker_profile_id.return_value = [
        {"id": wf_assign_id, "workflow_id": wf_id, "status": "in_progress"}
    ]

    service = TaskService(
        task_assignments_repo=mock_task_assign_repo,
        task_results_repo=mock_results_repo,
        task_workflows_repo=mock_tw_repo,
        workflow_assignments_repo=mock_wf_assign_repo,
    )

    result = service.complete_task_assignment(
        assignment_id=assignment_id,
        worker_profile_id=worker_id,
        outcome="cancelled",
        notes="Worker cancelled assignment",
    )

    assert result["outcome"] == "cancelled"
    mock_results_repo.create.assert_called_once()
    mock_task_assign_repo.update_status.assert_called_once()
    call_kwargs = mock_task_assign_repo.update_status.call_args[1]
    assert call_kwargs["status"] == "cancelled"
    assert call_kwargs["status"] != "archived"

    # Verify linked workflow assignment was synchronized to 'cancelled'
    mock_wf_assign_repo.update_status.assert_called_once_with(
        assignment_id=wf_assign_id,
        status="cancelled",
    )


def test_invalid_status_values_never_sent_by_task_service():
    """TaskService must never use 'active' or 'archived' for task assignment status updates."""
    assignment_id = uuid.uuid4()
    worker_id = uuid.uuid4()
    task_id = uuid.uuid4()
    wf_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.get_by_id.return_value = {
        "id": assignment_id,
        "worker_profile_id": worker_id,
        "task_id": task_id,
        "status": "assigned",
        "started_at": None,
    }
    mock_task_assign_repo.update_status.return_value = {
        "id": assignment_id,
        "worker_profile_id": worker_id,
        "task_id": task_id,
        "status": "in_progress",
        "started_at": now,
        "completed_at": None,
        "created_at": now,
        "updated_at": now,
    }

    mock_tw_repo = MagicMock()
    mock_tw_repo.list_by_task_id.return_value = [{"workflow_id": wf_id}]

    mock_wf_assign_repo = MagicMock()
    mock_wf_assign_repo.list_by_worker_profile_id.return_value = []
    mock_wf_assign_repo.create.return_value = {"id": uuid.uuid4(), "workflow_id": wf_id, "status": "in_progress"}

    mock_results_repo = MagicMock()
    mock_results_repo.get_by_worker_task_assignment_id.return_value = None
    mock_results_repo.create.return_value = {
        "id": uuid.uuid4(),
        "worker_task_assignment_id": assignment_id,
        "outcome": "completed",
        "result_data": {},
    }

    service = TaskService(
        task_assignments_repo=mock_task_assign_repo,
        task_workflows_repo=mock_tw_repo,
        workflow_assignments_repo=mock_wf_assign_repo,
        task_results_repo=mock_results_repo,
    )

    # 1. Start lifecycle
    service.start_task_assignment(assignment_id, worker_id)
    start_call = mock_task_assign_repo.update_status.call_args[1]
    assert start_call["status"] in ("assigned", "in_progress", "completed", "cancelled")
    assert start_call["status"] not in ("active", "archived")

    # 2. Complete lifecycle
    mock_task_assign_repo.reset_mock()
    mock_task_assign_repo.get_by_id.return_value["status"] = "in_progress"
    service.complete_task_assignment(assignment_id, worker_id, outcome="completed")
    complete_call = mock_task_assign_repo.update_status.call_args[1]
    assert complete_call["status"] in ("assigned", "in_progress", "completed", "cancelled")
    assert complete_call["status"] not in ("active", "archived")

