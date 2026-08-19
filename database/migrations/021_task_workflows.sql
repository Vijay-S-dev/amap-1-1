-- AMAP Database Migration 021
-- Link tasks to workflows

CREATE TABLE task_workflows (
    task_id UUID NOT NULL,
    workflow_id UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT task_workflows_pkey
        PRIMARY KEY (task_id, workflow_id),

    CONSTRAINT task_workflows_task_id_fkey
        FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE RESTRICT,

    CONSTRAINT task_workflows_workflow_id_fkey
        FOREIGN KEY (workflow_id)
        REFERENCES workflows(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_task_workflows_workflow_id
    ON task_workflows(workflow_id);