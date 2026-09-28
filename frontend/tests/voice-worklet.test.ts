/**
 * Voice streaming hook unit tests (frontend/tests/voice-worklet.test.ts)
 *
 * Validates the browser-side DSP of useVoiceStream against the WebSocket
 * protocol contract:
 *  - the AudioWorklet source is syntactically valid and registers itself
 *  - mono 16 kHz passthrough produces even-length 16-bit PCM frames
 *  - 48 kHz input is resampled to 16 kHz (3:1) without frame drift
 *  - frame size is exactly FRAME_SAMPLES (512) so the backend receives
 *    well-formed PCM (odd-length frames are rejected server-side)
 *  - clipping protection maps float [-1, 1] to int16 safely
 *
 * (A real physical microphone cannot be exercised in CI; the full speech
 * chain is covered by backend tests with real audio over the real WS route.)
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

// ---------------------------------------------------------------------------
// Minimal test framework (same style as gesture-engine.test.ts)
// ---------------------------------------------------------------------------
let passed = 0;
let failed = 0;
const failures: string[] = [];

function assert(condition: unknown, message: string): void {
  if (condition) {
    passed += 1;
  } else {
    failed += 1;
    failures.push(message);
    console.error(`  ✗ ${message}`);
  }
}

function assertEqual(actual: unknown, expected: unknown, message: string): void {
  assert(
    JSON.stringify(actual) === JSON.stringify(expected),
    `${message}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`
  );
}

function test(name: string, fn: () => void): void {
  console.log(`  • ${name}`);
  try {
    fn();
  } catch (err) {
    failed += 1;
    failures.push(`${name}: threw ${String(err)}`);
    console.error(`  ✗ ${name} threw:`, err);
  }
}

// ---------------------------------------------------------------------------
// Extract the worklet source from the hook and run it in a fake worklet scope
// ---------------------------------------------------------------------------
const hookSource = readFileSync(
  join(process.cwd(), 'shared', 'hooks', 'useVoiceStream.ts'),
  'utf8'
);
const start = hookSource.indexOf('const PCM_WORKLET_SRC = `');
const end = hookSource.indexOf('`;', start);
assert(start !== -1 && end !== -1, 'PCM_WORKLET_SRC found in useVoiceStream.ts');
const workletSource = hookSource
  .slice(start + 'const PCM_WORKLET_SRC = `'.length, end)
  .replace(/\$\{TARGET_SAMPLE_RATE\}/g, '16000')
  .replace(/\$\{FRAME_SAMPLES\}/g, '512');

let registeredName: string | null = null;
let registeredClass: any = null;

// Fake AudioWorkletGlobalScope
const fakeScope: Record<string, unknown> = {
  sampleRate: 48000, // overridden per test
  // Base class stub: the real one is provided by the browser runtime.
  AudioWorkletProcessor: class {
    port: unknown = null;
  },
  registerProcessor: (name: string, cls: any) => {
    registeredName = name;
    registeredClass = cls;
  },
};

function buildWorklet(sampleRate: number) {
  registeredName = null;
  registeredClass = null;
  const scope: Record<string, unknown> = { ...fakeScope, sampleRate };
  const keys = Object.keys(scope);
  const values = keys.map((k) => scope[k]);
  // eslint-disable-next-line no-new-func
  const factory = new Function(...keys, `${workletSource}`);
  factory(...values);
  assert(registeredName === 'amap-pcm-sender', `processor registered at ${sampleRate} Hz`);
  return new registeredClass();
}

console.log('\n— voice worklet (browser mic DSP) —\n');

test('worklet source registers amap-pcm-sender', () => {
  buildWorklet(16000);
  assert(!!registeredClass, 'class captured');
});

test('16 kHz passthrough: frames are 512-sample 16-bit PCM (even bytes)', () => {
  const processor: any = buildWorklet(16000);
  const frames: ArrayBuffer[] = [];
  processor.port = { postMessage: (data: ArrayBuffer) => frames.push(data) };
  // 128-sample quantum * 4 = one full 512-sample frame
  const quantum = new Float32Array(128).fill(0.5);
  for (let i = 0; i < 4; i++) {
    const keep = processor.process([[quantum]]);
    assert(keep === true, 'process returns true (keep alive)');
  }
  assertEqual(frames.length, 1, 'one 512-sample frame posted after 4 quanta');
  assertEqual(frames[0].byteLength, 1024, 'frame is 1024 bytes (512 × int16)');
  const view = new Int16Array(frames[0]);
  // 0.5 float -> ~16384 int16
  assert(Math.abs(view[0] - 0.5 * 0x7fff) < 4, '0.5 float converts to ~16384 int16');
});

test('48 kHz input is resampled to 16 kHz (3:1)', () => {
  const processor: any = buildWorklet(48000);
  const frames: ArrayBuffer[] = [];
  processor.port = { postMessage: (data: ArrayBuffer) => frames.push(data) };
  // A 440 Hz sine at 48 kHz: each 128-sample quantum resamples to
  // floor(128/3) = 42 output samples. 13 quanta -> 546 samples -> one full
  // 512-sample frame is posted (34 samples carry over).
  const quantum = new Float32Array(128);
  for (let i = 0; i < 128; i++) quantum[i] = Math.sin((2 * Math.PI * 440 * i) / 48000);
  for (let i = 0; i < 13; i++) processor.process([[quantum]]);
  assertEqual(frames.length, 1, 'resampling yields exactly one 512-sample frame');
  assertEqual(frames[0].byteLength, 1024, 'resampled frame byte length');
  // The resampled waveform is still a sine with the right amplitude range.
  const view = new Int16Array(frames[0]);
  const max = Math.max(...Array.from(view).map(Math.abs));
  assert(max > 10000, `resampled sine retains amplitude (max |sample| = ${max})`);
});

test('silence produces all-zero PCM frames', () => {
  const processor: any = buildWorklet(16000);
  const frames: ArrayBuffer[] = [];
  processor.port = { postMessage: (data: ArrayBuffer) => frames.push(data) };
  const silence = new Float32Array(128);
  for (let i = 0; i < 4; i++) processor.process([[silence]]);
  const view = new Int16Array(frames[0]);
  assert(view.every((sample) => sample === 0), 'silence maps to zero int16');
});

test('out-of-range floats clip instead of wrapping', () => {
  const processor: any = buildWorklet(16000);
  const frames: ArrayBuffer[] = [];
  processor.port = { postMessage: (data: ArrayBuffer) => frames.push(data) };
  const loud = new Float32Array(128).fill(2.0); // > 1.0
  const quiet = new Float32Array(128).fill(-2.0);
  processor.process([[loud]]);
  processor.process([[loud]]);
  processor.process([[quiet]]);
  processor.process([[quiet]]);
  const view = new Int16Array(frames[0]);
  assertEqual(view[0], 0x7fff, '+2.0 clips to int16 max');
  assertEqual(view[256], -0x8000, '-2.0 clips to int16 min');
});

test('no frame is ever odd-length (backend rejects odd PCM frames)', () => {
  const processor: any = buildWorklet(44100);
  const frames: ArrayBuffer[] = [];
  processor.port = { postMessage: (data: ArrayBuffer) => frames.push(data) };
  const quantum = new Float32Array(128).fill(0.1);
  for (let i = 0; i < 40; i++) processor.process([[quantum]]);
  assert(frames.length > 0, 'frames produced at 44.1 kHz');
  for (const frame of frames) {
    assertEqual(frame.byteLength % 2, 0, 'every frame has an even byte length');
    assertEqual(frame.byteLength, 1024, 'every frame is exactly 512 samples');
  }
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------
console.log('\n=========================================================');
if (failed > 0) {
  console.log(`  voice worklet tests: ${passed} passed, ${failed} failed`);
  console.log('\nFailures:');
  for (const failure of failures) console.log(`  - ${failure}`);
  process.exit(1);
} else {
  console.log(`  voice worklet tests: ${passed} passed, 0 failed`);
  console.log('=========================================================');
}
