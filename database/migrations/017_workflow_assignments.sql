-- AMAP Database Migration 017
-- Workflow assignments to workers

CREATE TABLE workflow_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workflow_id UUID NOT NULL,
    worker_profile_id UUID NOT NULL,

    status TEXT NOT NULL DEFAULT 'assigned'
        CHECK (status IN ('assigned', 'in_progress', 'completed', 'cancelled')),

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT workflow_assignments_workflow_id_fkey
        FOREIGN KEY (workflow_id)
        REFERENCES workflows(id)
        ON DELETE RESTRICT,

    CONSTRAINT workflow_assignments_worker_profile_id_fkey
        FOREIGN KEY (worker_profile_id)
        REFERENCES worker_profiles(id)
        ON DELETE RESTRICT,

    CONSTRAINT workflow_assignments_dates_check
        CHECK (
            (started_at IS NULL OR started_at >= assigned_at)
            AND
            (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)
        )
);

CREATE INDEX idx_workflow_assignments_workflow_id
    ON workflow_assignments(workflow_id);

CREATE INDEX idx_workflow_assignments_worker_profile_id
    ON workflow_assignments(worker_profile_id);

CREATE INDEX idx_workflow_assignments_status
    ON workflow_assignments(status);