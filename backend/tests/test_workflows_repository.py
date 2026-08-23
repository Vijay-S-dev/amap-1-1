from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.workflows import WorkflowsRepository


def test_get_by_id_returns_none_for_unknown_workflow():
    repository = WorkflowsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_create_and_get_workflow():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()

    organization = None
    workflow = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
            "Test workflow description",
        )

        assert workflow is not None
        assert workflow["organization_id"] == organization["id"]
        assert workflow["description"] == "Test workflow description"
        assert workflow["status"] == "active"

        result = workflows.get_by_id(workflow["id"])

        assert result is not None
        assert result["id"] == workflow["id"]

    finally:
        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_get_by_organization_and_name():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()

    organization = None
    workflow = None
    name = f"test-workflow-{uuid4()}"

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        workflow = workflows.create(
            organization["id"],
            name,
        )

        result = workflows.get_by_organization_and_name(
            organization["id"],
            name,
        )

        assert result is not None
        assert result["id"] == workflow["id"]

    finally:
        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_organization_id_contains_created_workflow():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()

    organization = None
    workflow = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        results = workflows.list_by_organization_id(
            organization["id"],
        )

        assert any(
            item["id"] == workflow["id"]
            for item in results
        )

    finally:
        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_all_contains_created_workflow():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()

    organization = None
    workflow = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        results = workflows.list_all()

        assert any(
            item["id"] == workflow["id"]
            for item in results
        )

    finally:
        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_update_workflow():
    organizations = OrganizationsRepository()
    workflows = WorkflowsRepository()

    organization = None
    workflow = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
            "Original description",
        )

        updated = workflows.update(
            workflow["id"],
            "updated-workflow",
            "Updated description",
            "inactive",
        )

        assert updated is not None
        assert updated["id"] == workflow["id"]
        assert updated["name"] == "updated-workflow"
        assert updated["description"] == "Updated description"
        assert updated["status"] == "inactive"

    finally:
        if workflow is not None:
            workflows.delete_by_id(workflow["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_update_returns_none_for_unknown_workflow():
    repository = WorkflowsRepository()

    result = repository.update(
        uuid4(),
        "unknown-workflow",
        "Unknown workflow",
        "inactive",
    )

    assert result is None


def test_delete_returns_false_for_unknown_workflow():
    repository = WorkflowsRepository()

    assert repository.delete_by_id(uuid4()) is False
