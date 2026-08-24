# AMAP: Accessible Multimodal Assembly Platform
> **Enterprise-Grade Cyber-Physical Manufacturing Interface for Workers with Physical and Cognitive Diversities**

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)]()
[![Backend Tests](https://img.shields.io/badge/tests-379%20passed-success)]()
[![WCAG](https://img.shields.io/badge/WCAG-2.1%20AA%20Compliant-blue)]()
[![Security](https://img.shields.io/badge/security%20audit-20%2F20%20passed-purple)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

---

## 🎯 Architectural Core Invariant
Every component across the AMAP platform strictly enforces the fundamental architectural principle:
$$\mathbf{Recognition \neq Intent \neq Authorization \neq Execution}$$

- **Recognition:** Raw optical hand-tracking coordinates or acoustic speech transcription capture physical worker input.
- **Intent:** Multi-signal temporal fusion, fuzzy keyword normalization, and dwell accumulator establish confirmed semantic intent while filtering involuntary tremors.
- **Authorization:** Multi-tenant cryptographic JWT and role-based access control (RBAC) verify worker/supervisor/admin permissions and organization boundaries.
- **Execution:** Critical, irreversible manufacturing actions trigger mandatory secondary interlocks before sending control signals to physical machinery.

---

## 🏗️ Architecture & Component Overview

```text
AMAP/
├── backend/                  # FastAPI 0.115+ & Python 3.11+ Core Services
│   ├── app/                  # Application factory, CORS, and dependency injection
│   ├── middleware/           # Rate limiting, security headers, exception handling, audit logging
│   ├── models/               # Strict Pydantic v2 domain schemas (extra='forbid')
│   ├── repositories/         # 23 Parameterized Database Repositories (SQL injection immune)
│   ├── routes/               # Modular REST endpoints (/auth, /sessions, /tasks, /multimodal, etc.)
│   ├── services/             # Pure domain business logic & multi-signal adaptation engines
│   ├── utils/                # PBKDF2 cryptography, Supabase RLS context, tenant scoping
│   └── tests/                # 379 Comprehensive automated unit, integration, and security tests
├── frontend/                 # Next.js 14+ / React 18+ Accessible Workstation Studio
│   ├── app/                  # App Router (/worker, /organization, /admin, /)
│   ├── worker/               # Multimodal HUD, Workflow Viewer, Accessible Modals, Dwell Timers
│   ├── organization/         # Live Session Telemetry, Assistance Ticket Resolution Queue
│   ├── admin/                # Preset Config Studio, Adaptation Review, Immutable Audit Log
│   └── shared/               # Vanilla CSS Design System Tokens (WCAG 2.1 AA, >=48px touch targets)
├── database/                 # PostgreSQL & Supabase Multi-Tenant Migrations
│   └── migrations/           # 24 Structured SQL DDL migrations with Row-Level Security (RLS)
└── docs/                     # Technical specifications, architecture designs, and API contracts
```

---

## 🚀 Key Features

### 1. Multimodal Interaction Engine
- **Optical Gesture Tracking:** Palm, Pinch, Thumbs Up, Point, Open Hand, and Fist recognition with temporal dwell smoothing (300ms–1500ms) to filter micro-tremors and involuntary spasms.
- **Acoustic Voice Pipeline:** Phonetic/fuzzy matching against bounded vocabulary ("next step", "confirm", "pause", "emergency stop") with ambient noise thresholding.
- **Cross-Modal Fusion:** Reinforcing confidence booster ($c_f = 1 - (1 - c_1)(1 - c_2)$) and safety confirmation gating on conflicting inputs.

### 2. Evidence-Based Adaptation & Personalization
- **Rule of Evidence:** Never alters interaction parameters on single random outliers.
- **Pattern Evaluation:** Aggregates repeated difficulty signals (e.g. 4 low-confidence gesture events or dwell timeouts) to generate structured adaptation recommendations (e.g., increasing dwell time from 450ms to 600ms or enlarging touch targets).

### 3. Multi-Role Portals
- **Worker Workstation (`/worker`):** High-contrast HUD, step-by-step spatial target overlays, circular dwell timers, non-intrusive supervisor assistance calling, and physical emergency lockout.
- **Supervisor Station (`/organization`):** Real-time line telemetry, worker status monitoring, and instant assistance ticket escalation/resolution queue.
- **Admin Studio (`/admin`):** Factory floor preset tuning, adaptation review/approval panel, and tamper-proof audit trail exploration.

### 4. Enterprise Security & Multi-Tenancy (20/20 Audit Passed)
- **PBKDF2 Hashing:** $\ge 600,000$ iterations with unique CSPRNG 32-byte salts.
- **Constant-Time Comparison:** All hashes, tokens, and signatures verified via `hmac.compare_digest`.
- **Row-Level Security (RLS):** Database-level tenant boundary isolation using PostgreSQL session contexts (`app.current_organization_id`).
- **Defensive Headers:** Strict CSP, nosniff, DENY framing, and Referrer policies.
- **Sliding-Window Rate Limiting:** Brute-force protection on authentication routes.

---

## 🛠️ Quickstart & Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or Supabase local/cloud instance)

### 1. Backend Setup
```bash
cd backend
python -m venv .venv

# Windows Powershell
.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python -m compileall app repositories routes middleware utils models services tests
pytest -q
```
*Expected output: `379 passed in ~70s`.*

Start FastAPI dev server:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive API docs available at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` to launch the AMAP Multimodal Suite.

---

## ♿ Accessibility Compliance (WCAG 2.1 AA)

| Standard | AMAP Implementation | Verified By |
|---|---|---|
| **Touch Target Size** (2.5.5 / 2.5.8) | `min-height: 48px`, `min-width: 48px` on all interactive elements | `test_wcag_css_design_system_tokens_and_accessibility` |
| **Focus Visible** (2.4.7) | High-visibility `:focus-visible` outline rings with 3px offset | `test_wcag_css_design_system_tokens_and_accessibility` |
| **Contrast Ratios** (1.4.3 / 1.4.6) | High-contrast mode switch providing pure `#000000` background and `#ffffff` text | `test_wcag_css_design_system_tokens_and_accessibility` |
| **Screen Reader Feedback** (4.1.3) | `aria-live="polite"` on HUD updates; `role="alert"` on Emergency Stop | `test_wcag_screen_reader_live_regions_in_worker_station` |
| **Non-Color Reliance** (1.4.1) | Dual-channel state representation (Icon + Text + Badge) | `test_wcag_non_reliance_on_color_alone` |
| **Dialog Semantics** (2.1) | Accessible modals with `role="dialog"`, `aria-modal="true"`, and `aria-labelledby` | `test_wcag_accessible_modal_dialog_semantics` |

---

## 🔒 Security Audit Compliance Matrix (All 20 Criteria)

All 20 mission-critical security criteria are covered with automated tests in `backend/tests/test_security_audit_all_20.py`:
- [x] **01. PBKDF2 Iterations & Salts:** 600k iterations, 32-byte CSPRNG salt
- [x] **02. Constant-Time Verification:** `compare_digest` prevents timing side-channels
- [x] **03. JWT Signature Integrity:** HS256 algorithm enforcement, reject forged tokens
- [x] **04. Expiration Lifecycle:** Strict token expiry checks returning 401 Unauthorized
- [x] **05. Production Secrets Guard:** Block dev secrets when `ENVIRONMENT=production`
- [x] **06. SQL Injection Immunity:** 100% parameterized queries across all 23 repositories
- [x] **07. Organization Multi-Tenant Isolation:** Zero cross-tenant data leakage
- [x] **08. Worker Self-Data Scoping:** Worker cannot access peer personalization profiles
- [x] **09. RBAC Permission Gating:** Granular route dependencies on all admin endpoints
- [x] **10. Invariant Separation:** Recognition != Intent != Authorization != Execution
- [x] **11. Safety Interlocks:** Mandatory confirmation dialogues on critical commands
- [x] **12. CORS Origin Whitelisting:** Strict origin validation in production
- [x] **13. Defensive Security Headers:** CSP, X-Frame-Options, nosniff, Referrer-Policy
- [x] **14. Pydantic Sanitization:** `extra = 'forbid'` prevents payload property injection
- [x] **15. Credential Masking:** Passwords and tokens excluded from application logs
- [x] **16. Rate Limiting:** Sliding-window throttle on `/auth/login` returning 429
- [x] **17. Immutable Audit Logs:** DELETE and UPDATE operations strictly prohibited
- [x] **18. Centralized Exception Shielding:** Internal tracebacks hidden in production
- [x] **19. Supabase Row-Level Security:** Database-level policy enforcement
- [x] **20. Temporal Dwell Safety:** Tremor smoothing and continuous hold thresholds

---

## 📄 License
This project is licensed under the MIT License.
