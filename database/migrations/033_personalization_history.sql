-- AMAP Database Migration 033
-- Historical record of worker personalization changes

CREATE TABLE personalization_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    worker_personalization_id UUID NOT NULL,

    personalization_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    change_reason TEXT,

    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT personalization_history_worker_personalization_id_fkey
        FOREIGN KEY (worker_personalization_id)
        REFERENCES worker_personalizations(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_personalization_history_worker_personalization_id
    ON personalization_history(worker_personalization_id);

CREATE INDEX idx_personalization_history_changed_at
    ON personalization_history(changed_at);