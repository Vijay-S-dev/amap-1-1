from uuid import uuid4

from repositories.departments import DepartmentsRepository
from repositories.organizations import OrganizationsRepository
from repositories.user_departments import UserDepartmentsRepository
from repositories.users import UsersRepository


def test_get_returns_none_for_unknown_assignment():
    repository = UserDepartmentsRepository()

    assert repository.get(uuid4(), uuid4()) is None


def test_create_and_get_user_department_assignment():
    organizations = OrganizationsRepository()
    departments = DepartmentsRepository()
    users = UsersRepository()
    user_departments = UserDepartmentsRepository()

    organization = None
    department = None
    user = None
    assignment = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        department = departments.create(
            organization["id"],
            f"test-department-{uuid4()}",
        )

        user = users.create(
            organization["id"],
            f"test-{uuid4()}@example.com",
            "Test User",
            "test-password-hash",
        )

        assignment = user_departments.create(
            user["id"],
            department["id"],
        )

        assert assignment is not None
        assert assignment["user_id"] == user["id"]
        assert assignment["department_id"] == department["id"]

        result = user_departments.get(
            user["id"],
            department["id"],
        )

        assert result is not None
        assert result["user_id"] == user["id"]
        assert result["department_id"] == department["id"]

    finally:
        if assignment is not None:
            user_departments.delete(
                assignment["user_id"],
                assignment["department_id"],
            )

        if user is not None:
            users.delete_by_id(user["id"])

        if department is not None:
            departments.delete_by_id(department["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_get_by_user_id_returns_assignments():
    organizations = OrganizationsRepository()
    departments = DepartmentsRepository()
    users = UsersRepository()
    user_departments = UserDepartmentsRepository()

    organization = None
    department = None
    user = None
    assignment = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        department = departments.create(
            organization["id"],
            f"test-department-{uuid4()}",
        )

        user = users.create(
            organization["id"],
            f"test-{uuid4()}@example.com",
            "Test User",
            "test-password-hash",
        )

        assignment = user_departments.create(
            user["id"],
            department["id"],
        )

        results = user_departments.get_by_user_id(user["id"])

        assert len(results) >= 1
        assert any(
            item["department_id"] == department["id"]
            for item in results
        )

    finally:
        if assignment is not None:
            user_departments.delete(
                assignment["user_id"],
                assignment["department_id"],
            )

        if user is not None:
            users.delete_by_id(user["id"])

        if department is not None:
            departments.delete_by_id(department["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_get_by_department_id_returns_assignments():
    organizations = OrganizationsRepository()
    departments = DepartmentsRepository()
    users = UsersRepository()
    user_departments = UserDepartmentsRepository()

    organization = None
    department = None
    user = None
    assignment = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        department = departments.create(
            organization["id"],
            f"test-department-{uuid4()}",
        )

        user = users.create(
            organization["id"],
            f"test-{uuid4()}@example.com",
            "Test User",
            "test-password-hash",
        )

        assignment = user_departments.create(
            user["id"],
            department["id"],
        )

        results = user_departments.get_by_department_id(department["id"])

        assert len(results) >= 1
        assert any(
            item["user_id"] == user["id"]
            for item in results
        )

    finally:
        if assignment is not None:
            user_departments.delete(
                assignment["user_id"],
                assignment["department_id"],
            )

        if user is not None:
            users.delete_by_id(user["id"])

        if department is not None:
            departments.delete_by_id(department["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_returns_false_for_unknown_assignment():
    repository = UserDepartmentsRepository()

    assert repository.delete(uuid4(), uuid4()) is False
