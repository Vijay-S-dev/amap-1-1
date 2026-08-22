from uuid import uuid4

from repositories.roles import RolesRepository


def test_get_by_id_returns_none_for_unknown_role():
    repository = RolesRepository()

    assert repository.get_by_id(uuid4()) is None


def test_get_by_name_returns_none_for_unknown_role():
    repository = RolesRepository()

    assert repository.get_by_name(f"unknown-role-{uuid4()}") is None


def test_create_and_get_role():
    repository = RolesRepository()

    role = None

    try:
        name = f"test-role-{uuid4()}"

        role = repository.create(
            name,
            "Test role description",
        )

        assert role is not None
        assert role["id"] is not None
        assert role["name"] == name
        assert role["description"] == "Test role description"

        by_id = repository.get_by_id(role["id"])

        assert by_id is not None
        assert by_id["id"] == role["id"]

        by_name = repository.get_by_name(name)

        assert by_name is not None
        assert by_name["id"] == role["id"]

    finally:
        if role is not None:
            repository.delete_by_id(role["id"])


def test_create_role_without_description():
    repository = RolesRepository()

    role = None

    try:
        name = f"test-role-{uuid4()}"

        role = repository.create(name)

        assert role is not None
        assert role["name"] == name
        assert role["description"] is None

    finally:
        if role is not None:
            repository.delete_by_id(role["id"])


def test_list_all_contains_created_role():
    repository = RolesRepository()

    role = None

    try:
        name = f"test-role-{uuid4()}"
        role = repository.create(name)

        roles = repository.list_all()

        assert any(
            item["id"] == role["id"]
            for item in roles
        )

    finally:
        if role is not None:
            repository.delete_by_id(role["id"])


def test_delete_by_id_returns_false_for_unknown_role():
    repository = RolesRepository()

    assert repository.delete_by_id(uuid4()) is False
