-- AMAP Database Migration 020
-- Link tasks to job responsibilities

CREATE TABLE task_responsibilities (
    task_id UUID NOT NULL,
    responsibility_id UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT task_responsibilities_pkey
        PRIMARY KEY (task_id, responsibility_id),

    CONSTRAINT task_responsibilities_task_id_fkey
        FOREIGN KEY (task_id)
        REFERENCES tasks(id)
        ON DELETE RESTRICT,

    CONSTRAINT task_responsibilities_responsibility_id_fkey
        FOREIGN KEY (responsibility_id)
        REFERENCES responsibilities(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_task_responsibilities_responsibility_id
    ON task_responsibilities(responsibility_id);