# AMAP — Real-Time Gesture / Voice / Multimodal Task Execution: Final Report

**Branch:** `arena/01a0e82b-amap` · **Commit:** `c818836` · **Working tree:** clean (all work committed & pushed)

---

## 1. What was delivered

Workers now execute **real** assembly tasks hands-free through the full pipeline:

```
Camera → MediaPipe landmarks → pose classification → personalized gesture→action map
  → real-time interaction engine (state machine) → unified action resolver
  → real UI actions (pointer/click/drag/scroll) + real AMAP task actions
    (start/next/complete/finish steps, assistance, pause/resume, e-stop)
  → /actions/execute safety gateway → PostgreSQL persistence (execution events,
    step executions, task results, sessions, assistance)
  → supervisor real-time dashboard driven only by real rows (heartbeat liveness,
    last action, progress, mode, assistance/emergency state)
```

Voice (faster-whisper transcripts) enters the **same** action resolver via
`/voice/process-command`; gesture+voice combinations fuse through
`/multimodal/fuse`. **No demo/fake data, no localStorage-authoritative state,
no second backend, no Vosk — the existing stack was extended, not replaced.**

---

## 2. Root causes found & fixed

| # | Bug / gap | Root cause | Fix |
|---|-----------|-----------|-----|
| 1 | **Fresher login not working** | Seed inserted `maria.newhire@amap.com` with an unverified hash and the interaction-config presets **after** personalizations (FK/ordering); gesture seeding in migration 052 ran before presets existed on a fresh DB | Re-verified PBKDF2 hash for `SecurePassword123!`; seed reordered (presets → personalizations); gesture seeding made idempotent in seed.sql (`ON CONFLICT DO NOTHING`); E2E + tests prove fresher login + 401 on wrong password |
| 2 | **Supervisor real-time worker view wrong** | (a) `is_online` was inferred from mere existence of a session row — stale sessions showed "WORKING"; (b) paused sessions were invisible (only `status='active'` fetched), so a paused worker showed COMPLETED/AVAILABLE; (c) `active_workers_count` counted rows, not live workers; (d) last-activity came from immutable user rows | Heartbeat-based liveness (`last_heartbeat_at` within 120 s, or `started_at` grace for just-started sessions); paused sessions surfaced as the live session → `PAUSED` status; count = online workers; last activity/action derived from real execution/interaction events. Org/tenant filters untouched (authz preserved) |
| 3 | Multimodal service had DB access + "cursor" naming | Test suite (correctly) enforces the fusion service stays pure | Service re-pured; route layer resolves the worker's effective mapping and injects it; action renamed `pointer_move` |
| 4 | `double_click` never fired | `registerDiscreteClick` resolved the timing-derived action through the gesture map — pinch→left_click remap swallowed it | `double_click` bypasses gesture-map resolution (engine fix, unit-tested) |
| 5 | Swipes fired once, then never again | `swipeArmed` re-armed only when the hand left the frame | Re-arm after the 600 ms cooldown elapses (engine fix, unit-tested) |
| 6 | Engine↔backend calibration mismatch | Panel used `pointer_sensitivity` key; backend canonical is `cursor_sensitivity` | `engineCalibrationFromBackend/ToBackend` adapters (round-trip tested); panel slider key fixed |
| 7 | Onboarding calibration page double-firing poses | Tracker delegated to the shared classifier but engine-managed poses were still dwell-confirmed | `dwellGestures` prop added; page opts into dwell only for THUMBS_UP/POINTING/OPEN_PALM |
| 8 | `AssistanceModal` used a placeholder `ws-001` session | Missing real session wiring | Modal only renders with a real PostgreSQL session; otherwise an explanatory notice is shown |
| 9 | E2E fixture cleanup silently failing | psycopg treats literal `%` in `LIKE` of parameterized SQL as a placeholder | Cleanup deletes by collected IDs |

---

## 3. Architecture & key files

### Database (migration `052_worker_realtime_interaction.sql`, applied + seeded)
- `work_sessions.last_heartbeat_at` (liveness), `organization_id`
- `actions.category` += `ui_interaction`; **17 actions**: `pointer_move`, `left_click`, `right_click`, `double_click`, `drag_start`, `drag_end`, `scroll`, `scroll_up`, `scroll_down`, `select_item`, `start_assignment`, `complete_step`, `finish_assignment`, `cancel_action`, + existing lifecycle actions
- 12 `gesture_configurations` per preset (org preset 0001 Alex / 0002 Jordan+Maria), backfilled via `worker_profiles→users` org join

### Backend
| File | Role |
|---|---|
| `services/worker_interaction_service.py` | Effective mapping (personalization > preset > canonical), calibration merge, action validation (30 s cache) |
| `services/multimodal_service.py` | Pure fusion: complementary binding (pinch+"move this"→`drag_start` at pointer; pointing+"select"→`select_item`), direction refinement (two_finger_move + "scroll down"→`scroll_down`), low-confidence rejection, ambiguity safety, fist→`emergency_stop` priority, spatial context propagation |
| `routes/multimodal.py` | Resolves worker's effective map, injects into `fuse_inputs` |
| `services/task_service.py` + `routes/tasks.py` | `get_step_executions` (ownership-enforced) + `GET /tasks/workflows/assignments/{id}/executions` — refresh/re-login progress restore |
| `services/supervisor_service.py` | Heartbeat liveness, paused-session status, real last-activity/last-action telemetry, online-based active count |
| `routes/sessions.py`, `repositories/work_sessions.py` | Heartbeat endpoint + `touch_heartbeat` |
| `services/voice_service.py` | Command vocabulary extended (scroll/click/drag/select/task lifecycle) |

### Frontend
| File | Role |
|---|---|
| `worker/lib/handPoses.ts` | Shared 21-landmark classifier (single source of truth for tracker + engine; backend-compatible) |
| `worker/lib/gestureEngine.ts` | Real-time state machine IDLE/HOVER/ARMED/TRIGGERED/HELD/DRAGGING/RELEASED/PAUSED/EMERGENCY_STOPPED; EMA-smoothed mirrored pointer (sensitivity, jitter deadband), pinch tap/double-click/debounce/select/drag, two-finger scroll + right-click, swipe flicks w/ cooldown, FIST e-stop bypass, pause gating, voice-armed drag, calibration adapters |
| `worker/lib/uiActionExecutor.ts` | Real DOM execution: `elementFromPoint` click/select, scrollable-ancestor scroll, drag ghost + `amapdrop`/`amapdrophover`/`amapdragstart` events |
| `worker/components/VirtualCursor.tsx` | State-aware virtual pointer (color/label per state, e-stop emphasis) |
| `worker/components/GestureContextMenu.tsx` | Real right-click menu at the pointer; actions dispatch the unified resolver |
| `worker/components/GestureControlPanel.tsx` | Per-gesture enable + action remap + calibration sliders; saves via `PUT /personalization/me/gesture-mapping` (PostgreSQL) with source badges |
| `worker/components/AssemblyDragBench.tsx` | Real drag & drop bench (`data-amap-draggable` / drop zones) consuming executor events |
| `worker/components/MultimodalHUD.tsx` | Every tracker frame → engine (unthrottled) **and** server pipeline (~8 fps); voice fusion prefers the freshest engine gesture with spatial binding (`spatial_x/y`, source `gesture-engine`) |
| `app/worker/page.tsx` | **Full rewrite**: session lifecycle + 30 s heartbeat, progress restore, unified action resolver (UI actions audited; task actions via `/actions/execute` gateway + `recordStepExecution` with per-step dedupe), confirmation staging (confirm/cancel + Escape), pause (UI-only actions stay live) / e-stop lockout with failure banner, batched scroll audit (2.5 s), context menu, drag bench, end-of-work summary |
| `organization/components/LiveWorkerMonitor.tsx` | 🟢/⚪ online indicator, last activity ("42s ago"), last action, mode/session grid |
| `shared/api/client.ts` | +8 methods: session lifecycle, gesture mapping get/update, step executions |

---

## 4. Gesture → action mapping (PostgreSQL-authoritative, worker-personalizable)

Canonical defaults (preset-seeded; overrides via personalization; precedence
`worker_personalizations.gesture_action_map` > `gesture_configurations` preset > canonical):

| Gesture | Action | Class |
|---|---|---|
| pointing (continuous) | `pointer_move` (engine continuous; audited) | UI |
| pinch (quick tap) | `left_click` | UI |
| pinch ×2 quick | `double_click` (timing-derived, not remappable) | UI |
| pinch_hold (≥650 ms) | `select_item` | UI |
| pinch + move | `drag_start` → `drag` moves → `drag_end` | UI |
| two_finger (release still) | `right_click` | UI |
| two_finger_move | `scroll` (direction from motion / voice refinement) | UI |
| swipe_up / swipe_down | `scroll_up` / `scroll_down` | UI |
| swipe_right / swipe_left | `next_step` / `previous_step` | Task |
| thumbs_up / thumbs_down | `confirm_action` / `cancel_action` | Task |
| open_palm | `pause_session` | Task |
| fist | `emergency_stop` (immediate, bypasses pause & debounce, backend-confirmed lockout) | Safety |

Calibration (persisted per worker): dwell, click debounce, double-click window,
pinch click/select/drag thresholds, pointer (`cursor_sensitivity`) & scroll
sensitivity, scroll throttle, smoothing alpha, jitter threshold, handedness,
per-gesture enable flags.

Voice examples entering the same resolver: "next step", "previous step",
"complete step", "confirm", "cancel", "pause", "resume", "scroll up/down",
"left/right/double click", "move this" (drag arm), "drop", "select",
"request assistance", "start task", "finish task", "emergency stop".

---

## 5. Test results (all real PostgreSQL)

| Suite | Command | Result |
|---|---|---|
| Backend (full) | `pytest tests -q` | **734 passed, 3 skipped** (was 664 before this wave; +70 new in `test_realtime_interaction_engine.py`) |
| Frontend types | `npx tsc --noEmit` | **clean** |
| Frontend engine unit tests | `npm run test:engine` | **34 passed, 0 failed** |
| Frontend build | `npm run build` | **clean** (16 routes) |
| E2E acceptance | `python ../scripts/e2e_worker_journey.py` | **37/37 checks passed** (run twice — idempotent) |

New backend coverage: fresher/role logins + 401s; all 17 actions registered &
executable with persisted events; 21-voice-command vocabulary + unmatched
feedback; geometric classification (pinch/two_finger/pointing) + dwell
single-fire; multimodal combinations (drag binding, select binding, direction
refinement, e-stop priority, low-confidence rejection, ambiguity safety);
personalization override changes fusion **and** direct gesture resolution and
survives a fresh service instance (restart); invalid action → 422; heartbeat
online/offline/foreign-session safety; pause/resume reflected in supervisor;
assignment start→steps→complete→result persistence; progress restore + worker
ownership (403 cross-worker); step-order enforcement (409).

Engine unit coverage: all 8 poses; pointer mirror/sensitivity/smoothing/jitter
deadband; click/double-click/debounce/select-once/drag lifecycle incl. hand-lost
safety; two-finger scroll + throttle + right-click; swipe direction + cooldown;
FIST e-stop + lockout; pause semantics (pointer live, actions suppressed);
personalized remap; disabled gesture; handedness preference; voice-armed drag;
calibration round-trip.

---

## 6. E2E acceptance scenario (§ 14) — `scripts/e2e_worker_journey.py`

Automated at the API level against real PostgreSQL — the exact endpoint
sequence the rewritten worker page drives:

1. Fresher login (maria.newhire@amap.com) ✅ + wrong-password 401 ✅
2. Session start + heartbeat → supervisor sees **Maria ONLINE** w/ live session ✅
3. Gesture mapping from PostgreSQL (pinch→left_click, calibration) ✅
4. Real assignment start (workflow from DB) ✅
5. Pinch landmarks → server classification → dwell trigger (once) → `left_click` ✅
6. Click executed via `/actions/execute`; supervisor sees **last action = left_click** ✅
7. Voice "scroll down" → `scroll_down` → executed + persisted ✅
8. Multimodal pinch(spatial 640,360) + "move this" → `drag_start` bound to pointer; `drag_end` persisted ✅
9. Step 1 completed → persisted ✅
10. **Re-login (refresh) → progress restore shows step 1 completed; supervisor sees 50%, step 2 current** ✅
11. Pause → supervisor **PAUSED**; resume → **WORKING** ✅
12. Assistance request → supervisor **ASSISTANCE_REQUESTED** → acknowledge → resolve ✅
13. Emergency stop → immutable event + urgent assistance → supervisor sees emergency state ✅
14. Step 2 + finish assignment → task result **2/2 steps** persisted ✅
15. End session → supervisor sees **OFFLINE** ✅

What the API-level E2E cannot cover (browser-only): actual webcam/MediaPipe
frame capture and faster-whisper microphone capture. Those reuse the untouched,
previously-working tracker/STT stack, verified by: engine unit tests on the same
classifier the tracker delegates to, typecheck, production build, and the
MediaPipe assets remaining in place (`frontend/public/mediapipe/wasm/*`,
`hand_landmarker.task`).

---

## 7. Authorization & tenancy (verified, not weakened)

- Worker A cannot execute Worker B's assignment / read B's executions (403, tested)
- Foreign-session heartbeat is a no-op returning `None` (tested)
- Supervisor views are org-filtered as before; the fix added **real telemetry**, not removed filters
- All task actions pass the `/actions/execute` safety gateway (Recognition ≠ Intent ≠ Authorization ≠ Execution)
- Emergency stop writes an immutable event + urgent assistance request (supervisor-visible)

---

## 8. Limitations

1. **Camera/microphone capture** requires a real browser with devices; the in-sandbox E2E verifies everything from landmarks/transcripts onward.
2. Emergency stop is a **software** safety boundary (documented in the route) — no physical machinery control is claimed.
3. `pointer_move`/scroll are audited in aggregated batches (2.5 s) to avoid event floods — per-pixel audit is intentionally not kept.
4. The supervisor dashboard updates on its existing polling cadence (no websockets in the repo); "without full reload" is satisfied by polling real endpoints.
5. Engine unit tests run via a tsc-compiled Node runner (`npm run test:engine`) — the repo has no JS test framework, and none was added to avoid dependency changes.

---

## 9. Reproduction

```bash
# backend tests (PostgreSQL must be up)
cd backend && DATABASE_URL="postgresql://amap_user:change_me@127.0.0.1:5432/amap" \
  /tmp/amapvenv/bin/python -m pytest tests -q          # 734 passed, 3 skipped

# E2E acceptance journey
cd backend && DATABASE_URL=... /tmp/amapvenv/bin/python ../scripts/e2e_worker_journey.py   # 37/37

# frontend
cd frontend && npx tsc --noEmit                        # clean
cd frontend && npm run test:engine                     # 34 passed
cd frontend && npm run build                           # clean
```

Seeded logins (org `9a61e05d-7a32-4112-9c17-1833d7b42f65`, password
`SecurePassword123!`): `admin@amap.com`, `supervisor@amap.com`,
`alex.worker@amap.com`, `jordan.worker@amap.com`,
`maria.newhire@amap.com` (fresher).
