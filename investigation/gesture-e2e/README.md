# Headless Real-Browser Camera Verification (synthetic webcam)

Reproduces the ENTIRE production gesture pipeline without a physical camera:
real Chromium + real @mediapipe/tasks-vision WASM + the real /worker page, with
`--use-file-for-fake-video-capture` feeding a Y4M video built from a real hand
photo as the "webcam".

## Verified with this harness (2026-09-29, extended-diagnostics build)
Panel = `[data-testid="amap-runtime-diagnostics"]` (rendered above the camera).
- open_palm feed, GPU path -> panel: `raw hands count 1 • first raw hand LMs 21
  • palm 0.187 (floor 0.035) • vis 0/21 reported avg n/a • accepted hands
  count 1 • last gesture OPEN_PALM (89%) • pipeline WAIT_FOR_RELEASE, hand
  count 1` + "Hands Tracked: 1 Active (21 LMs/hand)" + confirmation dialog
  ("Command 'OPEN_PALM' requires confirmation") — full chain executed.
- open_palm feed, `--disable-gpu` (CPU fallback path) -> identical values,
  OPEN_PALM executed.
- thumbs_up stock photo -> hand tracked + accepted (palm 0.142), pose "none"
  (photo pose not recognized by the geometric classifier — demonstrates the
  panel distinguishes DETECTION from CLASSIFICATION).
- `vis 0/21 reported` on every successful detection is the live proof of the
  original blackout root cause: tasks-vision materializes `visibility: 0`
  (sentinel for "not reported") for hand landmarks — the old gate averaged
  those zeros and rejected every hand.

## Rebuilding the environment in a fresh sandbox (network-restricted)
1. Rig: `mkdir -p /tmp/browser && cd /tmp/browser && npm i puppeteer-core@22
   @sparticuz/chromium`; `require('@sparticuz/chromium').default.executablePath()`
   -> /tmp/chromium. The harness resolves puppeteer-core from `/tmp/browser`
   (override with `RIG_DIR` env).
2. NSS/NSPR (not bundled, apt blocked): build from source —
   `git clone --depth 1 https://github.com/mozilla/nspr /tmp/nspr`,
   `git clone --depth 1 https://github.com/nss-dev/nss /tmp/nssbuild`,
   `git clone --depth 1 https://github.com/nodejs/gyp-next /tmp/gyp-next`,
   `pip3 install ninja pillow`, then
   `cd /tmp/nssbuild && GYP=/tmp/gyp-next/gyp_main.py ./build.sh --opt
   -Ddisable_tests=1 -Ddisable_tools=1` (signtool fails on missing zlib.h —
   harmless; libs complete in **/tmp/dist/Release/lib**). Export
   `LD_LIBRARY_PATH=/tmp/dist/Release/lib:/tmp`.
3. Feeds: `python3 make_feeds.py <photo.jpg> <out.y4m> [pct_width]` (any clear
   front-view hand photo works; the original feed sources live in the
   workspace-only `AMAP/image-search/` directory; 640x480 C420jpeg, 150 frames).
4. Stack: `scripts/sandbox_stack_up.sh`, then backend (:8000) and frontend
   (`NEXT_PUBLIC_API_BASE_URL=/api/v1 npm run dev`, :3000).
5. Run: `cd investigation/gesture-e2e && LD_LIBRARY_PATH=/tmp/dist/Release/lib:/tmp
   node headless_camera_test.mjs /tmp/feeds/open_palm.y4m run 35000`
   (DISABLE_GPU=1 env adds --disable-gpu for the CPU-fallback path).
