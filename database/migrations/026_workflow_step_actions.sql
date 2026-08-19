-- AMAP Database Migration 026
-- Link workflow steps to actions available during that step

CREATE TABLE workflow_step_actions (
    workflow_step_id UUID NOT NULL,
    action_id UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT workflow_step_actions_pkey
        PRIMARY KEY (workflow_step_id, action_id),

    CONSTRAINT workflow_step_actions_workflow_step_id_fkey
        FOREIGN KEY (workflow_step_id)
        REFERENCES workflow_steps(id)
        ON DELETE RESTRICT,

    CONSTRAINT workflow_step_actions_action_id_fkey
        FOREIGN KEY (action_id)
        REFERENCES actions(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_workflow_step_actions_action_id
    ON workflow_step_actions(action_id);