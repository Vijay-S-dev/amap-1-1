-- AMAP Database Migration 035
-- Worker work-session tracking
--
-- organization_id is REQUIRED: the RLS policy in migration 040 isolates
-- work_sessions by organization_id, and schema.sql (compose/Supabase path)
-- has always defined this column. Migration 035 originally omitted it,
-- which made migration 040 fail on fresh databases.

CREATE TABLE work_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    worker_profile_id UUID NOT NULL,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (
            status IN (
                'active', 'paused', 'completed', 'cancelled'
            )
        ),

    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT work_sessions_organization_id_fkey
        FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    CONSTRAINT work_sessions_worker_profile_id_fkey
        FOREIGN KEY (worker_profile_id)
        REFERENCES worker_profiles(id)
        ON DELETE RESTRICT,

    CONSTRAINT work_sessions_dates_check
        CHECK (
            ended_at IS NULL
            OR ended_at >= started_at
        )
);

CREATE INDEX idx_work_sessions_organization_id
    ON work_sessions(organization_id);

CREATE INDEX idx_work_sessions_worker_profile_id
    ON work_sessions(worker_profile_id);

CREATE INDEX idx_work_sessions_status
    ON work_sessions(status);

CREATE INDEX idx_work_sessions_started_at
    ON work_sessions(started_at);
