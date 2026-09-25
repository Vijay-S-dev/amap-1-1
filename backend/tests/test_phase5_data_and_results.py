"""
Phase 5 Comprehensive Verification Test Suite:
Data Management (FR-07), Assignment Management (FR-08), Result Tracking (FR-09), Error Handling (FR-10).

Covers all 18 mandatory audit cases:
1. Result retrieval for authorized worker (200)
2. Result retrieval forbidden for another worker (403)
3. Cancellation sets worker task assignment status to 'cancelled' (MUST FIX #1)
4. Cancellation sets workflow assignment status to 'cancelled'
5. Cancelled assignment cannot execute a step (409 ConflictError)
6. Completed assignment cannot execute a step (409 ConflictError)
7. Step 2 rejected when Step 1 incomplete (409 ConflictError)
8. Step 2 accepted when Step 1 completed (201 Created)
9. Step 3 rejected when Step 2 incomplete (409 ConflictError)
10. Completion rejected when required steps are incomplete (409 ConflictError)
11. Repeated completion on already-completed assignment rejected (409 ConflictError)
12. Organization tenancy enforced for task details (403 Forbidden on org mismatch)
13. Server-computed completed step count overrides client claims
14. Server-computed result integrity with execution duration
15. Dedicated cancel endpoint authorization (403 for unauthorized worker)
16. Cancelled assignment cannot be completed normally (409 ConflictError)
17. Duplicate step execution remains idempotent (201/200 without constraint violation)
18. Duplicate completion does not violate UNIQUE constraint on worker_task_assignment_id
"""

from datetime import datetime, timezone
import uuid
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_active_worker, get_current_user
from app.main import app
from models.auth import AuthenticatedUserContext
from routes.tasks import get_task_service
from services.base import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from services.task_service import TaskService


@pytest.fixture
def test_worker_alex():
    return AuthenticatedUserContext(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email="alex.worker@amap.com",
        full_name="Alex Morgan",
        status="active",
        roles=["worker"],
        permissions=["session:read", "session:write"],
        worker_profile_id=uuid.uuid4(),
    )


@pytest.fixture
def test_worker_bob(test_worker_alex):
    return AuthenticatedUserContext(
        user_id=uuid.uuid4(),
        organization_id=test_worker_alex.organization_id,  # same org
        email="bob.worker@amap.com",
        full_name="Bob Smith",
        status="active",
        roles=["worker"],
        permissions=["session:read", "session:write"],
        worker_profile_id=uuid.uuid4(),  # different worker
    )


@pytest.fixture
def test_supervisor(test_worker_alex):
    return AuthenticatedUserContext(
        user_id=uuid.uuid4(),
        organization_id=test_worker_alex.organization_id,
        email="supervisor@amap.com",
        full_name="Marcus Vance",
        status="active",
        roles=["supervisor"],
        permissions=["session:read", "session:write"],
        worker_profile_id=None,
    )


# ==============================================================================
# 1 & 2. Result Retrieval Authorization (FR-09 / MUST FIX #2)
# ==============================================================================

def test_get_task_result_authorized_worker(test_worker_alex):
    """Authorized worker can retrieve their own assignment result via GET /assignments/{id}/result."""
    assignment_id = uuid.uuid4()
    result_id = uuid.uuid4()

    mock_service = MagicMock(spec=TaskService)
    mock_service.get_task_result.return_value = {
        "id": str(result_id),
        "worker_task_assignment_id": str(assignment_id),
        "outcome": "completed",
        "result_data": {"completed_steps": 3, "total_steps": 3},
        "notes": "Assembly verified",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    app.dependency_overrides[get_current_user] = lambda: test_worker_alex
    app.dependency_overrides[get_task_service] = lambda: mock_service

    client = TestClient(app)
    resp = client.get(f"/api/v1/tasks/assignments/{assignment_id}/result")
    assert resp.status_code == 200
    data = resp.json()
    assert data["outcome"] == "completed"
    assert data["result_data"]["completed_steps"] == 3


def test_get_task_result_forbidden_for_other_worker(test_worker_bob):
    """A worker attempting to retrieve another worker's result receives 403 Forbidden."""
    assignment_id = uuid.uuid4()

    mock_service = MagicMock(spec=TaskService)
    mock_service.get_task_result.side_effect = UnauthorizedError("Task assignment does not belong to this worker.")

    app.dependency_overrides[get_current_user] = lambda: test_worker_bob
    app.dependency_overrides[get_task_service] = lambda: mock_service

    client = TestClient(app)
    resp = client.get(f"/api/v1/tasks/assignments/{assignment_id}/result")
    assert resp.status_code == 403
    assert "does not belong" in resp.text


# ==============================================================================
# 3 & 4. Cancellation Status Lifecycle (MUST FIX #1)
# ==============================================================================

def test_cancellation_sets_both_worker_and_workflow_assignment_to_cancelled(test_worker_alex):
    """Cancellation must transition worker task assignment to 'cancelled' (NOT 'completed') and sync workflow assignment."""
    assignment_id = uuid.uuid4()
    task_id = uuid.uuid4()
    wf_id = uuid.uuid4()
    wf_assign_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_assign_repo = MagicMock()
    mock_assign_repo.get_by_id.return_value = {
        "id": assignment_id,
        "worker_profile_id": test_worker_alex.worker_profile_id,
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
        "result_data": {"outcome": "cancelled"},
        "notes": "Worker cancelled shift",
    }

    mock_tw_repo = MagicMock()
    mock_tw_repo.list_by_task_id.return_value = [{"workflow_id": wf_id}]

    mock_wf_assign_repo = MagicMock()
    mock_wf_assign_repo.list_by_worker_profile_id.return_value = [
        {"id": wf_assign_id, "workflow_id": wf_id, "status": "in_progress"}
    ]

    mock_wf_steps_repo = MagicMock()
    mock_wf_steps_repo.list_by_workflow_id.return_value = []

    service = TaskService(
        task_assignments_repo=mock_assign_repo,
        task_results_repo=mock_results_repo,
        task_workflows_repo=mock_tw_repo,
        workflow_assignments_repo=mock_wf_assign_repo,
        workflow_steps_repo=mock_wf_steps_repo,
    )

    res = service.complete_task_assignment(
        assignment_id=assignment_id,
        worker_profile_id=test_worker_alex.worker_profile_id,
        outcome="cancelled",
        notes="Worker cancelled shift",
    )

    assert res["outcome"] == "cancelled"
    # Verify worker assignment status was updated to 'cancelled'
    mock_assign_repo.update_status.assert_called_once()
    call_kwargs = mock_assign_repo.update_status.call_args[1]
    assert call_kwargs["status"] == "cancelled"
    assert call_kwargs["status"] != "completed"

    # Verify linked workflow assignment was synchronized to 'cancelled'
    mock_wf_assign_repo.update_status.assert_called_once_with(
        assignment_id=wf_assign_id,
        status="cancelled",
    )


# ==============================================================================
# 5 & 6. Block Step Execution After Terminal State (MUST FIX #3)
# ==============================================================================

def test_cannot_execute_step_on_cancelled_assignment(test_worker_alex):
    """Step execution on a cancelled workflow assignment must be rejected with ConflictError (409)."""
    wf_assign_id = uuid.uuid4()
    step_id = uuid.uuid4()
    wf_id = uuid.uuid4()

    mock_wf_assign_repo = MagicMock()
    mock_wf_assign_repo.get_by_id.return_value = {
        "id": wf_assign_id,
        "worker_profile_id": test_worker_alex.worker_profile_id,
        "workflow_id": wf_id,
        "status": "cancelled",
    }

    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.list_by_worker_profile_id.return_value = []

    service = TaskService(
        workflow_assignments_repo=mock_wf_assign_repo,
        task_assignments_repo=mock_task_assign_repo,
    )

    with pytest.raises(ConflictError) as exc_info:
        service.record_step_execution(
            workflow_assignment_id=wf_assign_id,
            workflow_step_id=step_id,
            worker_profile_id=test_worker_alex.worker_profile_id,
        )
    assert "cancelled" in str(exc_info.value).lower()


def test_cannot_execute_step_on_completed_assignment(test_worker_alex):
    """Step execution on an already completed workflow assignment must be rejected with ConflictError (409)."""
    wf_assign_id = uuid.uuid4()
    step_id = uuid.uuid4()
    wf_id = uuid.uuid4()

    mock_wf_assign_repo = MagicMock()
    mock_wf_assign_repo.get_by_id.return_value = {
        "id": wf_assign_id,
        "worker_profile_id": test_worker_alex.worker_profile_id,
        "workflow_id": wf_id,
        "status": "completed",
    }

    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.list_by_worker_profile_id.return_value = []

    service = TaskService(
        workflow_assignments_repo=mock_wf_assign_repo,
        task_assignments_repo=mock_task_assign_repo,
    )

    with pytest.raises(ConflictError) as exc_info:
        service.record_step_execution(
            workflow_assignment_id=wf_assign_id,
            workflow_step_id=step_id,
            worker_profile_id=test_worker_alex.worker_profile_id,
        )
    assert "completed" in str(exc_info.value).lower()


# ==============================================================================
# 7, 8 & 9. Step Ordering Enforcement (MUST FIX #4)
# ==============================================================================

def test_step_order_step_2_rejected_when_step_1_incomplete(test_worker_alex):
    """Step 2 must be rejected if Step 1 is not completed."""
    wf_assign_id = uuid.uuid4()
    wf_id = uuid.uuid4()
    step1_id = uuid.uuid4()
    step2_id = uuid.uuid4()

    mock_wf_assign_repo = MagicMock()
    mock_wf_assign_repo.get_by_id.return_value = {
        "id": wf_assign_id,
        "worker_profile_id": test_worker_alex.worker_profile_id,
        "workflow_id": wf_id,
        "status": "in_progress",
    }
    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.list_by_worker_profile_id.return_value = []

    mock_steps_repo = MagicMock()
    mock_steps_repo.get_by_id.return_value = {
        "id": step2_id,
        "workflow_id": wf_id,
        "step_order": 2,
        "title": "Insert Bolts",
    }
    mock_steps_repo.list_by_workflow_id.return_value = [
        {"id": step1_id, "step_order": 1, "title": "Inspect Housing"},
        {"id": step2_id, "step_order": 2, "title": "Insert Bolts"},
    ]

    mock_exec_repo = MagicMock()
    mock_exec_repo.get_by_assignment_and_step.return_value = None
    # Step 1 is incomplete (no completed records)
    mock_exec_repo.list_by_workflow_assignment_id.return_value = []

    service = TaskService(
        workflow_assignments_repo=mock_wf_assign_repo,
        task_assignments_repo=mock_task_assign_repo,
        workflow_steps_repo=mock_steps_repo,
        step_executions_repo=mock_exec_repo,
    )

    with pytest.raises(ConflictError) as exc_info:
        service.record_step_execution(
            workflow_assignment_id=wf_assign_id,
            workflow_step_id=step2_id,
            worker_profile_id=test_worker_alex.worker_profile_id,
            status="completed",
        )
    assert "Step order violation" in str(exc_info.value)
    assert "Step 1" in str(exc_info.value)


def test_step_order_step_2_accepted_when_step_1_completed(test_worker_alex):
    """Step 2 must succeed once Step 1 is marked completed."""
    wf_assign_id = uuid.uuid4()
    wf_id = uuid.uuid4()
    step1_id = uuid.uuid4()
    step2_id = uuid.uuid4()

    mock_wf_assign_repo = MagicMock()
    mock_wf_assign_repo.get_by_id.return_value = {
        "id": wf_assign_id,
        "worker_profile_id": test_worker_alex.worker_profile_id,
        "workflow_id": wf_id,
        "status": "in_progress",
    }
    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.list_by_worker_profile_id.return_value = []

    mock_steps_repo = MagicMock()
    mock_steps_repo.get_by_id.return_value = {
        "id": step2_id,
        "workflow_id": wf_id,
        "step_order": 2,
        "title": "Insert Bolts",
    }
    mock_steps_repo.list_by_workflow_id.return_value = [
        {"id": step1_id, "step_order": 1, "title": "Inspect Housing"},
        {"id": step2_id, "step_order": 2, "title": "Insert Bolts"},
    ]

    mock_exec_repo = MagicMock()
    mock_exec_repo.get_by_assignment_and_step.return_value = None
    # Step 1 is recorded as completed
    mock_exec_repo.list_by_workflow_assignment_id.return_value = [
        {"workflow_step_id": step1_id, "status": "completed"}
    ]
    mock_exec_repo.create.return_value = {
        "id": uuid.uuid4(),
        "workflow_assignment_id": wf_assign_id,
        "workflow_step_id": step2_id,
        "status": "completed",
    }

    service = TaskService(
        workflow_assignments_repo=mock_wf_assign_repo,
        task_assignments_repo=mock_task_assign_repo,
        workflow_steps_repo=mock_steps_repo,
        step_executions_repo=mock_exec_repo,
    )

    res = service.record_step_execution(
        workflow_assignment_id=wf_assign_id,
        workflow_step_id=step2_id,
        worker_profile_id=test_worker_alex.worker_profile_id,
        status="completed",
    )
    assert res["status"] == "completed"


def test_step_order_step_3_rejected_when_step_2_incomplete(test_worker_alex):
    """Step 3 must be rejected if Step 1 is complete but Step 2 is incomplete."""
    wf_assign_id = uuid.uuid4()
    wf_id = uuid.uuid4()
    step1_id = uuid.uuid4()
    step2_id = uuid.uuid4()
    step3_id = uuid.uuid4()

    mock_wf_assign_repo = MagicMock()
    mock_wf_assign_repo.get_by_id.return_value = {
        "id": wf_assign_id,
        "worker_profile_id": test_worker_alex.worker_profile_id,
        "workflow_id": wf_id,
        "status": "in_progress",
    }
    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.list_by_worker_profile_id.return_value = []

    mock_steps_repo = MagicMock()
    mock_steps_repo.get_by_id.return_value = {
        "id": step3_id,
        "workflow_id": wf_id,
        "step_order": 3,
        "title": "Torque Fasteners",
    }
    mock_steps_repo.list_by_workflow_id.return_value = [
        {"id": step1_id, "step_order": 1, "title": "Step 1"},
        {"id": step2_id, "step_order": 2, "title": "Step 2"},
        {"id": step3_id, "step_order": 3, "title": "Step 3"},
    ]

    mock_exec_repo = MagicMock()
    mock_exec_repo.get_by_assignment_and_step.return_value = None
    # Only step 1 completed, step 2 missing
    mock_exec_repo.list_by_workflow_assignment_id.return_value = [
        {"workflow_step_id": step1_id, "status": "completed"}
    ]

    service = TaskService(
        workflow_assignments_repo=mock_wf_assign_repo,
        task_assignments_repo=mock_task_assign_repo,
        workflow_steps_repo=mock_steps_repo,
        step_executions_repo=mock_exec_repo,
    )

    with pytest.raises(ConflictError) as exc_info:
        service.record_step_execution(
            workflow_assignment_id=wf_assign_id,
            workflow_step_id=step3_id,
            worker_profile_id=test_worker_alex.worker_profile_id,
            status="completed",
        )
    assert "Step order violation" in str(exc_info.value)
    assert "Step 2" in str(exc_info.value)


# ==============================================================================
# 10 & 11. Completion Integrity & Prerequisite Validation
# ==============================================================================

def test_completion_rejected_when_required_steps_incomplete(test_worker_alex):
    """Task completion with outcome 'completed' is rejected if any workflow step is incomplete."""
    assignment_id = uuid.uuid4()
    task_id = uuid.uuid4()
    wf_id = uuid.uuid4()
    wf_assign_id = uuid.uuid4()

    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.get_by_id.return_value = {
        "id": assignment_id,
        "worker_profile_id": test_worker_alex.worker_profile_id,
        "task_id": task_id,
        "status": "in_progress",
    }
    mock_tw_repo = MagicMock()
    mock_tw_repo.list_by_task_id.return_value = [{"workflow_id": wf_id}]

    mock_wf_steps_repo = MagicMock()
    mock_wf_steps_repo.list_by_workflow_id.return_value = [
        {"id": uuid.uuid4(), "step_order": 1},
        {"id": uuid.uuid4(), "step_order": 2},
    ]

    mock_wf_assign_repo = MagicMock()
    mock_wf_assign_repo.list_by_worker_profile_id.return_value = [
        {"id": wf_assign_id, "workflow_id": wf_id, "status": "in_progress"}
    ]

    # Only 1 step completed out of 2
    mock_exec_repo = MagicMock()
    mock_exec_repo.list_by_workflow_assignment_id.return_value = [
        {"workflow_step_id": uuid.uuid4(), "status": "completed"}
    ]

    service = TaskService(
        task_assignments_repo=mock_task_assign_repo,
        task_workflows_repo=mock_tw_repo,
        workflow_steps_repo=mock_wf_steps_repo,
        workflow_assignments_repo=mock_wf_assign_repo,
        step_executions_repo=mock_exec_repo,
    )

    with pytest.raises(ConflictError) as exc_info:
        service.complete_task_assignment(
            assignment_id=assignment_id,
            worker_profile_id=test_worker_alex.worker_profile_id,
            outcome="completed",
        )
    assert "only" in str(exc_info.value).lower()
    assert "required steps are completed" in str(exc_info.value).lower()


def test_repeated_completion_on_already_completed_assignment_rejected(test_worker_alex):
    """Calling complete_task_assignment on an already completed task must raise ConflictError."""
    assignment_id = uuid.uuid4()

    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.get_by_id.return_value = {
        "id": assignment_id,
        "worker_profile_id": test_worker_alex.worker_profile_id,
        "status": "completed",
    }

    service = TaskService(task_assignments_repo=mock_task_assign_repo)

    with pytest.raises(ConflictError) as exc_info:
        service.complete_task_assignment(
            assignment_id=assignment_id,
            worker_profile_id=test_worker_alex.worker_profile_id,
            outcome="completed",
        )
    assert "already completed" in str(exc_info.value).lower()


# ==============================================================================
# 12. Organization Tenancy Boundary (MUST FIX #5)
# ==============================================================================

def test_organization_tenancy_enforced_for_task_details(test_worker_alex):
    """A user cannot access task metadata belonging to another organization."""
    task_id = uuid.uuid4()
    other_org_id = uuid.uuid4()

    mock_tasks_repo = MagicMock()
    mock_tasks_repo.get_by_id.return_value = {
        "id": task_id,
        "organization_id": other_org_id,
        "name": "Classified Prototype Assembly",
    }

    service = TaskService(tasks_repo=mock_tasks_repo)

    with pytest.raises(UnauthorizedError) as exc_info:
        service.get_task_details(
            task_id=task_id,
            organization_id=test_worker_alex.organization_id,  # different org
        )
    assert "organization" in str(exc_info.value).lower()


# ==============================================================================
# 13 & 14. Server-Computed Result Data Integrity (SHOULD FIX #8)
# ==============================================================================

def test_server_computed_result_data_overrides_false_client_claims(test_worker_alex):
    """Server accurately computes completed_steps and duration from persisted database records."""
    assignment_id = uuid.uuid4()
    task_id = uuid.uuid4()
    wf_id = uuid.uuid4()
    wf_assign_id = uuid.uuid4()
    step1_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.get_by_id.return_value = {
        "id": assignment_id,
        "worker_profile_id": test_worker_alex.worker_profile_id,
        "task_id": task_id,
        "status": "in_progress",
        "started_at": now,
    }
    mock_tw_repo = MagicMock()
    mock_tw_repo.list_by_task_id.return_value = [{"workflow_id": wf_id}]

    mock_wf_steps_repo = MagicMock()
    mock_wf_steps_repo.list_by_workflow_id.return_value = [
        {"id": step1_id, "step_order": 1}
    ]

    mock_wf_assign_repo = MagicMock()
    mock_wf_assign_repo.list_by_worker_profile_id.return_value = [
        {"id": wf_assign_id, "workflow_id": wf_id, "status": "in_progress"}
    ]

    mock_exec_repo = MagicMock()
    mock_exec_repo.list_by_workflow_assignment_id.return_value = [
        {"workflow_step_id": step1_id, "status": "completed"}
    ]

    mock_results_repo = MagicMock()
    mock_results_repo.get_by_worker_task_assignment_id.return_value = None
    mock_results_repo.create.side_effect = lambda **kwargs: kwargs

    service = TaskService(
        task_assignments_repo=mock_task_assign_repo,
        task_results_repo=mock_results_repo,
        task_workflows_repo=mock_tw_repo,
        workflow_steps_repo=mock_wf_steps_repo,
        workflow_assignments_repo=mock_wf_assign_repo,
        step_executions_repo=mock_exec_repo,
    )

    # Client falsely claims 99 completed steps
    res = service.complete_task_assignment(
        assignment_id=assignment_id,
        worker_profile_id=test_worker_alex.worker_profile_id,
        outcome="completed",
        result_data={"completed_steps": 99},
    )

    result_data = res["result_data"]
    # Server authority overrides client's 99
    assert result_data["completed_steps"] == 1
    assert result_data["total_steps"] == 1
    assert "duration_seconds" in result_data


# ==============================================================================
# 15 & 16. Cancel Endpoint Authorization & Subsequent Completion Guard
# ==============================================================================

def test_cancel_endpoint_rejects_unauthorized_worker(test_worker_bob):
    """Calling POST /assignments/{id}/cancel on another worker's assignment returns 403."""
    assignment_id = uuid.uuid4()

    mock_service = MagicMock(spec=TaskService)
    mock_service.cancel_task_assignment.side_effect = UnauthorizedError("Task assignment does not belong to this worker.")

    app.dependency_overrides[get_current_active_worker] = lambda: test_worker_bob
    app.dependency_overrides[get_task_service] = lambda: mock_service

    client = TestClient(app)
    resp = client.post(
        f"/api/v1/tasks/assignments/{assignment_id}/cancel",
        json={"notes": "Cancel attempt"},
    )
    assert resp.status_code == 403


def test_cancelled_assignment_cannot_be_completed_normally(test_worker_alex):
    """An assignment with status 'cancelled' cannot be subsequently completed with 'completed'."""
    assignment_id = uuid.uuid4()

    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.get_by_id.return_value = {
        "id": assignment_id,
        "worker_profile_id": test_worker_alex.worker_profile_id,
        "status": "cancelled",
    }

    service = TaskService(task_assignments_repo=mock_task_assign_repo)

    with pytest.raises(ConflictError) as exc_info:
        service.complete_task_assignment(
            assignment_id=assignment_id,
            worker_profile_id=test_worker_alex.worker_profile_id,
            outcome="completed",
        )
    assert "cancelled" in str(exc_info.value).lower()


# ==============================================================================
# 17 & 18. Idempotency Invariants
# ==============================================================================

def test_duplicate_step_execution_remains_idempotent(test_worker_alex):
    """Duplicate execution of an already completed step returns cleanly without error."""
    wf_assign_id = uuid.uuid4()
    wf_id = uuid.uuid4()
    step_id = uuid.uuid4()
    exec_id = uuid.uuid4()

    mock_wf_assign_repo = MagicMock()
    mock_wf_assign_repo.get_by_id.return_value = {
        "id": wf_assign_id,
        "worker_profile_id": test_worker_alex.worker_profile_id,
        "workflow_id": wf_id,
        "status": "in_progress",
    }
    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.list_by_worker_profile_id.return_value = []

    mock_steps_repo = MagicMock()
    mock_steps_repo.get_by_id.return_value = {
        "id": step_id,
        "workflow_id": wf_id,
        "step_order": 1,
    }

    existing_execution = {
        "id": exec_id,
        "workflow_assignment_id": wf_assign_id,
        "workflow_step_id": step_id,
        "status": "completed",
    }

    mock_exec_repo = MagicMock()
    mock_exec_repo.get_by_assignment_and_step.return_value = existing_execution
    mock_exec_repo.update_status.return_value = existing_execution

    service = TaskService(
        workflow_assignments_repo=mock_wf_assign_repo,
        task_assignments_repo=mock_task_assign_repo,
        workflow_steps_repo=mock_steps_repo,
        step_executions_repo=mock_exec_repo,
    )

    res = service.record_step_execution(
        workflow_assignment_id=wf_assign_id,
        workflow_step_id=step_id,
        worker_profile_id=test_worker_alex.worker_profile_id,
        status="completed",
    )
    assert res["id"] == exec_id
    mock_exec_repo.create.assert_not_called()


def test_duplicate_completion_updates_existing_task_result_idempotently(test_worker_alex):
    """When an existing task_results record is found, update() is called instead of duplicate create()."""
    assignment_id = uuid.uuid4()
    result_id = uuid.uuid4()

    mock_task_assign_repo = MagicMock()
    mock_task_assign_repo.get_by_id.return_value = {
        "id": assignment_id,
        "worker_profile_id": test_worker_alex.worker_profile_id,
        "task_id": uuid.uuid4(),
        "status": "in_progress",
    }
    mock_tw_repo = MagicMock()
    mock_tw_repo.list_by_task_id.return_value = []

    mock_results_repo = MagicMock()
    mock_results_repo.get_by_worker_task_assignment_id.return_value = {
        "id": result_id,
        "worker_task_assignment_id": assignment_id,
        "outcome": "completed",
    }
    mock_results_repo.update.return_value = {
        "id": result_id,
        "worker_task_assignment_id": assignment_id,
        "outcome": "completed",
        "notes": "Updated note",
    }

    service = TaskService(
        task_assignments_repo=mock_task_assign_repo,
        task_results_repo=mock_results_repo,
        task_workflows_repo=mock_tw_repo,
    )

    res = service.complete_task_assignment(
        assignment_id=assignment_id,
        worker_profile_id=test_worker_alex.worker_profile_id,
        outcome="completed",
        notes="Updated note",
    )
    assert res["id"] == result_id
    mock_results_repo.create.assert_not_called()
    mock_results_repo.update.assert_called_once()
