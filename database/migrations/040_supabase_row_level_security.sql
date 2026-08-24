-- ====================================================================
-- AMAP Database Migration: 040_supabase_row_level_security.sql
-- Description: Multi-Tenant Row-Level Security (RLS) Policies for Supabase / PostgreSQL
-- ====================================================================

-- 1. Helper Functions to Resolve Current Request Context
CREATE OR REPLACE FUNCTION current_app_org_id()
RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(
        COALESCE(
            current_setting('app.current_organization_id', true),
            (NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'organization_id')
        ),
        ''
    )::UUID;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

CREATE OR REPLACE FUNCTION current_app_user_id()
RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(
        COALESCE(
            current_setting('app.current_user_id', true),
            (NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
        ),
        ''
    )::UUID;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

CREATE OR REPLACE FUNCTION is_app_super_admin()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN COALESCE(
        current_setting('app.is_super_admin', true) = 'true',
        (NULLIF(current_setting('request.jwt.claims', true), '')::jsonb -> 'roles') ? 'super_admin',
        false
    );
EXCEPTION WHEN OTHERS THEN
    RETURN false;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ====================================================================
-- 2. Enable Row-Level Security (RLS) on Multi-Tenant Tables
-- ====================================================================

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE responsibilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_job_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflows ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_step_responsibilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_step_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_responsibilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_workflows ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_task_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE action_requirements ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_step_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE interaction_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE gesture_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_capability_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE worker_personalizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE personalization_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE interaction_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistance_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

-- ====================================================================
-- 3. Define RLS Policies for Organizations & Tenant Resources
-- ====================================================================

-- Organizations Policy
DROP POLICY IF EXISTS org_isolation_policy ON organizations;
CREATE POLICY org_isolation_policy ON organizations
    FOR ALL
    USING (is_app_super_admin() OR id = current_app_org_id());

-- Users Policy
DROP POLICY IF EXISTS users_isolation_policy ON users;
CREATE POLICY users_isolation_policy ON users
    FOR ALL
    USING (is_app_super_admin() OR organization_id = current_app_org_id());

-- Departments Policy
DROP POLICY IF EXISTS departments_isolation_policy ON departments;
CREATE POLICY departments_isolation_policy ON departments
    FOR ALL
    USING (is_app_super_admin() OR organization_id = current_app_org_id());

-- Tasks Policy
DROP POLICY IF EXISTS tasks_isolation_policy ON tasks;
CREATE POLICY tasks_isolation_policy ON tasks
    FOR ALL
    USING (is_app_super_admin() OR organization_id = current_app_org_id());

-- Workflows Policy
DROP POLICY IF EXISTS workflows_isolation_policy ON workflows;
CREATE POLICY workflows_isolation_policy ON workflows
    FOR ALL
    USING (is_app_super_admin() OR organization_id = current_app_org_id());

-- Work Sessions Policy
DROP POLICY IF EXISTS work_sessions_isolation_policy ON work_sessions;
CREATE POLICY work_sessions_isolation_policy ON work_sessions
    FOR ALL
    USING (is_app_super_admin() OR organization_id = current_app_org_id());

-- Interaction Configurations Policy
DROP POLICY IF EXISTS interaction_configs_isolation_policy ON interaction_configurations;
CREATE POLICY interaction_configs_isolation_policy ON interaction_configurations
    FOR ALL
    USING (is_app_super_admin() OR organization_id = current_app_org_id());

-- Assistance Requests Policy
DROP POLICY IF EXISTS assistance_requests_isolation_policy ON assistance_requests;
CREATE POLICY assistance_requests_isolation_policy ON assistance_requests
    FOR ALL
    USING (is_app_super_admin() OR organization_id = current_app_org_id());

-- Audit Events Policy (Immutable: SELECT and INSERT only)
DROP POLICY IF EXISTS audit_events_isolation_policy ON audit_events;
CREATE POLICY audit_events_isolation_policy ON audit_events
    FOR SELECT
    USING (is_app_super_admin() OR organization_id = current_app_org_id());

DROP POLICY IF EXISTS audit_events_insert_policy ON audit_events;
CREATE POLICY audit_events_insert_policy ON audit_events
    FOR INSERT
    WITH CHECK (is_app_super_admin() OR organization_id = current_app_org_id());
