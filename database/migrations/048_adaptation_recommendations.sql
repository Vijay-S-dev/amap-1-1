-- 048: Persistent adaptation recommendations (supervisor/admin review queue)
--
-- Evidence-based adaptation recommendations were computed ephemerally and never
-- stored; the admin review panel ran on hardcoded demo rows. Recommendations are
-- now first-class PostgreSQL rows with an approve/dismiss review lifecycle.

CREATE TABLE IF NOT EXISTS adaptation_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    worker_profile_id UUID NOT NULL REFERENCES worker_profiles(id) ON DELETE CASCADE,
    recommendation_type TEXT NOT NULL,
    current_value JSONB NOT NULL DEFAULT 'null'::jsonb,
    suggested_value JSONB NOT NULL DEFAULT 'null'::jsonb,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    reason TEXT NOT NULL,
    auto_applicable BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'dismissed')),
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_adaptation_recommendations_org_status
    ON adaptation_recommendations (organization_id, status);
CREATE INDEX IF NOT EXISTS idx_adaptation_recommendations_worker
    ON adaptation_recommendations (worker_profile_id);
