-- AMAP Database Migration 009
-- Role-to-permission assignments

CREATE TABLE role_permissions (
    role_id UUID NOT NULL,
    permission_id UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT role_permissions_pkey
        PRIMARY KEY (role_id, permission_id),

    CONSTRAINT role_permissions_role_id_fkey
        FOREIGN KEY (role_id)
        REFERENCES roles(id)
        ON DELETE RESTRICT,

    CONSTRAINT role_permissions_permission_id_fkey
        FOREIGN KEY (permission_id)
        REFERENCES permissions(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_role_permissions_permission_id
    ON role_permissions(permission_id);