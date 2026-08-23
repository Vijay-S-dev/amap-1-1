from uuid import uuid4

from repositories.interaction_configurations import (
    InteractionConfigurationsRepository,
)
from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.worker_personalizations import (
    WorkerPersonalizationsRepository,
)
from repositories.worker_profiles import WorkerProfilesRepository


def create_dependencies(
    with_interaction_configuration: bool = False,
):
    organizations_repository = OrganizationsRepository()
    users_repository = UsersRepository()
    worker_profiles_repository = WorkerProfilesRepository()
    interaction_configurations_repository = (
        InteractionConfigurationsRepository()
    )

    unique_id = uuid4()

    organization = organizations_repository.create(
        name=f"Test Organization {unique_id}",
    )

    user = users_repository.create(
        organization_id=organization["id"],
        email=f"worker-personalization-{unique_id}@example.com",
        full_name=f"Test Worker {unique_id}",
        password_hash="test-password-hash",
    )

    worker_profile = worker_profiles_repository.create(
        user_id=user["id"],
    )

    interaction_configuration = None

    if with_interaction_configuration:
        interaction_configuration = (
            interaction_configurations_repository.create(
                organization_id=organization["id"],
                name=f"Test Configuration {unique_id}",
                description="Test interaction configuration",
            )
        )

    return {
        "organization": organization,
        "user": user,
        "worker_profile": worker_profile,
        "interaction_configuration": interaction_configuration,
    }


def test_create_and_get_worker_personalization():
    dependencies = create_dependencies(
        with_interaction_configuration=True,
    )
    repository = WorkerPersonalizationsRepository()

    personalization_data = {
        "theme": "dark",
        "language": "en",
        "voice_speed": 1.1,
    }

    personalization = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
        interaction_configuration_id=(
            dependencies["interaction_configuration"]["id"]
        ),
        personalization_data=personalization_data,
        status="active",
    )

    fetched_personalization = repository.get_by_id(
        personalization["id"],
    )

    assert fetched_personalization is not None
    assert fetched_personalization["id"] == personalization["id"]
    assert (
        fetched_personalization["worker_profile_id"]
        == dependencies["worker_profile"]["id"]
    )
    assert (
        fetched_personalization["interaction_configuration_id"]
        == dependencies["interaction_configuration"]["id"]
    )
    assert (
        fetched_personalization["personalization_data"]
        == personalization_data
    )
    assert fetched_personalization["status"] == "active"


def test_create_without_interaction_configuration():
    dependencies = create_dependencies()
    repository = WorkerPersonalizationsRepository()

    personalization = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
        personalization_data={
            "theme": "light",
        },
    )

    fetched_personalization = repository.get_by_id(
        personalization["id"],
    )

    assert fetched_personalization is not None
    assert (
        fetched_personalization["interaction_configuration_id"]
        is None
    )
    assert fetched_personalization["personalization_data"] == {
        "theme": "light",
    }


def test_get_by_worker_profile_id_returns_created_personalization():
    dependencies = create_dependencies()
    repository = WorkerPersonalizationsRepository()

    personalization = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
        personalization_data={
            "language": "en",
        },
    )

    fetched_personalization = repository.get_by_worker_profile_id(
        dependencies["worker_profile"]["id"],
    )

    assert fetched_personalization is not None
    assert fetched_personalization["id"] == personalization["id"]


def test_get_by_worker_profile_id_returns_none_when_missing():
    repository = WorkerPersonalizationsRepository()

    fetched_personalization = repository.get_by_worker_profile_id(
        uuid4(),
    )

    assert fetched_personalization is None


def test_list_by_status_contains_created_personalization():
    dependencies = create_dependencies()
    repository = WorkerPersonalizationsRepository()

    personalization = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
        personalization_data={
            "theme": "dark",
        },
        status="inactive",
    )

    personalizations = repository.list_by_status("inactive")

    personalization_ids = {
        item["id"]
        for item in personalizations
    }

    assert personalization["id"] in personalization_ids


def test_create_uses_default_values():
    dependencies = create_dependencies()
    repository = WorkerPersonalizationsRepository()

    personalization = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
    )

    assert personalization["interaction_configuration_id"] is None
    assert personalization["personalization_data"] == {}
    assert personalization["status"] == "active"


def test_update_worker_personalization():
    dependencies = create_dependencies(
        with_interaction_configuration=True,
    )
    repository = WorkerPersonalizationsRepository()

    personalization = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
        personalization_data={
            "theme": "light",
        },
        status="active",
    )

    updated_data = {
        "theme": "dark",
        "language": "en",
        "voice_speed": 1.2,
    }

    updated_personalization = repository.update(
        worker_personalization_id=personalization["id"],
        interaction_configuration_id=(
            dependencies["interaction_configuration"]["id"]
        ),
        personalization_data=updated_data,
        status="inactive",
    )

    assert updated_personalization is not None
    assert updated_personalization["id"] == personalization["id"]
    assert (
        updated_personalization["interaction_configuration_id"]
        == dependencies["interaction_configuration"]["id"]
    )
    assert (
        updated_personalization["personalization_data"]
        == updated_data
    )
    assert updated_personalization["status"] == "inactive"


def test_update_returns_none_for_missing_personalization():
    repository = WorkerPersonalizationsRepository()

    updated_personalization = repository.update(
        worker_personalization_id=uuid4(),
        interaction_configuration_id=None,
        personalization_data={
            "theme": "dark",
        },
        status="active",
    )

    assert updated_personalization is None


def test_update_status():
    dependencies = create_dependencies()
    repository = WorkerPersonalizationsRepository()

    personalization = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
    )

    updated_personalization = repository.update_status(
        personalization["id"],
        "archived",
    )

    assert updated_personalization is not None
    assert updated_personalization["id"] == personalization["id"]
    assert updated_personalization["status"] == "archived"


def test_update_status_returns_none_for_missing_personalization():
    repository = WorkerPersonalizationsRepository()

    updated_personalization = repository.update_status(
        uuid4(),
        "inactive",
    )

    assert updated_personalization is None


def test_delete_by_id_returns_true_for_existing_personalization():
    dependencies = create_dependencies()
    repository = WorkerPersonalizationsRepository()

    personalization = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
    )

    deleted = repository.delete_by_id(personalization["id"])

    assert deleted is True
    assert repository.get_by_id(personalization["id"]) is None


def test_delete_by_id_returns_false_for_missing_personalization():
    repository = WorkerPersonalizationsRepository()

    deleted = repository.delete_by_id(uuid4())

    assert deleted is False
