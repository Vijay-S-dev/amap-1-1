-- AMAP Database Migration 013
-- Worker-to-job assignments with assignment history

CREATE TABLE worker_job_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    worker_profile_id UUID NOT NULL,
    job_id UUID NOT NULL,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'completed')),

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT worker_job_assignments_worker_profile_id_fkey
        FOREIGN KEY (worker_profile_id)
        REFERENCES worker_profiles(id)
        ON DELETE RESTRICT,

    CONSTRAINT worker_job_assignments_job_id_fkey
        FOREIGN KEY (job_id)
        REFERENCES jobs(id)
        ON DELETE RESTRICT,

    CONSTRAINT worker_job_assignments_dates_check
        CHECK (ended_at IS NULL OR ended_at >= assigned_at)
);

CREATE INDEX idx_worker_job_assignments_worker_profile_id
    ON worker_job_assignments(worker_profile_id);

CREATE INDEX idx_worker_job_assignments_job_id
    ON worker_job_assignments(job_id);

CREATE INDEX idx_worker_job_assignments_status
    ON worker_job_assignments(status);