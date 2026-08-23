from uuid import uuid4

from repositories.actions import ActionsRepository
from repositories.interaction_events import InteractionEventsRepository
from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.work_sessions import WorkSessionsRepository
from repositories.worker_profiles import WorkerProfilesRepository


def create_dependencies():
    """Create all database records required for interaction event tests."""

    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    work_sessions = WorkSessionsRepository()
    actions = ActionsRepository()

    organization = organizations.create(
        f"test-org-{uuid4()}",
    )

    user = users.create(
        organization["id"],
        f"test-user-{uuid4()}@example.com",
        f"Test User {uuid4()}",
        f"test-password-hash-{uuid4()}",
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

    return {
        "organizations": organizations,
        "users": users,
        "worker_profiles": worker_profiles,
        "work_sessions": work_sessions,
        "actions": actions,
        "organization": organization,
        "user": user,
        "worker_profile": worker_profile,
        "work_session": work_session,
        "action": action,
    }


def test_create_and_get_interaction_event():
    dependencies = create_dependencies()
    repository = InteractionEventsRepository()

    event = repository.create(
        organization_id=dependencies["organization"]["id"],
        worker_profile_id=dependencies["worker_profile"]["id"],
        work_session_id=dependencies["work_session"]["id"],
        action_id=dependencies["action"]["id"],
        interaction_mode="gesture",
        event_type="recognized",
        confidence=0.9500,
        interaction_data={"source": "test"},
    )

    fetched_event = repository.get_by_id(event["id"])

    assert fetched_event is not None
    assert fetched_event["id"] == event["id"]
    assert (
        fetched_event["organization_id"]
        == dependencies["organization"]["id"]
    )
    assert (
        fetched_event["worker_profile_id"]
        == dependencies["worker_profile"]["id"]
    )
    assert (
        fetched_event["work_session_id"]
        == dependencies["work_session"]["id"]
    )
    assert (
        fetched_event["action_id"]
        == dependencies["action"]["id"]
    )
    assert fetched_event["interaction_mode"] == "gesture"
    assert fetched_event["event_type"] == "recognized"
    assert fetched_event["confidence"] == 0.9500
    assert fetched_event["interaction_data"] == {"source": "test"}


def test_get_by_id_returns_none_for_missing_event():
    repository = InteractionEventsRepository()

    event = repository.get_by_id(uuid4())

    assert event is None


def test_list_by_organization_id_contains_created_event():
    dependencies = create_dependencies()
    repository = InteractionEventsRepository()

    event = repository.create(
        organization_id=dependencies["organization"]["id"],
        worker_profile_id=dependencies["worker_profile"]["id"],
        interaction_mode="voice",
        event_type="recognized",
    )

    events = repository.list_by_organization_id(
        dependencies["organization"]["id"],
    )

    event_ids = [item["id"] for item in events]

    assert event["id"] in event_ids


def test_list_by_worker_profile_id_contains_created_event():
    dependencies = create_dependencies()
    repository = InteractionEventsRepository()

    event = repository.create(
        organization_id=dependencies["organization"]["id"],
        worker_profile_id=dependencies["worker_profile"]["id"],
        interaction_mode="gesture",
        event_type="recognized",
    )

    events = repository.list_by_worker_profile_id(
        dependencies["worker_profile"]["id"],
    )

    event_ids = [item["id"] for item in events]

    assert event["id"] in event_ids


def test_list_by_work_session_id_contains_created_event():
    dependencies = create_dependencies()
    repository = InteractionEventsRepository()

    event = repository.create(
        organization_id=dependencies["organization"]["id"],
        worker_profile_id=dependencies["worker_profile"]["id"],
        work_session_id=dependencies["work_session"]["id"],
        interaction_mode="ui",
        event_type="clicked",
    )

    events = repository.list_by_work_session_id(
        dependencies["work_session"]["id"],
    )

    event_ids = [item["id"] for item in events]

    assert event["id"] in event_ids


def test_list_by_action_id_contains_created_event():
    dependencies = create_dependencies()
    repository = InteractionEventsRepository()

    event = repository.create(
        organization_id=dependencies["organization"]["id"],
        worker_profile_id=dependencies["worker_profile"]["id"],
        action_id=dependencies["action"]["id"],
        interaction_mode="gesture",
        event_type="recognized",
    )

    events = repository.list_by_action_id(
        dependencies["action"]["id"],
    )

    event_ids = [item["id"] for item in events]

    assert event["id"] in event_ids


def test_list_by_event_type_contains_created_event():
    dependencies = create_dependencies()
    repository = InteractionEventsRepository()

    event_type = f"test-event-{uuid4()}"

    event = repository.create(
        organization_id=dependencies["organization"]["id"],
        worker_profile_id=dependencies["worker_profile"]["id"],
        interaction_mode="other",
        event_type=event_type,
    )

    events = repository.list_by_event_type(
        event_type,
    )

    event_ids = [item["id"] for item in events]

    assert event["id"] in event_ids


def test_delete_by_id_returns_true_for_existing_event():
    dependencies = create_dependencies()
    repository = InteractionEventsRepository()

    event = repository.create(
        organization_id=dependencies["organization"]["id"],
        worker_profile_id=dependencies["worker_profile"]["id"],
        interaction_mode="gesture",
        event_type="recognized",
    )

    deleted = repository.delete_by_id(
        event["id"],
    )

    assert deleted is True
    assert repository.get_by_id(event["id"]) is None


def test_delete_by_id_returns_false_for_missing_event():
    repository = InteractionEventsRepository()

    deleted = repository.delete_by_id(
        uuid4(),
    )

    assert deleted is False
