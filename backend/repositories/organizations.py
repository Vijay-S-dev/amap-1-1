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
                    SELECT id, name, status, organization_type, industry, location, contact_email, default_language, supported_languages, accessibility_defaults, created_at, updated_at
                    FROM organizations
                    WHERE id = %s
                    """,
                    (organization_id,),
                )
                return cursor.fetchone()

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        """Return an organization by its name, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, status, organization_type, industry, location, contact_email, default_language, supported_languages, accessibility_defaults, created_at, updated_at
                    FROM organizations
                    WHERE name = %s
                    """,
                    (name,),
                )
                return cursor.fetchone()

    def list_all(self) -> list[dict[str, Any]]:
        """Return all organizations ordered by name."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, status, organization_type, industry, location, contact_email, default_language, supported_languages, accessibility_defaults, created_at, updated_at
                    FROM organizations
                    ORDER BY name
                    """
                )
                return list(cursor.fetchall())

    def create(self, name: str) -> dict[str, Any]:
        """Create and return an organization."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO organizations (name)
                    VALUES (%s)
                    RETURNING id, name, status, organization_type, industry, location, contact_email, default_language, supported_languages, accessibility_defaults, created_at, updated_at
                    """,
                    (name,),
                )
                organization = cursor.fetchone()
                connection.commit()

                return organization

    def update_name(
        self,
        organization_id: UUID,
        name: str,
    ) -> dict[str, Any]:
        """Update the organization name and return the refreshed row."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE organizations
                    SET name = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id, name, status, organization_type, industry, location,
                              contact_email, default_language, supported_languages,
                              accessibility_defaults, created_at, updated_at
                    """,
                    (name, organization_id),
                )
                row = cursor.fetchone()
                connection.commit()
                return row

    def update(
        self,
        organization_id: UUID,
        name: str,
        status: str,
    ) -> dict[str, Any]:
        """Update organization name/status and return the refreshed row."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE organizations
                    SET name = %s, status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id, name, status, organization_type, industry, location,
                              contact_email, default_language, supported_languages,
                              accessibility_defaults, created_at, updated_at
                    """,
                    (name, status, organization_id),
                )
                row = cursor.fetchone()
                connection.commit()
                return row

    def update_profile(
        self,
        organization_id: UUID,
        name: str,
        organization_type: str,
        industry: str,
        location: str,
        contact_email: str | None,
        default_language: str,
        supported_languages: list[str],
        accessibility_defaults: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist every exposed profile/settings field and return the row."""
        import json

        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE organizations
                    SET name = %s,
                        organization_type = %s,
                        industry = %s,
                        location = %s,
                        contact_email = %s,
                        default_language = %s,
                        supported_languages = %s::jsonb,
                        accessibility_defaults = %s::jsonb,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id, name, status, organization_type, industry, location,
                              contact_email, default_language, supported_languages,
                              accessibility_defaults, created_at, updated_at
                    """,
                    (
                        name,
                        organization_type,
                        industry,
                        location,
                        contact_email,
                        default_language,
                        json.dumps(supported_languages),
                        json.dumps(accessibility_defaults),
                        organization_id,
                    ),
                )
                row = cursor.fetchone()
                connection.commit()
                return row

    def delete_by_id(self, organization_id: UUID) -> bool:
        """
        Delete an organization by ID.

        Returns True if an organization was deleted, otherwise False.
        """
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM organizations
                    WHERE id = %s
                    """,
                    (organization_id,),
                )
                deleted = cursor.rowcount == 1
                connection.commit()

                return deleted
