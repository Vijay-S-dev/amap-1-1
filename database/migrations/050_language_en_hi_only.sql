-- 050: English + Hindi only in authoritative language configuration
--
-- The product specification allows only English and Hindi. The 046 defaults
-- shipped a five-language list; reduce the authoritative configuration to
-- en/hi for every organization (data + default).

UPDATE organizations
SET supported_languages = '["en", "hi"]'::jsonb,
    updated_at = CURRENT_TIMESTAMP
WHERE supported_languages IS NULL
   OR supported_languages <> '["en", "hi"]'::jsonb;

UPDATE organizations
SET default_language = 'en',
    updated_at = CURRENT_TIMESTAMP
WHERE default_language NOT IN ('en', 'hi');

ALTER TABLE organizations
    ALTER COLUMN supported_languages SET DEFAULT '["en", "hi"]'::jsonb;
