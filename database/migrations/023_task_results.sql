-- AMAP Database Migration 023
-- Store outcomes for worker task assignments

CREATE TABLE task_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    worker_task_assignment_id UUID NOT NULL,

    outcome TEXT NOT NULL
        CHECK (outcome IN ('completed', 'failed', 'partial', 'cancelled')),

    result_data JSONB,

    notes TEXT,

    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT task_results_worker_task_assignment_id_fkey
        FOREIGN KEY (worker_task_assignment_id)
        REFERENCES worker_task_assignments(id)
        ON DELETE RESTRICT,

    CONSTRAINT task_results_assignment_key
        UNIQUE (worker_task_assignment_id)
);

CREATE INDEX idx_task_results_outcome
    ON task_results(outcome);