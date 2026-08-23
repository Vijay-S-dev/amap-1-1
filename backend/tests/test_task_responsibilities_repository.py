from uuid import uuid4

from repositories.jobs import JobsRepository
from repositories.organizations import OrganizationsRepository
from repositories.responsibilities import ResponsibilitiesRepository
from repositories.task_responsibilities import TaskResponsibilitiesRepository
from repositories.tasks import TasksRepository


def test_get_by_ids_returns_none_for_unknown_link():
    repository = TaskResponsibilitiesRepository()

    assert repository.get_by_ids(uuid4(), uuid4()) is None


def test_create_and_get_task_responsibility():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()
    responsibilities = ResponsibilitiesRepository()
    tasks = TasksRepository()
    task_responsibilities = TaskResponsibilitiesRepository()

    organization = None
    job = None
    responsibility = None
    task = None
    link = None

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

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        link = task_responsibilities.create(
            task["id"],
            responsibility["id"],
        )

        assert link is not None
        assert link["task_id"] == task["id"]
        assert link["responsibility_id"] == responsibility["id"]

        result = task_responsibilities.get_by_ids(
            task["id"],
            responsibility["id"],
        )

        assert result is not None
        assert result["task_id"] == task["id"]
        assert result["responsibility_id"] == responsibility["id"]

    finally:
        if link is not None:
            task_responsibilities.delete(
                task["id"],
                responsibility["id"],
            )

        if task is not None:
            tasks.delete_by_id(task["id"])

        if responsibility is not None:
            responsibilities.delete_by_id(responsibility["id"])

        if job is not None:
            jobs.delete_by_id(job["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_task_id_contains_created_link():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()
    responsibilities = ResponsibilitiesRepository()
    tasks = TasksRepository()
    task_responsibilities = TaskResponsibilitiesRepository()

    organization = None
    job = None
    responsibility = None
    task = None
    link = None

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

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        link = task_responsibilities.create(
            task["id"],
            responsibility["id"],
        )

        results = task_responsibilities.list_by_task_id(task["id"])

        assert any(
            item["responsibility_id"] == responsibility["id"]
            for item in results
        )

    finally:
        if link is not None:
            task_responsibilities.delete(
                task["id"],
                responsibility["id"],
            )

        if task is not None:
            tasks.delete_by_id(task["id"])

        if responsibility is not None:
            responsibilities.delete_by_id(responsibility["id"])

        if job is not None:
            jobs.delete_by_id(job["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_list_by_responsibility_id_contains_created_link():
    organizations = OrganizationsRepository()
    jobs = JobsRepository()
    responsibilities = ResponsibilitiesRepository()
    tasks = TasksRepository()
    task_responsibilities = TaskResponsibilitiesRepository()

    organization = None
    job = None
    responsibility = None
    task = None
    link = None

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

        task = tasks.create(
            organization["id"],
            f"test-task-{uuid4()}",
        )

        link = task_responsibilities.create(
            task["id"],
            responsibility["id"],
        )

        results = task_responsibilities.list_by_responsibility_id(
            responsibility["id"],
        )

        assert any(
            item["task_id"] == task["id"]
            for item in results
        )

    finally:
        if link is not None:
            task_responsibilities.delete(
                task["id"],
                responsibility["id"],
            )

        if task is not None:
            tasks.delete_by_id(task["id"])

        if responsibility is not None:
            responsibilities.delete_by_id(responsibility["id"])

        if job is not None:
            jobs.delete_by_id(job["id"])

        if organization is not None:
            organizations.delete_by_id(organization["id"])


def test_delete_returns_false_for_unknown_link():
    repository = TaskResponsibilitiesRepository()

    assert repository.delete(uuid4(), uuid4()) is False
