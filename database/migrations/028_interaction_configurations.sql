-- AMAP Database Migration 028
-- General interaction configuration settings

CREATE TABLE interaction_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL,

    name TEXT NOT NULL,

    description TEXT,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'archived')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT interaction_configurations_organization_id_fkey
        FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    CONSTRAINT interaction_configurations_organization_name_key
        UNIQUE (organization_id, name)
);

CREATE INDEX idx_interaction_configurations_organization_id
    ON interaction_configurations(organization_id);

CREATE INDEX idx_interaction_configurations_status
    ON interaction_configurations(status);