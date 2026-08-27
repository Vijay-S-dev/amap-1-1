"""
Custom Gestures Repository for AMAP (§ 24, § 25, § 26, § 27).

Provides parameterized SQL database operations for persisting and loading
worker-specific custom gesture profiles into the database with full transactional commits.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.database import get_db_connection

# Persistent local SQLite fallback database path
DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_DB_PATH = DB_DIR / "amap_persisted.db"


def _init_sqlite_tables():
    """Ensure custom_gestures table exists in local database."""
    with sqlite3.connect(str(SQLITE_DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_gestures (
                id TEXT PRIMARY KEY,
                worker_id TEXT NOT NULL,
                organization_id TEXT NOT NULL,
                gesture_name TEXT NOT NULL,
                intent TEXT NOT NULL,
                action_mapping TEXT NOT NULL,
                handedness TEXT NOT NULL,
                sample_count INTEGER NOT NULL,
                stability_score REAL NOT NULL,
                feature_template TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


_init_sqlite_tables()


class CustomGesturesRepository:
    """Data access operations for worker custom gestures."""

    def __init__(self) -> None:
        _init_sqlite_tables()

    def get_by_id(self, gesture_id: UUID) -> Optional[Dict[str, Any]]:
        """Return a custom gesture by its ID."""
        # Try PostgreSQL first if available
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, worker_id, organization_id, gesture_name, intent,
                               action_mapping, handedness, sample_count, stability_score,
                               feature_template, version, status, created_at, updated_at
                        FROM custom_gestures
                        WHERE id = %s
                        """,
                        (str(gesture_id),),
                    )
                    row = cur.fetchone()
                    if row:
                        return self._format_row(row)
        except Exception:
            pass

        # Local SQLite database
        with sqlite3.connect(str(SQLITE_DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, worker_id, organization_id, gesture_name, intent,
                       action_mapping, handedness, sample_count, stability_score,
                       feature_template, version, status, created_at, updated_at
                FROM custom_gestures
                WHERE id = ? AND status = 'active'
                """,
                (str(gesture_id),),
            )
            row = cursor.fetchone()
            if row:
                return self._format_sqlite_row(row)
        return None

    def list_by_worker_id(self, worker_id: UUID) -> List[Dict[str, Any]]:
        """Return all active custom gestures for a specific worker profile."""
        results: List[Dict[str, Any]] = []

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, worker_id, organization_id, gesture_name, intent,
                               action_mapping, handedness, sample_count, stability_score,
                               feature_template, version, status, created_at, updated_at
                        FROM custom_gestures
                        WHERE worker_id = %s AND status = 'active'
                        ORDER BY created_at DESC
                        """,
                        (str(worker_id),),
                    )
                    rows = cur.fetchall()
                    for r in rows:
                        results.append(self._format_row(r))
                    return results
        except Exception:
            pass

        # Local SQLite database
        with sqlite3.connect(str(SQLITE_DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, worker_id, organization_id, gesture_name, intent,
                       action_mapping, handedness, sample_count, stability_score,
                       feature_template, version, status, created_at, updated_at
                FROM custom_gestures
                WHERE worker_id = ? AND status = 'active'
                ORDER BY created_at DESC
                """,
                (str(worker_id),),
            )
            rows = cursor.fetchall()
            for r in rows:
                results.append(self._format_sqlite_row(r))
        return results

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
        Insert or update a worker custom gesture profile in the database with commit.
        """
        now = datetime.now(timezone.utc).isoformat()
        template_json = json.dumps(feature_template)
        gesture_id = str(uuid4())

        # 1. Try PostgreSQL
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Deactivate existing same intent for worker
                    cur.execute(
                        """
                        UPDATE custom_gestures
                        SET status = 'replaced', updated_at = %s
                        WHERE worker_id = %s AND intent = %s AND status = 'active'
                        """,
                        (now, str(worker_id), intent.upper()),
                    )
                    cur.execute(
                        """
                        INSERT INTO custom_gestures (
                            id, worker_id, organization_id, gesture_name, intent,
                            action_mapping, handedness, sample_count, stability_score,
                            feature_template, version, status, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, worker_id, organization_id, gesture_name, intent,
                                  action_mapping, handedness, sample_count, stability_score,
                                  feature_template, version, status, created_at, updated_at
                        """,
                        (
                            gesture_id, str(worker_id), str(organization_id),
                            gesture_name, intent.upper(), action_mapping,
                            handedness, sample_count, stability_score,
                            template_json, version, status, now, now,
                        ),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    if row:
                        return self._format_row(row)
        except Exception:
            pass

        # 2. SQLite local database persistence
        with sqlite3.connect(str(SQLITE_DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Deactivate previous active gesture for same intent
            cursor.execute(
                """
                UPDATE custom_gestures
                SET status = 'replaced', updated_at = ?
                WHERE worker_id = ? AND intent = ? AND status = 'active'
                """,
                (now, str(worker_id), intent.upper()),
            )

            cursor.execute(
                """
                INSERT INTO custom_gestures (
                    id, worker_id, organization_id, gesture_name, intent,
                    action_mapping, handedness, sample_count, stability_score,
                    feature_template, version, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gesture_id, str(worker_id), str(organization_id),
                    gesture_name, intent.upper(), action_mapping,
                    handedness, sample_count, stability_score,
                    template_json, version, status, now, now,
                ),
            )
            conn.commit()

            cursor.execute("SELECT * FROM custom_gestures WHERE id = ?", (gesture_id,))
            saved_row = cursor.fetchone()
            return self._format_sqlite_row(saved_row)

    def delete_by_id(self, gesture_id: UUID, worker_id: UUID) -> bool:
        """Deactivate a custom gesture profile for a worker."""
        now = datetime.now(timezone.utc).isoformat()
        deleted = False

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE custom_gestures
                        SET status = 'deleted', updated_at = %s
                        WHERE id = %s AND worker_id = %s
                        """,
                        (now, str(gesture_id), str(worker_id)),
                    )
                    deleted = cur.rowcount > 0
                    conn.commit()
                    if deleted:
                        return True
        except Exception:
            pass

        with sqlite3.connect(str(SQLITE_DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE custom_gestures
                SET status = 'deleted', updated_at = ?
                WHERE id = ? AND worker_id = ?
                """,
                (now, str(gesture_id), str(worker_id)),
            )
            deleted = cursor.rowcount > 0
            conn.commit()
        return deleted

    def _format_row(self, r: Any) -> Dict[str, Any]:
        template_raw = r[9] if isinstance(r, (list, tuple)) else r.get("feature_template")
        template = json.loads(template_raw) if isinstance(template_raw, str) else template_raw

        created_val = r[12] if isinstance(r, (list, tuple)) else r.get("created_at")
        updated_val = r[13] if isinstance(r, (list, tuple)) else r.get("updated_at")

        return {
            "id": UUID(str(r[0] if isinstance(r, (list, tuple)) else r.get("id"))),
            "worker_id": UUID(str(r[1] if isinstance(r, (list, tuple)) else r.get("worker_id"))),
            "organization_id": UUID(str(r[2] if isinstance(r, (list, tuple)) else r.get("organization_id"))),
            "gesture_name": r[3] if isinstance(r, (list, tuple)) else r.get("gesture_name"),
            "intent": r[4] if isinstance(r, (list, tuple)) else r.get("intent"),
            "action_mapping": r[5] if isinstance(r, (list, tuple)) else r.get("action_mapping"),
            "handedness": r[6] if isinstance(r, (list, tuple)) else r.get("handedness"),
            "sample_count": int(r[7] if isinstance(r, (list, tuple)) else r.get("sample_count")),
            "stability_score": float(r[8] if isinstance(r, (list, tuple)) else r.get("stability_score")),
            "feature_template": template,
            "version": int(r[10] if isinstance(r, (list, tuple)) else r.get("version", 1)),
            "status": r[11] if isinstance(r, (list, tuple)) else r.get("status", "active"),
            "created_at": created_val if isinstance(created_val, datetime) else datetime.fromisoformat(str(created_val)),
            "updated_at": updated_val if isinstance(updated_val, datetime) else datetime.fromisoformat(str(updated_val)),
        }

    def _format_sqlite_row(self, r: sqlite3.Row) -> Dict[str, Any]:
        template_raw = r["feature_template"]
        template = json.loads(template_raw) if isinstance(template_raw, str) else template_raw
        return {
            "id": UUID(r["id"]),
            "worker_id": UUID(r["worker_id"]),
            "organization_id": UUID(r["organization_id"]),
            "gesture_name": r["gesture_name"],
            "intent": r["intent"],
            "action_mapping": r["action_mapping"],
            "handedness": r["handedness"],
            "sample_count": int(r["sample_count"]),
            "stability_score": float(r["stability_score"]),
            "feature_template": template,
            "version": int(r["version"]),
            "status": r["status"],
            "created_at": datetime.fromisoformat(r["created_at"]),
            "updated_at": datetime.fromisoformat(r["updated_at"]),
        }
