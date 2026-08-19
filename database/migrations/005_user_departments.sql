-- AMAP Database Migration 005
-- User-to-department assignments

CREATE TABLE user_departments (
    user_id UUID NOT NULL,
    department_id UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT user_departments_pkey
        PRIMARY KEY (user_id, department_id),

    CONSTRAINT user_departments_user_id_fkey
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE RESTRICT,

    CONSTRAINT user_departments_department_id_fkey
        FOREIGN KEY (department_id)
        REFERENCES departments(id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_user_departments_department_id
    ON user_departments(department_id);