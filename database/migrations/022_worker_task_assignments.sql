-- AMAP Database Migration 022
-- Assign tasks to workers and track assignment lifecycle

CREATE TABLE worker_task_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    task_id UUID NOT NULL,
    worker_profile_id UUID NOT NULL,

    status TEXT NOT NULL DEFAULT 'assigned'
        CHECK (
            status IN (
                'assigned',
                'in_progress',
                'completed',
                'cancelled'
            )
        ),

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT worker_task_assignments_task_id_fkey
        FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE RESTRICT,

    CONSTRAINT worker_task_assignments_worker_profile_id_fkey
        FOREIGN KEY (worker_profile_id)
        REFERENCES worker_profiles(id)
        ON DELETE RESTRICT,

    CONSTRAINT worker_task_assignments_dates_check
        CHECK (
            (started_at IS NULL OR started_at >= assigned_at)
            AND
            (
                completed_at IS NULL
                OR started_at IS NULL
                OR completed_at >= started_at
            )
        )
);

CREATE INDEX idx_worker_task_assignments_task_id
    ON worker_task_assignments(task_id);

CREATE INDEX idx_worker_task_assignments_worker_profile_id
    ON worker_task_assignments(worker_profile_id);

CREATE INDEX idx_worker_task_assignments_status
    ON worker_task_assignments(status);