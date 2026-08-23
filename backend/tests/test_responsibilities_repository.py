from uuid import uuid4

from repositories.jobs import JobsRepository
from repositories.organizations import OrganizationsRepository
from repositories.responsibilities import ResponsibilitiesRepository


def test_get_by_id_returns_none_for_unknown_responsibility():
    repository = ResponsibilitiesRepository()

    assert repository.get_by_id(uuid4()) is None


def test_get_by_name_returns_none_for_unknown_responsibility():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()
    responsibilities = ResponsibilitiesRepository()

    organization = None
    job = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")
        job = jobs.create(
            organization["id"],
            f"test-job-{uuid4()}",
        )

        result = responsibilities.get_by_name(
            job["id"],
            f"unknown-responsibility-{uuid4()}",
        )

        assert result is None

    finally:
        if job is not None:
            jobs.delete_by_id(job["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_create_and_get_responsibility():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()
    responsibilities = ResponsibilitiesRepository()

    organization = None
    job = None
    responsibility = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        job = jobs.create(
            organization["id"],
            f"test-job-{uuid4()}",
        )

        name = f"test-responsibility-{uuid4()}"

        responsibility = responsibilities.create(
            job["id"],
            name,
            "Test responsibility description",
        )

        assert responsibility is not None
        assert responsibility["id"] is not None
        assert responsibility["job_id"] == job["id"]
        assert responsibility["name"] == name
        assert responsibility["description"] == "Test responsibility description"
        assert responsibility["status"] == "active"

        by_id = responsibilities.get_by_id(responsibility["id"])

        assert by_id is not None
        assert by_id["id"] == responsibility["id"]

        by_name = responsibilities.get_by_name(
            job["id"],
            name,
        )

        assert by_name is not None
        assert by_name["id"] == responsibility["id"]

    finally:
        if responsibility is not None:
            responsibilities.delete_by_id(responsibility["id"])

        if job is not None:
            jobs.delete_by_id(job["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_create_responsibility_with_custom_status():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()
    responsibilities = ResponsibilitiesRepository()

    organization = None
    job = None
    responsibility = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        job = jobs.create(
            organization["id"],
            f"test-job-{uuid4()}",
        )

        responsibility = responsibilities.create(
            job["id"],
            f"test-responsibility-{uuid4()}",
            status="inactive",
        )

        assert responsibility["status"] == "inactive"

    finally:
        if responsibility is not None:
            responsibilities.delete_by_id(responsibility["id"])

        if job is not None:
            jobs.delete_by_id(job["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_job_id_contains_created_responsibility():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()
    responsibilities = ResponsibilitiesRepository()

    organization = None
    job = None
    responsibility = None

    try:
        organization = organizations.create(f"test-org-{uuid4()}")

        job = jobs.create(
            organization["id"],
            f"test-job-{uuid4()}",
        )

        responsibility = responsibilities.create(
            job["id"],
            f"test-responsibility-{uuid4()}",
        )

        results = responsibilities.list_by_job_id(job["id"])

        assert any(
            item["id"] == responsibility["id"]
            for item in results
        )

    finally:
        if responsibility is not None:
            responsibilities.delete_by_id(responsibility["id"])

        if job is not None:
            jobs.delete_by_id(job["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_by_id_returns_false_for_unknown_responsibility():
    repository = ResponsibilitiesRepository()

    assert repository.delete_by_id(uuid4()) is False
