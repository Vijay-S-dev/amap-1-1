from uuid import uuid4

from repositories.permissions import PermissionsRepository
from repositories.role_permissions import RolePermissionsRepository
from repositories.roles import RolesRepository


def test_get_returns_none_for_unknown_assignment():
    repository = RolePermissionsRepository()

    assert repository.get(uuid4(), uuid4()) is None


def test_create_and_get_role_permission_assignment():
    roles = RolesRepository()
    permissions = PermissionsRepository()
    role_permissions = RolePermissionsRepository()

    role = None
    permission = None
    assignment = None

    try:
        role = roles.create(f"test-role-{uuid4()}")

        permission = permissions.create(
            f"test-permission-{uuid4()}"
        )

        assignment = role_permissions.create(
            role["id"],
            permission["id"],
        )

        assert assignment is not None
        assert assignment["role_id"] == role["id"]
        assert assignment["permission_id"] == permission["id"]

        result = role_permissions.get(
            role["id"],
            permission["id"],
        )

        assert result is not None
        assert result["role_id"] == role["id"]
        assert result["permission_id"] == permission["id"]

    finally:
        if assignment is not None:
            role_permissions.delete(
                assignment["role_id"],
                assignment["permission_id"],
            )

        if permission is not None:
            permissions.delete_by_id(permission["id"])

        if role is not None:
            roles.delete_by_id(role["id"])


def test_get_by_role_id_returns_assignments():
    roles = RolesRepository()
    permissions = PermissionsRepository()
    role_permissions = RolePermissionsRepository()

    role = None
    permission = None
    assignment = None

    try:
        role = roles.create(f"test-role-{uuid4()}")
        permission = permissions.create(
            f"test-permission-{uuid4()}"
        )

        assignment = role_permissions.create(
            role["id"],
            permission["id"],
        )

        results = role_permissions.get_by_role_id(role["id"])

        assert any(
            item["permission_id"] == permission["id"]
            for item in results
        )

    finally:
        if assignment is not None:
            role_permissions.delete(
                assignment["role_id"],
                assignment["permission_id"],
            )

        if permission is not None:
            permissions.delete_by_id(permission["id"])

        if role is not None:
            roles.delete_by_id(role["id"])


def test_get_by_permission_id_returns_assignments():
    roles = RolesRepository()
    permissions = PermissionsRepository()
    role_permissions = RolePermissionsRepository()

    role = None
    permission = None
    assignment = None

    try:
        role = roles.create(f"test-role-{uuid4()}")
        permission = permissions.create(
            f"test-permission-{uuid4()}"
        )

        assignment = role_permissions.create(
            role["id"],
            permission["id"],
        )

        results = role_permissions.get_by_permission_id(
            permission["id"]
        )

        assert any(
            item["role_id"] == role["id"]
            for item in results
        )

    finally:
        if assignment is not None:
            role_permissions.delete(
                assignment["role_id"],
                assignment["permission_id"],
            )

        if permission is not None:
            permissions.delete_by_id(permission["id"])

        if role is not None:
            roles.delete_by_id(role["id"])


def test_delete_returns_false_for_unknown_assignment():
    repository = RolePermissionsRepository()

    assert repository.delete(uuid4(), uuid4()) is False
