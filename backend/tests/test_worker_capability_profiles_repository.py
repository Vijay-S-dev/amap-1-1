from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.worker_capability_profiles import (
    WorkerCapabilityProfilesRepository,
)
from repositories.worker_profiles import WorkerProfilesRepository


def create_dependencies():
    organizations_repository = OrganizationsRepository()
    users_repository = UsersRepository()
    worker_profiles_repository = WorkerProfilesRepository()

    unique_id = uuid4()

    organization = organizations_repository.create(
        name=f"Test Organization {unique_id}",
    )

    user = users_repository.create(
        organization_id=organization["id"],
        email=f"worker-{unique_id}@example.com",
        full_name=f"Test Worker {unique_id}",
        password_hash="test-password-hash",
    )

    worker_profile = worker_profiles_repository.create(
        user_id=user["id"],
    )

    return {
        "organization": organization,
        "user": user,
        "worker_profile": worker_profile,
    }


def test_create_and_get_worker_capability_profile():
    dependencies = create_dependencies()
    repository = WorkerCapabilityProfilesRepository()

    capability_data = {
        "skills": ["voice", "gesture"],
        "max_tasks": 5,
    }

    profile = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
        capability_data=capability_data,
        status="active",
    )

    fetched_profile = repository.get_by_id(profile["id"])

    assert fetched_profile is not None
    assert fetched_profile["id"] == profile["id"]
    assert (
        fetched_profile["worker_profile_id"]
        == dependencies["worker_profile"]["id"]
    )
    assert fetched_profile["capability_data"] == capability_data
    assert fetched_profile["status"] == "active"


def test_get_by_worker_profile_id_returns_created_profile():
    dependencies = create_dependencies()
    repository = WorkerCapabilityProfilesRepository()

    profile = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
        capability_data={"skills": ["voice"]},
    )

    fetched_profile = repository.get_by_worker_profile_id(
        dependencies["worker_profile"]["id"],
    )

    assert fetched_profile is not None
    assert fetched_profile["id"] == profile["id"]


def test_get_by_worker_profile_id_returns_none_when_missing():
    repository = WorkerCapabilityProfilesRepository()

    fetched_profile = repository.get_by_worker_profile_id(uuid4())

    assert fetched_profile is None


def test_list_by_status_contains_created_profile():
    dependencies = create_dependencies()
    repository = WorkerCapabilityProfilesRepository()

    profile = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
        capability_data={"skills": ["gesture"]},
        status="inactive",
    )

    profiles = repository.list_by_status("inactive")

    profile_ids = {
        capability_profile["id"]
        for capability_profile in profiles
    }

    assert profile["id"] in profile_ids


def test_create_uses_default_values():
    dependencies = create_dependencies()
    repository = WorkerCapabilityProfilesRepository()

    profile = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
    )

    assert profile["capability_data"] == {}
    assert profile["status"] == "active"


def test_update_worker_capability_profile():
    dependencies = create_dependencies()
    repository = WorkerCapabilityProfilesRepository()

    profile = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
        capability_data={"skills": ["voice"]},
        status="active",
    )

    updated_data = {
        "skills": ["voice", "gesture", "ui"],
        "max_tasks": 10,
    }

    updated_profile = repository.update(
        worker_capability_profile_id=profile["id"],
        capability_data=updated_data,
        status="inactive",
    )

    assert updated_profile is not None
    assert updated_profile["id"] == profile["id"]
    assert updated_profile["capability_data"] == updated_data
    assert updated_profile["status"] == "inactive"


def test_update_returns_none_for_missing_profile():
    repository = WorkerCapabilityProfilesRepository()

    updated_profile = repository.update(
        worker_capability_profile_id=uuid4(),
        capability_data={"skills": []},
        status="active",
    )

    assert updated_profile is None


def test_update_status():
    dependencies = create_dependencies()
    repository = WorkerCapabilityProfilesRepository()

    profile = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
    )

    updated_profile = repository.update_status(
        profile["id"],
        "archived",
    )

    assert updated_profile is not None
    assert updated_profile["id"] == profile["id"]
    assert updated_profile["status"] == "archived"


def test_update_status_returns_none_for_missing_profile():
    repository = WorkerCapabilityProfilesRepository()

    updated_profile = repository.update_status(
        uuid4(),
        "inactive",
    )

    assert updated_profile is None


def test_delete_by_id_returns_true_for_existing_profile():
    dependencies = create_dependencies()
    repository = WorkerCapabilityProfilesRepository()

    profile = repository.create(
        worker_profile_id=dependencies["worker_profile"]["id"],
    )

    deleted = repository.delete_by_id(profile["id"])

    assert deleted is True
    assert repository.get_by_id(profile["id"]) is None


def test_delete_by_id_returns_false_for_missing_profile():
    repository = WorkerCapabilityProfilesRepository()

    deleted = repository.delete_by_id(uuid4())

    assert deleted is False
