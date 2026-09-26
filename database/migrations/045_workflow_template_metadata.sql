-- AMAP Database Migration 045
-- Phase 6: make workflow CRUD fully representable in PostgreSQL.
--
-- The API contract (WorkflowTemplate/WorkflowStepItem) carries
-- department/version/estimated-duration metadata and per-step safety
-- fields that had no storage, which is why list/create/update were
-- faked with hardcoded templates and audit-only writes. These columns
-- let the real repository persist every field the API exposes.
--
-- workflows: which department owns the template, its version (bumped
-- on each update) and the estimated duration.
-- workflow_steps: safety-critical flag, expected duration and the
-- required voice/multimodal intent for advancing the step.

ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS department_id UUID
        REFERENCES departments(id) ON DELETE SET NULL;

ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS estimated_duration_minutes DOUBLE PRECISION NOT NULL DEFAULT 15.0;

ALTER TABLE workflow_steps
    ADD COLUMN IF NOT EXISTS is_safety_critical BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE workflow_steps
    ADD COLUMN IF NOT EXISTS expected_duration_seconds INTEGER NOT NULL DEFAULT 120;

ALTER TABLE workflow_steps
    ADD CONSTRAINT workflow_steps_expected_duration_positive
        CHECK (expected_duration_seconds > 0);

ALTER TABLE workflow_steps
    ADD COLUMN IF NOT EXISTS required_intent TEXT;

CREATE INDEX IF NOT EXISTS idx_workflows_department_id
    ON workflows(department_id);
