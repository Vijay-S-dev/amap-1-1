-- AMAP Database Migration 039
-- Audit trail for important system and user actions

CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    actor_user_id UUID,

    event_type TEXT NOT NULL,

    resource_type TEXT,

    resource_id UUID,

    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT audit_events_organization_id_fkey
        FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    CONSTRAINT audit_events_actor_user_id_fkey
        FOREIGN KEY (actor_user_id)
        REFERENCES users(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_audit_events_organization_id
    ON audit_events(organization_id);

CREATE INDEX idx_audit_events_actor_user_id
    ON audit_events(actor_user_id);

CREATE INDEX idx_audit_events_event_type
    ON audit_events(event_type);

CREATE INDEX idx_audit_events_resource
    ON audit_events(resource_type, resource_id);

CREATE INDEX idx_audit_events_occurred_at
    ON audit_events(occurred_at);