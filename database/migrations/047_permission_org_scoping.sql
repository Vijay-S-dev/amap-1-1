-- 047: Organization-scoped role permissions (tenant isolation for the RBAC matrix)
--
-- role_permissions was platform-global: any organization's admin edits would
-- leak across tenants. Scope every grant to an organization so the permission
-- matrix, enforcement, and audit are organization-isolated.

ALTER TABLE role_permissions
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE;

-- Capture the platform grants, empty the table (releasing the old primary
-- key), then re-insert one grant per existing organization.
DROP TABLE IF EXISTS tmp_old_role_grants;
CREATE TEMP TABLE tmp_old_role_grants AS
    SELECT DISTINCT role_id, permission_id FROM role_permissions;

DELETE FROM role_permissions;

ALTER TABLE role_permissions DROP CONSTRAINT IF EXISTS role_permissions_pkey;

INSERT INTO role_permissions (organization_id, role_id, permission_id)
SELECT org.id, g.role_id, g.permission_id
FROM tmp_old_role_grants AS g
CROSS JOIN organizations AS org;

DROP TABLE tmp_old_role_grants;

ALTER TABLE role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (organization_id, role_id, permission_id);

ALTER TABLE role_permissions
    ALTER COLUMN organization_id SET NOT NULL;
