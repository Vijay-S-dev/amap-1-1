from uuid import uuid4

from repositories.permissions import PermissionsRepository


def test_get_by_id_returns_none_for_unknown_permission():
    repository = PermissionsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_get_by_name_returns_none_for_unknown_permission():
    repository = PermissionsRepository()

    assert repository.get_by_name(
        f"unknown-permission-{uuid4()}"
    ) is None


def test_create_and_get_permission():
    repository = PermissionsRepository()

    permission = None

    try:
        name = f"test-permission-{uuid4()}"

        permission = repository.create(
            name,
            "Test permission description",
        )

        assert permission is not None
        assert permission["id"] is not None
        assert permission["name"] == name
        assert permission["description"] == "Test permission description"

        by_id = repository.get_by_id(permission["id"])

        assert by_id is not None
        assert by_id["id"] == permission["id"]

        by_name = repository.get_by_name(name)

        assert by_name is not None
        assert by_name["id"] == permission["id"]

    finally:
        if permission is not None:
            repository.delete_by_id(permission["id"])


def test_create_permission_without_description():
    repository = PermissionsRepository()

    permission = None

    try:
        name = f"test-permission-{uuid4()}"

        permission = repository.create(name)

        assert permission is not None
        assert permission["name"] == name
        assert permission["description"] is None

    finally:
        if permission is not None:
            repository.delete_by_id(permission["id"])


def test_list_all_contains_created_permission():
    repository = PermissionsRepository()

    permission = None

    try:
        name = f"test-permission-{uuid4()}"
        permission = repository.create(name)

        permissions = repository.list_all()

        assert any(
            item["id"] == permission["id"]
            for item in permissions
        )

    finally:
        if permission is not None:
            repository.delete_by_id(permission["id"])


def test_delete_by_id_returns_false_for_unknown_permission():
    repository = PermissionsRepository()

    assert repository.delete_by_id(uuid4()) is False
