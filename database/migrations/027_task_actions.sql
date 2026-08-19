-- AMAP Database Migration 027
-- Link tasks to actions allowed at the task level

CREATE TABLE task_actions (
    task_id UUID NOT NULL,
    action_id UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT task_actions_pkey
        PRIMARY KEY (task_id, action_id),

    CONSTRAINT task_actions_task_id_fkey
        FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE RESTRICT,

    CONSTRAINT task_actions_action_id_fkey
        FOREIGN KEY (action_id)
        REFERENCES actions(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_task_actions_action_id
    ON task_actions(action_id);