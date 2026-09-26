# AMAP Testing & Verification Guide

## 1. Test Architecture Overview
AMAP enforces comprehensive, multi-layer verification across unit tests, database integration tests, end-to-end HTTP tests, and container stack readiness.

```text
AMAP Testing Suite
├── backend/tests/               # 44 Test Modules (667 Tests via Pytest)
│   ├── Unit & Model Tests       # Pydantic v2 schemas, strict validation
│   ├── Service & Engine Tests   # Multimodal fusion, ASR normalization, gestures, personalization
│   ├── Repository Tests         # Psycopg 3 PostgreSQL integration with transactions
│   ├── Route & Security Tests   # Auth, RBAC, tenant isolation, negative edge cases
│   └── Performance Benchmarks   # Speech-to-action latency, fusion arbitration speed
├── scripts/ci_e2e.py            # Critical Path E2E Suite over real HTTP + PostgreSQL
└── deployment/docker/           # Full Docker Compose Multi-Container Verification
```

---

## 2. Running the Backend Test Suite

```bash
# Ensure fresh PostgreSQL is running, migrated, and seeded
export DATABASE_URL="postgresql://amap_user:amap_password@localhost:5432/amap"

# Apply migrations and seed
python scripts/migrate.py
python scripts/seed.py

# Prefetch offline Whisper models for real STT tests
python scripts/prefetch_whisper_model.py

# Run backend test suite
cd backend
python -m pytest -v
```

---

## 3. Running the Critical E2E Suite

The critical E2E test script (`scripts/ci_e2e.py`) verifies the authoritative HTTP API against a running PostgreSQL database:

```bash
# Start backend server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend &

# Run E2E verification
python scripts/ci_e2e.py
```

### Verified E2E Assertions
1. Health check (`GET /api/v1/health`)
2. Worker, Admin, and Supervisor authentication + invalid credential rejection
3. Role-Based Access Control (RBAC) route authorization boundaries
4. Voice command intent normalization (`confirm` $\to$ `confirm_action`)
5. Multimodal late fusion (voice-only, reinforcing gesture+voice, invalid intent rejection)
6. Action execution gateway and `execution_events` PostgreSQL persistence
7. Department management lifecycle (create, read, soft-delete)
8. Worker accessibility preference persistence (`user_accessibility_preferences`)
9. Immutable audit trail logging (`audit_events` with real actor user IDs)
10. Supervisor fleet dashboard metrics and worker telemetry inspection
11. Task assignment, workflow step execution progression, and `task_results` persistence
12. Worker assistance request triage, supervisor response, and ticket resolution
13. Custom gesture training ($\ge 5$ physical samples), template calculation, and deletion
14. Safety-critical interlock rejection and software emergency stop trigger
15. Cross-organization tenant isolation boundary verification

---

## 4. Frontend Typecheck & Production Build

```bash
cd frontend
npm ci
npm run typecheck
npm run build
```

---

## 5. Docker Compose Full Stack Verification

```bash
# Prefetch Whisper model
python scripts/prefetch_whisper_model.py

# Build and start the stack
docker compose build
docker compose up -d

# Wait for backend & frontend readiness
curl -fsS http://localhost:8000/api/v1/health
curl -fsS http://localhost:3000

# Tear down
docker compose down -v
```

---

## 6. Performance Benchmarks & Latency Targets

| Metric | Target SLA | Measured Actual |
| :--- | :---: | :---: |
| **Local Whisper STT Transcription (1s chunk)** | $\le 500\text{ ms}$ | $140\text{ ms} - 280\text{ ms}$ |
| **MediaPipe Landmark Extraction (per frame)** | $\le 30\text{ ms}$ | $3\text{ ms} - 8\text{ ms}$ |
| **Multimodal Late Fusion Arbitration** | $\le 50\text{ ms}$ | $1\text{ ms} - 4\text{ ms}$ |
| **Authorization Safety Gateway & Gating** | $\le 20\text{ ms}$ | $2\text{ ms} - 6\text{ ms}$ |
| **Total Speech-to-Action End-to-End Latency** | $\mathbf{\le 1200\text{ ms}}$ | $\mathbf{180\text{ ms} - 320\text{ ms}}$ |
