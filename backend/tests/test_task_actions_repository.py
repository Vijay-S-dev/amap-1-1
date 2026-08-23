from uuid import uuid4

from repositories.actions import ActionsRepository
from repositories.organizations import OrganizationsRepository
from repositories.task_actions import TaskActionsRepository
from repositories.tasks import TasksRepository


def test_get_by_ids_returns_none_for_unknown_link():
    repository = TaskActionsRepository()

    assert repository.get_by_ids(uuid4(), uuid4()) is None


def test_create_and_get_task_action():
    organizations = OrganizationsRepository()
    actions = ActionsRepository()
    tasks = TasksRepository()
    task_actions = TaskActionsRepository()

    organization = None
    action = None
    task = None
    link = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        action = actions.create(
            f"test-action-{uuid4()}",
            f"Test Action {uuid4()}",
        )

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        link = task_actions.create(
            task["id"],
            action["id"],
        )

        assert link is not None
        assert link["task_id"] == task["id"]
        assert link["action_id"] == action["id"]

        result = task_actions.get_by_ids(
            task["id"],
            action["id"],
        )

        assert result is not None
        assert result["task_id"] == task["id"]
        assert result["action_id"] == action["id"]

    finally:
        if link is not None:
            task_actions.delete(task["id"], action["id"])

        if task is not None:
            tasks.delete_by_id(task["id"])

        if action is not None:
            actions.delete_by_id(action["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_task_id_contains_created_link():
    organizations = OrganizationsRepository()
    actions = ActionsRepository()
    tasks = TasksRepository()
    task_actions = TaskActionsRepository()

    organization = None
    action = None
    task = None
    link = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        action = actions.create(
            f"test-action-{uuid4()}",
            f"Test Action {uuid4()}",
        )

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        link = task_actions.create(task["id"], action["id"])

        results = task_actions.list_by_task_id(task["id"])

        assert any(
            item["action_id"] == action["id"]
            for item in results
        )

    finally:
        if link is not None:
            task_actions.delete(task["id"], action["id"])

        if task is not None:
            tasks.delete_by_id(task["id"])

        if action is not None:
            actions.delete_by_id(action["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_action_id_contains_created_link():
    organizations = OrganizationsRepository()
    actions = ActionsRepository()
    tasks = TasksRepository()
    task_actions = TaskActionsRepository()

    organization = None
    action = None
    task = None
    link = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        action = actions.create(
            f"test-action-{uuid4()}",
            f"Test Action {uuid4()}",
        )

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        link = task_actions.create(task["id"], action["id"])

        results = task_actions.list_by_action_id(action["id"])

        assert any(
            item["task_id"] == task["id"]
            for item in results
        )

    finally:
        if link is not None:
            task_actions.delete(task["id"], action["id"])

        if task is not None:
            tasks.delete_by_id(task["id"])

        if action is not None:
            actions.delete_by_id(action["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_returns_false_for_unknown_link():
    repository = TaskActionsRepository()

    assert repository.delete(uuid4(), uuid4()) is False
