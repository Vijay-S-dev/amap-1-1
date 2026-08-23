from uuid import uuid4

from repositories.actions import ActionsRepository
from repositories.gesture_configurations import (
    GestureConfigurationsRepository,
)
from repositories.interaction_configurations import (
    InteractionConfigurationsRepository,
)
from repositories.organizations import OrganizationsRepository


def create_dependencies():
    organizations = OrganizationsRepository()
    configurations = InteractionConfigurationsRepository()
    actions = ActionsRepository()

    organization = organizations.create(f"test-org-{uuid4()}")

    configuration = configurations.create(
        organization["id"],
        f"test-interaction-{uuid4()}",
    )

    action = actions.create(
        f"test-action-{uuid4()}",
        f"Test Action {uuid4()}",
    )

    return (
        organizations,
        configurations,
        actions,
        organization,
        configuration,
        action,
    )


def test_create_and_get_gesture_configuration():
    gestures = GestureConfigurationsRepository()

    (
        organizations,
        configurations,
        actions,
        organization,
        configuration,
        action,
    ) = create_dependencies()

    gesture = None

    try:
        gesture = gestures.create(
            configuration["id"],
            f"test-gesture-{uuid4()}",
            action["id"],
            confidence_threshold=0.75,
        )

        assert gesture is not None
        assert gesture["interaction_configuration_id"] == configuration["id"]
        assert gesture["action_id"] == action["id"]
        assert gesture["is_enabled"] is True

        fetched = gestures.get_by_id(gesture["id"])

        assert fetched is not None
        assert fetched["id"] == gesture["id"]

    finally:
        if gesture is not None:
            gestures.delete_by_id(gesture["id"])

        actions.delete_by_id(action["id"])
        configurations.delete_by_id(configuration["id"])
        organizations.delete_by_id(organization["id"])


def test_get_by_name_returns_created_gesture_configuration():
    gestures = GestureConfigurationsRepository()

    (
        organizations,
        configurations,
        actions,
        organization,
        configuration,
        action,
    ) = create_dependencies()

    gesture = None
    gesture_name = f"test-gesture-{uuid4()}"

    try:
        gesture = gestures.create(
            configuration["id"],
            gesture_name,
            action["id"],
        )

        fetched = gestures.get_by_name(
            configuration["id"],
            gesture_name,
        )

        assert fetched is not None
        assert fetched["id"] == gesture["id"]

    finally:
        if gesture is not None:
            gestures.delete_by_id(gesture["id"])

        actions.delete_by_id(action["id"])
        configurations.delete_by_id(configuration["id"])
        organizations.delete_by_id(organization["id"])


def test_list_by_interaction_configuration_id_contains_created_gesture():
    gestures = GestureConfigurationsRepository()

    (
        organizations,
        configurations,
        actions,
        organization,
        configuration,
        action,
    ) = create_dependencies()

    gesture = None

    try:
        gesture = gestures.create(
            configuration["id"],
            f"test-gesture-{uuid4()}",
            action["id"],
        )

        results = gestures.list_by_interaction_configuration_id(
            configuration["id"],
        )

        assert any(
            result["id"] == gesture["id"]
            for result in results
        )

    finally:
        if gesture is not None:
            gestures.delete_by_id(gesture["id"])

        actions.delete_by_id(action["id"])
        configurations.delete_by_id(configuration["id"])
        organizations.delete_by_id(organization["id"])


def test_list_by_action_id_contains_created_gesture():
    gestures = GestureConfigurationsRepository()

    (
        organizations,
        configurations,
        actions,
        organization,
        configuration,
        action,
    ) = create_dependencies()

    gesture = None

    try:
        gesture = gestures.create(
            configuration["id"],
            f"test-gesture-{uuid4()}",
            action["id"],
        )

        results = gestures.list_by_action_id(action["id"])

        assert any(
            result["id"] == gesture["id"]
            for result in results
        )

    finally:
        if gesture is not None:
            gestures.delete_by_id(gesture["id"])

        actions.delete_by_id(action["id"])
        configurations.delete_by_id(configuration["id"])
        organizations.delete_by_id(organization["id"])


def test_update_enabled():
    gestures = GestureConfigurationsRepository()

    (
        organizations,
        configurations,
        actions,
        organization,
        configuration,
        action,
    ) = create_dependencies()

    gesture = None

    try:
        gesture = gestures.create(
            configuration["id"],
            f"test-gesture-{uuid4()}",
            action["id"],
        )

        updated = gestures.update_enabled(
            gesture["id"],
            False,
        )

        assert updated is not None
        assert updated["is_enabled"] is False

    finally:
        if gesture is not None:
            gestures.delete_by_id(gesture["id"])

        actions.delete_by_id(action["id"])
        configurations.delete_by_id(configuration["id"])
        organizations.delete_by_id(organization["id"])


def test_delete_by_id_returns_true_for_existing_gesture():
    gestures = GestureConfigurationsRepository()

    (
        organizations,
        configurations,
        actions,
        organization,
        configuration,
        action,
    ) = create_dependencies()

    gesture = None

    try:
        gesture = gestures.create(
            configuration["id"],
            f"test-gesture-{uuid4()}",
            action["id"],
        )

        deleted = gestures.delete_by_id(gesture["id"])

        assert deleted is True

        gesture = None

    finally:
        if gesture is not None:
            gestures.delete_by_id(gesture["id"])

        actions.delete_by_id(action["id"])
        configurations.delete_by_id(configuration["id"])
        organizations.delete_by_id(organization["id"])
