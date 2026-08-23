from uuid import uuid4

from repositories.actions import ActionsRepository
from repositories.interaction_events import InteractionEventsRepository
from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.work_sessions import WorkSessionsRepository
from repositories.worker_profiles import WorkerProfilesRepository


def create_dependencies():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    work_sessions = WorkSessionsRepository()
    actions = ActionsRepository()

    organization = organizations.create(
        f"test-org-{uuid4()}",
    )

    user = users.create(
        f"test-user-{uuid4()}@example.com",
        f"Test User {uuid4()}",
    )

    worker_profile = worker_profiles.create(
        user["id"],
    )

    work_session = work_sessions.create(
        worker_profile["id"],
    )

    action = actions.create(
        f"test-action-{uuid4()}",
        f"Test Action {uuid4()}",
    )

    return (
        organizations,
        users,
        worker_profiles,
        work_sessions,
        actions,
        organization,
        user,
        worker_profile,
        work_session,
        action,
    )


def cleanup_dependencies(
    organizations,
    users,
    worker_profiles,
    work_sessions,
    actions,
    organization,
    user,
    worker_profile,
    work_session,
    action,
):
    work_sessions.delete_by_id(work_session["id"])
    actions.delete_by_id(action["id"])
    worker_profiles.delete_by_id(worker_profile["id"])
    users.delete_by_id(user["id"])
    organizations.delete_by_id(organization["id"])


def test_create_and_get_interaction_event():
    events = InteractionEventsRepository()

    dependencies = create_dependencies()

    (
        organizations,
        users,
        worker_profiles,
        work_sessions,
        actions,
        organization,
        user,
        worker_profile,
        work_session,
        action,
    ) = dependencies

    event = None

    try:
        event = events.create(
            organization["id"],
            worker_profile["id"],
            "gesture",
            f"detected-{uuid4()}",
            work_session_id=work_session["id"],
            action_id=action["id"],
            confidence=0.95,
            interaction_data={"source": "test"},
        )

        assert event is not None
        assert event["organization_id"] == organization["id"]
        assert event["worker_profile_id"] == worker_profile["id"]
        assert event["interaction_mode"] == "gesture"
        assert event["interaction_data"] == {"source": "test"}

        fetched = events.get_by_id(event["id"])

        assert fetched is not None
        assert fetched["id"] == event["id"]

    finally:
        if event is not None:
            events.delete_by_id(event["id"])

        cleanup_dependencies(*dependencies)


def test_list_by_organization_id_contains_created_event():
    events = InteractionEventsRepository()
    dependencies = create_dependencies()

    organization = dependencies[5]
    worker_profile = dependencies[7]

    event = None

    try:
        event = events.create(
            organization["id"],
            worker_profile["id"],
            "voice",
            f"test-event-{uuid4()}",
        )

        results = events.list_by_organization_id(
            organization["id"],
        )

        assert any(
            result["id"] == event["id"]
            for result in results
        )

    finally:
        if event is not None:
            events.delete_by_id(event["id"])

        cleanup_dependencies(*dependencies)


def test_list_by_worker_profile_id_contains_created_event():
    events = InteractionEventsRepository()
    dependencies = create_dependencies()

    organization = dependencies[5]
    worker_profile = dependencies[7]

    event = None

    try:
        event = events.create(
            organization["id"],
            worker_profile["id"],
            "ui",
            f"test-event-{uuid4()}",
        )

        results = events.list_by_worker_profile_id(
            worker_profile["id"],
        )

        assert any(
            result["id"] == event["id"]
            for result in results
        )

    finally:
        if event is not None:
            events.delete_by_id(event["id"])

        cleanup_dependencies(*dependencies)


def test_list_by_work_session_id_contains_created_event():
    events = InteractionEventsRepository()
    dependencies = create_dependencies()

    organization = dependencies[5]
    worker_profile = dependencies[7]
    work_session = dependencies[8]

    event = None

    try:
        event = events.create(
            organization["id"],
            worker_profile["id"],
            "gesture",
            f"test-event-{uuid4()}",
            work_session_id=work_session["id"],
        )

        results = events.list_by_work_session_id(
            work_session["id"],
        )

        assert any(
            result["id"] == event["id"]
            for result in results
        )

    finally:
        if event is not None:
            events.delete_by_id(event["id"])

        cleanup_dependencies(*dependencies)


def test_list_by_action_id_contains_created_event():
    events = InteractionEventsRepository()
    dependencies = create_dependencies()

    organization = dependencies[5]
    worker_profile = dependencies[7]
    action = dependencies[9]

    event = None

    try:
        event = events.create(
            organization["id"],
            worker_profile["id"],
            "gesture",
            f"test-event-{uuid4()}",
            action_id=action["id"],
        )

        results = events.list_by_action_id(action["id"])

        assert any(
            result["id"] == event["id"]
            for result in results
        )

    finally:
        if event is not None:
            events.delete_by_id(event["id"])

        cleanup_dependencies(*dependencies)


def test_list_by_event_type_contains_created_event():
    events = InteractionEventsRepository()
    dependencies = create_dependencies()

    organization = dependencies[5]
    worker_profile = dependencies[7]
    event_type = f"test-event-{uuid4()}"

    event = None

    try:
        event = events.create(
            organization["id"],
            worker_profile["id"],
            "other",
            event_type,
        )

        results = events.list_by_event_type(event_type)

        assert any(
            result["id"] == event["id"]
            for result in results
        )

    finally:
        if event is not None:
            events.delete_by_id(event["id"])

        cleanup_dependencies(*dependencies)


def test_delete_by_id_returns_true_for_existing_event():
    events = InteractionEventsRepository()
    dependencies = create_dependencies()

    organization = dependencies[5]
    worker_profile = dependencies[7]

    event = None

    try:
        event = events.create(
            organization["id"],
            worker_profile["id"],
            "ui",
            f"test-event-{uuid4()}",
        )

        deleted = events.delete_by_id(event["id"])

        assert deleted is True
        event = None

    finally:
        if event is not None:
            events.delete_by_id(event["id"])

        cleanup_dependencies(*dependencies)
