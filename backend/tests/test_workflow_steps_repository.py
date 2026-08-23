from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.workflows import WorkflowsRepository
from repositories.workflow_steps import WorkflowStepsRepository


def test_get_by_id_returns_none_for_unknown_workflow_step():
    repository = WorkflowStepsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_create_and_get_workflow_step():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()
    workflow_steps = WorkflowStepsRepository()

    organization = None
    workflow = None
    workflow_step = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        workflow_step = workflow_steps.create(
            workflow["id"],
            1,
            f"test-step-{uuid4()}",
            "Test step description",
        )

        assert workflow_step is not None
        assert workflow_step["workflow_id"] == workflow["id"]
        assert workflow_step["step_order"] == 1
        assert workflow_step["description"] == "Test step description"
        assert workflow_step["status"] == "active"

        result = workflow_steps.get_by_id(workflow_step["id"])

        assert result is not None
        assert result["id"] == workflow_step["id"]

    finally:
        if workflow_step is not None:
            workflow_steps.delete_by_id(workflow_step["id"])

        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_get_by_workflow_and_step_order():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()
    workflow_steps = WorkflowStepsRepository()

    organization = None
    workflow = None
    workflow_step = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        workflow_step = workflow_steps.create(
            workflow["id"],
            1,
            f"test-step-{uuid4()}",
        )

        result = workflow_steps.get_by_workflow_and_step_order(
            workflow["id"],
            1,
        )

        assert result is not None
        assert result["id"] == workflow_step["id"]

    finally:
        if workflow_step is not None:
            workflow_steps.delete_by_id(workflow_step["id"])

        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_workflow_id_contains_created_workflow_step():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()
    workflow_steps = WorkflowStepsRepository()

    organization = None
    workflow = None
    workflow_step = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        workflow_step = workflow_steps.create(
            workflow["id"],
            1,
            f"test-step-{uuid4()}",
        )

        results = workflow_steps.list_by_workflow_id(
            workflow["id"],
        )

        assert any(
            item["id"] == workflow_step["id"]
            for item in results
        )

    finally:
        if workflow_step is not None:
            workflow_steps.delete_by_id(workflow_step["id"])

        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_all_contains_created_workflow_step():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()
    workflow_steps = WorkflowStepsRepository()

    organization = None
    workflow = None
    workflow_step = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        workflow_step = workflow_steps.create(
            workflow["id"],
            1,
            f"test-step-{uuid4()}",
        )

        results = workflow_steps.list_all()

        assert any(
            item["id"] == workflow_step["id"]
            for item in results
        )

    finally:
        if workflow_step is not None:
            workflow_steps.delete_by_id(workflow_step["id"])

        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_update_workflow_step():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()
    workflow_steps = WorkflowStepsRepository()

    organization = None
    workflow = None
    workflow_step = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        workflow_step = workflow_steps.create(
            workflow["id"],
            1,
            f"test-step-{uuid4()}",
            "Original description",
        )

        updated = workflow_steps.update(
            workflow_step["id"],
            2,
            "updated-step",
            "Updated description",
            "inactive",
        )

        assert updated is not None
        assert updated["id"] == workflow_step["id"]
        assert updated["step_order"] == 2
        assert updated["name"] == "updated-step"
        assert updated["description"] == "Updated description"
        assert updated["status"] == "inactive"

    finally:
        if workflow_step is not None:
            workflow_steps.delete_by_id(workflow_step["id"])

        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_update_returns_none_for_unknown_workflow_step():
    repository = WorkflowStepsRepository()

    result = repository.update(
        uuid4(),
        1,
        "unknown-step",
        "Unknown step",
        "inactive",
    )

    assert result is None


def test_delete_returns_false_for_unknown_workflow_step():
    repository = WorkflowStepsRepository()

    assert repository.delete_by_id(uuid4()) is False
