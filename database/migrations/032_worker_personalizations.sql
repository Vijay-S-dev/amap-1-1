-- AMAP Database Migration 032
-- Worker-specific personalization settings

CREATE TABLE worker_personalizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    worker_profile_id UUID NOT NULL,

    interaction_configuration_id UUID,

    personalization_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'archived')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT worker_personalizations_worker_profile_id_fkey
        FOREIGN KEY (worker_profile_id)
        REFERENCES worker_profiles(id)
        ON DELETE RESTRICT,

    CONSTRAINT worker_personalizations_interaction_configuration_id_fkey
        FOREIGN KEY (interaction_configuration_id)
        REFERENCES interaction_configurations(id)
        ON DELETE RESTRICT,

    CONSTRAINT worker_personalizations_worker_profile_key
        UNIQUE (worker_profile_id)
);

CREATE INDEX idx_worker_personalizations_interaction_configuration_id
    ON worker_personalizations(interaction_configuration_id);

CREATE INDEX idx_worker_personalizations_status
    ON worker_personalizations(status);