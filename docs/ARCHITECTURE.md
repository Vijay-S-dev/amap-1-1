# AMAP System Architecture Document

## 1. High-Level Architectural Invariant

$$\mathbf{Recognition \neq Intent \neq Authorization \neq Execution}$$

```text
┌────────────────┐     ┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│  RECOGNITION   │     │     INTENT     │     │ AUTHORIZATION  │     │   EXECUTION    │
│  (Perception)  │ ──> │ (Confirmation) │ ──> │  (Governance)  │ ──> │ (Safety Gated) │
│ Optical Hands  │     │ Dwell Smoothing│     │ JWT Claims     │     │ Physical Acts  │
│ Speech Tokens  │     │ Cross-Modal    │     │ RBAC / Tenant  │     │ Machine Stops  │
└────────────────┘     └────────────────┘     └────────────────┘     └────────────────┘
```

---

## 2. Multimodal Fusion Engine

The Multimodal Service combines multiple input streams within an adjustable temporal fusion window ($\Delta t \in [500\text{ms}, 2500\text{ms}]$):

1. **Reinforcing Strategy:** When gesture and speech agree on the candidate action, the combined confidence score is calculated:
   $$c_{\text{fused}} = 1 - (1 - c_{\text{gesture}}) \times (1 - c_{\text{voice}})$$
   If $c_{\text{fused}} \ge 0.85$, the action proceeds without secondary confirmation unless classified as safety-critical.

2. **Conflicting Strategy:** When inputs disagree, the system arbitrates based on modality confidence differential or forces a disambiguation dialogue.

3. **Critical Action Interlock:** Actions designated as `safety_critical` (such as Emergency Stop, Station Shutdown, or Voltage Adjustment) unconditionally mandate secondary explicit confirmation regardless of raw recognition confidence.

---

## 3. Evidence-Based Adaptation Engine

AMAP adheres to the **Principle of Multi-Signal Evidence**:
- Single interaction failures (e.g. one missed gesture or speech misrecognition) are treated as transient noise.
- When a worker encounters repeated difficulties ($\ge 3$ occurrences within a sliding window of 20 interactions), the adaptation engine formulates structured recommendations:
  - **Tremor / Spasm Pattern:** Increase dwell time ($450\text{ms} \to 600\text{ms} \to 750\text{ms}$) and enlarge clickable bounding targets.
  - **Acoustic Noise Pattern:** Enable speech noise cancellation filter or suggest gesture fallback mode.
- Adaptations are either automatically applied (for low-risk ergonomics) or queued for supervisor/admin review.

---

## 4. Multi-Tenant Database & Row-Level Security (RLS)

Each tenant organization is completely isolated:
- PostgreSQL session context `app.current_organization_id` is set at the start of each transaction.
- Row-Level Security policies filter every table (`organizations`, `users`, `worker_profiles`, `work_sessions`, `tasks`, `workflow_steps`, `audit_events`) so that cross-tenant queries return zero records or raise `403 Forbidden`.
- Immutable Audit Event logs enforce `REVOKE UPDATE, DELETE ON audit_events FROM ALL`.
