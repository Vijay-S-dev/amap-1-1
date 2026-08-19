-- AMAP Database Migration 008
-- User-to-role assignments

CREATE TABLE user_roles (
    user_id UUID NOT NULL,
    role_id UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT user_roles_pkey
        PRIMARY KEY (user_id, role_id),

    CONSTRAINT user_roles_user_id_fkey
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE RESTRICT,

    CONSTRAINT user_roles_role_id_fkey
        FOREIGN KEY (role_id)
        REFERENCES roles(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_user_roles_role_id
    ON user_roles(role_id);