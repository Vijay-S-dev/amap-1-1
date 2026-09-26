-- 051: Per-user accessibility preferences (PostgreSQL-authoritative)
--
-- The AccessibilityContext stored language, high contrast, text scale,
-- reduced motion, audio feedback, modality, and onboarding milestones only in
-- localStorage (local-state-only authoritative settings). Persist them per
-- user so refresh, logout/login, and backend restart all preserve them.

CREATE TABLE IF NOT EXISTS user_accessibility_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
