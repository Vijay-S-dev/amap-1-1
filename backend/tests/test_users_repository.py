from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository


def test_get_by_id_returns_none_for_unknown_user():
    repository = UsersRepository()

    result = repository.get_by_id(uuid4())

    assert result is None


def test_get_by_email_returns_none_for_unknown_user():
    repository = UsersRepository()

    result = repository.get_by_email(
        uuid4(),
        f"unknown-{uuid4()}@example.com",
    )

    assert result is None


def test_list_by_organization_returns_a_list():
    repository = UsersRepository()

    result = repository.list_by_organization(uuid4())

    assert isinstance(result, list)


def test_create_and_get_user():
    organizations = OrganizationsRepository()
    users = UsersRepository()

    organization = None
    user = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        email = f"test-{uuid4()}@example.com"
        full_name = "Test User"
        password_hash = "test-password-hash"

        user = users.create(
            organization["id"],
            email,
            full_name,
            password_hash,
        )

        assert user is not None
        assert user["id"] is not None
        assert user["organization_id"] == organization["id"]
        assert user["email"] == email
        assert user["full_name"] == full_name
        assert user["password_hash"] == password_hash
        assert user["status"] == "active"

        by_id = users.get_by_id(user["id"])

        assert by_id is not None
        assert by_id["id"] == user["id"]

        by_email = users.get_by_email(
            organization["id"],
            email,
        )

        assert by_email is not None
        assert by_email["id"] == user["id"]

    finally:
        if user is not None:
            users.delete_by_id(user["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_create_user_appears_in_organization_list():
    organizations = OrganizationsRepository()
    users = UsersRepository()

    organization = None
    user = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-{uuid4()}@example.com",
            "Test User",
            "test-password-hash",
        )

        user_list = users.list_by_organization(
            organization["id"]
        )

        assert any(
            item["id"] == user["id"]
            for item in user_list
        )

    finally:
        if user is not None:
            users.delete_by_id(user["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_by_id_returns_false_for_unknown_user():
    repository = UsersRepository()

    result = repository.delete_by_id(uuid4())

    assert result is False
