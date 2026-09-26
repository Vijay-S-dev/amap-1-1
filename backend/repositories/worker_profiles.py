"""
Worker profile repository.

Provides database access operations for the worker_profiles table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class WorkerProfilesRepository:
    """Data access operations for worker profiles."""

    def get_by_id(
        self,
        worker_profile_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a worker profile by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, created_at, updated_at
                    FROM worker_profiles
                    WHERE id = %s
                    """,
                    (worker_profile_id,),
                )
                return cursor.fetchone()

    def get_by_user_id(
        self,
        user_id: UUID,
    ) -> dict[str, Any] | None:
        """Return a worker profile by user ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, created_at, updated_at
                    FROM worker_profiles
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                return cursor.fetchone()

    def create(
        self,
        user_id: UUID,
        badge_number: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """Create and return a worker profile (optionally with badge/lifecycle status)."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO worker_profiles (user_id, badge_number, status)
                    VALUES (%s, %s, %s)
                    RETURNING id, user_id, badge_number, status, created_at, updated_at
                    """,
                    (user_id, badge_number, status),
                )

                worker_profile = cursor.fetchone()
                connection.commit()

                return worker_profile

    def delete_by_id(
        self,
        worker_profile_id: UUID,
    ) -> bool:
        """Delete a worker profile and return whether it was deleted."""
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM worker_profiles
                    WHERE id = %s
                    """,
                    (worker_profile_id,),
                )

                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted


    def list_enterprise_directory(
        self,
        organization_id: UUID,
        limit: int = 25,
        offset: int = 0,
        status_filter: str | None = None,
        dept_filter: UUID | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Real worker directory for an organization.

        Joins worker_profiles + users + departments + worker_readiness and
        derives lifecycle status (INVITED/ONBOARDING/READY/WORKING/PAUSED/
        ASSISTANCE_REQUESTED/DEACTIVATED) from actual database state.
        Returns (page rows, total matching count).
        """
        base_cte = """
            WITH dir AS (
                SELECT
                    wp.id AS worker_profile_id,
                    u.id AS user_id,
                    u.organization_id,
                    u.full_name,
                    u.email,
                    u.status AS user_status,
                    wp.badge_number,
                    wp.status AS profile_status,
                    u.created_at,
                    d.id AS department_id,
                    COALESCE(d.name, 'Unassigned') AS department_name,
                    COALESCE(wr.interaction_mode, 'multimodal') AS interaction_mode,
                    COALESCE(wr.overall_ready, FALSE) AS overall_ready,
                    COALESCE(wr.completed_stages, '[]'::jsonb) AS completed_stages,
                    (wr.worker_profile_id IS NOT NULL) AS has_readiness,
                    EXISTS (
                        SELECT 1 FROM work_sessions ws
                        WHERE ws.worker_profile_id = wp.id AND ws.status = 'active'
                    ) AS has_active_session,
                    EXISTS (
                        SELECT 1 FROM work_sessions ws
                        WHERE ws.worker_profile_id = wp.id AND ws.status = 'paused'
                    ) AS has_paused_session,
                    EXISTS (
                        SELECT 1 FROM assistance_requests ar
                        WHERE ar.worker_profile_id = wp.id
                          AND ar.status IN ('open', 'acknowledged', 'in_progress')
                    ) AS has_open_assistance,
                    EXISTS (
                        SELECT 1 FROM worker_task_assignments wta
                        WHERE wta.worker_profile_id = wp.id
                          AND wta.status IN ('assigned', 'in_progress')
                    ) AS has_active_assignment,
                    (
                        SELECT t.name
                        FROM worker_task_assignments wta
                        JOIN tasks t ON t.id = wta.task_id
                        WHERE wta.worker_profile_id = wp.id
                          AND wta.status IN ('assigned', 'in_progress')
                        ORDER BY wta.assigned_at DESC
                        LIMIT 1
                    ) AS current_task_name
                FROM worker_profiles wp
                JOIN users u ON u.id = wp.user_id
                LEFT JOIN LATERAL (
                    SELECT ud.department_id
                    FROM user_departments ud
                    WHERE ud.user_id = u.id
                    ORDER BY ud.created_at
                    LIMIT 1
                ) udl ON TRUE
                LEFT JOIN departments d ON d.id = udl.department_id
                LEFT JOIN worker_readiness wr ON wr.worker_profile_id = wp.id
                WHERE u.organization_id = %s
            ),
            computed AS (
                SELECT
                    dir.*,
                    CASE
                        WHEN user_status IN ('archived', 'suspended', 'inactive')
                             OR profile_status = 'inactive'
                            THEN 'DEACTIVATED'
                        WHEN has_open_assistance
                            THEN 'ASSISTANCE_REQUESTED'
                        WHEN has_active_session
                            THEN 'WORKING'
                        WHEN has_paused_session
                            THEN 'PAUSED'
                        WHEN overall_ready
                            THEN 'READY'
                        WHEN has_active_assignment
                            THEN 'WORKING'
                        WHEN has_readiness
                             AND jsonb_array_length(completed_stages) = 0
                             AND NOT has_active_session
                             AND NOT has_active_assignment
                            THEN 'INVITED'
                        WHEN has_readiness
                            THEN 'ONBOARDING'
                        ELSE 'INVITED'
                    END AS lifecycle_status
                FROM dir
            )
        """
        filters = ["TRUE"]
        params: list[Any] = [organization_id]
        if status_filter:
            filters.append("UPPER(lifecycle_status) = UPPER(%s)")
            params.append(status_filter)
        if dept_filter:
            filters.append("department_id = %s")
            params.append(dept_filter)
        where_sql = " AND ".join(filters)

        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    base_cte
                    + f"""
                    SELECT COUNT(*) AS total
                    FROM computed
                    WHERE {where_sql}
                    """,
                    tuple(params),
                )
                total = int(cursor.fetchone()["total"])

                cursor.execute(
                    base_cte
                    + f"""
                    SELECT *
                    FROM computed
                    WHERE {where_sql}
                    ORDER BY created_at DESC, full_name
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params) + (limit, offset),
                )
                rows = cursor.fetchall()
                return rows, total
