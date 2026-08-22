from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.roles import RolesRepository
from repositories.user_roles import UserRolesRepository
from repositories.users import UsersRepository


def test_get_returns_none_for_unknown_assignment():
    repository = UserRolesRepository()

    assert repository.get(uuid4(), uuid4()) is None


def test_create_and_get_user_role_assignment():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    roles = RolesRepository()
    user_roles = UserRolesRepository()

    organization = None
    user = None
    role = None
    assignment = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-{uuid4()}@example.com",
            "Test User",
            "test-password-hash",
        )

        role = roles.create(f"test-role-{uuid4()}")

        assignment = user_roles.create(
            user["id"],
            role["id"],
        )

        assert assignment is not None
        assert assignment["user_id"] == user["id"]
        assert assignment["role_id"] == role["id"]

        result = user_roles.get(
            user["id"],
            role["id"],
        )

        assert result is not None
        assert result["user_id"] == user["id"]
        assert result["role_id"] == role["id"]

    finally:
        if assignment is not None:
            user_roles.delete(
                assignment["user_id"],
                assignment["role_id"],
            )

        if user is not None:
            users.delete_by_id(user["id"])

        if role is not None:
            roles.delete_by_id(role["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_get_by_user_id_returns_assignments():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    roles = RolesRepository()
    user_roles = UserRolesRepository()

    organization = None
    user = None
    role = None
    assignment = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-{uuid4()}@example.com",
            "Test User",
            "test-password-hash",
        )

        role = roles.create(f"test-role-{uuid4()}")

        assignment = user_roles.create(
            user["id"],
            role["id"],
        )

        results = user_roles.get_by_user_id(user["id"])

        assert any(
            item["role_id"] == role["id"]
            for item in results
        )

    finally:
        if assignment is not None:
            user_roles.delete(
                assignment["user_id"],
                assignment["role_id"],
            )

        if user is not None:
            users.delete_by_id(user["id"])

        if role is not None:
            roles.delete_by_id(role["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_get_by_role_id_returns_assignments():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    roles = RolesRepository()
    user_roles = UserRolesRepository()

    organization = None
    user = None
    role = None
    assignment = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        user = users.create(
            organization["id"],
            f"test-{uuid4()}@example.com",
            "Test User",
            "test-password-hash",
        )

        role = roles.create(f"test-role-{uuid4()}")

        assignment = user_roles.create(
            user["id"],
            role["id"],
        )

        results = user_roles.get_by_role_id(role["id"])

        assert any(
            item["user_id"] == user["id"]
            for item in results
        )

    finally:
        if assignment is not None:
            user_roles.delete(
                assignment["user_id"],
                assignment["role_id"],
            )

        if user is not None:
            users.delete_by_id(user["id"])

        if role is not None:
            roles.delete_by_id(role["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_returns_false_for_unknown_assignment():
    repository = UserRolesRepository()

    assert repository.delete(uuid4(), uuid4()) is False
