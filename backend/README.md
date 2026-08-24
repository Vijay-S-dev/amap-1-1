# AMAP Backend Services

FastAPI 0.115+ core platform powering the Accessible Multimodal Assembly Platform (AMAP).

---

## 🏛️ Architecture

- **`app/`**: FastAPI application initialization, lifecycle hooks, CORS middleware, global dependency injection (`get_current_user`, `require_roles`, `require_permissions`, `validate_organization_access`).
- **`middleware/`**:
  - `security_headers.py`: Injects CSP, X-Frame-Options, XSS protection, Referrer policy.
  - `rate_limiting.py`: Sliding-window in-memory limiter for brute-force prevention.
  - `logging_middleware.py`: Structured JSON request/response telemetry.
  - `error_handling.py`: Exception shield formatting domain exceptions into RFC 7807 problem details.
- **`models/`**: Strict Pydantic v2 domain schemas (`extra = 'forbid'`) enforcing complete schema validation.
- **`repositories/`**: 23 Parameterized Database Repositories executing direct SQL with zero string concatenation.
- **`services/`**: Pure domain logic layer (Multimodal Fusion, Gesture Pipeline, Voice Pipeline, Personalization Engine, Admin Service, Authorization Service).
- **`utils/`**: PBKDF2 cryptography (`security.py`), JWT token issuance, tenant context managers (`tenant_context.py`), Supabase helper (`supabase.py`).
- **`tests/`**: 379 Automated unit, integration, security audit, and accessibility tests.

---

## ⚙️ Configuration & Environment Variables

Create `.env` inside `backend/`:
```ini
ENVIRONMENT=development
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/amap
SECRET_KEY=amap-dev-super-secret-key-change-in-production-min32chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
PBKDF2_ITERATIONS=600000
RATE_LIMIT_LOGIN_MAX_REQUESTS=10
RATE_LIMIT_LOGIN_WINDOW_SECONDS=60
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Optional Supabase Connection
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

---

## 🧪 Testing

Run all 379 tests:
```bash
python -m pytest -q
```

Run targeted suites:
```bash
# All 20 Security Criteria Audit
python -m pytest tests/test_security_audit_all_20.py -v

# Full-Stack End-to-End Lifecycle & WCAG Accessibility
python -m pytest tests/test_e2e_full_lifecycle.py tests/test_accessibility_compliance.py -v

# Multimodal & Adaptation Pipeline
python -m pytest tests/test_multimodal_processing.py tests/test_personalization_pipeline.py -v
```

---

## 🚀 Running Dev Server

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open `http://127.0.0.1:8000/docs` to view the interactive Swagger/OpenAPI documentation.
