-- AMAP Database Migration 015
-- Ordered steps within organization workflows

CREATE TABLE workflow_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    workflow_id UUID NOT NULL,

    step_order INTEGER NOT NULL
        CHECK (step_order > 0),

    name TEXT NOT NULL,

    description TEXT,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'archived')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT workflow_steps_workflow_id_fkey
        FOREIGN KEY (workflow_id)
        REFERENCES workflows(id)
        ON DELETE RESTRICT,

    CONSTRAINT workflow_steps_workflow_step_order_key
        UNIQUE (workflow_id, step_order)
);

CREATE INDEX idx_workflow_steps_workflow_id
    ON workflow_steps(workflow_id);