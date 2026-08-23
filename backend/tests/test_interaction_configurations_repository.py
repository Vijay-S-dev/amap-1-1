from uuid import uuid4

from repositories.interaction_configurations import (
    InteractionConfigurationsRepository,
)
from repositories.organizations import OrganizationsRepository


def test_create_and_get_interaction_configuration():
    organizations = OrganizationsRepository()
    configurations = InteractionConfigurationsRepository()

    organization = None
    configuration = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        configuration = configurations.create(
            organization["id"],
            f"test-configuration-{uuid4()}",
            "Test interaction configuration",
        )

        assert configuration is not None
        assert configuration["organization_id"] == organization["id"]
        assert configuration["status"] == "active"

        fetched = configurations.get_by_id(configuration["id"])

        assert fetched is not None
        assert fetched["id"] == configuration["id"]

    finally:
        if configuration is not None:
            configurations.delete_by_id(configuration["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_get_by_name_returns_created_configuration():
    organizations = OrganizationsRepository()
    configurations = InteractionConfigurationsRepository()

    organization = None
    configuration = None
    name = f"test-configuration-{uuid4()}"

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        configuration = configurations.create(
            organization["id"],
            name,
        )

        fetched = configurations.get_by_name(
            organization["id"],
            name,
        )

        assert fetched is not None
        assert fetched["id"] == configuration["id"]

    finally:
        if configuration is not None:
            configurations.delete_by_id(configuration["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_organization_id_contains_created_configuration():
    organizations = OrganizationsRepository()
    configurations = InteractionConfigurationsRepository()

    organization = None
    configuration = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        configuration = configurations.create(
            organization["id"],
            f"test-configuration-{uuid4()}",
        )

        results = configurations.list_by_organization_id(
            organization["id"],
        )

        assert any(
            result["id"] == configuration["id"]
            for result in results
        )

    finally:
        if configuration is not None:
            configurations.delete_by_id(configuration["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_status_contains_created_configuration():
    organizations = OrganizationsRepository()
    configurations = InteractionConfigurationsRepository()

    organization = None
    configuration = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        configuration = configurations.create(
            organization["id"],
            f"test-configuration-{uuid4()}",
            status="inactive",
        )

        results = configurations.list_by_status("inactive")

        assert any(
            result["id"] == configuration["id"]
            for result in results
        )

    finally:
        if configuration is not None:
            configurations.delete_by_id(configuration["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_update_status():
    organizations = OrganizationsRepository()
    configurations = InteractionConfigurationsRepository()

    organization = None
    configuration = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        configuration = configurations.create(
            organization["id"],
            f"test-configuration-{uuid4()}",
        )

        updated = configurations.update_status(
            configuration["id"],
            "archived",
        )

        assert updated is not None
        assert updated["status"] == "archived"

    finally:
        if configuration is not None:
            configurations.delete_by_id(configuration["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_by_id_returns_true_for_existing_configuration():
    organizations = OrganizationsRepository()
    configurations = InteractionConfigurationsRepository()

    organization = None
    configuration = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        configuration = configurations.create(
            organization["id"],
            f"test-configuration-{uuid4()}",
        )

        deleted = configurations.delete_by_id(configuration["id"])

        assert deleted is True

        configuration = None

    finally:
        if configuration is not None:
            configurations.delete_by_id(configuration["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])
