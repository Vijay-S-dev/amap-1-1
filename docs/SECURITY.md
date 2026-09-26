# AMAP Security Architecture & Threat Model

## 1. Core Security Principle
The Accessible Multimodal Assembly Platform (AMAP) operates under a zero-trust model governed by the core architectural invariant:
$$\mathbf{Recognition \neq Intent \neq Authorization \neq Execution}$$

1. **Recognition:** Raw optical landmarks (MediaPipe) or acoustic signals (Whisper ASR) capture worker physical input.
2. **Intent:** Multimodal late fusion, confidence arbitration, and dwell-time accumulation filter involuntary movements or speech artifacts into semantic intent.
3. **Authorization:** Organization-scoped JWT tokens and Role-Based Access Control (RBAC) verify caller permissions and tenant boundaries.
4. **Execution:** Actions pass through server-side safety gating, parameter validation, and workflow state checks before modifying state.

---

## 2. Authentication & Session Security
- **Algorithm:** PBKDF2 with SHA-256 (600,000 iterations) for password hashing.
- **Tokens:** Signed JSON Web Tokens (JWT) using HMAC-SHA256 with 24-hour expiration.
- **Claims:** JWT payload contains `user_id`, `organization_id`, `worker_profile_id` (if applicable), `roles`, and `permissions`.
- **Session Revocation:** Logout and session expiration reject invalid or expired tokens immediately (HTTP 401 Unauthorized).

---

## 3. Multi-Tenant Organization Isolation
- **Tenant Scope:** Every domain entity in PostgreSQL includes `organization_id UUID NOT NULL`.
- **Repository-Level Scoping:** All SQL queries and parameterized DML statements enforce `WHERE organization_id = %s`.
- **Cross-Organization Protection:** Accessing resources across organization boundaries results in HTTP 403 Forbidden or HTTP 404 Not Found.
- **Tenant Validation:** Authenticated user context (`AuthenticatedUserContext`) injects verified `organization_id` from the cryptographically signed JWT.

---

## 4. Role-Based Access Control (RBAC)
Authoritative roles defined in `database/seed/seed.sql`:
- **Worker (`worker`):** Access to assigned tasks, workflow step progression, assistance requests, custom gesture training, and accessibility preferences.
- **Supervisor (`supervisor`):** Access to live fleet telemetry, worker inspection, task assignment/reassignment, and assistance request resolution.
- **Organization Admin (`admin`):** Full tenant administration, user provisioning, department management, interaction presets, and immutable audit logs.
- **Manager (`manager`):** Operational oversight, task management, and supervisor escalation triage.

---

## 5. Input Validation & Mass-Assignment Prevention
- **Pydantic v2 Strict Input Models:** All request schemas inherit from `StrictInputModel` (`ConfigDict(extra="forbid", str_strip_whitespace=True)`).
- **SQL Injection Immunization:** 100% of database queries use psycopg parameterized placeholders (`%s`); zero dynamic string interpolation.
- **Safety Interlocks:** Dangerous or safety-critical workflow actions require secondary explicit confirmation before execution.

---

## 6. Software Emergency Stop Safety Boundary
- **Software Boundary Definition:** The endpoint `/api/v1/actions/emergency-stop` provides a digital session-level interlock that locks the UI, pauses workstation sessions, notifies supervisors, and logs immutable audit records.
- **Operational Boundary:** Software emergency stops operate at the application layer and do not replace hardwired physical machinery emergency stops (SIL-3 / ISO 13849-1 PLe).

---

## 7. Immutable Audit Trail
- All security-sensitive actions (logins, authorization failures, permission updates, department changes, emergency stops, assistance triage) are appended to the `audit_events` and `execution_events` tables in PostgreSQL with actor IDs, timestamps, and resource references.
