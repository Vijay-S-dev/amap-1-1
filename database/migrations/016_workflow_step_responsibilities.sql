-- AMAP Database Migration 016
-- Link workflow steps to job responsibilities

CREATE TABLE workflow_step_responsibilities (
    workflow_step_id UUID NOT NULL,
    responsibility_id UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT workflow_step_responsibilities_pkey
        PRIMARY KEY (workflow_step_id, responsibility_id),

    CONSTRAINT workflow_step_responsibilities_workflow_step_id_fkey
        FOREIGN KEY (workflow_step_id)
        REFERENCES workflow_steps(id)
        ON DELETE RESTRICT,

    CONSTRAINT workflow_step_responsibilities_responsibility_id_fkey
        FOREIGN KEY (responsibility_id)
        REFERENCES responsibilities(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_workflow_step_responsibilities_responsibility_id
    ON workflow_step_responsibilities(responsibility_id);