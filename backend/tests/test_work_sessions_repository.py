from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.worker_profiles import WorkerProfilesRepository
from repositories.work_sessions import WorkSessionsRepository


def create_worker_profile():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()

    organization = organizations.create(
        f"test-org-{uuid4()}"
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

    return (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    )


def cleanup_worker_profile(
    organizations,
    users,
    worker_profiles,
    organization,
    user,
    worker_profile,
):
    if worker_profile is not None:
        worker_profiles.delete_by_id(worker_profile["id"])

    if user is not None:
        users.delete_by_id(user["id"])

    if organization is not None:
        organizations.delete_by_id(organization["id"])


def test_get_by_id_returns_none_for_unknown_work_session():
    repository = WorkSessionsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_create_and_get_work_session():
    repository = WorkSessionsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_profile()

    work_session = None

    try:
        work_session = repository.create(
            worker_profile["id"],
        )

        assert work_session is not None
        assert work_session["worker_profile_id"] == worker_profile["id"]
        assert work_session["status"] == "active"
        assert work_session["started_at"] is not None
        assert work_session["ended_at"] is None

        result = repository.get_by_id(
            work_session["id"],
        )

        assert result is not None
        assert result["id"] == work_session["id"]
        assert result["worker_profile_id"] == worker_profile["id"]

    finally:
        if work_session is not None:
            repository.delete_by_id(work_session["id"])

        cleanup_worker_profile(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )


def test_list_by_worker_profile_id_contains_created_work_session():
    repository = WorkSessionsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_profile()

    work_session = None

    try:
        work_session = repository.create(
            worker_profile["id"],
        )

        results = repository.list_by_worker_profile_id(
            worker_profile["id"],
        )

        assert any(
            item["id"] == work_session["id"]
            for item in results
        )

    finally:
        if work_session is not None:
            repository.delete_by_id(work_session["id"])

        cleanup_worker_profile(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )


def test_list_by_status_contains_created_work_session():
    repository = WorkSessionsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_profile()

    work_session = None

    try:
        work_session = repository.create(
            worker_profile["id"],
            "active",
        )

        results = repository.list_by_status("active")

        assert any(
            item["id"] == work_session["id"]
            for item in results
        )

    finally:
        if work_session is not None:
            repository.delete_by_id(work_session["id"])

        cleanup_worker_profile(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )


def test_update_status():
    repository = WorkSessionsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_profile()

    work_session = None

    try:
        work_session = repository.create(
            worker_profile["id"],
        )

        updated = repository.update_status(
            work_session["id"],
            "paused",
        )

        assert updated is not None
        assert updated["id"] == work_session["id"]
        assert updated["status"] == "paused"

        result = repository.get_by_id(
            work_session["id"],
        )

        assert result is not None
        assert result["status"] == "paused"

    finally:
        if work_session is not None:
            repository.delete_by_id(work_session["id"])

        cleanup_worker_profile(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )


def test_end_work_session():
    repository = WorkSessionsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_profile()

    work_session = None

    try:
        work_session = repository.create(
            worker_profile["id"],
        )

        ended = repository.end(
            work_session["id"],
        )

        assert ended is not None
        assert ended["id"] == work_session["id"]
        assert ended["status"] == "completed"
        assert ended["ended_at"] is not None
        assert ended["ended_at"] >= ended["started_at"]

    finally:
        if work_session is not None:
            repository.delete_by_id(work_session["id"])

        cleanup_worker_profile(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )


def test_delete_by_id_returns_false_for_unknown_work_session():
    repository = WorkSessionsRepository()

    assert repository.delete_by_id(uuid4()) is False


def test_delete_by_id_returns_true_for_existing_work_session():
    repository = WorkSessionsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_profile()

    work_session = None

    try:
        work_session = repository.create(
            worker_profile["id"],
        )

        deleted = repository.delete_by_id(
            work_session["id"],
        )

        assert deleted is True
        work_session = None

        assert repository.get_by_id(
            work_session["id"]
        ) is None

    finally:
        if work_session is not None:
            repository.delete_by_id(work_session["id"])

        cleanup_worker_profile(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )
