-- AMAP Database Migration 018
-- Execution tracking for individual workflow steps

CREATE TABLE workflow_step_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workflow_assignment_id UUID NOT NULL,
    workflow_step_id UUID NOT NULL,

    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'skipped', 'failed')),

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT workflow_step_executions_assignment_id_fkey
        FOREIGN KEY (workflow_assignment_id)
        REFERENCES workflow_assignments(id)
        ON DELETE RESTRICT,

    CONSTRAINT workflow_step_executions_step_id_fkey
        FOREIGN KEY (workflow_step_id)
        REFERENCES workflow_steps(id)
        ON DELETE RESTRICT,

    CONSTRAINT workflow_step_executions_assignment_step_key
        UNIQUE (workflow_assignment_id, workflow_step_id),

    CONSTRAINT workflow_step_executions_dates_check
        CHECK (
            completed_at IS NULL
            OR started_at IS NULL
            OR completed_at >= started_at
        )
);

CREATE INDEX idx_workflow_step_executions_assignment_id
    ON workflow_step_executions(workflow_assignment_id);

CREATE INDEX idx_workflow_step_executions_workflow_step_id
    ON workflow_step_executions(workflow_step_id);

CREATE INDEX idx_workflow_step_executions_status
    ON workflow_step_executions(status);