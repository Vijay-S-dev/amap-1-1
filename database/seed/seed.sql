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
    ('a0000000-0000-0000-0000-000000000003', 'worker', 'Assembly line technician operating accessible multimodal workstations'),
    ('a0000000-0000-0000-0000-000000000004', 'organization_admin', 'Organization administrator governing users, departments, and workflows within their organization')
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

-- 5. Role Permissions (organization-scoped since migration 047)
INSERT INTO role_permissions (organization_id, role_id, permission_id)
SELECT org.id, v.role_id, v.permission_id
FROM (
    VALUES
        ('a0000000-0000-0000-0000-000000000001'::uuid, 'b0000000-0000-0000-0000-000000000001'::uuid),
        ('a0000000-0000-0000-0000-000000000001'::uuid, 'b0000000-0000-0000-0000-000000000006'::uuid),
        ('a0000000-0000-0000-0000-000000000002'::uuid, 'b0000000-0000-0000-0000-000000000001'::uuid),
        ('a0000000-0000-0000-0000-000000000002'::uuid, 'b0000000-0000-0000-0000-000000000005'::uuid),
        ('a0000000-0000-0000-0000-000000000003'::uuid, 'b0000000-0000-0000-0000-000000000001'::uuid),
        ('a0000000-0000-0000-0000-000000000003'::uuid, 'b0000000-0000-0000-0000-000000000002'::uuid),
        ('a0000000-0000-0000-0000-000000000003'::uuid, 'b0000000-0000-0000-0000-000000000003'::uuid),
        ('a0000000-0000-0000-0000-000000000003'::uuid, 'b0000000-0000-0000-0000-000000000004'::uuid),
        ('a0000000-0000-0000-0000-000000000004'::uuid, 'b0000000-0000-0000-0000-000000000001'::uuid),
        ('a0000000-0000-0000-0000-000000000004'::uuid, 'b0000000-0000-0000-0000-000000000005'::uuid),
        ('a0000000-0000-0000-0000-000000000004'::uuid, 'b0000000-0000-0000-0000-000000000006'::uuid)
) AS v(role_id, permission_id)
CROSS JOIN organizations AS org
ON CONFLICT DO NOTHING;

-- 6. Users (Default Password for all: SecurePassword123!)
-- Hash: pbkdf2_sha256$600000$bc5ab92aba13d70295b07ec1b9619ccc$10df13a62e551e5879a3d5829abbd57ba89f49d25c78d936f2a426309971e3d9
-- NOTE: maria.newhire@amap.com is the Fresher (new hire) demo account
-- referenced by the login screen. It MUST exist for fresher login to work.
INSERT INTO users (id, organization_id, email, full_name, password_hash, status)
VALUES
    ('c0000000-0000-0000-0000-000000000001', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'admin@amap.com', 'Sarah Jenkins (Admin)', 'pbkdf2_sha256$600000$bc5ab92aba13d70295b07ec1b9619ccc$10df13a62e551e5879a3d5829abbd57ba89f49d25c78d936f2a426309971e3d9', 'active'),
    ('c0000000-0000-0000-0000-000000000002', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'supervisor@amap.com', 'Marcus Vance (Supervisor)', 'pbkdf2_sha256$600000$bc5ab92aba13d70295b07ec1b9619ccc$10df13a62e551e5879a3d5829abbd57ba89f49d25c78d936f2a426309971e3d9', 'active'),
    ('c0000000-0000-0000-0000-000000000003', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'alex.worker@amap.com', 'Alex Morgan (Worker)', 'pbkdf2_sha256$600000$bc5ab92aba13d70295b07ec1b9619ccc$10df13a62e551e5879a3d5829abbd57ba89f49d25c78d936f2a426309971e3d9', 'active'),
    ('c0000000-0000-0000-0000-000000000004', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'jordan.worker@amap.com', 'Jordan Lee (Worker)', 'pbkdf2_sha256$600000$bc5ab92aba13d70295b07ec1b9619ccc$10df13a62e551e5879a3d5829abbd57ba89f49d25c78d936f2a426309971e3d9', 'active'),
    ('c0000000-0000-0000-0000-000000000005', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'maria.newhire@amap.com', 'Maria Rodriguez (Fresher Worker)', 'pbkdf2_sha256$600000$bc5ab92aba13d70295b07ec1b9619ccc$10df13a62e551e5879a3d5829abbd57ba89f49d25c78d936f2a426309971e3d9', 'active')
ON CONFLICT (id) DO NOTHING;

-- 7. User Roles Assignments
INSERT INTO user_roles (user_id, role_id)
VALUES
    ('c0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001'),
    ('c0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000004'),
    ('c0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000002'),
    ('c0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000003'),
    ('c0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000003'),
    ('c0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000003')
ON CONFLICT DO NOTHING;

-- 8. Worker Profiles
INSERT INTO worker_profiles (id, user_id)
VALUES
    ('d0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000003'),
    ('d0000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000004'),
    ('d0000000-0000-0000-0000-000000000003', 'c0000000-0000-0000-0000-000000000005')
ON CONFLICT (id) DO NOTHING;

-- 11. Interaction Configurations
INSERT INTO interaction_configurations (id, organization_id, name, description, status)
VALUES
    ('80000000-0000-0000-0000-000000000001', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'Powertrain High-Noise Preset', 'Default configuration for noisy industrial floors', 'active'),
    ('80000000-0000-0000-0000-000000000002', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'Motor Diversity Enhanced Dwell Preset', 'Configuration with extended dwell times for motor accessibility', 'active')
ON CONFLICT (id) DO NOTHING;

-- 11b. Default gesture -> action mappings for the seeded interaction presets
-- (migration 052 seeds these too, but on a fresh database it runs before the
-- presets exist, so the seed guarantees them once presets are created).
-- gesture_configurations is preset-scoped; worker-level overrides live in
-- worker_personalizations.personalization_data.gesture_action_map.
INSERT INTO gesture_configurations (interaction_configuration_id, gesture_name, action_id, is_enabled, confidence_threshold)
SELECT preset.id, g.gesture_name, g.action_id, TRUE, g.confidence
FROM (
    VALUES
        ('pinch',           '40000000-0000-0000-0000-000000000011'::uuid, 0.75),
        ('pinch_hold',      '40000000-0000-0000-0000-000000000022'::uuid, 0.75),
        ('two_finger',      '40000000-0000-0000-0000-000000000012'::uuid, 0.80),
        ('two_finger_move', '40000000-0000-0000-0000-000000000019'::uuid, 0.75),
        ('swipe_up',        '40000000-0000-0000-0000-000000000017'::uuid, 0.80),
        ('swipe_down',      '40000000-0000-0000-0000-000000000018'::uuid, 0.80),
        ('swipe_left',      '40000000-0000-0000-0000-000000000003'::uuid, 0.80),
        ('swipe_right',     '40000000-0000-0000-0000-000000000001'::uuid, 0.80),
        ('thumbs_up',       '40000000-0000-0000-0000-000000000002'::uuid, 0.78),
        ('thumbs_down',     '40000000-0000-0000-0000-000000000026'::uuid, 0.78),
        ('open_palm',       '40000000-0000-0000-0000-000000000004'::uuid, 0.82),
        ('fist',            '40000000-0000-0000-0000-000000000006'::uuid, 0.75)
) AS g(gesture_name, action_id, confidence)
CROSS JOIN interaction_configurations AS preset
ON CONFLICT (interaction_configuration_id, gesture_name) DO NOTHING;

-- 9. Worker Personalization & Capability Profiles
INSERT INTO worker_capability_profiles (worker_profile_id, capability_data, status)
VALUES
    ('d0000000-0000-0000-0000-000000000001', '{"preferred_modality": "multimodal", "has_motor_tremor": true, "has_speech_diversity": false}'::jsonb, 'active'),
    ('d0000000-0000-0000-0000-000000000002', '{"preferred_modality": "gesture", "has_motor_tremor": false, "has_speech_diversity": true}'::jsonb, 'active'),
    ('d0000000-0000-0000-0000-000000000003', '{"preferred_modality": "multimodal", "has_motor_tremor": false, "has_speech_diversity": false}'::jsonb, 'active')
ON CONFLICT (worker_profile_id) DO NOTHING;

INSERT INTO worker_personalizations (worker_profile_id, interaction_configuration_id, personalization_data, status)
VALUES
    ('d0000000-0000-0000-0000-000000000001', '80000000-0000-0000-0000-000000000001', '{"dwell_time_ms": 650, "hitbox_scaling_factor": 1.25, "voice_noise_gate_db": 14.0, "is_auto_adapted": true}'::jsonb, 'active'),
    ('d0000000-0000-0000-0000-000000000002', '80000000-0000-0000-0000-000000000002', '{"dwell_time_ms": 500, "hitbox_scaling_factor": 1.00, "voice_noise_gate_db": 18.0, "is_auto_adapted": false}'::jsonb, 'active'),
    ('d0000000-0000-0000-0000-000000000003', '80000000-0000-0000-0000-000000000002', '{"dwell_time_ms": 500, "hitbox_scaling_factor": 1.00, "voice_noise_gate_db": 16.0, "is_auto_adapted": false}'::jsonb, 'active')
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

-- 12. Active Work Session & Open Assistance Ticket
INSERT INTO work_sessions (id, organization_id, worker_profile_id, status, started_at)
VALUES
    ('90000000-0000-0000-0000-000000000001', '9a61e05d-7a32-4112-9c17-1833d7b42f65', 'd0000000-0000-0000-0000-000000000001', 'active', CURRENT_TIMESTAMP)
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
    ('61000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'assigned'),
    ('61000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000003', 'assigned')
ON CONFLICT (id) DO NOTHING;

INSERT INTO workflow_assignments (id, workflow_id, worker_profile_id, status)
VALUES
    ('60000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'assigned')
ON CONFLICT (id) DO NOTHING;

-- 16. Worker Readiness (persisted onboarding lifecycle state)
INSERT INTO worker_readiness (
    worker_profile_id, is_fresher, onboarding_completed, readiness_status,
    interaction_mode, gesture_ready, voice_ready, multimodal_ready,
    task_training_complete, overall_ready, completed_stages, active_preferences
)
VALUES
    (
        'd0000000-0000-0000-0000-000000000001', FALSE, TRUE, 'ready',
        'multimodal', TRUE, TRUE, TRUE,
        TRUE, TRUE,
        '["language", "accessibility", "gesture_calibration", "voice_setup", "training"]'::jsonb,
        '{"language": "en", "modality": "multimodal", "dwell_time_ms": 500, "high_contrast": false, "text_scale": 1.0}'::jsonb
    ),
    (
        'd0000000-0000-0000-0000-000000000002', TRUE, FALSE, 'incomplete',
        'multimodal', FALSE, FALSE, FALSE,
        FALSE, FALSE,
        '[]'::jsonb,
        '{"language": "en", "modality": "multimodal", "dwell_time_ms": 500, "high_contrast": false, "text_scale": 1.0}'::jsonb
    ),
    (
        'd0000000-0000-0000-0000-000000000003', TRUE, FALSE, 'incomplete',
        'multimodal', FALSE, FALSE, FALSE,
        FALSE, FALSE,
        '[]'::jsonb,
        '{"language": "en", "modality": "multimodal", "dwell_time_ms": 500, "high_contrast": false, "text_scale": 1.0}'::jsonb
    )
ON CONFLICT (worker_profile_id) DO NOTHING;
