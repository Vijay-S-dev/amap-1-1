from uuid import uuid4

from repositories.execution_events import ExecutionEventsRepository
from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.worker_profiles import WorkerProfilesRepository


def test_create_and_get_execution_event():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    execution_events = ExecutionEventsRepository()

    organization = None
    user = None
    worker_profile = None
    execution_event = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-user-{uuid4()}@example.com",
            f"Test User {uuid4()}",
            "test-password-hash",
        )

        worker_profile = worker_profiles.create(user["id"])

        execution_event = execution_events.create(
            organization["id"],
            "task.started",
            worker_profile_id=worker_profile["id"],
            event_data={"source": "test"},
        )

        assert execution_event is not None
        assert execution_event["organization_id"] == organization["id"]
        assert execution_event["worker_profile_id"] == worker_profile["id"]
        assert execution_event["event_type"] == "task.started"
        assert execution_event["event_data"] == {"source": "test"}

        fetched = execution_events.get_by_id(execution_event["id"])

        assert fetched is not None
        assert fetched["id"] == execution_event["id"]

    finally:
        if execution_event is not None:
            execution_events.delete_by_id(execution_event["id"])

        if worker_profile is not None:
            worker_profiles.delete_by_id(worker_profile["id"])

        if user is not None:
            users.delete_by_id(user["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_organization_id_contains_created_event():
    organizations = OrganizationsRepository()
    execution_events = ExecutionEventsRepository()

    organization = None
    execution_event = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        execution_event = execution_events.create(
            organization["id"],
            "organization.event",
        )

        events = execution_events.list_by_organization_id(
            organization["id"],
        )

        assert any(
            event["id"] == execution_event["id"]
            for event in events
        )

    finally:
        if execution_event is not None:
            execution_events.delete_by_id(execution_event["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_worker_profile_id_contains_created_event():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    execution_events = ExecutionEventsRepository()

    organization = None
    user = None
    worker_profile = None
    execution_event = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-user-{uuid4()}@example.com",
            f"Test User {uuid4()}",
            "test-password-hash",
        )

        worker_profile = worker_profiles.create(user["id"])

        execution_event = execution_events.create(
            organization["id"],
            "worker.event",
            worker_profile_id=worker_profile["id"],
        )

        events = execution_events.list_by_worker_profile_id(
            worker_profile["id"],
        )

        assert any(
            event["id"] == execution_event["id"]
            for event in events
        )

    finally:
        if execution_event is not None:
            execution_events.delete_by_id(execution_event["id"])

        if worker_profile is not None:
            worker_profiles.delete_by_id(worker_profile["id"])

        if user is not None:
            users.delete_by_id(user["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_event_type_contains_created_event():
    organizations = OrganizationsRepository()
    execution_events = ExecutionEventsRepository()

    organization = None
    execution_event = None
    event_type = f"test.event.{uuid4()}"

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        execution_event = execution_events.create(
            organization["id"],
            event_type,
        )

        events = execution_events.list_by_event_type(event_type)

        assert any(
            event["id"] == execution_event["id"]
            for event in events
        )

    finally:
        if execution_event is not None:
            execution_events.delete_by_id(execution_event["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_by_id_returns_true_for_existing_event():
    organizations = OrganizationsRepository()
    execution_events = ExecutionEventsRepository()

    organization = None
    execution_event = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        execution_event = execution_events.create(
            organization["id"],
            "event.to.delete",
        )

        deleted = execution_events.delete_by_id(execution_event["id"])

        assert deleted is True

        execution_event = None

    finally:
        if execution_event is not None:
            execution_events.delete_by_id(execution_event["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])
