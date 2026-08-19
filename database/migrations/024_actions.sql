-- AMAP Database Migration 024
-- Controlled actions recognized and executed by the system

CREATE TABLE actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name TEXT NOT NULL,

    display_name TEXT NOT NULL,

    description TEXT,

    category TEXT NOT NULL DEFAULT 'general'
        CHECK (
            category IN (
                'general',
                'navigation',
                'workflow',
                'task',
                'assistance',
                'system'
            )
        ),

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'archived')),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT actions_name_key
        UNIQUE (name)
);

CREATE INDEX idx_actions_category
    ON actions(category);

CREATE INDEX idx_actions_status
    ON actions(status);