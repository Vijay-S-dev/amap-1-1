-- AMAP Database Migration 034
-- Execution and runtime event tracking

CREATE TABLE execution_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    worker_profile_id UUID,

    workflow_assignment_id UUID,

    worker_task_assignment_id UUID,

    event_type TEXT NOT NULL,

    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT execution_events_organization_id_fkey
        FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    CONSTRAINT execution_events_worker_profile_id_fkey
        FOREIGN KEY (worker_profile_id)
        REFERENCES worker_profiles(id)
        ON DELETE RESTRICT,

    CONSTRAINT execution_events_workflow_assignment_id_fkey
        FOREIGN KEY (workflow_assignment_id)
        REFERENCES workflow_assignments(id)
        ON DELETE RESTRICT,

    CONSTRAINT execution_events_worker_task_assignment_id_fkey
        FOREIGN KEY (worker_task_assignment_id)
        REFERENCES worker_task_assignments(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_execution_events_organization_id
    ON execution_events(organization_id);

CREATE INDEX idx_execution_events_worker_profile_id
    ON execution_events(worker_profile_id);

CREATE INDEX idx_execution_events_workflow_assignment_id
    ON execution_events(workflow_assignment_id);

CREATE INDEX idx_execution_events_worker_task_assignment_id
    ON execution_events(worker_task_assignment_id);

CREATE INDEX idx_execution_events_event_type
    ON execution_events(event_type);

CREATE INDEX idx_execution_events_occurred_at
    ON execution_events(occurred_at);