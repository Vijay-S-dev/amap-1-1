# AMAP — Phase 0 Baseline Snapshot

**Date:** 2026-09-26 (Asia/Calcutta)
**Phase:** 0 — Baseline Snapshot (read-only measurement; no code modified in this phase)
**Program:** Full Repair + Dynamic Implementation Program

---

## 1. Repository state

| Item | Value |
|---|---|
| Branch | `arena/01a0dc53-amap` |
| Commit (baseline) | `e4c6a6ea097f30c969cbcd4100df632be8715b33` — *"Implement AMAP RBAC and admin functionality"* |
| Working tree | **clean** (`git status` → no changes) |
| Stashes | 0 |
| Worktrees | 1 (this checkout only) |
| Clone type | shallow (`.git/shallow` = `e4c6a6e`); remote `main` = `e4c6a6e`, 161 ancestor commits |
| Remote | `https://github.com/Vijay-S-dev/AMAP.git` |

## 2. Database migrations

| Item | Value |
|---|---|
| Migration count | **40** (`001_extensions.sql` … `040_supabase_row_level_security.sql`) |
| Latest migration | `040_supabase_row_level_security.sql` |
| Known migration defect | **040 fails on fresh DBs**: creates RLS policy on `work_sessions.organization_id`, but `035_work_sessions.sql` never creates that column → `column "organization_id" does not exist` |
| Missing migrations | no `custom_gestures` table migration; no readiness persistence migration |

## 3. Backend tests (this environment, Python 3.11, no PostgreSQL)

| Metric | Value |
|---|---|
| Tests collected | **509** |
| Collection errors | **3** — `tests/test_ai_subsystem.py`, `tests/test_fr01_user_input_capture.py`, `tests/test_master_fr01_to_fr10.py` (all `NameError: name 'Any' is not defined` at `ai/personalization/analyzer.py:46`) |
| Passed | **243** |
| Failed | **266** (predominantly `psycopg.OperationalError` — no database available) |
| Skipped | 0 |
| Reference (previous audit, real PostgreSQL properly provisioned) | **508 passed / 1 failed** (`test_unauthenticated_request_to_org_management_denied`: 403≠401) / 3 collection errors |

Baseline without DB reproduces the original forensic audit's 509 / 243 / 266 / 3 figures exactly.

## 4. Frontend

| Gate | Result |
|---|---|
| `npm ci` | PASS (287 top-level packages; Node v22.22.3, npm 10.9.8) |
| Typecheck (`tsc --noEmit`) | **FAIL (exit 2)** — `worker/components/MultimodalHUD.tsx(237,31): TS2345: Argument of type 'null' is not assignable to parameter of type 'SetStateAction<string>'` |
| Production build (`next build`) | **FAIL (exit 1)** — compiles, then fails type-check with the same `MultimodalHUD.tsx:237` error |
| Frontend test framework | none configured |

## 5. Known failures carried into the program

From the accepted forensic/acceptance audit (all verified live at this commit):

1. **Authentication** — seeded hash ≠ `SecurePassword123!` (401 for all seeded accounts); `verify_token` `NameError` → 500; missing credentials → 403 instead of 401.
2. **RBAC** — divergent roles (`super_admin`, `superadmin`, `manager`, `organization_admin`); canonical set is `admin/organization_admin/supervisor/worker`.
3. **Database** — migration 040 fails; custom gestures have no PG table (silent SQLite fallback with `except: pass`); readiness fully in-memory.
4. **Admin users** — `GET /admin/users` → 500 (`UsersRepository.list_by_organization_id` AttributeError).
5. **Org audit** — `GET /organizations/manage/audit` → 500 (`list_by_organization_id() got unexpected keyword 'limit'`).
6. **Departments** — update/deactivate audit-only (fake 200); counts hardcoded (1/2/1); duplicate → 400 not 409.
7. **Workers** — list = 5 hardcoded records; invite = 201 with no DB write; duplicate email unhandled.
8. **Supervisors** — invite/update audit-only; list real but with fabricated department/counts.
9. **Workflows** — list = 3 hardcoded; create/update audit-only; seeded workflow not shown.
10. **Analytics** — fabricated constants (19, 94.5%, 8.2 min, …) derived from hardcoded worker list.
11. **Permissions** — static `INITIAL_PERMISSIONS`, no API.
12. **Adaptations** — `DEMO_ADAPTATIONS`, no persistence.
13. **Assistance/emergencies** — org-level assistance hardcoded; emergencies literal `return []`.
14. **Readiness** — in-memory store, lost on restart; no language validation.
15. **Language** — frontend supports `en/es/ta/hi/de`; requirement is English + Hindi only.
16. **Voice** — clean install 503 (`requests` undeclared for faster-whisper import); no FFmpeg in Docker; transcription never verified E2E.
17. **Multimodal** — `test_multimodal_spatial_voice_integration` FAILS (`fused_action == None`); HUD never sends `context_data`.
18. **Frontend** — typecheck/build fail (MultimodalHUD.tsx:237).
19. **CI** — `.github/workflows/ci.yml` is 0 bytes.
20. **E2E** — no browser framework; `tests/e2e` uncollectable (`ai/` `Any` bug).
21. **Results** — repository tests exist; completion→result loop not live-verified.
22. **Training screen** — not verified.

## 6. Acceptance status at baseline

**NOT ACCEPTED** (per the final acceptance audit): 0 fully-WORKING features on complete-path criteria except task-assignment core, admin audit read, and emergency-stop sub-path; 11 PARTIAL; 12 BROKEN; 1 NOT VERIFIED.

---

*This report is the Phase 0 deliverable. No application code was modified in Phase 0.*
