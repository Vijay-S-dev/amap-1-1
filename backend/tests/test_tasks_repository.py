from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.tasks import TasksRepository


def test_get_by_id_returns_none_for_unknown_task():
    repository = TasksRepository()

    assert repository.get_by_id(uuid4()) is None


def test_create_and_get_task_by_id():
    organizations = OrganizationsRepository()
    tasks = TasksRepository()

    organization = None
    task = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
            "Test task description",
        )

        assert task is not None
        assert task["organization_id"] == organization["id"]
        assert task["status"] == "active"

        result = tasks.get_by_id(task["id"])

        assert result is not None
        assert result["id"] == task["id"]
        assert result["name"] == task["name"]

    finally:
        if task is not None:
            tasks.delete_by_id(task["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_get_by_organization_and_name_returns_task():
    organizations = OrganizationsRepository()
    tasks = TasksRepository()

    organization = None
    task = None
    name = f"test-task-{uuid4()}"

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        task = tasks.create(
            organization["id"],
            name,
        )

        result = tasks.get_by_organization_and_name(
            organization["id"],
            name,
        )

        assert result is not None
        assert result["id"] == task["id"]

    finally:
        if task is not None:
            tasks.delete_by_id(task["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_organization_id_contains_created_task():
    organizations = OrganizationsRepository()
    tasks = TasksRepository()

    organization = None
    task = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        results = tasks.list_by_organization_id(organization["id"])

        assert any(
            item["id"] == task["id"]
            for item in results
        )

    finally:
        if task is not None:
            tasks.delete_by_id(task["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_update_task():
    organizations = OrganizationsRepository()
    tasks = TasksRepository()

    organization = None
    task = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        updated = tasks.update(
            task["id"],
            "Updated task",
            "Updated description",
            "inactive",
        )

        assert updated is not None
        assert updated["id"] == task["id"]
        assert updated["name"] == "Updated task"
        assert updated["description"] == "Updated description"
        assert updated["status"] == "inactive"

    finally:
        if task is not None:
            tasks.delete_by_id(task["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_returns_false_for_unknown_task():
    repository = TasksRepository()

    assert repository.delete_by_id(uuid4()) is False
