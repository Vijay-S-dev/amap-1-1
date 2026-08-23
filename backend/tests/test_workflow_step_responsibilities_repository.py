from uuid import uuid4

from repositories.jobs import JobsRepository
from repositories.organizations import OrganizationsRepository
from repositories.responsibilities import ResponsibilitiesRepository
from repositories.workflow_step_responsibilities import (
    WorkflowStepResponsibilitiesRepository,
)
from repositories.workflow_steps import WorkflowStepsRepository
from repositories.workflows import WorkflowsRepository


def test_get_by_ids_returns_none_for_unknown_link():
    repository = WorkflowStepResponsibilitiesRepository()

    assert repository.get_by_ids(uuid4(), uuid4()) is None


def test_create_and_get_workflow_step_responsibility():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()
    workflows = WorkflowsRepository()
    workflow_steps = WorkflowStepsRepository()
    responsibilities = ResponsibilitiesRepository()
    workflow_step_responsibilities = (
        WorkflowStepResponsibilitiesRepository()
    )

    organization = None
    job = None
    workflow = None
    workflow_step = None
    responsibility = None
    link = None

    try:
        organization = organizations.create(
            f"test-org-{uuid4()}"
        )

        job = jobs.create(
            organization["id"],
            f"test-job-{uuid4()}",
        )

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        workflow_step = workflow_steps.create(
            workflow["id"],
            1,
            f"test-step-{uuid4()}",
        )

        responsibility = responsibilities.create(
            job["id"],
            f"test-responsibility-{uuid4()}",
        )

        link = workflow_step_responsibilities.create(
            workflow_step["id"],
            responsibility["id"],
        )

        assert link is not None
        assert link["workflow_step_id"] == workflow_step["id"]
        assert link["responsibility_id"] == responsibility["id"]

        result = workflow_step_responsibilities.get_by_ids(
            workflow_step["id"],
            responsibility["id"],
        )

        assert result is not None
        assert result["workflow_step_id"] == workflow_step["id"]
        assert result["responsibility_id"] == responsibility["id"]

    finally:
        if link is not None:
            workflow_step_responsibilities.delete(
                workflow_step["id"],
                responsibility["id"],
            )

        if responsibility is not None:
            responsibilities.delete_by_id(
                responsibility["id"]
            )

        if workflow_step is not None:
            workflow_steps.delete_by_id(
                workflow_step["id"]
            )

        if workflow is not None:
            workflows.delete_by_id(
                workflow["id"]
            )

        if job is not None:
            jobs.delete_by_id(
                job["id"]
            )

        if organization is not None:
            organizations.delete_by_id(
                organization["id"]
            )


def test_list_by_workflow_step_id_contains_created_link():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()
    workflows = WorkflowsRepository()
    workflow_steps = WorkflowStepsRepository()
    responsibilities = ResponsibilitiesRepository()
    workflow_step_responsibilities = (
        WorkflowStepResponsibilitiesRepository()
    )

    organization = None
    job = None
    workflow = None
    workflow_step = None
    responsibility = None
    link = None

    try:
        organization = organizations.create(
            f"test-org-{uuid4()}"
        )

        job = jobs.create(
            organization["id"],
            f"test-job-{uuid4()}",
        )

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        workflow_step = workflow_steps.create(
            workflow["id"],
            1,
            f"test-step-{uuid4()}",
        )

        responsibility = responsibilities.create(
            job["id"],
            f"test-responsibility-{uuid4()}",
        )

        link = workflow_step_responsibilities.create(
            workflow_step["id"],
            responsibility["id"],
        )

        results = (
            workflow_step_responsibilities
            .list_by_workflow_step_id(workflow_step["id"])
        )

        assert any(
            item["responsibility_id"] == responsibility["id"]
            for item in results
        )

    finally:
        if link is not None:
            workflow_step_responsibilities.delete(
                workflow_step["id"],
                responsibility["id"],
            )

        if responsibility is not None:
            responsibilities.delete_by_id(
                responsibility["id"]
            )

        if workflow_step is not None:
            workflow_steps.delete_by_id(
                workflow_step["id"]
            )

        if workflow is not None:
            workflows.delete_by_id(
                workflow["id"]
            )

        if job is not None:
            jobs.delete_by_id(
                job["id"]
            )

        if organization is not None:
            organizations.delete_by_id(
                organization["id"]
            )


def test_list_by_responsibility_id_contains_created_link():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()
    workflows = WorkflowsRepository()
    workflow_steps = WorkflowStepsRepository()
    responsibilities = ResponsibilitiesRepository()
    workflow_step_responsibilities = (
        WorkflowStepResponsibilitiesRepository()
    )

    organization = None
    job = None
    workflow = None
    workflow_step = None
    responsibility = None
    link = None

    try:
        organization = organizations.create(
            f"test-org-{uuid4()}"
        )

        job = jobs.create(
            organization["id"],
            f"test-job-{uuid4()}",
        )

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        workflow_step = workflow_steps.create(
            workflow["id"],
            1,
            f"test-step-{uuid4()}",
        )

        responsibility = responsibilities.create(
            job["id"],
            f"test-responsibility-{uuid4()}",
        )

        link = workflow_step_responsibilities.create(
            workflow_step["id"],
            responsibility["id"],
        )

        results = (
            workflow_step_responsibilities
            .list_by_responsibility_id(responsibility["id"])
        )

        assert any(
            item["workflow_step_id"] == workflow_step["id"]
            for item in results
        )

    finally:
        if link is not None:
            workflow_step_responsibilities.delete(
                workflow_step["id"],
                responsibility["id"],
            )

        if responsibility is not None:
            responsibilities.delete_by_id(
                responsibility["id"]
            )

        if workflow_step is not None:
            workflow_steps.delete_by_id(
                workflow_step["id"]
            )

        if workflow is not None:
            workflows.delete_by_id(
                workflow["id"]
            )

        if job is not None:
            jobs.delete_by_id(
                job["id"]
            )

        if organization is not None:
            organizations.delete_by_id(
                organization["id"]
            )


def test_delete_returns_false_for_unknown_link():
    repository = WorkflowStepResponsibilitiesRepository()

    assert repository.delete(uuid4(), uuid4()) is False
