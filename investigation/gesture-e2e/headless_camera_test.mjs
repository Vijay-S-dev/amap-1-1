// AMAP gesture pipeline headless-browser verification harness.
// Runs the REAL frontend with a REAL Chromium and a fake webcam fed by a
// Y4M video of a hand photo. Captures console output + UI state.
// Usage: node headless_camera_test.mjs <feed.y4m> <outPrefix> [waitMs]
//   (puppeteer-core is installed in the rig dir — RIG_DIR env, default
//    /tmp/browser; Chromium at /tmp/chromium; see README.md)
import { createRequire } from 'module';
const rigRequire = createRequire((process.env.RIG_DIR || '/tmp/browser') + '/');
const puppeteer = rigRequire('puppeteer-core');

const FEED = process.argv[2];
const PREFIX = process.argv[3] || 'run';
const WAIT = parseInt(process.argv[4] || '25000', 10);
const BASE = 'http://127.0.0.1:3000';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/tmp/chromium',
    args: [
      '--no-sandbox', '--disable-dev-shm-usage', '--headless=new',
      '--use-fake-device-for-media-stream',
      '--use-fake-ui-for-media-stream',
      `--use-file-for-fake-video-capture=${FEED}`,
      '--autoplay-policy=no-user-gesture-required',
      '--window-size=1600,1200',
      ...(process.env.DISABLE_GPU ? ['--disable-gpu'] : []),
    ],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1200 });
  const logs = [];
  page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', (e) => logs.push(`[PAGEERROR] ${e.message}`));

  // 1. Login via API to mint a token, then set the auth cookie directly.
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle2', timeout: 120000 });
  const loginRes = await page.evaluate(async (url) => {
    const r = await fetch(`${url}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        organization_id: '9a61e05d-7a32-4112-9c17-1833d7b42f65',
        email: 'alex.worker@amap.com',
        password: 'SecurePassword123!',
      }),
    });
    return await r.json();
  }, BASE);
  if (!loginRes.access_token) { console.error('LOGIN FAILED', loginRes); process.exit(1); }
  // The API client reads localStorage on construction; seed it BEFORE /worker loads.
  await page.evaluateOnNewDocument((t) => {
    localStorage.setItem('amap_token', t);
    localStorage.setItem('amap_org_id', '9a61e05d-7a32-4112-9c17-1833d7b42f65');
    document.cookie = `amap_token=${t}; path=/; max-age=86400; SameSite=Lax`;
  }, loginRes.access_token);
  await page.setCookie({ name: 'amap_token', value: loginRes.access_token, url: BASE });

  // 2. Open worker console.
  await page.goto(`${BASE}/worker`, { waitUntil: 'networkidle2', timeout: 120000 });

  // 3. Switch modality to GESTURE.
  const clickResult = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const g = btns.find((b) => /gesture/i.test(b.textContent || ''));
    if (g) { g.click(); return 'clicked: ' + (g.textContent || '').trim().slice(0, 40); }
    return 'NO_BUTTON (' + btns.length + ' buttons on page)';
  });
  console.log('GESTURE BUTTON:', clickResult);

  // 4. Let the pipeline run.
  await new Promise((r) => setTimeout(r, WAIT));

  // 5. Read the tracker UI state from the DOM.
  const state = await page.evaluate(() => {
    const text = document.body.innerText;
    const grab = (re) => { const m = text.match(re); return m ? m[0] : null; };
    return {
      title: document.title,
      searching: grab(/Searching for Hand\(s\)\.\.\./),
      handTracked: grab(/Hands Tracked: [^\n•]*/),
      fps: grab(/\d+ FPS/),
      statusLine: grab(/(Initializing Dual-Hand Camera|Hand\(s\) Tracked|Multi-Hand Conflict|Analyzing|Holding|Confirmed|Searching for Hand|Vision Error)[^\n]*/),
      cameraReady: /READY/i.test(text),
      diagPanel: (document.querySelector('[data-testid="amap-runtime-diagnostics"]')?.textContent || 'PANEL NOT FOUND').replace(/\s+/g, ' ').trim(),
    };
  });

  await page.screenshot({ path: `/tmp/browser/${PREFIX}.png`, fullPage: false });

  // 6. Report.
  const amapLogs = logs.filter((l) => l.includes('[AMAP') || l.includes('PAGEERROR'));
  const mpLogs = logs.filter((l) => /Graph|landmark_projection|gl_context|wasm/i.test(l)).slice(0, 6);
  console.log('=== UI STATE ===');
  console.log(JSON.stringify(state, null, 2));
  const bodySnippet = await page.evaluate(() => document.body.innerText.replace(/\n{2,}/g, '\n').slice(0, 1200));
  console.log('=== BODY TEXT (first 1200 chars) ===');
  console.log(bodySnippet);
  console.log('=== ALL CONSOLE (first 25) ===');
  logs.slice(0, 25).forEach((l) => console.log(l.slice(0, 160)));
  console.log('=== AMAP/ERROR CONSOLE (' + amapLogs.length + ') ===');
  amapLogs.slice(0, 60).forEach((l) => console.log(l));
  console.log('=== MEDIAPIPE CONSOLE (first 6) ===');
  mpLogs.forEach((l) => console.log(l.slice(0, 140)));
  await browser.close();
})().catch((e) => { console.error('HARNESS FAIL:', e.message); process.exit(1); });
