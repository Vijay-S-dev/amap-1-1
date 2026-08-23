from datetime import datetime, timedelta, timezone
from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.worker_profiles import WorkerProfilesRepository
from repositories.workflow_assignments import WorkflowAssignmentsRepository
from repositories.workflow_step_executions import (
    WorkflowStepExecutionsRepository,
)
from repositories.workflow_steps import WorkflowStepsRepository
from repositories.workflows import WorkflowsRepository


def create_test_data():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    workflows = WorkflowsRepository()
    workflow_steps = WorkflowStepsRepository()
    workflow_assignments = WorkflowAssignmentsRepository()
    executions = WorkflowStepExecutionsRepository()

    organization = organizations.create(
        f"test-org-{uuid4()}"
    )

    user = users.create(
        organization["id"],
        f"test-user-{uuid4()}@example.com",
        "Test User",
        "test-password-hash",
    )

    worker_profile = worker_profiles.create(
        user["id"],
    )

    workflow = workflows.create(
        organization["id"],
        f"Test Workflow {uuid4()}",
    )

    workflow_step = workflow_steps.create(
        workflow["id"],
        1,
        f"Test Step {uuid4()}",
    )

    workflow_assignment = workflow_assignments.create(
        workflow["id"],
        worker_profile["id"],
    )

    return {
        "organizations": organizations,
        "users": users,
        "worker_profiles": worker_profiles,
        "workflows": workflows,
        "workflow_steps": workflow_steps,
        "workflow_assignments": workflow_assignments,
        "executions": executions,
        "organization": organization,
        "user": user,
        "worker_profile": worker_profile,
        "workflow": workflow,
        "workflow_step": workflow_step,
        "workflow_assignment": workflow_assignment,
    }


def cleanup_test_data(data, execution=None):
    executions = data["executions"]
    workflow_assignments = data["workflow_assignments"]
    workflow_steps = data["workflow_steps"]
    workflows = data["workflows"]
    worker_profiles = data["worker_profiles"]
    users = data["users"]
    organizations = data["organizations"]

    if execution is not None:
        executions.delete_by_id(execution["id"])

    workflow_assignments.delete_by_id(
        data["workflow_assignment"]["id"]
    )

    workflow_steps.delete_by_id(
        data["workflow_step"]["id"]
    )

    workflows.delete_by_id(
        data["workflow"]["id"]
    )

    worker_profiles.delete_by_id(
        data["worker_profile"]["id"]
    )

    users.delete_by_id(
        data["user"]["id"]
    )

    organizations.delete_by_id(
        data["organization"]["id"]
    )


def test_get_by_id_returns_none_for_unknown_execution():
    repository = WorkflowStepExecutionsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_get_by_assignment_and_step_returns_none_for_unknown_execution():
    repository = WorkflowStepExecutionsRepository()

    assert repository.get_by_assignment_and_step(
        uuid4(),
        uuid4(),
    ) is None


def test_create_and_get_workflow_step_execution():
    data = create_test_data()
    execution = None

    try:
        execution = data["executions"].create(
            data["workflow_assignment"]["id"],
            data["workflow_step"]["id"],
        )

        assert execution is not None
        assert execution["status"] == "pending"

        assert (
            execution["workflow_assignment_id"]
            == data["workflow_assignment"]["id"]
        )

        assert (
            execution["workflow_step_id"]
            == data["workflow_step"]["id"]
        )

        result = data["executions"].get_by_id(
            execution["id"]
        )

        assert result is not None
        assert result["id"] == execution["id"]

        result = data["executions"].get_by_assignment_and_step(
            data["workflow_assignment"]["id"],
            data["workflow_step"]["id"],
        )

        assert result is not None
        assert result["id"] == execution["id"]

    finally:
        cleanup_test_data(data, execution)


def test_list_by_workflow_assignment_id_contains_created_execution():
    data = create_test_data()
    execution = None

    try:
        execution = data["executions"].create(
            data["workflow_assignment"]["id"],
            data["workflow_step"]["id"],
        )

        results = (
            data["executions"].list_by_workflow_assignment_id(
                data["workflow_assignment"]["id"]
            )
        )

        assert any(
            item["id"] == execution["id"]
            for item in results
        )

    finally:
        cleanup_test_data(data, execution)


def test_list_by_workflow_step_id_contains_created_execution():
    data = create_test_data()
    execution = None

    try:
        execution = data["executions"].create(
            data["workflow_assignment"]["id"],
            data["workflow_step"]["id"],
        )

        results = data["executions"].list_by_workflow_step_id(
            data["workflow_step"]["id"]
        )

        assert any(
            item["id"] == execution["id"]
            for item in results
        )

    finally:
        cleanup_test_data(data, execution)


def test_update_status():
    data = create_test_data()
    execution = None

    try:
        execution = data["executions"].create(
            data["workflow_assignment"]["id"],
            data["workflow_step"]["id"],
        )

        started_at = datetime.now(timezone.utc)
        completed_at = started_at + timedelta(minutes=5)

        updated = data["executions"].update_status(
            execution["id"],
            "completed",
            started_at,
            completed_at,
            "Workflow step completed successfully",
        )

        assert updated is not None
        assert updated["id"] == execution["id"]
        assert updated["status"] == "completed"

        assert (
            updated["notes"]
            == "Workflow step completed successfully"
        )

        assert updated["started_at"] is not None
        assert updated["completed_at"] is not None

    finally:
        cleanup_test_data(data, execution)


def test_update_status_returns_none_for_unknown_execution():
    repository = WorkflowStepExecutionsRepository()

    result = repository.update_status(
        uuid4(),
        "completed",
    )

    assert result is None


def test_delete_by_id_returns_true_for_existing_execution():
    data = create_test_data()
    execution = None

    try:
        execution = data["executions"].create(
            data["workflow_assignment"]["id"],
            data["workflow_step"]["id"],
        )

        deleted = data["executions"].delete_by_id(
            execution["id"]
        )

        assert deleted is True

        execution = None

    finally:
        cleanup_test_data(data, execution)


def test_delete_by_id_returns_false_for_unknown_execution():
    repository = WorkflowStepExecutionsRepository()

    assert repository.delete_by_id(uuid4()) is False
