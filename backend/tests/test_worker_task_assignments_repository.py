from datetime import timedelta
from uuid import uuid4

#from app.database import get_db_connection
from repositories.organizations import OrganizationsRepository
from repositories.tasks import TasksRepository
from repositories.users import UsersRepository
from repositories.worker_profiles import WorkerProfilesRepository
from repositories.worker_task_assignments import (
    WorkerTaskAssignmentsRepository,
)


def test_get_by_id_returns_none_for_unknown_assignment():
    repository = WorkerTaskAssignmentsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_create_and_get_worker_task_assignment():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    tasks = TasksRepository()
    assignments = WorkerTaskAssignmentsRepository()

    organization = None
    user = None
    worker_profile = None
    task = None
    assignment = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-user-{uuid4()}@example.com",
        )

        worker_profile = worker_profiles.create(user["id"])

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        assignment = assignments.create(
            task["id"],
            worker_profile["id"],
        )

        assert assignment is not None
        assert assignment["task_id"] == task["id"]
        assert assignment["worker_profile_id"] == worker_profile["id"]
        assert assignment["status"] == "assigned"

        result = assignments.get_by_id(assignment["id"])

        assert result is not None
        assert result["id"] == assignment["id"]

    finally:
        if assignment is not None:
            assignments.delete_by_id(assignment["id"])

        if task is not None:
            tasks.delete_by_id(task["id"])

        if worker_profile is not None:
            worker_profiles.delete_by_id(worker_profile["id"])

        if user is not None:
            users.delete_by_id(user["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_task_id_contains_created_assignment():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    tasks = TasksRepository()
    assignments = WorkerTaskAssignmentsRepository()

    organization = None
    user = None
    worker_profile = None
    task = None
    assignment = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-user-{uuid4()}@example.com",
        )

        worker_profile = worker_profiles.create(user["id"])

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        assignment = assignments.create(
            task["id"],
            worker_profile["id"],
        )

        results = assignments.list_by_task_id(task["id"])

        assert any(
            item["id"] == assignment["id"]
            for item in results
        )

    finally:
        if assignment is not None:
            assignments.delete_by_id(assignment["id"])

        if task is not None:
            tasks.delete_by_id(task["id"])

        if worker_profile is not None:
            worker_profiles.delete_by_id(worker_profile["id"])

        if user is not None:
            users.delete_by_id(user["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_worker_profile_id_contains_created_assignment():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    tasks = TasksRepository()
    assignments = WorkerTaskAssignmentsRepository()

    organization = None
    user = None
    worker_profile = None
    task = None
    assignment = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-user-{uuid4()}@example.com",
        )

        worker_profile = worker_profiles.create(user["id"])

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        assignment = assignments.create(
            task["id"],
            worker_profile["id"],
        )

        results = assignments.list_by_worker_profile_id(
            worker_profile["id"]
        )

        assert any(
            item["id"] == assignment["id"]
            for item in results
        )

    finally:
        if assignment is not None:
            assignments.delete_by_id(assignment["id"])

        if task is not None:
            tasks.delete_by_id(task["id"])

        if worker_profile is not None:
            worker_profiles.delete_by_id(worker_profile["id"])

        if user is not None:
            users.delete_by_id(user["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_update_status():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    tasks = TasksRepository()
    assignments = WorkerTaskAssignmentsRepository()

    organization = None
    user = None
    worker_profile = None
    task = None
    assignment = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-user-{uuid4()}@example.com",
        )

        worker_profile = worker_profiles.create(user["id"])

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        assignment = assignments.create(
            task["id"],
            worker_profile["id"],
        )

        started_at = assignment["assigned_at"] + timedelta(minutes=1)

        updated = assignments.update_status(
            assignment["id"],
            "in_progress",
            started_at=started_at,
        )

        assert updated is not None
        assert updated["status"] == "in_progress"
        assert updated["started_at"] == started_at
        assert updated["completed_at"] is None

    finally:
        if assignment is not None:
            assignments.delete_by_id(assignment["id"])

        if task is not None:
            tasks.delete_by_id(task["id"])

        if worker_profile is not None:
            worker_profiles.delete_by_id(worker_profile["id"])

        if user is not None:
            users.delete_by_id(user["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_by_id_returns_false_for_unknown_assignment():
    repository = WorkerTaskAssignmentsRepository()

    assert repository.delete_by_id(uuid4()) is False
