-- ====================================================================
-- AMAP Database Seed Data
-- Demo Manufacturing Floor Scenario: Acme Motors Assembly Plant 1
-- Populates: Organizations, Departments, Users, Roles, Permissions,
-- Worker Profiles, Jobs, Workflows, Steps, Tasks, Presets & Personalizations
-- ====================================================================

-- 1. Organization
INSERT INTO organizations (id, name, status)
VALUES ('9a61e05d-7a32-4112-9c17-1833d7b42f65', 'Acme Motors — Assembly Plant 1', 'active')
ON CONFLICT (id) DO NOTHING;

-- 2. Departments
INSERT INTO departments (id, organization_id, name, status)
VALUES
    ('11111111-1111-1111-1111-111111111111', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'Powertrain & Gearbox Integration', 'active'),
    ('22222222-2222-2222-2222-222222222222', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'Chassis & Structural Welding', 'active'),
    ('33333333-3333-3333-3333-333333333333', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'Quality Control & Diagnostics', 'active')
ON CONFLICT (id) DO NOTHING;

-- 3. Roles
INSERT INTO roles (id, name, description)
VALUES
    ('a0000000-0000-0000-0000-000000000001', 'admin', 'System administrator with full organizational governance'),
    ('a0000000-0000-0000-0000-000000000002', 'supervisor', 'Floor supervisor managing line workers and assistance queue'),
    ('a0000000-0000-0000-0000-000000000003', 'worker', 'Assembly line technician operating accessible multimodal workstations')
ON CONFLICT (id) DO NOTHING;

-- 4. Permissions
INSERT INTO permissions (id, name, description)
VALUES
    ('b0000000-0000-0000-0000-000000000001', 'session:read', 'Read active session telemetry'),
    ('b0000000-0000-0000-0000-000000000002', 'session:write', 'Start, pause, and advance work sessions'),
    ('b0000000-0000-0000-0000-000000000003', 'multimodal:input', 'Submit gesture and voice multimodal frames'),
    ('b0000000-0000-0000-0000-000000000004', 'assistance:request', 'Trigger supervisor assistance calls'),
    ('b0000000-0000-0000-0000-000000000005', 'assistance:resolve', 'Claim and resolve assistance tickets'),
    ('b0000000-0000-0000-0000-000000000006', 'admin:config', 'Configure station interaction presets and audit logs')
ON CONFLICT (id) DO NOTHING;

-- 5. Role Permissions
INSERT INTO role_permissions (role_id, permission_id)
VALUES
    ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001'),
    ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000006'),
    ('a0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000001'),
    ('a0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000005'),
    ('a0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000001'),
    ('a0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000002'),
    ('a0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000003'),
    ('a0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000004')
ON CONFLICT DO NOTHING;

-- 6. Users (Default Password for all: SecurePassword123!)
-- Hash: pbkdf2_sha256$600000$5608b4923e3ecbcf3a1e2f9d5c80e1b2$5c2c79bf270c5384666579ec7d983e20df38a14b0114092b6a22c53fcf58b688
INSERT INTO users (id, organization_id, email, full_name, password_hash, status)
VALUES
    ('c0000000-0000-0000-0000-000000000001', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'admin@amap.com', 'Sarah Jenkins (Admin)', 'pbkdf2_sha256$600000$5608b4923e3ecbcf3a1e2f9d5c80e1b2$5c2c79bf270c5384666579ec7d983e20df38a14b0114092b6a22c53fcf58b688', 'active'),
    ('c0000000-0000-0000-0000-000000000002', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'supervisor@amap.com', 'Marcus Vance (Supervisor)', 'pbkdf2_sha256$600000$5608b4923e3ecbcf3a1e2f9d5c80e1b2$5c2c79bf270c5384666579ec7d983e20df38a14b0114092b6a22c53fcf58b688', 'active'),
    ('c0000000-0000-0000-0000-000000000003', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'alex.worker@amap.com', 'Alex Morgan (Worker)', 'pbkdf2_sha256$600000$5608b4923e3ecbcf3a1e2f9d5c80e1b2$5c2c79bf270c5384666579ec7d983e20df38a14b0114092b6a22c53fcf58b688', 'active'),
    ('c0000000-0000-0000-0000-000000000004', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'jordan.worker@amap.com', 'Jordan Lee (Worker)', 'pbkdf2_sha256$600000$5608b4923e3ecbcf3a1e2f9d5c80e1b2$5c2c79bf270c5384666579ec7d983e20df38a14b0114092b6a22c53fcf58b688', 'active')
ON CONFLICT (id) DO NOTHING;

-- 7. User Roles Assignments
INSERT INTO user_roles (user_id, role_id)
VALUES
    ('c0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001'),
    ('c0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000002'),
    ('c0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000003'),
    ('c0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000003')
ON CONFLICT DO NOTHING;

-- 8. Worker Profiles
INSERT INTO worker_profiles (id, user_id)
VALUES
    ('d0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000003'),
    ('d0000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000004')
ON CONFLICT (id) DO NOTHING;

-- 9. Worker Personalization & Capability Profiles
INSERT INTO worker_capability_profiles (worker_profile_id, capability_data, status)
VALUES
    ('d0000000-0000-0000-0000-000000000001', '{"preferred_modality": "multimodal", "has_motor_tremor": true, "has_speech_diversity": false}'::jsonb, 'active'),
    ('d0000000-0000-0000-0000-000000000002', '{"preferred_modality": "gesture", "has_motor_tremor": false, "has_speech_diversity": true}'::jsonb, 'active')
ON CONFLICT (worker_profile_id) DO NOTHING;

INSERT INTO worker_personalizations (worker_profile_id, personalization_data, status)
VALUES
    ('d0000000-0000-0000-0000-000000000001', '{"dwell_time_ms": 650, "hitbox_scaling_factor": 1.25, "voice_noise_gate_db": 14.0, "is_auto_adapted": true}'::jsonb, 'active'),
    ('d0000000-0000-0000-0000-000000000002', '{"dwell_time_ms": 500, "hitbox_scaling_factor": 1.00, "voice_noise_gate_db": 18.0, "is_auto_adapted": false}'::jsonb, 'active')
ON CONFLICT (worker_profile_id) DO NOTHING;

-- 10. Workflows & Assembly Steps
INSERT INTO workflows (id, organization_id, name, description, status)
VALUES
    ('e0000000-0000-0000-0000-000000000001', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'Inverter Sub-Assembly Alpha', 'Precision power electronics mounting and high-voltage busbar torque sequence', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO workflow_steps (id, workflow_id, step_order, name, description, status)
VALUES
    ('f0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 1, 'Optical Component Inspection', 'Verify thermal paste application and capacitor polarity on PCB bed.', 'active'),
    ('f0000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-000000000001', 2, 'Primary Busbar Torquing', 'Align copper busbar and torque M6 fasteners to 9.2 Nm in star pattern.', 'active'),
    ('f0000000-0000-0000-0000-000000000003', 'e0000000-0000-0000-0000-000000000001', 3, 'High Voltage Isolation Check', 'Connect dielectric probe to safety terminal and engage automated 500V test.', 'active')
ON CONFLICT (id) DO NOTHING;

-- 11. Interaction Configurations
INSERT INTO interaction_configurations (id, organization_id, name, description, status)
VALUES
    ('80000000-0000-0000-0000-000000000001', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'Powertrain High-Noise Preset', 'Default configuration for noisy industrial floors', 'active'),
    ('80000000-0000-0000-0000-000000000002', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'Motor Diversity Enhanced Dwell Preset', 'Configuration with extended dwell times for motor accessibility', 'active')
ON CONFLICT (id) DO NOTHING;

-- 12. Active Work Session & Open Assistance Ticket
INSERT INTO work_sessions (id, worker_profile_id, status, started_at)
VALUES
    ('90000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'active', CURRENT_TIMESTAMP)
ON CONFLICT (id) DO NOTHING;

INSERT INTO assistance_requests (id, organization_id, worker_profile_id, status, priority, reason)
VALUES
    ('70000000-0000-0000-0000-000000000001', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'd0000000-0000-0000-0000-000000000001', 'open', 'high', 'Dielectric probe calibration error on step 3.')
ON CONFLICT (id) DO NOTHING;

-- 13. Canonical Actions
INSERT INTO actions (id, name, display_name, description, category, status)
VALUES
    ('40000000-0000-0000-0000-000000000001', 'next_step', 'Next Step', 'Advance to the next workflow step', 'workflow', 'active'),
    ('40000000-0000-0000-0000-000000000002', 'confirm_action', 'Confirm Step Action', 'Confirm and complete current step action', 'workflow', 'active'),
    ('40000000-0000-0000-0000-000000000003', 'previous_step', 'Previous Step', 'Navigate back to the previous workflow step', 'navigation', 'active'),
    ('40000000-0000-0000-0000-000000000004', 'pause_session', 'Pause Work Session', 'Temporarily pause active workstation assembly', 'system', 'active'),
    ('40000000-0000-0000-0000-000000000005', 'resume_session', 'Resume Work Session', 'Resume paused workstation assembly', 'system', 'active'),
    ('40000000-0000-0000-0000-000000000006', 'emergency_stop', 'Emergency Stop', 'Software safety stop interlock and supervisor dispatch', 'system', 'active'),
    ('40000000-0000-0000-0000-000000000007', 'request_assistance', 'Request Assistance', 'Request floor supervisor assistance ticket', 'assistance', 'active')
ON CONFLICT (name) DO NOTHING;

-- 14. Assembly Task & Workflow Link
INSERT INTO tasks (id, organization_id, name, description, status)
VALUES
    ('50000000-0000-0000-0000-000000000001', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'Inverter Alpha Assembly', 'Power inverter electronics mounting and busbar torque sequence', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO task_workflows (task_id, workflow_id)
VALUES
    ('50000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001')
ON CONFLICT (task_id, workflow_id) DO NOTHING;

-- 15. Initial Worker Task Assignment & Workflow Assignment
INSERT INTO worker_task_assignments (id, task_id, worker_profile_id, status)
VALUES
    ('61000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'assigned')
ON CONFLICT (id) DO NOTHING;

INSERT INTO workflow_assignments (id, workflow_id, worker_profile_id, status)
VALUES
    ('60000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'assigned')
ON CONFLICT (id) DO NOTHING;
