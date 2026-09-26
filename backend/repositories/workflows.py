"""
Workflow repository.

Provides database access operations for the workflows table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class WorkflowsRepository:
    """Data access operations for workflows."""

    def get_by_id(
        self,
        workflow_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a workflow by ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        name,
                        description,
                        department_id,
                        version,
                        estimated_duration_minutes,
                        status,
                        created_at,
                        updated_at
                    FROM workflows
                    WHERE id = %s
                    """,
                    (workflow_id,),
                )
                return cursor.fetchone()

    def get_by_organization_and_name(
        self,
        organization_id: UUID,
        name: str,
    ) -> dict[str, Any] | None:
        """Return a workflow by organization and name."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        name,
                        description,
                        department_id,
                        version,
                        estimated_duration_minutes,
                        status,
                        created_at,
                        updated_at
                    FROM workflows
                    WHERE organization_id = %s
                      AND name = %s
                    """,
                    (organization_id, name),
                )
                return cursor.fetchone()

    def list_by_organization_id(
        self,
        organization_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all workflows for an organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        name,
                        description,
                        department_id,
                        version,
                        estimated_duration_minutes,
                        status,
                        created_at,
                        updated_at
                    FROM workflows
                    WHERE organization_id = %s
                    ORDER BY created_at
                    """,
                    (organization_id,),
                )
                return cursor.fetchall()

    def list_all(self) -> list[dict[str, Any]]:
        """Return all workflows."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        organization_id,
                        name,
                        description,
                        department_id,
                        version,
                        estimated_duration_minutes,
                        status,
                        created_at,
                        updated_at
                    FROM workflows
                    ORDER BY created_at
                    """
                )
                return cursor.fetchall()

    def create(
        self,
        organization_id: UUID,
        name: str,
        description: str | None = None,
        status: str = "active",
        department_id: UUID | None = None,
        version: int = 1,
        estimated_duration_minutes: float = 15.0,
    ) -> dict[str, Any]:
        """Create and return a workflow."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO workflows (
                        organization_id,
                        name,
                        description,
                        department_id,
                        version,
                        estimated_duration_minutes,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        organization_id,
                        name,
                        description,
                        department_id,
                        version,
                        estimated_duration_minutes,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        organization_id,
                        name,
                        description,
                        department_id,
                        version,
                        estimated_duration_minutes,
                        status,
                    ),
                )

                workflow = cursor.fetchone()
                connection.commit()

                return workflow

    def update(
        self,
        workflow_id: UUID,
        name: str,
        description: str | None,
        status: str,
        department_id: UUID | None = None,
        version: int | None = None,
        estimated_duration_minutes: float | None = None,
    ) -> dict[str, Any] | None:
        """Update and return a workflow, or None if it does not exist.

        ``department_id`` is written as passed (``None`` clears ownership).
        ``version``/``estimated_duration_minutes`` keep their current value
        when ``None`` is passed.
        """
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE workflows
                    SET
                        name = %s,
                        description = %s,
                        department_id = %s,
                        version = COALESCE(%s, version),
                        estimated_duration_minutes = COALESCE(%s, estimated_duration_minutes),
                        status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING
                        id,
                        organization_id,
                        name,
                        description,
                        department_id,
                        version,
                        estimated_duration_minutes,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        name,
                        description,
                        department_id,
                        version,
                        estimated_duration_minutes,
                        status,
                        workflow_id,
                    ),
                )

                workflow = cursor.fetchone()
                connection.commit()

                return workflow

    def delete_by_id(
        self,
        workflow_id: UUID,
    ) -> bool:
        """Delete a workflow and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM workflows
                    WHERE id = %s
                    """,
                    (workflow_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
