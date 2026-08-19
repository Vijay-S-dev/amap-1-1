-- AMAP Database Migration 010
-- Worker-specific user profiles

CREATE TABLE worker_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL UNIQUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT worker_profiles_user_id_fkey
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE RESTRICT
);