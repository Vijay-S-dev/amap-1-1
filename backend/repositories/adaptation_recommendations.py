"""
Adaptation recommendations repository.

Provides database access operations for the adaptation_recommendations table
(pending/approved/dismissed evidence-based worker adaptation suggestions).
Business logic does not belong in this module.
"""

import json
from typing import Any, Optional
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection

_COLUMNS = """
    id,
    organization_id,
    worker_profile_id,
    recommendation_type,
    current_value,
    suggested_value,
    confidence,
    reason,
    auto_applicable,
    evidence_count,
    status,
    reviewed_by,
    reviewed_at,
    created_at,
    updated_at
"""


class AdaptationRecommendationsRepository:
    """Data access operations for adaptation recommendations."""

    def create(
        self,
        organization_id: UUID,
        worker_profile_id: UUID,
        recommendation_type: str,
        current_value: Any,
        suggested_value: Any,
        confidence: float,
        reason: str,
        auto_applicable: bool,
        evidence_count: int,
    ) -> dict[str, Any]:
        """Create and return a pending adaptation recommendation."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO adaptation_recommendations (
                        organization_id,
                        worker_profile_id,
                        recommendation_type,
                        current_value,
                        suggested_value,
                        confidence,
                        reason,
                        auto_applicable,
                        evidence_count
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s)
                    RETURNING {_COLUMNS}
                    """,
                    (
                        organization_id,
                        worker_profile_id,
                        recommendation_type,
                        json.dumps(current_value),
                        json.dumps(suggested_value),
                        confidence,
                        reason,
                        auto_applicable,
                        evidence_count,
                    ),
                )
                row = cursor.fetchone()
                connection.commit()
                return row

    def get_by_id(self, recommendation_id: UUID) -> dict[str, Any] | None:
        """Return one recommendation by ID."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"SELECT {_COLUMNS} FROM adaptation_recommendations WHERE id = %s",
                    (recommendation_id,),
                )
                return cursor.fetchone()

    def find_pending(
        self,
        organization_id: UUID,
        worker_profile_id: UUID,
        recommendation_type: str,
    ) -> dict[str, Any] | None:
        """Return an existing pending recommendation of this type for a worker."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {_COLUMNS}
                    FROM adaptation_recommendations
                    WHERE organization_id = %s
                      AND worker_profile_id = %s
                      AND recommendation_type = %s
                      AND status = 'pending'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (organization_id, worker_profile_id, recommendation_type),
                )
                return cursor.fetchone()

    def list_by_organization(
        self,
        organization_id: UUID,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List recommendations for an organization with worker-name enrichment."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        ar.id,
                        ar.organization_id,
                        ar.worker_profile_id,
                        ar.recommendation_type,
                        ar.current_value,
                        ar.suggested_value,
                        ar.confidence,
                        ar.reason,
                        ar.auto_applicable,
                        ar.evidence_count,
                        ar.status,
                        ar.reviewed_by,
                        ar.reviewed_at,
                        ar.created_at,
                        ar.updated_at,
                        u.full_name AS worker_name,
                        wp.id AS worker_profile_join_id
                    FROM adaptation_recommendations ar
                    JOIN worker_profiles wp ON wp.id = ar.worker_profile_id
                    JOIN users u ON u.id = wp.user_id
                    WHERE ar.organization_id = %s
                      AND (%s::text IS NULL OR ar.status = %s)
                    ORDER BY ar.created_at DESC
                    LIMIT %s
                    """,
                    (organization_id, status, status, limit),
                )
                return cursor.fetchall()

    def update_status(
        self,
        recommendation_id: UUID,
        status: str,
        reviewed_by: UUID,
    ) -> dict[str, Any] | None:
        """Mark a recommendation approved/dismissed with reviewer attribution."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    UPDATE adaptation_recommendations
                    SET status = %s,
                        reviewed_by = %s,
                        reviewed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING {_COLUMNS}
                    """,
                    (status, reviewed_by, recommendation_id),
                )
                row = cursor.fetchone()
                connection.commit()
                return row
