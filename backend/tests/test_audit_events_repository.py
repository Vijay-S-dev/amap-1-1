from uuid import uuid4

from repositories.audit_events import AuditEventsRepository
from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository


def test_create_and_get_audit_event():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    audit_events = AuditEventsRepository()

    organization = None
    user = None
    audit_event = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-user-{uuid4()}@example.com",
            f"Test User {uuid4()}",
            "test-password-hash",
        )

        audit_event = audit_events.create(
            organization["id"],
            "user.created",
            actor_user_id=user["id"],
            resource_type="users",
            resource_id=user["id"],
            event_data={"source": "test"},
        )

        assert audit_event is not None
        assert audit_event["organization_id"] == organization["id"]
        assert audit_event["actor_user_id"] == user["id"]
        assert audit_event["event_type"] == "user.created"
        assert audit_event["resource_type"] == "users"
        assert audit_event["resource_id"] == user["id"]
        assert audit_event["event_data"] == {"source": "test"}

        fetched = audit_events.get_by_id(audit_event["id"])

        assert fetched is not None
        assert fetched["id"] == audit_event["id"]

    finally:
        if audit_event is not None:
            audit_events.delete_by_id(audit_event["id"])

        if user is not None:
            users.delete_by_id(user["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_organization_id_contains_created_event():
    organizations = OrganizationsRepository()
    audit_events = AuditEventsRepository()

    organization = None
    audit_event = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        audit_event = audit_events.create(
            organization["id"],
            "organization.created",
        )

        events = audit_events.list_by_organization_id(
            organization["id"],
        )

        assert any(
            event["id"] == audit_event["id"]
            for event in events
        )

    finally:
        if audit_event is not None:
            audit_events.delete_by_id(audit_event["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_actor_user_id_contains_created_event():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    audit_events = AuditEventsRepository()

    organization = None
    user = None
    audit_event = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-user-{uuid4()}@example.com",
            f"Test User {uuid4()}",
            "test-password-hash",
        )

        audit_event = audit_events.create(
            organization["id"],
            "user.updated",
            actor_user_id=user["id"],
        )

        events = audit_events.list_by_actor_user_id(user["id"])

        assert any(
            event["id"] == audit_event["id"]
            for event in events
        )

    finally:
        if audit_event is not None:
            audit_events.delete_by_id(audit_event["id"])

        if user is not None:
            users.delete_by_id(user["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_event_type_contains_created_event():
    organizations = OrganizationsRepository()
    audit_events = AuditEventsRepository()

    organization = None
    audit_event = None

    event_type = f"test.event.{uuid4()}"

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        audit_event = audit_events.create(
            organization["id"],
            event_type,
        )

        events = audit_events.list_by_event_type(event_type)

        assert any(
            event["id"] == audit_event["id"]
            for event in events
        )

    finally:
        if audit_event is not None:
            audit_events.delete_by_id(audit_event["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_resource_contains_created_event():
    organizations = OrganizationsRepository()
    audit_events = AuditEventsRepository()

    organization = None
    audit_event = None

    resource_id = uuid4()

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        audit_event = audit_events.create(
            organization["id"],
            "resource.updated",
            resource_type="test_resource",
            resource_id=resource_id,
        )

        events = audit_events.list_by_resource(
            "test_resource",
            resource_id,
        )

        assert any(
            event["id"] == audit_event["id"]
            for event in events
        )

    finally:
        if audit_event is not None:
            audit_events.delete_by_id(audit_event["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_by_id_returns_true_for_existing_event():
    organizations = OrganizationsRepository()
    audit_events = AuditEventsRepository()

    organization = None
    audit_event = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        audit_event = audit_events.create(
            organization["id"],
            "event.to.delete",
        )

        deleted = audit_events.delete_by_id(audit_event["id"])

        assert deleted is True

        audit_event = None

    finally:
        if audit_event is not None:
            audit_events.delete_by_id(audit_event["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])
