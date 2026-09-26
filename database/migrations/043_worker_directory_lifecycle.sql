-- AMAP Database Migration 043
-- Worker directory lifecycle columns (Phase 3: real worker CRUD)
--
-- 1. users.status: the API contract (UserStatusUpdatePayload) and admin UI
--    allow 'suspended'; migration 004 only permitted active/inactive/archived,
--    so every suspension attempt raised a CHECK violation -> HTTP 500.
-- 2. worker_profiles.badge_number: schema.sql (compose path) has defined it
--    since the beginning; the migration path lacked it, so real worker
--    invitations could not persist badge numbers.
-- 3. worker_profiles.status: lifecycle state used to deactivate a worker's
--    profile ('active' | 'inactive' | 'on_leave'), aligned with schema.sql.
--
-- NOTE (documented drift): schema.sql also defines worker_profiles.organization_id.
-- The migration path derives organization through users.organization_id instead;
-- no migration reads worker_profiles.organization_id, so the column is not
-- added here. Reconciling that denormalization is tracked with schema drift.

-- 1. Allow 'suspended' in users.status
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_status_check;
ALTER TABLE users
    ADD CONSTRAINT users_status_check
    CHECK (status IN ('active', 'inactive', 'archived', 'suspended'));

-- 2. Badge number for worker directory
ALTER TABLE worker_profiles ADD COLUMN badge_number TEXT;

-- 3. Worker profile lifecycle status
ALTER TABLE worker_profiles
    ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'inactive', 'on_leave'));

CREATE INDEX IF NOT EXISTS idx_worker_profiles_status
    ON worker_profiles(status);
