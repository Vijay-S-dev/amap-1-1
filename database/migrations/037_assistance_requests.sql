-- AMAP Database Migration 037
-- Worker assistance request tracking

CREATE TABLE assistance_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    worker_profile_id UUID NOT NULL,

    work_session_id UUID,

    workflow_assignment_id UUID,

    worker_task_assignment_id UUID,

    status TEXT NOT NULL DEFAULT 'open'
        CHECK (
            status IN (
                'open',
                'acknowledged',
                'in_progress',
                'resolved',
                'cancelled'
            )
        ),

    priority TEXT NOT NULL DEFAULT 'normal'
        CHECK (
            priority IN (
                'low',
                'normal',
                'high',
                'urgent'
            )
        ),

    reason TEXT,

    request_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    acknowledged_at TIMESTAMPTZ,

    resolved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT assistance_requests_organization_id_fkey
        FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    CONSTRAINT assistance_requests_worker_profile_id_fkey
        FOREIGN KEY (worker_profile_id)
        REFERENCES worker_profiles(id)
        ON DELETE RESTRICT,

    CONSTRAINT assistance_requests_work_session_id_fkey
        FOREIGN KEY (work_session_id)
        REFERENCES work_sessions(id)
        ON DELETE RESTRICT,

    CONSTRAINT assistance_requests_workflow_assignment_id_fkey
        FOREIGN KEY (workflow_assignment_id)
        REFERENCES workflow_assignments(id)
        ON DELETE RESTRICT,

    CONSTRAINT assistance_requests_worker_task_assignment_id_fkey
        FOREIGN KEY (worker_task_assignment_id)
        REFERENCES worker_task_assignments(id)
        ON DELETE RESTRICT,

    CONSTRAINT assistance_requests_dates_check
        CHECK (
            (acknowledged_at IS NULL OR acknowledged_at >= requested_at)
            AND
            (resolved_at IS NULL OR resolved_at >= requested_at)
        )
);

CREATE INDEX idx_assistance_requests_organization_id
    ON assistance_requests(organization_id);

CREATE INDEX idx_assistance_requests_worker_profile_id
    ON assistance_requests(worker_profile_id);

CREATE INDEX idx_assistance_requests_work_session_id
    ON assistance_requests(work_session_id);

CREATE INDEX idx_assistance_requests_workflow_assignment_id
    ON assistance_requests(workflow_assignment_id);

CREATE INDEX idx_assistance_requests_worker_task_assignment_id
    ON assistance_requests(worker_task_assignment_id);

CREATE INDEX idx_assistance_requests_status
    ON assistance_requests(status);

CREATE INDEX idx_assistance_requests_priority
    ON assistance_requests(priority);

CREATE INDEX idx_assistance_requests_requested_at
    ON assistance_requests(requested_at);