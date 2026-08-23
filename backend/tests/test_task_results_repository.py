from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.tasks import TasksRepository
from repositories.task_results import TaskResultsRepository
from repositories.users import UsersRepository
from repositories.worker_profiles import WorkerProfilesRepository
from repositories.worker_task_assignments import (
    WorkerTaskAssignmentsRepository,
)


def create_test_assignment():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    tasks = TasksRepository()
    assignments = WorkerTaskAssignmentsRepository()

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
        user["id"]
    )

    task = tasks.create(
        organization["id"],
        f"test-task-{uuid4()}",
    )

    assignment = assignments.create(
        task["id"],
        worker_profile["id"],
    )

    return {
        "organization": organization,
        "user": user,
        "worker_profile": worker_profile,
        "task": task,
        "assignment": assignment,
    }


def cleanup_test_assignment(data):
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    tasks = TasksRepository()
    assignments = WorkerTaskAssignmentsRepository()

    assignment = data["assignment"]
    task = data["task"]
    worker_profile = data["worker_profile"]
    user = data["user"]
    organization = data["organization"]

    assignments.delete_by_id(assignment["id"])
    tasks.delete_by_id(task["id"])
    worker_profiles.delete_by_id(worker_profile["id"])
    users.delete_by_id(user["id"])
    organizations.delete_by_id(organization["id"])


def test_get_by_id_returns_none_for_unknown_task_result():
    repository = TaskResultsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_get_by_worker_task_assignment_id_returns_none_for_unknown_assignment():
    repository = TaskResultsRepository()

    assert repository.get_by_worker_task_assignment_id(
        uuid4()
    ) is None


def test_create_and_get_task_result():
    repository = TaskResultsRepository()
    data = create_test_assignment()
    task_result = None

    try:
        task_result = repository.create(
            data["assignment"]["id"],
            "completed",
            {"score": 100},
            "Task completed successfully",
        )

        assert task_result is not None
        assert task_result["worker_task_assignment_id"] == (
            data["assignment"]["id"]
        )
        assert task_result["outcome"] == "completed"
        assert task_result["result_data"] == {"score": 100}
        assert task_result["notes"] == "Task completed successfully"

        result = repository.get_by_id(task_result["id"])

        assert result is not None
        assert result["id"] == task_result["id"]

    finally:
        if task_result is not None:
            repository.delete_by_id(task_result["id"])

        cleanup_test_assignment(data)


def test_get_by_worker_task_assignment_id_returns_created_result():
    repository = TaskResultsRepository()
    data = create_test_assignment()
    task_result = None

    try:
        task_result = repository.create(
            data["assignment"]["id"],
            "failed",
            {"error": "test error"},
            "Task failed",
        )

        result = repository.get_by_worker_task_assignment_id(
            data["assignment"]["id"]
        )

        assert result is not None
        assert result["id"] == task_result["id"]
        assert result["outcome"] == "failed"

    finally:
        if task_result is not None:
            repository.delete_by_id(task_result["id"])

        cleanup_test_assignment(data)


def test_list_by_outcome_contains_created_result():
    repository = TaskResultsRepository()
    data = create_test_assignment()
    task_result = None

    try:
        task_result = repository.create(
            data["assignment"]["id"],
            "partial",
            {"progress": 50},
            "Task partially completed",
        )

        results = repository.list_by_outcome("partial")

        assert any(
            item["id"] == task_result["id"]
            for item in results
        )

    finally:
        if task_result is not None:
            repository.delete_by_id(task_result["id"])

        cleanup_test_assignment(data)


def test_update_task_result():
    repository = TaskResultsRepository()
    data = create_test_assignment()
    task_result = None

    try:
        task_result = repository.create(
            data["assignment"]["id"],
            "completed",
            {"score": 50},
            "Original result",
        )

        updated = repository.update(
            task_result["id"],
            "partial",
            {"score": 75},
            "Updated result",
        )

        assert updated is not None
        assert updated["id"] == task_result["id"]
        assert updated["outcome"] == "partial"
        assert updated["result_data"] == {"score": 75}
        assert updated["notes"] == "Updated result"

    finally:
        if task_result is not None:
            repository.delete_by_id(task_result["id"])

        cleanup_test_assignment(data)


def test_update_returns_none_for_unknown_task_result():
    repository = TaskResultsRepository()

    result = repository.update(
        uuid4(),
        "completed",
        {"score": 100},
        "Unknown result",
    )

    assert result is None


def test_delete_returns_false_for_unknown_task_result():
    repository = TaskResultsRepository()

    assert repository.delete_by_id(uuid4()) is False
