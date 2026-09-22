/**
 * Tests for scripts/mutation-guard.mjs + scripts/patch-stryker-vitest5-names.cjs
 * (WP: stryker-10 × vitest-5 silent-red, 2026-09-22).
 *
 * Doctrine mirrored from scripts/test_mutation_score.py (backend): a run that
 * measured nothing must be LOUD, and the pin is to the real broken artifact's
 * shape — the synthesized fixtures below replay CI run 35634327238
 * ("killed 0 | survived 261 | errors 62", continue-on-error green) as pytest
 * cases, so the guard can never rot back to calling a dead harness green.
 *
 * Run: node scripts/test_mutation_guard.cjs   (CI: mutation-testing.yml guard step +
 *      this file's own pass printed in the step summary)
 */
'use strict';

const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const HERE = __dirname;
const GUARD = path.join(HERE, 'mutation-guard.mjs');
const PATCHER = path.join(HERE, 'patch-stryker-vitest5-names.cjs');

let failures = 0;
function check(name, fn) {
  try {
    fn();
    console.log(`ok - ${name}`);
  } catch (err) {
    failures++;
    console.log(`NOT OK - ${name}: ${err.message}`);
  }
}
function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}
function assertEqual(actual, expected, msg) {
  if (actual !== expected) throw new Error(`${msg}: expected ${expected}, got ${actual}`);
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'mguard-'));

function writeReport(name, mutantsByFile) {
  const p = path.join(tmp, name);
  const files = {};
  for (const [file, mutants] of Object.entries(mutantsByFile)) {
    files[file] = { mutants: Object.fromEntries(mutants.map((m, i) => [String(i), { id: String(i), ...m }])) };
  }
  fs.writeFileSync(p, JSON.stringify({ files }));
  return p;
}

function runGuard(reportPath) {
  try {
    const out = execFileSync('node', [GUARD, reportPath], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    return { rc: 0, out };
  } catch (err) {
    return { rc: err.status, out: (err.stdout || '') + (err.stderr || '') };
  }
}

// --- the run 35634327238 signature (the artifact that motivated this guard) ---
check('run-29 signature report is BROKEN (rc=1, cites the name-filter)', () => {
  const p = writeReport('run29.json', {
    'src/utils/time.ts': Array.from({ length: 261 }, () => ({ status: 'Survived' })),
    'src/utils/risk.ts': Array.from({ length: 62 }, () => ({ status: 'CompileError' })),
    'src/utils/confidence.ts': Array.from({ length: 61 }, () => ({ status: 'NoCoverage' })),
  });
  const { rc, out } = runGuard(p);
  assertEqual(rc, 1, 'guard exit code');
  assert(/vitest-name-filter/.test(out), 'output must name the vitest-5 filter signature');
});

check('healthy report (killed>0, tests ran) passes (rc=0)', () => {
  const p = writeReport('healthy.json', {
    'src/utils/confidence.ts': [
      ...Array.from({ length: 40 }, () => ({ status: 'Killed', testsCompleted: 5 })),
      ...Array.from({ length: 10 }, () => ({ status: 'Survived', testsCompleted: 5 })),
      ...Array.from({ length: 20 }, () => ({ status: 'CompileError' })),
    ],
  });
  const { rc, out } = runGuard(p);
  assertEqual(rc, 0, 'guard exit code');
  assert(/OK: harness measured/.test(out), 'healthy output');
});

check('all-error report (no survivors, all errors) is BROKEN', () => {
  const p = writeReport('allerr.json', { x: Array.from({ length: 9 }, () => ({ status: 'RuntimeError' })) });
  const { rc } = runGuard(p);
  assertEqual(rc, 1, 'guard exit code');
});

check('missing report is FAIL (rc=2)', () => {
  const { rc } = runGuard(path.join(tmp, 'nope.json'));
  assertEqual(rc, 2, 'guard exit code');
});

check('zero-mutant report is FAIL (rc=2)', () => {
  const p = writeReport('empty.json', { x: [] });
  const { rc } = runGuard(p);
  assertEqual(rc, 2, 'guard exit code');
});

check('killed>0 but 0 tests per mutant is BROKEN (avg-tests rule fires independently)', () => {
  const p = writeReport('weird.json', {
    x: [
      ...Array.from({ length: 5 }, () => ({ status: 'Killed', testsCompleted: 0 })),
      ...Array.from({ length: 5 }, () => ({ status: 'Survived', testsCompleted: 0 })),
    ],
  });
  const { rc, out } = runGuard(p);
  assertEqual(rc, 1, 'guard exit code');
  assert(/Ran 0\.00 tests per mutant/.test(out), 'output cites the 0.00 line');
});

// --- patcher idempotence against a fake node_modules layout ---
function fakeRunner(dir, { fixed = false, vulnerable = true, missing = false } = {}) {
  const distSrc = path.join(dir, 'node_modules', '@stryker-mutator', 'vitest-runner', 'dist', 'src');
  fs.mkdirSync(distSrc, { recursive: true });
  for (const f of ['test-helpers.js', 'stryker-setup.js']) {
    if (missing) continue;
    const content = vulnerable
      ? `const x = nameParts.join(' ').trim();`
      : fixed
        ? `const x = nameParts.join(' > ').trim();`
        : `const x = totallyDifferent();`;
    fs.writeFileSync(path.join(distSrc, f), content);
  }
  return distSrc;
}

check('patcher fixes vulnerable files', () => {
  const dir = fs.mkdtempSync(path.join(tmp, 'patcher-vuln-'));
  // place a copy of the patcher's expected layout: scripts sit in frontend/scripts (HERE);
  // the patcher resolves node_modules relative to its OWN dir — so we copy the patcher into dir/scripts.
  fs.mkdirSync(path.join(dir, 'scripts'), { recursive: true });
  fs.copyFileSync(PATCHER, path.join(dir, 'scripts', 'patch-stryker-vitest5-names.cjs'));
  const distSrc = fakeRunner(dir, { vulnerable: true });
  execFileSync('node', [path.join(dir, 'scripts', 'patch-stryker-vitest5-names.cjs')], { stdio: 'pipe' });
  const a = fs.readFileSync(path.join(distSrc, 'test-helpers.js'), 'utf8');
  const b = fs.readFileSync(path.join(distSrc, 'stryker-setup.js'), 'utf8');
  assert(a.includes("nameParts.join(' > ')") && b.includes("nameParts.join(' > ')"), 'both files patched');
});

check('patcher is idempotent (second run is a no-op)', () => {
  const dir = fs.mkdtempSync(path.join(tmp, 'patcher-idem-'));
  fs.mkdirSync(path.join(dir, 'scripts'), { recursive: true });
  fs.copyFileSync(PATCHER, path.join(dir, 'scripts', 'patch-stryker-vitest5-names.cjs'));
  const distSrc = fakeRunner(dir, { vulnerable: true });
  const script = path.join(dir, 'scripts', 'patch-stryker-vitest5-names.cjs');
  execFileSync('node', [script], { stdio: 'pipe' });
  const first = fs.readFileSync(path.join(distSrc, 'test-helpers.js'), 'utf8');
  execFileSync('node', [script], { stdio: 'pipe' });
  const second = fs.readFileSync(path.join(distSrc, 'test-helpers.js'), 'utf8');
  assertEqual(second, first, 'second run must not alter content');
  assert(second.split("nameParts.join(' > ')").length === 2, 'exactly one join occurrence, not doubled');
});

check('patcher tolerates a missing runner package (no throw)', () => {
  const dir = fs.mkdtempSync(path.join(tmp, 'patcher-miss-'));
  fs.mkdirSync(path.join(dir, 'scripts'), { recursive: true });
  fs.copyFileSync(PATCHER, path.join(dir, 'scripts', 'patch-stryker-vitest5-names.cjs'));
  fakeRunner(dir, { missing: true });
  const out = execFileSync('node', [path.join(dir, 'scripts', 'patch-stryker-vitest5-names.cjs')], { encoding: 'utf8' });
  assert(out === '' || !/Error/.test(out), 'silent on absent package');
});

check('patcher is silent+no-op when runner already carries the fix upstream', () => {
  const dir = fs.mkdtempSync(path.join(tmp, 'patcher-fixed-'));
  fs.mkdirSync(path.join(dir, 'scripts'), { recursive: true });
  fs.copyFileSync(PATCHER, path.join(dir, 'scripts', 'patch-stryker-vitest5-names.cjs'));
  const distSrc = fakeRunner(dir, { vulnerable: false, fixed: true });
  execFileSync('node', [path.join(dir, 'scripts', 'patch-stryker-vitest5-names.cjs')], { stdio: 'pipe' });
  const a = fs.readFileSync(path.join(distSrc, 'test-helpers.js'), 'utf8');
  assert(a.includes("nameParts.join(' > ')"), 'content unchanged');
});

// --- the real installed runner is consistent right now (fails if npm ci
//     ran WITHOUT the postinstall hook, i.e. patch never applied) ---
check('installed vitest-runner has the " > " join in BOTH files', () => {
  const distSrc = path.join(HERE, '..', 'node_modules', '@stryker-mutator', 'vitest-runner', 'dist', 'src');
  if (!fs.existsSync(distSrc)) {
    console.log('ok - installed vitest-runner (skipped: not installed here)');
    return;
  }
  for (const f of ['test-helpers.js', 'stryker-setup.js']) {
    const c = fs.readFileSync(path.join(distSrc, f), 'utf8');
    assert(c.includes("nameParts.join(' > ')"), `${f} lacks the vitest-5 separator — postinstall patch did not run`);
  }
});

if (failures) {
  console.log(`\nFAILED ${failures} check(s)`);
  process.exit(1);
}
console.log('\nAll mutation-guard suite checks passed.');
