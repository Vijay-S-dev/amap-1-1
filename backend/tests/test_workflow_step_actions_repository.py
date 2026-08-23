from uuid import uuid4

from repositories.actions import ActionsRepository
from repositories.organizations import OrganizationsRepository
from repositories.workflow_step_actions import WorkflowStepActionsRepository
from repositories.workflow_steps import WorkflowStepsRepository
from repositories.workflows import WorkflowsRepository


def test_get_by_ids_returns_none_for_unknown_link():
    repository = WorkflowStepActionsRepository()

    assert repository.get_by_ids(uuid4(), uuid4()) is None


def test_create_and_get_workflow_step_action():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()
    workflow_steps = WorkflowStepsRepository()
    actions = ActionsRepository()
    workflow_step_actions = WorkflowStepActionsRepository()

    organization = None
    workflow = None
    workflow_step = None
    action = None
    link = None

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

        action = actions.create(
            f"test-action-{uuid4()}",
            f"Test Action {uuid4()}",
        )

        link = workflow_step_actions.create(
            workflow_step["id"],
            action["id"],
        )

        assert link is not None
        assert link["workflow_step_id"] == workflow_step["id"]
        assert link["action_id"] == action["id"]

        result = workflow_step_actions.get_by_ids(
            workflow_step["id"],
            action["id"],
        )

        assert result is not None
        assert result["workflow_step_id"] == workflow_step["id"]
        assert result["action_id"] == action["id"]

    finally:
        if link is not None:
            workflow_step_actions.delete(
                workflow_step["id"],
                action["id"],
            )

        if action is not None:
            actions.delete_by_id(action["id"])

        if workflow_step is not None:
            workflow_steps.delete_by_id(workflow_step["id"])

        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_workflow_step_id_contains_created_link():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()
    workflow_steps = WorkflowStepsRepository()
    actions = ActionsRepository()
    workflow_step_actions = WorkflowStepActionsRepository()

    organization = None
    workflow = None
    workflow_step = None
    action = None
    link = None

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

        action = actions.create(
            f"test-action-{uuid4()}",
            f"Test Action {uuid4()}",
        )

        link = workflow_step_actions.create(
            workflow_step["id"],
            action["id"],
        )

        results = workflow_step_actions.list_by_workflow_step_id(
            workflow_step["id"],
        )

        assert any(
            item["action_id"] == action["id"]
            for item in results
        )

    finally:
        if link is not None:
            workflow_step_actions.delete(
                workflow_step["id"],
                action["id"],
            )

        if action is not None:
            actions.delete_by_id(action["id"])

        if workflow_step is not None:
            workflow_steps.delete_by_id(workflow_step["id"])

        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_action_id_contains_created_link():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()
    workflow_steps = WorkflowStepsRepository()
    actions = ActionsRepository()
    workflow_step_actions = WorkflowStepActionsRepository()

    organization = None
    workflow = None
    workflow_step = None
    action = None
    link = None

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

        action = actions.create(
            f"test-action-{uuid4()}",
            f"Test Action {uuid4()}",
        )

        link = workflow_step_actions.create(
            workflow_step["id"],
            action["id"],
        )

        results = workflow_step_actions.list_by_action_id(
            action["id"],
        )

        assert any(
            item["workflow_step_id"] == workflow_step["id"]
            for item in results
        )

    finally:
        if link is not None:
            workflow_step_actions.delete(
                workflow_step["id"],
                action["id"],
            )

        if action is not None:
            actions.delete_by_id(action["id"])

        if workflow_step is not None:
            workflow_steps.delete_by_id(workflow_step["id"])

        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_returns_false_for_unknown_link():
    repository = WorkflowStepActionsRepository()

    assert repository.delete(uuid4(), uuid4()) is False
