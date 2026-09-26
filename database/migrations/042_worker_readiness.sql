-- AMAP Database Migration 042
-- Worker readiness / onboarding lifecycle persistence
--
-- Replaces the in-memory _WORKER_READINESS_STORE in backend/routes/readiness.py.
-- One readiness record per worker profile; must survive backend restarts.

CREATE TABLE worker_readiness (
    worker_profile_id UUID PRIMARY KEY
        REFERENCES worker_profiles(id)
        ON DELETE CASCADE,

    is_fresher BOOLEAN NOT NULL DEFAULT TRUE,
    onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,

    readiness_status TEXT NOT NULL DEFAULT 'incomplete'
        CHECK (readiness_status IN ('ready', 'incomplete')),

    interaction_mode TEXT NOT NULL DEFAULT 'multimodal',

    gesture_ready BOOLEAN NOT NULL DEFAULT FALSE,
    voice_ready BOOLEAN NOT NULL DEFAULT FALSE,
    multimodal_ready BOOLEAN NOT NULL DEFAULT FALSE,
    task_training_complete BOOLEAN NOT NULL DEFAULT FALSE,
    overall_ready BOOLEAN NOT NULL DEFAULT FALSE,

    completed_stages JSONB NOT NULL DEFAULT '[]'::jsonb,
    active_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_worker_readiness_status
    ON worker_readiness(readiness_status);
