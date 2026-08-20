-- AMAP Database Migration 038
-- User notification tracking

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    recipient_user_id UUID NOT NULL,

    notification_type TEXT NOT NULL,

    title TEXT NOT NULL,

    message TEXT NOT NULL,

    notification_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    status TEXT NOT NULL DEFAULT 'unread'
        CHECK (
            status IN (
                'unread',
                'read',
                'archived'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    read_at TIMESTAMPTZ,

    CONSTRAINT notifications_organization_id_fkey
        FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    CONSTRAINT notifications_recipient_user_id_fkey
        FOREIGN KEY (recipient_user_id)
        REFERENCES users(id)
        ON DELETE RESTRICT,

    CONSTRAINT notifications_read_at_check
        CHECK (
            read_at IS NULL
            OR read_at >= created_at
        )
);

CREATE INDEX idx_notifications_organization_id
    ON notifications(organization_id);

CREATE INDEX idx_notifications_recipient_user_id
    ON notifications(recipient_user_id);

CREATE INDEX idx_notifications_status
    ON notifications(status);

CREATE INDEX idx_notifications_created_at
    ON notifications(created_at);