from uuid import uuid4

from repositories.actions import ActionsRepository


def test_get_by_id_returns_none_for_unknown_action():
    repository = ActionsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_create_and_get_action_by_id():
    repository = ActionsRepository()
    action = None

    try:
        action = repository.create(
            f"test-action-{uuid4()}",
            f"Test Action {uuid4()}",
            "Test action description",
        )

        assert action is not None
        assert action["status"] == "active"
        assert action["category"] == "general"

        result = repository.get_by_id(action["id"])

        assert result is not None
        assert result["id"] == action["id"]
        assert result["name"] == action["name"]

    finally:
        if action is not None:
            repository.delete_by_id(action["id"])


def test_get_by_name_returns_action():
    repository = ActionsRepository()
    action = None
    name = f"test-action-{uuid4()}"

    try:
        action = repository.create(
            name,
            f"Test Action {uuid4()}",
        )

        result = repository.get_by_name(name)

        assert result is not None
        assert result["id"] == action["id"]

    finally:
        if action is not None:
            repository.delete_by_id(action["id"])


def test_list_all_contains_created_action():
    repository = ActionsRepository()
    action = None

    try:
        action = repository.create(
            f"test-action-{uuid4()}",
            f"Test Action {uuid4()}",
        )

        results = repository.list_all()

        assert any(
            item["id"] == action["id"]
            for item in results
        )

    finally:
        if action is not None:
            repository.delete_by_id(action["id"])


def test_update_action():
    repository = ActionsRepository()
    action = None

    try:
        action = repository.create(
            f"test-action-{uuid4()}",
            "Original Action",
        )

        updated = repository.update(
            action["id"],
            "updated-action",
            "Updated Action",
            "Updated description",
            "updated-category",
            "inactive",
        )

        assert updated is not None
        assert updated["id"] == action["id"]
        assert updated["name"] == "updated-action"
        assert updated["display_name"] == "Updated Action"
        assert updated["description"] == "Updated description"
        assert updated["category"] == "updated-category"
        assert updated["status"] == "inactive"

    finally:
        if action is not None:
            repository.delete_by_id(action["id"])


def test_delete_returns_false_for_unknown_action():
    repository = ActionsRepository()

    assert repository.delete_by_id(uuid4()) is False
