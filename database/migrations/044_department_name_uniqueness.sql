-- AMAP Database Migration 044
-- Department name uniqueness per organization (Phase 5: real 409 semantics)
--
-- Duplicate department creation previously relied solely on an application
-- level SELECT check with no database guarantee (race window), and the API
-- returned 400 instead of 409. This unique index makes the constraint
-- authoritative; the service maps UniqueViolation -> HTTP 409.

CREATE UNIQUE INDEX uq_departments_org_name
    ON departments(organization_id, name);
