from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.worker_profiles import WorkerProfilesRepository


def test_get_by_id_returns_none_for_unknown_worker_profile():
    repository = WorkerProfilesRepository()

    assert repository.get_by_id(uuid4()) is None


def test_get_by_user_id_returns_none_for_unknown_user():
    repository = WorkerProfilesRepository()

    assert repository.get_by_user_id(uuid4()) is None


def test_create_and_get_worker_profile():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()

    organization = None
    user = None
    worker_profile = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-{uuid4()}@example.com",
            "Test User",
            "test-password-hash",
        )

        worker_profile = worker_profiles.create(user["id"])

        assert worker_profile is not None
        assert worker_profile["id"] is not None
        assert worker_profile["user_id"] == user["id"]

        by_id = worker_profiles.get_by_id(worker_profile["id"])

        assert by_id is not None
        assert by_id["id"] == worker_profile["id"]

        by_user_id = worker_profiles.get_by_user_id(user["id"])

        assert by_user_id is not None
        assert by_user_id["id"] == worker_profile["id"]

    finally:
        # Delete children before parents because of foreign keys.
        if worker_profile is not None:
            worker_profiles.delete_by_id(worker_profile["id"])

        if user is not None:
            users.delete_by_id(user["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_by_id_returns_false_for_unknown_worker_profile():
    repository = WorkerProfilesRepository()

    assert repository.delete_by_id(uuid4()) is False
