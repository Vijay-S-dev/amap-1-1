"""
User accessibility preferences repository.

Provides database access operations for the user_accessibility_preferences
table (per-user accessibility + onboarding state, PostgreSQL-authoritative).
Business logic does not belong in this module.
"""

import json
from typing import Any, Optional
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection


class UserAccessibilityPreferencesRepository:
    """Data access operations for per-user accessibility preferences."""

    def get(self, user_id: UUID) -> Optional[dict[str, Any]]:
        """Return the stored preference blob for a user, or None."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT user_id, preferences, updated_at
                    FROM user_accessibility_preferences
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                return cursor.fetchone()

    def upsert(self, user_id: UUID, preferences: dict[str, Any]) -> dict[str, Any]:
        """Insert or replace the preference blob for a user."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_accessibility_preferences (user_id, preferences)
                    VALUES (%s, %s::jsonb)
                    ON CONFLICT (user_id) DO UPDATE
                    SET preferences = EXCLUDED.preferences,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING user_id, preferences, updated_at
                    """,
                    (user_id, json.dumps(preferences)),
                )
                row = cursor.fetchone()
                connection.commit()
                return row
