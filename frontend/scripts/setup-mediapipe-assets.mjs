/**
 * Materialize MediaPipe runtime assets into public/ so the browser loads
 * them from this origin (no CDN/network dependency at runtime):
 *  - public/mediapipe/wasm/*            <- node_modules/@mediapipe/tasks-vision/wasm
 *  - public/mediapipe/hand_landmarker.task <- node_modules/expo-vision-camera-v4-mediapipe
 * Runs automatically via the package.json "postinstall" hook.
 */
import { copyFileSync, mkdirSync, existsSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const outDir = join(root, 'public', 'mediapipe');
const wasmOut = join(outDir, 'wasm');
mkdirSync(wasmOut, { recursive: true });

const wasmSrc = join(root, 'node_modules', '@mediapipe', 'tasks-vision', 'wasm');
if (!existsSync(wasmSrc)) {
  console.error('[mediapipe-assets] missing ' + wasmSrc + ' — run npm install');
  process.exit(1);
}
for (const f of readdirSync(wasmSrc)) {
  copyFileSync(join(wasmSrc, f), join(wasmOut, f));
}

const taskSrc = join(root, 'node_modules', 'expo-vision-camera-v4-mediapipe', 'hand_landmarker.task');
if (!existsSync(taskSrc)) {
  console.error('[mediapipe-assets] missing hand_landmarker.task — run npm install');
  process.exit(1);
}
copyFileSync(taskSrc, join(outDir, 'hand_landmarker.task'));

console.log('[mediapipe-assets] wasm + hand_landmarker.task -> public/mediapipe/');
