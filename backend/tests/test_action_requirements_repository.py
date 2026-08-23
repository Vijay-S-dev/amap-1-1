from uuid import uuid4

from repositories.action_requirements import ActionRequirementsRepository
from repositories.actions import ActionsRepository


def test_get_by_id_returns_none_for_unknown_action_requirement():
    repository = ActionRequirementsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_create_and_get_action_requirement():
    actions = ActionsRepository()
    requirements = ActionRequirementsRepository()

    action = None
    requirement = None

    try:
        action = actions.create(
            f"test-action-{uuid4()}",
            f"Test Action {uuid4()}",
        )

        requirement = requirements.create(
            action["id"],
            f"test-requirement-{uuid4()}",
            "Test requirement description",
            requirement_data={"field": "value"},
        )

        assert requirement is not None
        assert requirement["action_id"] == action["id"]
        assert requirement["requirement_type"] == "validation"
        assert requirement["requirement_data"] == {"field": "value"}
        assert requirement["status"] == "active"

        result = requirements.get_by_id(requirement["id"])

        assert result is not None
        assert result["id"] == requirement["id"]
        assert result["name"] == requirement["name"]

    finally:
        if requirement is not None:
            requirements.delete_by_id(requirement["id"])

        if action is not None:
            actions.delete_by_id(action["id"])


def test_get_by_action_id_and_name_returns_requirement():
    actions = ActionsRepository()
    requirements = ActionRequirementsRepository()

    action = None
    requirement = None
    name = f"test-requirement-{uuid4()}"

    try:
        action = actions.create(
            f"test-action-{uuid4()}",
            f"Test Action {uuid4()}",
        )

        requirement = requirements.create(
            action["id"],
            name,
        )

        result = requirements.get_by_action_id_and_name(
            action["id"],
            name,
        )

        assert result is not None
        assert result["id"] == requirement["id"]

    finally:
        if requirement is not None:
            requirements.delete_by_id(requirement["id"])

        if action is not None:
            actions.delete_by_id(action["id"])


def test_list_by_action_id_contains_created_requirement():
    actions = ActionsRepository()
    requirements = ActionRequirementsRepository()

    action = None
    requirement = None

    try:
        action = actions.create(
            f"test-action-{uuid4()}",
            f"Test Action {uuid4()}",
        )

        requirement = requirements.create(
            action["id"],
            f"test-requirement-{uuid4()}",
        )

        results = requirements.list_by_action_id(action["id"])

        assert any(
            item["id"] == requirement["id"]
            for item in results
        )

    finally:
        if requirement is not None:
            requirements.delete_by_id(requirement["id"])

        if action is not None:
            actions.delete_by_id(action["id"])


def test_update_action_requirement():
    actions = ActionsRepository()
    requirements = ActionRequirementsRepository()

    action = None
    requirement = None

    try:
        action = actions.create(
            f"test-action-{uuid4()}",
            f"Test Action {uuid4()}",
        )

        requirement = requirements.create(
            action["id"],
            f"test-requirement-{uuid4()}",
        )

        updated = requirements.update(
            requirement["id"],
            "updated-requirement",
            "Updated requirement description",
            "validation",
            {"updated": True},
            "active",
        )

        assert updated is not None
        assert updated["id"] == requirement["id"]
        assert updated["name"] == "updated-requirement"
        assert updated["description"] == "Updated requirement description"
        assert updated["requirement_type"] == "validation"
        assert updated["requirement_data"] == {"updated": True}
        assert updated["status"] == "active"

    finally:
        if requirement is not None:
            requirements.delete_by_id(requirement["id"])

        if action is not None:
            actions.delete_by_id(action["id"])


def test_delete_returns_false_for_unknown_action_requirement():
    repository = ActionRequirementsRepository()

    assert repository.delete_by_id(uuid4()) is False
