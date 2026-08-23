from datetime import timedelta
from uuid import uuid4

from repositories.jobs import JobsRepository
from repositories.organizations import OrganizationsRepository
from repositories.users import UsersRepository
from repositories.worker_job_assignments import WorkerJobAssignmentsRepository
from repositories.worker_profiles import WorkerProfilesRepository


def create_worker_job_assignment_dependencies():
    organizations = OrganizationsRepository()
    users = UsersRepository()
    worker_profiles = WorkerProfilesRepository()
    jobs = JobsRepository()

    organization = organizations.create(
        f"test-org-{uuid4()}"
    )

    user = users.create(
        organization["id"],
        f"test-user-{uuid4()}@example.com",
        f"Test User {uuid4()}",
        "test-password-hash",
    )

    worker_profile = worker_profiles.create(
        user["id"],
    )

    job = jobs.create(
        organization["id"],
        f"test-job-{uuid4()}",
    )

    return (
        organizations,
        users,
        worker_profiles,
        jobs,
        organization,
        user,
        worker_profile,
        job,
    )


def cleanup_worker_job_assignment_dependencies(
    organizations,
    users,
    worker_profiles,
    jobs,
    organization,
    user,
    worker_profile,
    job,
):
    if job is not None:
        jobs.delete_by_id(job["id"])

    if worker_profile is not None:
        worker_profiles.delete_by_id(worker_profile["id"])

    if user is not None:
        users.delete_by_id(user["id"])

    if organization is not None:
        organizations.delete_by_id(organization["id"])


def test_get_by_id_returns_none_for_unknown_assignment():
    repository = WorkerJobAssignmentsRepository()

    assert repository.get_by_id(uuid4()) is None


def test_create_and_get_worker_job_assignment():
    assignments = WorkerJobAssignmentsRepository()
    assignment = None

    dependencies = (
        create_worker_job_assignment_dependencies()
    )

    (
        organizations,
        users,
        worker_profiles,
        jobs,
        organization,
        user,
        worker_profile,
        job,
    ) = dependencies

    try:
        assignment = assignments.create(
            worker_profile["id"],
            job["id"],
        )

        assert assignment is not None
        assert assignment["worker_profile_id"] == worker_profile["id"]
        assert assignment["job_id"] == job["id"]
        assert assignment["status"] == "active"

        result = assignments.get_by_id(
            assignment["id"]
        )

        assert result is not None
        assert result["id"] == assignment["id"]
        assert result["worker_profile_id"] == worker_profile["id"]
        assert result["job_id"] == job["id"]

    finally:
        if assignment is not None:
            assignments.delete_by_id(assignment["id"])

        cleanup_worker_job_assignment_dependencies(
            organizations,
            users,
            worker_profiles,
            jobs,
            organization,
            user,
            worker_profile,
            job,
        )


def test_list_by_worker_profile_id_contains_created_assignment():
    assignments = WorkerJobAssignmentsRepository()
    assignment = None

    dependencies = (
        create_worker_job_assignment_dependencies()
    )

    (
        organizations,
        users,
        worker_profiles,
        jobs,
        organization,
        user,
        worker_profile,
        job,
    ) = dependencies

    try:
        assignment = assignments.create(
            worker_profile["id"],
            job["id"],
        )

        results = assignments.list_by_worker_profile_id(
            worker_profile["id"]
        )

        assert any(
            item["id"] == assignment["id"]
            for item in results
        )

    finally:
        if assignment is not None:
            assignments.delete_by_id(assignment["id"])

        cleanup_worker_job_assignment_dependencies(
            organizations,
            users,
            worker_profiles,
            jobs,
            organization,
            user,
            worker_profile,
            job,
        )


def test_list_by_job_id_contains_created_assignment():
    assignments = WorkerJobAssignmentsRepository()
    assignment = None

    dependencies = (
        create_worker_job_assignment_dependencies()
    )

    (
        organizations,
        users,
        worker_profiles,
        jobs,
        organization,
        user,
        worker_profile,
        job,
    ) = dependencies

    try:
        assignment = assignments.create(
            worker_profile["id"],
            job["id"],
        )

        results = assignments.list_by_job_id(
            job["id"]
        )

        assert any(
            item["id"] == assignment["id"]
            for item in results
        )

    finally:
        if assignment is not None:
            assignments.delete_by_id(assignment["id"])

        cleanup_worker_job_assignment_dependencies(
            organizations,
            users,
            worker_profiles,
            jobs,
            organization,
            user,
            worker_profile,
            job,
        )


def test_update_status():
    assignments = WorkerJobAssignmentsRepository()
    assignment = None

    dependencies = (
        create_worker_job_assignment_dependencies()
    )

    (
        organizations,
        users,
        worker_profiles,
        jobs,
        organization,
        user,
        worker_profile,
        job,
    ) = dependencies

    try:
        assignment = assignments.create(
            worker_profile["id"],
            job["id"],
        )

        ended_at = (
            assignment["assigned_at"] + timedelta(minutes=1)
        )

        updated = assignments.update_status(
            assignment["id"],
            "completed",
            ended_at,
        )

        assert updated is not None
        assert updated["id"] == assignment["id"]
        assert updated["status"] == "completed"
        assert updated["ended_at"] == ended_at

    finally:
        if assignment is not None:
            assignments.delete_by_id(assignment["id"])

        cleanup_worker_job_assignment_dependencies(
            organizations,
            users,
            worker_profiles,
            jobs,
            organization,
            user,
            worker_profile,
            job,
        )


def test_delete_by_id_returns_false_for_unknown_assignment():
    repository = WorkerJobAssignmentsRepository()

    assert repository.delete_by_id(uuid4()) is False
