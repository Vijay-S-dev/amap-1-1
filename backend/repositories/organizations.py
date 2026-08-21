"""
Organization repository.

Provides database access operations for the organizations table.
Business logic does not belong in this module.
"""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class OrganizationsRepository:
    """Data access operations for organizations."""

    def get_by_id(self, organization_id: UUID) -> dict[str, Any] | None:
        """Return an organization by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, status, created_at, updated_at
                    FROM organizations
                    WHERE id = %s
                    """,
                    (organization_id,),
                )
                return cursor.fetchone()
