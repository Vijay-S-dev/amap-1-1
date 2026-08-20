-- AMAP Database Migration 036
-- Worker interaction event tracking

CREATE TABLE interaction_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    worker_profile_id UUID NOT NULL,

    work_session_id UUID,

    action_id UUID,

    interaction_mode TEXT NOT NULL
        CHECK (
            interaction_mode IN (
                'gesture',
                'voice',
                'ui',
                'other'
            )
        ),

    event_type TEXT NOT NULL,

    confidence NUMERIC(5,4)
        CHECK (
            confidence IS NULL
            OR (
                confidence >= 0
                AND confidence <= 1
            )
        ),

    interaction_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT interaction_events_organization_id_fkey
        FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    CONSTRAINT interaction_events_worker_profile_id_fkey
        FOREIGN KEY (worker_profile_id)
        REFERENCES worker_profiles(id)
        ON DELETE RESTRICT,

    CONSTRAINT interaction_events_work_session_id_fkey
        FOREIGN KEY (work_session_id)
        REFERENCES work_sessions(id)
        ON DELETE RESTRICT,

    CONSTRAINT interaction_events_action_id_fkey
        FOREIGN KEY (action_id)
        REFERENCES actions(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_interaction_events_organization_id
    ON interaction_events(organization_id);

CREATE INDEX idx_interaction_events_worker_profile_id
    ON interaction_events(worker_profile_id);

CREATE INDEX idx_interaction_events_work_session_id
    ON interaction_events(work_session_id);

CREATE INDEX idx_interaction_events_action_id
    ON interaction_events(action_id);

CREATE INDEX idx_interaction_events_interaction_mode
    ON interaction_events(interaction_mode);

CREATE INDEX idx_interaction_events_event_type
    ON interaction_events(event_type);

CREATE INDEX idx_interaction_events_occurred_at
    ON interaction_events(occurred_at);