from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.personalization_history import (
    PersonalizationHistoryRepository,
)
from repositories.users import UsersRepository
from repositories.worker_personalizations import (
    WorkerPersonalizationsRepository,
)
from repositories.worker_profiles import WorkerProfilesRepository


def create_dependencies():
    organizations_repository = OrganizationsRepository()
    users_repository = UsersRepository()
    worker_profiles_repository = WorkerProfilesRepository()
    worker_personalizations_repository = (
        WorkerPersonalizationsRepository()
    )

    organization = organizations_repository.create(
        name=f"test-personalization-history-org-{uuid4()}",
    )

    user = users_repository.create(
        organization_id=organization["id"],
        email=f"personalization-history-{uuid4()}@example.com",
        full_name="Test Personalization History User",
        password_hash="test-password-hash",
    )

    worker_profile = worker_profiles_repository.create(
        user_id=user["id"],
    )

    worker_personalization = worker_personalizations_repository.create(
        worker_profile_id=worker_profile["id"],
    )

    return {
        "organization": organization,
        "user": user,
        "worker_profile": worker_profile,
        "worker_personalization": worker_personalization,
    }


def test_create_and_get_personalization_history():
    dependencies = create_dependencies()
    repository = PersonalizationHistoryRepository()

    personalization_data = {
        "theme": "dark",
        "language": "en",
        "voice_speed": 1.1,
    }

    history_record = repository.create(
        worker_personalization_id=(
            dependencies["worker_personalization"]["id"]
        ),
        personalization_data=personalization_data,
        change_reason="Updated user preferences",
    )

    fetched_record = repository.get_by_id(history_record["id"])

    assert fetched_record is not None
    assert fetched_record["id"] == history_record["id"]
    assert (
        fetched_record["worker_personalization_id"]
        == dependencies["worker_personalization"]["id"]
    )
    assert fetched_record["personalization_data"] == personalization_data
    assert (
        fetched_record["change_reason"]
        == "Updated user preferences"
    )
    assert fetched_record["changed_at"] is not None
    assert fetched_record["created_at"] is not None


def test_list_by_worker_personalization_id_contains_created_record():
    dependencies = create_dependencies()
    repository = PersonalizationHistoryRepository()

    history_record = repository.create(
        worker_personalization_id=(
            dependencies["worker_personalization"]["id"]
        ),
        personalization_data={
            "notification_level": "high",
        },
        change_reason="Changed notification preference",
    )

    records = repository.list_by_worker_personalization_id(
        dependencies["worker_personalization"]["id"],
    )

    assert any(
        record["id"] == history_record["id"]
        for record in records
    )


def test_create_with_default_personalization_data():
    dependencies = create_dependencies()
    repository = PersonalizationHistoryRepository()

    history_record = repository.create(
        worker_personalization_id=(
            dependencies["worker_personalization"]["id"]
        ),
    )

    fetched_record = repository.get_by_id(history_record["id"])

    assert fetched_record is not None
    assert fetched_record["personalization_data"] == {}
    assert fetched_record["change_reason"] is None


def test_get_by_id_returns_none_for_missing_record():
    repository = PersonalizationHistoryRepository()

    record = repository.get_by_id(uuid4())

    assert record is None


def test_list_by_worker_personalization_id_returns_empty_for_missing_id():
    repository = PersonalizationHistoryRepository()

    records = repository.list_by_worker_personalization_id(uuid4())

    assert records == []


def test_delete_by_id_returns_true_for_existing_record():
    dependencies = create_dependencies()
    repository = PersonalizationHistoryRepository()

    history_record = repository.create(
        worker_personalization_id=(
            dependencies["worker_personalization"]["id"]
        ),
        personalization_data={
            "setting": "value",
        },
    )

    deleted = repository.delete_by_id(history_record["id"])

    assert deleted is True
    assert repository.get_by_id(history_record["id"]) is None


def test_delete_by_id_returns_false_for_missing_record():
    repository = PersonalizationHistoryRepository()

    deleted = repository.delete_by_id(uuid4())

    assert deleted is False
