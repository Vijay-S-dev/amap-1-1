-- AMAP Database Migration 004
-- Core organization user identities

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    email TEXT NOT NULL,

    full_name TEXT NOT NULL,

    password_hash TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'archived')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT users_organization_id_fkey
        FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    CONSTRAINT users_organization_email_key
        UNIQUE (organization_id, email)
);

CREATE INDEX idx_users_organization_id
    ON users(organization_id);