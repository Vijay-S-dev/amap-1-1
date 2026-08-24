"""
Work session service for AMAP.

Orchestrates worker session lifecycle (start, pause, resume, end)
and enforces single-active-session constraints per worker profile.
"""

from typing import Optional
from uuid import UUID

from models.session import WorkSessionRead
from repositories.work_sessions import WorkSessionsRepository
from services.base import ConflictError, NotFoundError, UnauthorizedError, ValidationError


class WorkSessionService:
    """Business logic for worker work sessions."""

    def __init__(self, repo: Optional[WorkSessionsRepository] = None) -> None:
        self.repo = repo or WorkSessionsRepository()

    def get_active_session(self, worker_profile_id: UUID) -> Optional[WorkSessionRead]:
        """Return the current active or paused session for a worker, or None."""
        sessions = self.repo.list_by_worker_profile_id(worker_profile_id)
        for s in sessions:
            if s.get("status") in ("active", "paused"):
                return WorkSessionRead.model_validate(s)
        return None

    def start_session(self, worker_profile_id: UUID) -> WorkSessionRead:
        """
        Start a new work session for a worker.
        Rejects if the worker already has an active or paused session.
        """
        active = self.get_active_session(worker_profile_id)
        if active:
            raise ConflictError(
                f"Worker profile {worker_profile_id} already has an ongoing session ({active.id})."
            )

        session_data = self.repo.create(
            worker_profile_id=worker_profile_id,
            status="active",
        )
        return WorkSessionRead.model_validate(session_data)

    def pause_session(self, work_session_id: UUID, worker_profile_id: UUID) -> WorkSessionRead:
        """Pause an active work session."""
        session = self.repo.get_by_id(work_session_id)
        if not session:
            raise NotFoundError(f"Work session {work_session_id} not found.")

        if session["worker_profile_id"] != worker_profile_id:
            raise UnauthorizedError("Work session does not belong to this worker.")

        if session["status"] != "active":
            raise ValidationError(f"Cannot pause a session with status '{session['status']}'.")

        updated = self.repo.update_status(work_session_id, status="paused")
        return WorkSessionRead.model_validate(updated)

    def resume_session(self, work_session_id: UUID, worker_profile_id: UUID) -> WorkSessionRead:
        """Resume a paused work session."""
        session = self.repo.get_by_id(work_session_id)
        if not session:
            raise NotFoundError(f"Work session {work_session_id} not found.")

        if session["worker_profile_id"] != worker_profile_id:
            raise UnauthorizedError("Work session does not belong to this worker.")

        if session["status"] != "paused":
            raise ValidationError(f"Cannot resume a session with status '{session['status']}'.")

        updated = self.repo.update_status(work_session_id, status="active")
        return WorkSessionRead.model_validate(updated)

    def end_session(
        self,
        work_session_id: UUID,
        worker_profile_id: UUID,
        status: str = "completed",
    ) -> WorkSessionRead:
        """End a work session."""
        if status not in ("completed", "cancelled"):
            raise ValidationError(f"Invalid end status '{status}'. Must be 'completed' or 'cancelled'.")

        session = self.repo.get_by_id(work_session_id)
        if not session:
            raise NotFoundError(f"Work session {work_session_id} not found.")

        if session["worker_profile_id"] != worker_profile_id:
            raise UnauthorizedError("Work session does not belong to this worker.")

        if session["status"] in ("completed", "cancelled"):
            raise ConflictError(f"Session {work_session_id} is already ended with status '{session['status']}'.")

        ended = self.repo.end(work_session_id, status=status)
        return WorkSessionRead.model_validate(ended)
