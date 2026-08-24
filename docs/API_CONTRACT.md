# AMAP REST API Specification (OpenAPI Contract)

Base URL: `/api/v1`

---

## 1. Authentication & Tenant Authorization (`/auth`)

### `POST /auth/login`
- **Description:** Authenticate user via email and PBKDF2 password verification.
- **Rate Limit:** 10 requests / 60 seconds (Sliding Window).
- **Request Body:**
  ```json
  {
    "email": "alex.worker@amap.com",
    "password": "SecurePassword123!"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "c1f729b8-...",
      "email": "alex.worker@amap.com",
      "full_name": "Alex Morgan",
      "organization_id": "9a61e05d-...",
      "roles": ["worker"],
      "permissions": ["session:read", "session:write", "multimodal:input"]
    }
  }
  ```

---

## 2. Work Session Management (`/sessions`)

- `POST /sessions/start`: Start active assembly work session.
- `GET /sessions/active`: Retrieve worker's currently active or paused session.
- `POST /sessions/{session_id}/pause`: Pause active session.
- `POST /sessions/{session_id}/resume`: Resume paused session.
- `POST /sessions/{session_id}/end`: Conclude session.

---

## 3. Multimodal Interaction Processing (`/multimodal`)

### `POST /multimodal/fuse`
- **Description:** Multi-signal temporal fusion of optical gesture and speech inputs.
- **Request Body:**
  ```json
  {
    "inputs": [
      {
        "mode": "gesture",
        "raw_intent": "thumbs_up",
        "confidence": 0.92,
        "timestamp_ms": 1000
      },
      {
        "mode": "voice",
        "raw_intent": "confirm_action",
        "confidence": 0.94,
        "timestamp_ms": 1050
      }
    ],
    "temporal_window_ms": 1500
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "fused_action": "confirm_action",
    "fused_confidence": 0.995,
    "fusion_strategy": "reinforcing",
    "requires_confirmation": false,
    "validation_status": "valid"
  }
  ```

---

## 4. Personalization & Adaptation Engine (`/workers`)

- `GET /workers/{worker_profile_id}/personalization`: Worker's active personalization configuration.
- `PUT /workers/{worker_profile_id}/personalization`: Update personalization settings.
- `POST /workers/{worker_profile_id}/adaptations/evaluate`: Evaluate multi-signal interaction history for adaptation recommendations.
- `POST /workers/{worker_profile_id}/adaptations/apply`: Apply approved adaptation recommendation.

---

## 5. Supervisor Assistance Queue (`/assistance`)

- `POST /assistance/request`: Worker dispatches help call to supervisor station.
- `GET /assistance/active`: Supervisor queries live open assistance tickets.
- `POST /assistance/{request_id}/assign`: Supervisor claims ticket.
- `POST /assistance/{request_id}/resolve`: Supervisor completes and closes ticket.

---

## 6. Administration & Governance (`/admin`)

- `GET /admin/configs`: List organization interaction presets.
- `POST /admin/configs`: Create new interaction preset.
- `PUT /admin/configs/{config_id}`: Update interaction preset.
- `GET /admin/audit-logs`: Query immutable tenant audit trail logs.
