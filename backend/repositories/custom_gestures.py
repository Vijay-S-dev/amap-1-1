"""
Custom Gestures Repository for AMAP (§ 24, § 25, § 26, § 27).

PostgreSQL-authoritative persistence for worker-specific custom gesture profiles.

Design notes:
- All CRUD runs against PostgreSQL (table created in migration 041).
- There is NO SQLite fallback and NO silent exception swallowing: database
  errors propagate to the caller/API error handler instead of being masked.
- Retraining replaces the previously active row for the same (worker, intent).
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from psycopg import errors
from psycopg.rows import dict_row

from app.database import get_db_connection

_SELECT_COLUMNS = """
    id, worker_id, organization_id, gesture_name, intent,
    action_mapping, handedness, sample_count, stability_score,
    feature_template, version, status, created_at, updated_at
"""


class CustomGesturesRepository:
    """PostgreSQL data access for worker custom gestures."""

    def get_by_id(self, gesture_id: UUID) -> Optional[Dict[str, Any]]:
        """Return a custom gesture by its ID, or None if it does not exist."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {_SELECT_COLUMNS}
                    FROM custom_gestures
                    WHERE id = %s
                    """,
                    (str(gesture_id),),
                )
                row = cursor.fetchone()
                return self._format_row(row) if row else None

    def list_by_worker_id(self, worker_id: UUID) -> List[Dict[str, Any]]:
        """Return all active custom gestures for a specific worker profile."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {_SELECT_COLUMNS}
                    FROM custom_gestures
                    WHERE worker_id = %s AND status = 'active'
                    ORDER BY created_at DESC
                    """,
                    (str(worker_id),),
                )
                return [self._format_row(row) for row in cursor.fetchall()]

    def save(
        self,
        worker_id: UUID,
        organization_id: UUID,
        gesture_name: str,
        intent: str,
        action_mapping: str,
        handedness: str,
        sample_count: int,
        stability_score: float,
        feature_template: List[float],
        version: int = 1,
        status: str = "active",
    ) -> Dict[str, Any]:
        """
        Insert a worker custom gesture profile in PostgreSQL.

        Any previously active gesture for the same (worker, intent) is marked
        'replaced' in the same transaction so at most one active row exists
        per (worker, intent).
        """
        now = datetime.now(timezone.utc).isoformat()
        template_json = json.dumps(feature_template)
        gesture_id = str(uuid4())

        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                try:
                    cursor.execute(
                        """
                        UPDATE custom_gestures
                        SET status = 'replaced', updated_at = %s
                        WHERE worker_id = %s AND intent = %s AND status = 'active'
                        """,
                        (now, str(worker_id), intent.upper()),
                    )
                    cursor.execute(
                        f"""
                        INSERT INTO custom_gestures (
                            id, worker_id, organization_id, gesture_name, intent,
                            action_mapping, handedness, sample_count, stability_score,
                            feature_template, version, status, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING {_SELECT_COLUMNS}
                        """,
                        (
                            gesture_id,
                            str(worker_id),
                            str(organization_id),
                            gesture_name,
                            intent.upper(),
                            action_mapping,
                            handedness,
                            sample_count,
                            stability_score,
                            template_json,
                            version,
                            status,
                            now,
                            now,
                        ),
                    )
                    row = cursor.fetchone()
                    connection.commit()
                except errors.ForeignKeyViolation as exc:
                    connection.rollback()
                    raise ValueError(
                        "Unknown worker profile or organization: custom gesture "
                        "could not be persisted."
                    ) from exc
                except Exception:
                    connection.rollback()
                    raise

                return self._format_row(row)

    def delete_by_id(self, gesture_id: UUID, worker_id: UUID) -> bool:
        """Mark a custom gesture profile as deleted (soft delete). Returns True if a row changed."""
        now = datetime.now(timezone.utc).isoformat()

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE custom_gestures
                    SET status = 'deleted', updated_at = %s
                    WHERE id = %s AND worker_id = %s AND status <> 'deleted'
                    """,
                    (now, str(gesture_id), str(worker_id)),
                )
                deleted = cursor.rowcount > 0
                connection.commit()
                return deleted

    @staticmethod
    def _format_row(row: Any) -> Dict[str, Any]:
        template_raw = row["feature_template"] if isinstance(row, dict) else row[9]
        template = json.loads(template_raw) if isinstance(template_raw, str) else template_raw

        created_val = row["created_at"] if isinstance(row, dict) else row[12]
        updated_val = row["updated_at"] if isinstance(row, dict) else row[13]

        return {
            "id": UUID(str(row["id"] if isinstance(row, dict) else row[0])),
            "worker_id": UUID(str(row["worker_id"] if isinstance(row, dict) else row[1])),
            "organization_id": UUID(str(row["organization_id"] if isinstance(row, dict) else row[2])),
            "gesture_name": row["gesture_name"] if isinstance(row, dict) else row[3],
            "intent": row["intent"] if isinstance(row, dict) else row[4],
            "action_mapping": row["action_mapping"] if isinstance(row, dict) else row[5],
            "handedness": row["handedness"] if isinstance(row, dict) else row[6],
            "sample_count": int(row["sample_count"] if isinstance(row, dict) else row[7]),
            "stability_score": float(row["stability_score"] if isinstance(row, dict) else row[8]),
            "feature_template": template,
            "version": int(row["version"] if isinstance(row, dict) else row[10]),
            "status": row["status"] if isinstance(row, dict) else row[11],
            "created_at": created_val
            if isinstance(created_val, datetime)
            else datetime.fromisoformat(str(created_val)),
            "updated_at": updated_val
            if isinstance(updated_val, datetime)
            else datetime.fromisoformat(str(updated_val)),
        }
