# AMAP Architecture Decision Records (ADRs)

## ADR-001: PostgreSQL as Single Source of Truth
- **Context:** The system requires multi-tenant isolation, immutable audit trails, and strict persistence across sessions.
- **Decision:** Use PostgreSQL 16 with numbered migrations (`001..051`) and psycopg 3 parameterized repositories. Prohibit in-memory authoritative state and SQLite fallback persistence.
- **Status:** Accepted & Implemented.

---

## ADR-002: Late Multimodal Fusion Arbitration Engine
- **Context:** Workers interact using voice commands, hand gestures, spatial pointing, or physical buttons simultaneously or sequentially.
- **Decision:** Implement a rule-based late fusion engine evaluating a temporal window ($\Delta t \le 1500\text{ ms}$). Support complementary fusion (spatial pointing + voice command), reinforcing fusion (confidence boosting), and conflict resolution with modality confidence prioritization.
- **Status:** Accepted & Implemented.

---

## ADR-003: Offline-First ML Pipeline for ASR and Vision
- **Context:** Industrial manufacturing shop floors frequently have strict air-gapped network policies or high latency connectivity.
- **Decision:** Package local Faster-Whisper / Whisper-tiny multilingual models for ASR and offline MediaPipe WebAssembly assets (`hand_landmarker.task`) for hand tracking. All model inference runs locally on workstation or server edge without external cloud APIs.
- **Status:** Accepted & Implemented.

---

## ADR-004: Strict Separation of Recognition, Intent, Authorization, and Execution
- **Context:** Multimodal input (e.g. accidental speech or involuntary motor tremor) must never bypass safety checks or directly mutate physical state.
- **Decision:** Enforce four distinct layers:
  1. Optical/Acoustic Recognition
  2. Temporal Dwell & Intent Resolution
  3. RBAC & Tenancy Authorization
  4. Deterministic Action Execution Gateway with Safety Interlocks.
- **Status:** Accepted & Implemented.

---

## ADR-005: Chunked PCM Audio Ingestion Model
- **Context:** Balancing low-latency speech recognition with robust network transport across diverse edge network setups.
- **Decision:** Process audio input as discrete $0.5\text{s} - 2.0\text{s}$ 16kHz mono PCM chunks transmitted over HTTP/WebSocket rather than proprietary continuous duplex audio streams.
- **Status:** Accepted & Implemented.
