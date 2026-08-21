from uuid import uuid4

from app.database import get_db_connection
from repositories.organizations import OrganizationsRepository


def test_get_by_id_returns_none_for_unknown_organization():
    repository = OrganizationsRepository()

    result = repository.get_by_id(uuid4())

    assert result is None


def test_get_by_name_returns_none_for_unknown_organization():
    repository = OrganizationsRepository()

    result = repository.get_by_name(f"unknown-org-{uuid4()}")

    assert result is None


def test_list_all_returns_a_list():
    repository = OrganizationsRepository()

    result = repository.list_all()

    assert isinstance(result, list)


def test_create_and_get_organization():
    repository = OrganizationsRepository()
    name = f"test-org-{uuid4()}"
    organization = None

    try:
        organization = repository.create(name)

        assert organization is not None
        assert organization["id"] is not None
        assert organization["name"] == name
        assert organization["status"] == "active"

        by_id = repository.get_by_id(organization["id"])
        assert by_id is not None
        assert by_id["id"] == organization["id"]

        by_name = repository.get_by_name(name)
        assert by_name is not None
        assert by_name["id"] == organization["id"]

    finally:
        if organization is not None:
            repository.delete_by_id(organization["id"])


def test_delete_by_id_returns_false_for_unknown_organization():
    repository = OrganizationsRepository()

    result = repository.delete_by_id(uuid4())

    assert result is False


def test_create_organization_appears_in_list():
    repository = OrganizationsRepository()
    name = f"test-org-{uuid4()}"
    organization = None

    try:
        organization = repository.create(name)

        organizations = repository.list_all()

        assert any(
            item["id"] == organization["id"]
            for item in organizations
        )

    finally:
        if organization is not None:
            repository.delete_by_id(organization["id"])
