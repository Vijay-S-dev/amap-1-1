from uuid import uuid4

from repositories.organizations import OrganizationsRepository
from repositories.permissions import PermissionsRepository
from repositories.role_permissions import RolePermissionsRepository
from repositories.roles import RolesRepository


def _make_org():
    orgs = OrganizationsRepository()
    org = orgs.create(f"test-org-{uuid4().hex[:8]}")
    return org


def test_get_returns_none_for_unknown_assignment():
    repository = RolePermissionsRepository()
    org = _make_org()
    try:
        assert repository.get(org["id"], uuid4(), uuid4()) is None
    finally:
        OrganizationsRepository().delete_by_id(org["id"]) if hasattr(
            OrganizationsRepository(), "delete_by_id"
        ) else None


def test_create_and_get_role_permission_assignment():
    roles = RolesRepository()
    permissions = PermissionsRepository()
    role_permissions = RolePermissionsRepository()
    org = _make_org()

    role = None
    permission = None
    assignment = None

    try:
        role = roles.create(f"test-role-{uuid4()}")
        permission = permissions.create(f"test-permission-{uuid4()}")

        assignment = role_permissions.create(
            org["id"],
            role["id"],
            permission["id"],
        )

        assert assignment is not None
        assert assignment["organization_id"] == org["id"]
        assert assignment["role_id"] == role["id"]
        assert assignment["permission_id"] == permission["id"]

        result = role_permissions.get(
            org["id"],
            role["id"],
            permission["id"],
        )
        assert result is not None
        assert result["organization_id"] == org["id"]

        # Tenant isolation: another organization must not see this grant.
        other = _make_org()
        try:
            assert role_permissions.get(other["id"], role["id"], permission["id"]) is None
        finally:
            _delete_org(other["id"])

    finally:
        if assignment is not None:
            role_permissions.delete(
                org["id"],
                assignment["role_id"],
                assignment["permission_id"],
            )
        if permission is not None:
            permissions.delete_by_id(permission["id"])
        if role is not None:
            roles.delete_by_id(role["id"])
        _delete_org(org["id"])


def test_get_by_role_id_returns_assignments():
    roles = RolesRepository()
    permissions = PermissionsRepository()
    role_permissions = RolePermissionsRepository()
    org = _make_org()

    role = None
    permission = None
    assignment = None

    try:
        role = roles.create(f"test-role-{uuid4()}")
        permission = permissions.create(f"test-permission-{uuid4()}")

        assignment = role_permissions.create(org["id"], role["id"], permission["id"])

        results = role_permissions.get_by_role_id(org["id"], role["id"])
        assert any(item["permission_id"] == permission["id"] for item in results)
    finally:
        if assignment is not None:
            role_permissions.delete(org["id"], role["id"], permission["id"])
        if permission is not None:
            permissions.delete_by_id(permission["id"])
        if role is not None:
            roles.delete_by_id(role["id"])
        _delete_org(org["id"])


def test_list_matrix_returns_joined_grants():
    roles = RolesRepository()
    permissions = PermissionsRepository()
    role_permissions = RolePermissionsRepository()
    org = _make_org()

    role = None
    permission = None
    try:
        role = roles.create(f"test-role-{uuid4()}")
        permission = permissions.create(f"test-permission-{uuid4()}")
        role_permissions.create(org["id"], role["id"], permission["id"])

        matrix = role_permissions.list_matrix(org["id"])
        assert any(
            m["role_name"] == role["name"] and m["permission_name"] == permission["name"]
            for m in matrix
        )

        other = _make_org()
        try:
            other_matrix = role_permissions.list_matrix(other["id"])
            assert not any(
                m["permission_name"] == permission["name"] for m in other_matrix
            )
        finally:
            _delete_org(other["id"])
    finally:
        if permission is not None:
            role_permissions.delete(org["id"], role["id"], permission["id"])
        if permission is not None:
            permissions.delete_by_id(permission["id"])
        if role is not None:
            roles.delete_by_id(role["id"])
        _delete_org(org["id"])


def test_delete_returns_false_for_unknown_assignment():
    repository = RolePermissionsRepository()
    org = _make_org()
    try:
        assert repository.delete(org["id"], uuid4(), uuid4()) is False
    finally:
        _delete_org(org["id"])


def _delete_org(org_id):
    from app.database import get_db_connection

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM organizations WHERE id = %s", (org_id,))
            conn.commit()
