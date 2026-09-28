-- AMAP Database Migration 052
-- Real-time worker interaction engine support:
--   1. work_sessions.last_heartbeat_at — real online/offline detection for the
--      supervisor live worker monitor (replaces "session row exists == online").
--   2. actions.category extended with 'ui_interaction' for computer/UI
--      interaction actions (cursor, clicks, drag, scroll, select) that ride the
--      same /actions/execute safety gateway as workflow actions.
--   3. Canonical UI-interaction and task-lifecycle actions registered.
--   4. Default gesture -> action mappings persisted per interaction preset
--      (gesture_configurations), giving PostgreSQL-authoritative gesture
--      mapping that workers can override via worker_personalizations.
--
-- Idempotent: safe to re-run on existing databases.

-- 1. Heartbeat column for live online/offline telemetry
ALTER TABLE work_sessions
    ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMPTZ;

-- 2. Extend allowed action categories with 'ui_interaction'
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'actions_category_check'
          AND conrelid = 'actions'::regclass
    ) THEN
        ALTER TABLE actions DROP CONSTRAINT actions_category_check;
    END IF;
END $$;

ALTER TABLE actions
    ADD CONSTRAINT actions_category_check
    CHECK (
        category IN (
            'general',
            'navigation',
            'workflow',
            'task',
            'assistance',
            'system',
            'ui_interaction'
        )
    );

-- 3. Canonical actions: UI/computer interaction + task lifecycle
INSERT INTO actions (id, name, display_name, description, category, status)
VALUES
    ('40000000-0000-0000-0000-000000000010', 'pointer_move', 'Pointer Move', 'Move the virtual application pointer', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000011', 'left_click', 'Left Click', 'Primary activation click at the virtual cursor position', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000012', 'right_click', 'Right Click', 'Open the application context menu at the virtual cursor position', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000013', 'double_click', 'Double Click', 'Rapid double activation click at the virtual cursor position', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000014', 'drag_start', 'Drag Start', 'Grab the element under the virtual cursor and begin dragging', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000015', 'drag_move', 'Drag Move', 'Continuous movement of an actively dragged element (batched client-side)', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000016', 'drag_end', 'Drag End', 'Release the dragged element at the current virtual cursor position', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000017', 'scroll_up', 'Scroll Up', 'Scroll the application view upward', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000018', 'scroll_down', 'Scroll Down', 'Scroll the application view downward', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000019', 'scroll', 'Scroll', 'Scroll the application view in a parameterized direction', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000020', 'scroll_left', 'Scroll Left', 'Scroll the application view horizontally left', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000021', 'scroll_right', 'Scroll Right', 'Scroll the application view horizontally right', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000022', 'select_item', 'Select Item', 'Select/focus the UI or task item under the virtual cursor', 'ui_interaction', 'active'),
    ('40000000-0000-0000-0000-000000000023', 'start_assignment', 'Start Assignment', 'Begin working an assigned task', 'task', 'active'),
    ('40000000-0000-0000-0000-000000000024', 'complete_step', 'Complete Step', 'Mark the current workflow step as completed', 'workflow', 'active'),
    ('40000000-0000-0000-0000-000000000025', 'finish_assignment', 'Finish Assignment', 'Finish the assigned task and record the authoritative result', 'task', 'active'),
    ('40000000-0000-0000-0000-000000000026', 'cancel_action', 'Cancel Action', 'Cancel the current pending action where safe', 'workflow', 'active')
ON CONFLICT (name) DO NOTHING;

-- 4. Default gesture -> action mappings for the seeded interaction presets.
--    gesture_configurations is preset-scoped; worker-level overrides live in
--    worker_personalizations.personalization_data.gesture_action_map.
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

-- 5. Backfill: attach worker personalizations that have no preset to their
--    organization's default preset so preset gesture mappings apply.
UPDATE worker_personalizations wp
SET interaction_configuration_id = (
    SELECT ic.id
    FROM interaction_configurations ic
    JOIN worker_profiles wprof ON wprof.id = wp.worker_profile_id
    JOIN users u ON u.id = wprof.user_id
    WHERE ic.organization_id = u.organization_id
      AND ic.status = 'active'
    ORDER BY ic.created_at
    LIMIT 1
)
WHERE wp.interaction_configuration_id IS NULL;
