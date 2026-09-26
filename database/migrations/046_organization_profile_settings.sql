-- AMAP Database Migration 046
-- Phase 8: organization profile/settings persistence.
--
-- GET /organizations/manage/profile previously fabricated
-- organization_type/industry/location/contact_email/default_language/
-- supported_languages/accessibility_defaults as hardcoded constants, and
-- PUT only wrote the name (audit-only for everything else). These columns
-- let every exposed profile/settings field persist to PostgreSQL.
--
-- Defaults preserve today's declared API behavior so Phase 10 can then
-- migrate language policy (en/hi) as a real data change.

ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS organization_type TEXT
        NOT NULL DEFAULT 'industrial_manufacturing';

ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS industry TEXT
        NOT NULL DEFAULT 'Automotive & Aerospace Assembly';

ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS location TEXT
        NOT NULL DEFAULT 'Main Operations Facility';

ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS contact_email TEXT;

ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS default_language TEXT
        NOT NULL DEFAULT 'en';

ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS supported_languages JSONB
        NOT NULL DEFAULT '["en", "es", "ta", "hi", "de"]'::jsonb;

ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS accessibility_defaults JSONB
        NOT NULL DEFAULT jsonb_build_object(
            'default_dwell_time_ms', 500,
            'high_contrast_default', FALSE,
            'min_target_size_px', 48,
            'voice_confirmation_default', FALSE
        );
