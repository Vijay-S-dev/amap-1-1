"""
Worker Readiness Repository for AMAP (§ 4, § 13, § 18).

PostgreSQL persistence for the worker onboarding/readiness lifecycle.
Replaces the former in-memory _WORKER_READINESS_STORE so readiness state
survives backend restarts (table created in migration 042).
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional
from uuid import UUID

from psycopg.rows import dict_row

from app.database import get_db_connection

_COLUMNS = """
    worker_profile_id, is_fresher, onboarding_completed, readiness_status,
    interaction_mode, gesture_ready, voice_ready, multimodal_ready,
    task_training_complete, overall_ready, completed_stages, active_preferences,
    created_at, updated_at
"""


class WorkerReadinessRepository:
    """Data access for worker readiness records."""

    def get(self, worker_profile_id: UUID) -> Optional[Dict[str, Any]]:
        """Return the readiness record for a worker profile, or None."""
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {_COLUMNS}
                    FROM worker_readiness
                    WHERE worker_profile_id = %s
                    """,
                    (str(worker_profile_id),),
                )
                return cursor.fetchone()

    def create_default(self, worker_profile_id: UUID) -> Dict[str, Any]:
        """
        Create the default 'fresher / incomplete' readiness record for a worker.

        Idempotent: if the record already exists, the existing row is returned.
        """
        now = datetime.now(timezone.utc).isoformat()
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO worker_readiness (
                        worker_profile_id, is_fresher, onboarding_completed,
                        readiness_status, interaction_mode, gesture_ready,
                        voice_ready, multimodal_ready, task_training_complete,
                        overall_ready, completed_stages, active_preferences,
                        created_at, updated_at
                    ) VALUES (%s, TRUE, FALSE, 'incomplete', 'multimodal',
                              FALSE, FALSE, FALSE, FALSE, FALSE,
                              '[]'::jsonb, %s::jsonb, %s, %s)
                    ON CONFLICT (worker_profile_id) DO NOTHING
                    RETURNING {_COLUMNS}
                    """,
                    (
                        str(worker_profile_id),
                        '{"language": "en", "modality": "multimodal", "dwell_time_ms": 500, "high_contrast": false, "text_scale": 1.0}',
                        now,
                        now,
                    ),
                )
                row = cursor.fetchone()
                connection.commit()
                if row:
                    return row
                # Conflict: record already exists — read it back.
                cursor.execute(
                    f"""
                    SELECT {_COLUMNS}
                    FROM worker_readiness
                    WHERE worker_profile_id = %s
                    """,
                    (str(worker_profile_id),),
                )
                return cursor.fetchone()

    def upsert(self, worker_profile_id: UUID, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert or replace the readiness record for a worker profile.

        `state` must contain: is_fresher, onboarding_completed,
        readiness_status, interaction_mode, gesture_ready, voice_ready,
        multimodal_ready, task_training_complete, overall_ready,
        completed_stages (list), active_preferences (dict).
        """
        now = datetime.now(timezone.utc).isoformat()
        with get_db_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO worker_readiness (
                        worker_profile_id, is_fresher, onboarding_completed,
                        readiness_status, interaction_mode, gesture_ready,
                        voice_ready, multimodal_ready, task_training_complete,
                        overall_ready, completed_stages, active_preferences,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                              %s::jsonb, %s::jsonb, %s, %s)
                    ON CONFLICT (worker_profile_id) DO UPDATE SET
                        is_fresher = EXCLUDED.is_fresher,
                        onboarding_completed = EXCLUDED.onboarding_completed,
                        readiness_status = EXCLUDED.readiness_status,
                        interaction_mode = EXCLUDED.interaction_mode,
                        gesture_ready = EXCLUDED.gesture_ready,
                        voice_ready = EXCLUDED.voice_ready,
                        multimodal_ready = EXCLUDED.multimodal_ready,
                        task_training_complete = EXCLUDED.task_training_complete,
                        overall_ready = EXCLUDED.overall_ready,
                        completed_stages = EXCLUDED.completed_stages,
                        active_preferences = EXCLUDED.active_preferences,
                        updated_at = EXCLUDED.updated_at
                    RETURNING {_COLUMNS}
                    """,
                    (
                        str(worker_profile_id),
                        bool(state["is_fresher"]),
                        bool(state["onboarding_completed"]),
                        str(state["readiness_status"]),
                        str(state["interaction_mode"]),
                        bool(state["gesture_ready"]),
                        bool(state["voice_ready"]),
                        bool(state["multimodal_ready"]),
                        bool(state["task_training_complete"]),
                        bool(state["overall_ready"]),
                        json.dumps(state["completed_stages"]),
                        json.dumps(state["active_preferences"]),
                        now,
                        now,
                    ),
                )
                row = cursor.fetchone()
                connection.commit()
                return row
