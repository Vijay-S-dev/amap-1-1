-- AMAP Database Migration 025
-- Requirements and validation rules associated with actions

CREATE TABLE action_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    action_id UUID NOT NULL,

    name TEXT NOT NULL,

    description TEXT,

    requirement_type TEXT NOT NULL DEFAULT 'validation'
        CHECK (
            requirement_type IN (
                'validation',
                'permission',
                'state',
                'context',
                'confirmation'
            )
        ),

    requirement_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'archived')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT action_requirements_action_id_fkey
        FOREIGN KEY (action_id)
        REFERENCES actions(id)
        ON DELETE RESTRICT,

    CONSTRAINT action_requirements_action_name_key
        UNIQUE (action_id, name)
);

CREATE INDEX idx_action_requirements_action_id
    ON action_requirements(action_id);

CREATE INDEX idx_action_requirements_requirement_type
    ON action_requirements(requirement_type);

CREATE INDEX idx_action_requirements_status
    ON action_requirements(status);