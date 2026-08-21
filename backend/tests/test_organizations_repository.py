from uuid import uuid4

from repositories.organizations import OrganizationsRepository


def test_get_by_id_returns_none_for_unknown_organization():
    repository = OrganizationsRepository()

    result = repository.get_by_id(uuid4())

    assert result is None
