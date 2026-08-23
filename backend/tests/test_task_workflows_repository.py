from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.task_workflows import TaskWorkflowsRepository
from repositories.tasks import TasksRepository
from repositories.workflows import WorkflowsRepository


def test_get_by_ids_returns_none_for_unknown_link():
    repository = TaskWorkflowsRepository()

    assert repository.get_by_ids(
        uuid4(),
        uuid4(),
    ) is None


def test_create_and_get_task_workflow():
    organizations = OrganizationsRepository()
    tasks = TasksRepository()
    workflows = WorkflowsRepository()
    task_workflows = TaskWorkflowsRepository()

    organization = None
    task = None
    workflow = None
    link = None

    try:
        organization = organizations.create(
            f"test-org-{uuid4()}"
        )

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        link = task_workflows.create(
            task["id"],
            workflow["id"],
        )

        assert link is not None
        assert link["task_id"] == task["id"]
        assert link["workflow_id"] == workflow["id"]

        result = task_workflows.get_by_ids(
            task["id"],
            workflow["id"],
        )

        assert result is not None
        assert result["task_id"] == task["id"]
        assert result["workflow_id"] == workflow["id"]

    finally:
        if link is not None:
            task_workflows.delete(
                task["id"],
                workflow["id"],
            )

        if task is not None:
            tasks.delete_by_id(task["id"])

        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_task_id_contains_created_link():
    organizations = OrganizationsRepository()
    tasks = TasksRepository()
    workflows = WorkflowsRepository()
    task_workflows = TaskWorkflowsRepository()

    organization = None
    task = None
    workflow = None
    link = None

    try:
        organization = organizations.create(
            f"test-org-{uuid4()}"
        )

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        link = task_workflows.create(
            task["id"],
            workflow["id"],
        )

        results = task_workflows.list_by_task_id(
            task["id"]
        )

        assert any(
            item["workflow_id"] == workflow["id"]
            for item in results
        )

    finally:
        if link is not None:
            task_workflows.delete(
                task["id"],
                workflow["id"],
            )

        if task is not None:
            tasks.delete_by_id(task["id"])

        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_workflow_id_contains_created_link():
    organizations = OrganizationsRepository()
    tasks = TasksRepository()
    workflows = WorkflowsRepository()
    task_workflows = TaskWorkflowsRepository()

    organization = None
    task = None
    workflow = None
    link = None

    try:
        organization = organizations.create(
            f"test-org-{uuid4()}"
        )

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        link = task_workflows.create(
            task["id"],
            workflow["id"],
        )

        results = task_workflows.list_by_workflow_id(
            workflow["id"]
        )

        assert any(
            item["task_id"] == task["id"]
            for item in results
        )

    finally:
        if link is not None:
            task_workflows.delete(
                task["id"],
                workflow["id"],
            )

        if task is not None:
            tasks.delete_by_id(task["id"])

        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_returns_false_for_unknown_link():
    repository = TaskWorkflowsRepository()

    assert repository.delete(
        uuid4(),
        uuid4(),
    ) is False
