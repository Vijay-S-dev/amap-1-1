from uuid import uuid4

from repositories.departments import DepartmentsRepository
from repositories.organizations import OrganizationsRepository


def test_get_by_id_returns_none_for_unknown_department():
    repository = DepartmentsRepository()

    result = repository.get_by_id(uuid4())

    assert result is None


def test_get_by_name_returns_none_for_unknown_department():
    repository = DepartmentsRepository()

    result = repository.get_by_name(
        uuid4(),
        f"unknown-department-{uuid4()}",
    )

    assert result is None


def test_list_by_organization_returns_a_list():
    repository = DepartmentsRepository()

    result = repository.list_by_organization(uuid4())

    assert isinstance(result, list)


def test_create_and_get_department():
    organizations = OrganizationsRepository()
    departments = DepartmentsRepository()

    organization = None
    department = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        department_name = f"test-department-{uuid4()}"

        department = departments.create(
            organization["id"],
            department_name,
        )

        assert department is not None
        assert department["id"] is not None
        assert department["organization_id"] == organization["id"]
        assert department["name"] == department_name
        assert department["status"] == "active"

        by_id = departments.get_by_id(department["id"])

        assert by_id is not None
        assert by_id["id"] == department["id"]

        by_name = departments.get_by_name(
            organization["id"],
            department_name,
        )

        assert by_name is not None
        assert by_name["id"] == department["id"]

    finally:
        if department is not None:
            departments.delete_by_id(department["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_create_department_appears_in_organization_list():
    organizations = OrganizationsRepository()
    departments = DepartmentsRepository()

    organization = None
    department = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        department = departments.create(
            organization["id"],
            f"test-department-{uuid4()}",
        )

        department_list = departments.list_by_organization(
            organization["id"]
        )

        assert any(
            item["id"] == department["id"]
            for item in department_list
        )

    finally:
        if department is not None:
            departments.delete_by_id(department["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_by_id_returns_false_for_unknown_department():
    repository = DepartmentsRepository()

    result = repository.delete_by_id(uuid4())

    assert result is False
