-- 049: Persist interaction configuration payloads
--
-- The admin preset editor echoed config_data back in API responses but the
-- column did not exist in PostgreSQL, so every saved preset silently lost its
-- parameters (audit-only write). Persist config_data for real.

ALTER TABLE interaction_configurations
    ADD COLUMN IF NOT EXISTS config_data JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE interaction_configurations
SET config_data = '{}'::jsonb
WHERE config_data IS NULL;
