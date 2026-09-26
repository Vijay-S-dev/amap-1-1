-- AMAP Database Migration 041
-- Worker custom gesture profiles (PostgreSQL-authoritative storage)
--
-- Replaces the dangerous SQLite fallback in backend/repositories/custom_gestures.py.
-- One row per (worker, intent) may be 'active' at any time; retraining marks
-- the previous row 'replaced' and inserts a new active row.

CREATE TABLE custom_gestures (
    id UUID PRIMARY KEY,

    worker_id UUID NOT NULL
        REFERENCES worker_profiles(id)
        ON DELETE CASCADE,

    organization_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    gesture_name TEXT NOT NULL,
    intent TEXT NOT NULL,
    action_mapping TEXT NOT NULL,
    handedness TEXT NOT NULL,

    sample_count INTEGER NOT NULL
        CHECK (sample_count >= 1),

    stability_score DOUBLE PRECISION NOT NULL,
    feature_template TEXT NOT NULL,

    version INTEGER NOT NULL DEFAULT 1,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'replaced', 'deleted')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_custom_gestures_worker_id
    ON custom_gestures(worker_id);

CREATE INDEX idx_custom_gestures_organization_id
    ON custom_gestures(organization_id);

-- At most one ACTIVE custom gesture per (worker, intent).
CREATE UNIQUE INDEX uq_custom_gestures_active_worker_intent
    ON custom_gestures(worker_id, intent)
    WHERE status = 'active';
