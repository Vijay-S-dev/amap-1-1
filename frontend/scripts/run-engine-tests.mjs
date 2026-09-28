/**
 * Frontend gesture-engine test runner.
 *
 * Compiles the pure-logic engine modules + tests with the repo's TypeScript
 * compiler and executes them under Node (no external test framework required).
 *
 * Usage:  node scripts/run-engine-tests.mjs
 */

import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const outDir = mkdtempSync(join(tmpdir(), 'amap-engine-tests-'));

let exitCode = 1;
try {
  // Compile engine + classifier + voice-worklet tests to CommonJS in a temp dir.
  execFileSync(
    process.execPath,
    [
      join(frontendRoot, 'node_modules', 'typescript', 'bin', 'tsc'),
      'tests/gesture-engine.test.ts',
      'tests/voice-worklet.test.ts',
      '--outDir', outDir,
      '--module', 'commonjs',
      '--target', 'es2020',
      '--esModuleInterop',
      '--skipLibCheck',
      '--moduleResolution', 'node',
      '--strict',
    ],
    { cwd: frontendRoot, stdio: 'inherit' }
  );

  // Run the compiled test suites.
  execFileSync(process.execPath, [join(outDir, 'tests', 'gesture-engine.test.js')], {
    cwd: frontendRoot,
    stdio: 'inherit',
  });
  execFileSync(process.execPath, [join(outDir, 'tests', 'voice-worklet.test.js')], {
    cwd: frontendRoot,
    stdio: 'inherit',
  });
  exitCode = 0;
} catch (err) {
  if (err.status !== undefined) exitCode = err.status;
  else throw err;
} finally {
  rmSync(outDir, { recursive: true, force: true });
}

process.exit(exitCode);
