from uuid import uuid4

from repositories.actions import ActionsRepository
from repositories.interaction_configurations import (
    InteractionConfigurationsRepository,
)
from repositories.organizations import OrganizationsRepository
from repositories.voice_configurations import (
    VoiceConfigurationsRepository,
)


def create_dependencies():
    organizations_repository = OrganizationsRepository()
    interaction_configurations_repository = (
        InteractionConfigurationsRepository()
    )
    actions_repository = ActionsRepository()

    unique_id = uuid4()

    organization = organizations_repository.create(
        name=f"Test Organization {unique_id}",
    )

    interaction_configuration = (
        interaction_configurations_repository.create(
            organization_id=organization["id"],
            name=f"Test Voice Configuration {unique_id}",
            description="Test interaction configuration",
            status="active",
        )
    )

    action = actions_repository.create(
        name=f"test-voice-action-{unique_id}",
        display_name="Test Voice Action",
        description="Test action for voice configuration",
        category="general",
        status="active",
    )

    return {
        "organization": organization,
        "interaction_configuration": interaction_configuration,
        "action": action,
    }


def test_create_and_get_voice_configuration():
    dependencies = create_dependencies()
    repository = VoiceConfigurationsRepository()

    voice_configuration = repository.create(
        interaction_configuration_id=(
            dependencies["interaction_configuration"]["id"]
        ),
        command_phrase="start task",
        action_id=dependencies["action"]["id"],
        is_enabled=True,
        confidence_threshold=0.9500,
    )

    fetched_configuration = repository.get_by_id(
        voice_configuration["id"]
    )

    assert fetched_configuration is not None
    assert fetched_configuration["id"] == voice_configuration["id"]
    assert (
        fetched_configuration["interaction_configuration_id"]
        == dependencies["interaction_configuration"]["id"]
    )
    assert fetched_configuration["command_phrase"] == "start task"
    assert (
        fetched_configuration["action_id"]
        == dependencies["action"]["id"]
    )
    assert fetched_configuration["is_enabled"] is True
    assert fetched_configuration["confidence_threshold"] == 0.9500


def test_get_by_command_phrase_returns_created_configuration():
    dependencies = create_dependencies()
    repository = VoiceConfigurationsRepository()

    voice_configuration = repository.create(
        interaction_configuration_id=(
            dependencies["interaction_configuration"]["id"]
        ),
        command_phrase="pause task",
        action_id=dependencies["action"]["id"],
    )

    fetched_configuration = repository.get_by_command_phrase(
        dependencies["interaction_configuration"]["id"],
        "pause task",
    )

    assert fetched_configuration is not None
    assert fetched_configuration["id"] == voice_configuration["id"]
    assert fetched_configuration["command_phrase"] == "pause task"


def test_get_by_command_phrase_returns_none_when_missing():
    dependencies = create_dependencies()
    repository = VoiceConfigurationsRepository()

    fetched_configuration = repository.get_by_command_phrase(
        dependencies["interaction_configuration"]["id"],
        "does not exist",
    )

    assert fetched_configuration is None


def test_list_by_interaction_configuration_id_contains_created_configuration():
    dependencies = create_dependencies()
    repository = VoiceConfigurationsRepository()

    voice_configuration = repository.create(
        interaction_configuration_id=(
            dependencies["interaction_configuration"]["id"]
        ),
        command_phrase="complete task",
        action_id=dependencies["action"]["id"],
    )

    configurations = (
        repository.list_by_interaction_configuration_id(
            dependencies["interaction_configuration"]["id"]
        )
    )

    configuration_ids = {
        configuration["id"]
        for configuration in configurations
    }

    assert voice_configuration["id"] in configuration_ids


def test_list_by_action_id_contains_created_configuration():
    dependencies = create_dependencies()
    repository = VoiceConfigurationsRepository()

    voice_configuration = repository.create(
        interaction_configuration_id=(
            dependencies["interaction_configuration"]["id"]
        ),
        command_phrase="cancel task",
        action_id=dependencies["action"]["id"],
    )

    configurations = repository.list_by_action_id(
        dependencies["action"]["id"]
    )

    configuration_ids = {
        configuration["id"]
        for configuration in configurations
    }

    assert voice_configuration["id"] in configuration_ids


def test_create_uses_default_values():
    dependencies = create_dependencies()
    repository = VoiceConfigurationsRepository()

    voice_configuration = repository.create(
        interaction_configuration_id=(
            dependencies["interaction_configuration"]["id"]
        ),
        command_phrase="resume task",
        action_id=dependencies["action"]["id"],
    )

    assert voice_configuration["is_enabled"] is True
    assert voice_configuration["confidence_threshold"] is None


def test_update_voice_configuration():
    dependencies = create_dependencies()
    repository = VoiceConfigurationsRepository()

    voice_configuration = repository.create(
        interaction_configuration_id=(
            dependencies["interaction_configuration"]["id"]
        ),
        command_phrase="start work",
        action_id=dependencies["action"]["id"],
        is_enabled=True,
        confidence_threshold=0.8000,
    )

    updated_configuration = repository.update(
        voice_configuration_id=voice_configuration["id"],
        command_phrase="begin work",
        action_id=dependencies["action"]["id"],
        is_enabled=False,
        confidence_threshold=0.9000,
    )

    assert updated_configuration is not None
    assert updated_configuration["id"] == voice_configuration["id"]
    assert updated_configuration["command_phrase"] == "begin work"
    assert updated_configuration["is_enabled"] is False
    assert updated_configuration["confidence_threshold"] == 0.9000


def test_update_returns_none_for_missing_configuration():
    dependencies = create_dependencies()
    repository = VoiceConfigurationsRepository()

    updated_configuration = repository.update(
        voice_configuration_id=uuid4(),
        command_phrase="missing",
        action_id=dependencies["action"]["id"],
        is_enabled=True,
        confidence_threshold=None,
    )

    assert updated_configuration is None


def test_delete_by_id_returns_true_for_existing_configuration():
    dependencies = create_dependencies()
    repository = VoiceConfigurationsRepository()

    voice_configuration = repository.create(
        interaction_configuration_id=(
            dependencies["interaction_configuration"]["id"]
        ),
        command_phrase="delete me",
        action_id=dependencies["action"]["id"],
    )

    deleted = repository.delete_by_id(
        voice_configuration["id"]
    )

    assert deleted is True
    assert repository.get_by_id(voice_configuration["id"]) is None


def test_delete_by_id_returns_false_for_missing_configuration():
    repository = VoiceConfigurationsRepository()

    deleted = repository.delete_by_id(uuid4())

    assert deleted is False
