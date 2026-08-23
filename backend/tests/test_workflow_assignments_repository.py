from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.worker_profiles import WorkerProfilesRepository
from repositories.workflow_assignments import WorkflowAssignmentsRepository
from repositories.workflows import WorkflowsRepository


def create_user(users, organization_id):
    """Create a test user using the current UsersRepository signature."""
    unique_id = uuid4()

    return users.create(
        organization_id,
        f"test-user-{unique_id}@example.com",
        f"Test User {unique_id}",
        "test-password-hash",
    )


def test_get_by_id_returns_none_for_unknown_assignment():
    repository = WorkflowAssignmentsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_create_and_get_workflow_assignment():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    workflows = WorkflowsRepository()
    assignments = WorkflowAssignmentsRepository()

    organization = None
    user = None
    worker_profile = None
    workflow = None
    assignment = None

    try:
        organization = organizations.create(
            f"test-org-{uuid4()}"
        )

        user = create_user(
            users,
            organization["id"],
        )

        worker_profile = worker_profiles.create(
            user["id"],
        )

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        assignment = assignments.create(
            workflow["id"],
            worker_profile["id"],
        )

        assert assignment is not None
        assert assignment["workflow_id"] == workflow["id"]
        assert (
            assignment["worker_profile_id"]
            == worker_profile["id"]
        )
        assert assignment["status"] == "assigned"

        result = assignments.get_by_id(
            assignment["id"]
        )

        assert result is not None
        assert result["id"] == assignment["id"]

    finally:
        if assignment is not None:
            assignments.delete_by_id(
                assignment["id"]
            )

        if workflow is not None:
            workflows.delete_by_id(
                workflow["id"]
            )

        if worker_profile is not None:
            worker_profiles.delete_by_id(
                worker_profile["id"]
            )

        if user is not None:
            users.delete_by_id(
                user["id"]
            )

        if organization is not None:
            organizations.delete_by_id(
                organization["id"]
            )


def test_list_by_workflow_id_contains_created_assignment():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    workflows = WorkflowsRepository()
    assignments = WorkflowAssignmentsRepository()

    organization = None
    user = None
    worker_profile = None
    workflow = None
    assignment = None

    try:
        organization = organizations.create(
            f"test-org-{uuid4()}"
        )

        user = create_user(
            users,
            organization["id"],
        )

        worker_profile = worker_profiles.create(
            user["id"],
        )

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        assignment = assignments.create(
            workflow["id"],
            worker_profile["id"],
        )

        results = assignments.list_by_workflow_id(
            workflow["id"]
        )

        assert any(
            item["id"] == assignment["id"]
            for item in results
        )

    finally:
        if assignment is not None:
            assignments.delete_by_id(
                assignment["id"]
            )

        if workflow is not None:
            workflows.delete_by_id(
                workflow["id"]
            )

        if worker_profile is not None:
            worker_profiles.delete_by_id(
                worker_profile["id"]
            )

        if user is not None:
            users.delete_by_id(
                user["id"]
            )

        if organization is not None:
            organizations.delete_by_id(
                organization["id"]
            )


def test_list_by_worker_profile_id_contains_created_assignment():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    workflows = WorkflowsRepository()
    assignments = WorkflowAssignmentsRepository()

    organization = None
    user = None
    worker_profile = None
    workflow = None
    assignment = None

    try:
        organization = organizations.create(
            f"test-org-{uuid4()}"
        )

        user = create_user(
            users,
            organization["id"],
        )

        worker_profile = worker_profiles.create(
            user["id"],
        )

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        assignment = assignments.create(
            workflow["id"],
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
            assignments.delete_by_id(
                assignment["id"]
            )

        if workflow is not None:
            workflows.delete_by_id(
                workflow["id"]
            )

        if worker_profile is not None:
            worker_profiles.delete_by_id(
                worker_profile["id"]
            )

        if user is not None:
            users.delete_by_id(
                user["id"]
            )

        if organization is not None:
            organizations.delete_by_id(
                organization["id"]
            )


def test_update_status():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    workflows = WorkflowsRepository()
    assignments = WorkflowAssignmentsRepository()

    organization = None
    user = None
    worker_profile = None
    workflow = None
    assignment = None

    try:
        organization = organizations.create(
            f"test-org-{uuid4()}"
        )

        user = create_user(
            users,
            organization["id"],
        )

        worker_profile = worker_profiles.create(
            user["id"],
        )

        workflow = workflows.create(
            organization["id"],
            f"test-workflow-{uuid4()}",
        )

        assignment = assignments.create(
            workflow["id"],
            worker_profile["id"],
        )

        updated = assignments.update_status(
            assignment["id"],
            "in_progress",
        )

        assert updated is not None
        assert updated["id"] == assignment["id"]
        assert updated["status"] == "in_progress"

    finally:
        if assignment is not None:
            assignments.delete_by_id(
                assignment["id"]
            )

        if workflow is not None:
            workflows.delete_by_id(
                workflow["id"]
            )

        if worker_profile is not None:
            worker_profiles.delete_by_id(
                worker_profile["id"]
            )

        if user is not None:
            users.delete_by_id(
                user["id"]
            )

        if organization is not None:
            organizations.delete_by_id(
                organization["id"]
            )


def test_delete_by_id_returns_false_for_unknown_assignment():
    repository = WorkflowAssignmentsRepository()

    assert repository.delete_by_id(uuid4()) is False
