-- AMAP Database Migration 012
-- Job responsibilities

CREATE TABLE responsibilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    job_id UUID NOT NULL,

    name TEXT NOT NULL,

    description TEXT,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'archived')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT responsibilities_job_id_fkey
        FOREIGN KEY (job_id)
        REFERENCES jobs(id)
        ON DELETE RESTRICT,

    CONSTRAINT responsibilities_job_name_key
        UNIQUE (job_id, name)
);

CREATE INDEX idx_responsibilities_job_id
    ON responsibilities(job_id);