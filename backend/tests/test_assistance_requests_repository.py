from uuid import uuid4

from repositories.assistance_requests import AssistanceRequestsRepository
from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.worker_profiles import WorkerProfilesRepository


def create_worker_context():
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


def cleanup_worker_context(
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


def test_get_by_id_returns_none_for_unknown_request():
    repository = AssistanceRequestsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_create_and_get_assistance_request():
    repository = AssistanceRequestsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_context()

    assistance_request = None

    try:
        assistance_request = repository.create(
            organization["id"],
            worker_profile["id"],
            priority="high",
            reason="Need assistance",
            request_data={"source": "test"},
        )

        assert assistance_request is not None
        assert assistance_request["organization_id"] == organization["id"]
        assert assistance_request["worker_profile_id"] == worker_profile["id"]
        assert assistance_request["status"] == "open"
        assert assistance_request["priority"] == "high"
        assert assistance_request["reason"] == "Need assistance"
        assert assistance_request["request_data"] == {"source": "test"}

        result = repository.get_by_id(
            assistance_request["id"],
        )

        assert result is not None
        assert result["id"] == assistance_request["id"]

    finally:
        if assistance_request is not None:
            repository.delete_by_id(assistance_request["id"])

        cleanup_worker_context(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )


def test_list_by_organization_id_contains_created_request():
    repository = AssistanceRequestsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_context()

    assistance_request = None

    try:
        assistance_request = repository.create(
            organization["id"],
            worker_profile["id"],
        )

        results = repository.list_by_organization_id(
            organization["id"],
        )

        assert any(
            item["id"] == assistance_request["id"]
            for item in results
        )

    finally:
        if assistance_request is not None:
            repository.delete_by_id(assistance_request["id"])

        cleanup_worker_context(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )


def test_list_by_worker_profile_id_contains_created_request():
    repository = AssistanceRequestsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_context()

    assistance_request = None

    try:
        assistance_request = repository.create(
            organization["id"],
            worker_profile["id"],
        )

        results = repository.list_by_worker_profile_id(
            worker_profile["id"],
        )

        assert any(
            item["id"] == assistance_request["id"]
            for item in results
        )

    finally:
        if assistance_request is not None:
            repository.delete_by_id(assistance_request["id"])

        cleanup_worker_context(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )


def test_list_by_status_contains_created_request():
    repository = AssistanceRequestsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_context()

    assistance_request = None

    try:
        assistance_request = repository.create(
            organization["id"],
            worker_profile["id"],
        )

        results = repository.list_by_status("open")

        assert any(
            item["id"] == assistance_request["id"]
            for item in results
        )

    finally:
        if assistance_request is not None:
            repository.delete_by_id(assistance_request["id"])

        cleanup_worker_context(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )


def test_update_status():
    repository = AssistanceRequestsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_context()

    assistance_request = None

    try:
        assistance_request = repository.create(
            organization["id"],
            worker_profile["id"],
        )

        updated = repository.update_status(
            assistance_request["id"],
            "in_progress",
        )

        assert updated is not None
        assert updated["status"] == "in_progress"

        result = repository.get_by_id(
            assistance_request["id"],
        )

        assert result is not None
        assert result["status"] == "in_progress"

    finally:
        if assistance_request is not None:
            repository.delete_by_id(assistance_request["id"])

        cleanup_worker_context(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )


def test_acknowledge_request():
    repository = AssistanceRequestsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_context()

    assistance_request = None

    try:
        assistance_request = repository.create(
            organization["id"],
            worker_profile["id"],
        )

        acknowledged = repository.acknowledge(
            assistance_request["id"],
        )

        assert acknowledged is not None
        assert acknowledged["status"] == "acknowledged"
        assert acknowledged["acknowledged_at"] is not None
        assert acknowledged["acknowledged_at"] >= acknowledged["requested_at"]

    finally:
        if assistance_request is not None:
            repository.delete_by_id(assistance_request["id"])

        cleanup_worker_context(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )


def test_resolve_request():
    repository = AssistanceRequestsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_context()

    assistance_request = None

    try:
        assistance_request = repository.create(
            organization["id"],
            worker_profile["id"],
        )

        resolved = repository.resolve(
            assistance_request["id"],
        )

        assert resolved is not None
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"] is not None
        assert resolved["resolved_at"] >= resolved["requested_at"]

    finally:
        if assistance_request is not None:
            repository.delete_by_id(assistance_request["id"])

        cleanup_worker_context(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )


def test_delete_by_id_returns_false_for_unknown_request():
    repository = AssistanceRequestsRepository()

    assert repository.delete_by_id(uuid4()) is False


def test_delete_by_id_returns_true_for_existing_request():
    repository = AssistanceRequestsRepository()

    (
        organizations,
        users,
        worker_profiles,
        organization,
        user,
        worker_profile,
    ) = create_worker_context()

    assistance_request = None

    try:
        assistance_request = repository.create(
            organization["id"],
            worker_profile["id"],
        )

        assistance_request_id = assistance_request["id"]

        deleted = repository.delete_by_id(
            assistance_request_id,
        )

        assert deleted is True
        assistance_request = None

        assert repository.get_by_id(
            assistance_request_id,
        ) is None

    finally:
        if assistance_request is not None:
            repository.delete_by_id(assistance_request["id"])

        cleanup_worker_context(
            organizations,
            users,
            worker_profiles,
            organization,
            user,
            worker_profile,
        )
