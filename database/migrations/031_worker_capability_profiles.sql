-- AMAP Database Migration 031
-- Worker capability profile for personalization and adaptation

CREATE TABLE worker_capability_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    worker_profile_id UUID NOT NULL,

    capability_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'archived')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT worker_capability_profiles_worker_profile_id_fkey
        FOREIGN KEY (worker_profile_id)
        REFERENCES worker_profiles(id)
        ON DELETE RESTRICT,

    CONSTRAINT worker_capability_profiles_worker_profile_key
        UNIQUE (worker_profile_id)
);

CREATE INDEX idx_worker_capability_profiles_status
    ON worker_capability_profiles(status);