-- AMAP Database Migration 035
-- Worker work-session tracking

CREATE TABLE work_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    worker_profile_id UUID NOT NULL,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (
            status IN (
                'active',
                'paused',
                'completed',
                'cancelled'
            )
        ),

    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

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

CREATE INDEX idx_work_sessions_worker_profile_id
    ON work_sessions(worker_profile_id);

CREATE INDEX idx_work_sessions_status
    ON work_sessions(status);

CREATE INDEX idx_work_sessions_started_at
    ON work_sessions(started_at);