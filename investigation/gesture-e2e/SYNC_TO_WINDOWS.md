# Sync a Windows AMAP checkout with the VERIFIED gesture implementation

The verified, end-to-end-tested gesture pipeline lives on
`origin/arena/01a0e82b-amap` (commit `37ea62d` on top of `b94749b`).
The remote branch tip BEFORE `37ea62d` still contained the hand-tracking
blackout bug (inline quality gate that treated tasks-vision's materialized
`visibility: 0` sentinel as a real score and rejected every detected hand).

## What `37ea62d` contains (the exact verified delta)

| File | Change | Class |
|---|---|---|
| `frontend/worker/components/MediaPipeHandTracker.tsx` | visibility-sentinel gate fix via extracted gate; GPU→CPU delegate fallback (init + 20-error recovery); `Promise.race` on `video.play()`; `handedness ?? handednesses` fallback; `videoWidth > 0` guard; explicit CAMERA_ERROR on missing video element; always-visible runtime diagnostics panel above the camera | REQUIRED (implementation) |
| `frontend/worker/lib/handQuality.ts` | NEW file: unit-tested quality gate (`MIN_PALM_SIZE = 0.035`, visibility counts only when `> 0`, average enforced only when all 21 report real scores) | REQUIRED (implementation) |
| `frontend/tests/gesture-engine.test.ts` | +10 quality-gate regression tests (53 total), incl. the exact blackout shape | REQUIRED (regression protection) |

`frontend/worker/lib/handPoses.ts`, `gestureEngine.ts`, `cameraTransform.ts`,
`uiActionExecutor.ts`, `frontend/scripts/run-engine-tests.mjs`,
`frontend/app/worker/page.tsx`, `frontend/worker/components/MultimodalHUD.tsx`
and `frontend/package.json` are byte-identical to `b94749b` — copy them only if
the diff in step A shows differences on your machine.

## Commands (Windows)

```bat
cd C:\Users\srini\AMAP
git fetch origin

REM A. See the EXACT per-file differences between YOUR tree and the verified tree
git diff origin/arena/01a0e82b-amap -- frontend/worker/components/MediaPipeHandTracker.tsx frontend/worker/lib frontend/tests/gesture-engine.test.ts frontend/app/worker/page.tsx frontend/worker/components/MultimodalHUD.tsx frontend/scripts/run-engine-tests.mjs frontend/package.json

REM B. Take the REQUIRED verified files (wholesale — overwrites your local versions)
git checkout origin/arena/01a0e82b-amap -- frontend/worker/components/MediaPipeHandTracker.tsx frontend/worker/lib/handQuality.ts frontend/tests/gesture-engine.test.ts

REM C. IF step A showed diffs in any of these, take them too (dependency set)
git checkout origin/arena/01a0e82b-amap -- frontend/worker/lib/handPoses.ts frontend/worker/lib/gestureEngine.ts frontend/worker/lib/cameraTransform.ts frontend/worker/lib/uiActionExecutor.ts frontend/scripts/run-engine-tests.mjs frontend/package.json frontend/app/worker/page.tsx frontend/worker/components/MultimodalHUD.tsx

REM D. Validate locally
cd frontend
npm run typecheck && npm run lint && npm run test:engine && npm run build
cd ..

REM E. Rebuild the frontend image (the running image predates the fix) and recreate it
docker compose build --no-cache frontend
docker compose up -d frontend
```

## Post-deploy acceptance check (physical webcam)

1. Hard-refresh the browser (Ctrl+Shift+R), open `/worker`, switch to Gesture mode.
2. The yellow/black **AMAP RUNTIME DIAGNOSTICS** panel must be visible directly
   above the camera. **If it is not visible, the browser is running a stale
   bundle — do not debug gestures, fix the deployment first.**
3. With your hand in frame, the panel must show, in order:
   `raw hands count >= 1` → `first raw hand LMs 21` → `palm >= 0.035` →
   `accepted hands count >= 1` → `hand count 1` → a classified gesture while
   posing → dwell progress → execution.
   (`vis 0/21 reported avg n/a` is the EXPECTED healthy value — the hand model
   does not emit visibility scores.)
