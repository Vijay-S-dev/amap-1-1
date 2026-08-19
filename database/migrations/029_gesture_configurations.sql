-- AMAP Database Migration 029
-- Gesture-specific interaction configuration

CREATE TABLE gesture_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    interaction_configuration_id UUID NOT NULL,

    gesture_name TEXT NOT NULL,

    action_id UUID NOT NULL,

    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    confidence_threshold NUMERIC(5,4)
        CHECK (
            confidence_threshold IS NULL
            OR (
                confidence_threshold >= 0
                AND confidence_threshold <= 1
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT gesture_configurations_interaction_configuration_id_fkey
        FOREIGN KEY (interaction_configuration_id)
        REFERENCES interaction_configurations(id)
        ON DELETE RESTRICT,

    CONSTRAINT gesture_configurations_action_id_fkey
        FOREIGN KEY (action_id)
        REFERENCES actions(id)
        ON DELETE RESTRICT,

    CONSTRAINT gesture_configurations_configuration_gesture_key
        UNIQUE (interaction_configuration_id, gesture_name)
);

CREATE INDEX idx_gesture_configurations_action_id
    ON gesture_configurations(action_id);

CREATE INDEX idx_gesture_configurations_enabled
    ON gesture_configurations(is_enabled);