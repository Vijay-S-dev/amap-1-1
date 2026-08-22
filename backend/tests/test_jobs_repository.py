from uuid import uuid4

from repositories.jobs import JobsRepository
from repositories.organizations import OrganizationsRepository


def test_get_by_id_returns_none_for_unknown_job():
    repository = JobsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_get_by_name_returns_none_for_unknown_job():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()

    organization = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        result = jobs.get_by_name(
            organization["id"],
            f"unknown-job-{uuid4()}",
        )

        assert result is None

    finally:
        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_create_and_get_job():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()

    organization = None
    job = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        name = f"test-job-{uuid4()}"

        job = jobs.create(
            organization["id"],
            name,
            "Test job description",
        )

        assert job is not None
        assert job["id"] is not None
        assert job["organization_id"] == organization["id"]
        assert job["name"] == name
        assert job["description"] == "Test job description"
        assert job["status"] == "active"

        by_id = jobs.get_by_id(job["id"])

        assert by_id is not None
        assert by_id["id"] == job["id"]

        by_name = jobs.get_by_name(
            organization["id"],
            name,
        )

        assert by_name is not None
        assert by_name["id"] == job["id"]

    finally:
        if job is not None:
            jobs.delete_by_id(job["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_create_job_with_custom_status():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()

    organization = None
    job = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        job = jobs.create(
            organization["id"],
            f"test-job-{uuid4()}",
            status="inactive",
        )

        assert job["status"] == "inactive"

    finally:
        if job is not None:
            jobs.delete_by_id(job["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_organization_id_contains_created_job():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()

    organization = None
    job = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        job = jobs.create(
            organization["id"],
            f"test-job-{uuid4()}",
        )

        results = jobs.list_by_organization_id(
            organization["id"]
        )

        assert any(
            item["id"] == job["id"]
            for item in results
        )

    finally:
        if job is not None:
            jobs.delete_by_id(job["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_by_id_returns_false_for_unknown_job():
    repository = JobsRepository()

    assert repository.delete_by_id(uuid4()) is False
