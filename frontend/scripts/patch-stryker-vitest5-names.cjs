/**
 * Postinstall compatibility patch: @stryker-mutator/vitest-runner 10.0.0 ×
 * vitest 5 full-test-name separator.
 *
 * Background (measured 2026-09-22, CI run 35634327238 + local repro):
 * vitest 5 matches `testNamePattern` against the full test name joined with
 * " > " (suite names + leaf name). vitest ≤4 joined with spaces, which is
 * what stryker 10's collectTestName still builds ("suite > " had been " ":
 * `nameParts.join(' ')`). The per-mutant filter regex therefore matched
 * ZERO tests on vitest 5, and stryker reported every covered mutant as
 * Survived — "Ran 0.00 tests per mutant", 0 killed, "0.00%" score, job
 * green. Upstream: stryker-mutator/stryker-js issues #6210, #6213, #6214,
 * #6220 (open as of this patch; #6220 fix matches Vitest 5 full test names).
 *
 * This patch rewrites `nameParts.join(' ')` to `nameParts.join(' > ')` in
 * the two places the runner assembles a full test name:
 *   - dist/src/test-helpers.js  (main-process side: test id construction)
 *   - dist/src/stryker-setup.js (worker side: ids injected into the sandbox)
 * Both MUST be patched together — the setup file builds the ids that the
 * dry run's `coveredBy`/testIds carry, and the main process regex is built
 * from the same strings; a one-sided patch silently mismatches to 0 tests
 * again (the exact failure this file exists to prevent).
 *
 * Verification that the patch WORKS (not just applies): the mutation-score
 * harness guard scripts/mutation-guard.mjs fails any report where the
 * runner executed 0 tests per mutant (killed+timeout == 0 with survived>0),
 * so a silently-unpatched/ineffective patch turns CI Frontend Mutation
 * Testing red at the guard instead of green at 0.00%.
 *
 * Run: remove when the installed @stryker-mutator/vitest-runner contains
 * the upstream fix (check for issue #6220 in its changelog).
 */
'use strict';

const fs = require('fs');
const path = require('path');

const RUNNER_DIR = path.join(
  __dirname,
  '..',
  'node_modules',
  '@stryker-mutator',
  'vitest-runner',
  'dist',
  'src'
);

const TARGETS = ['test-helpers.js', 'stryker-setup.js'];
const NEEDLE = "nameParts.join(' ')";
const REPLACEMENT = "nameParts.join(' > ')";

let patched = 0;
let already = 0;
const missing = [];

for (const file of TARGETS) {
  const full = path.join(RUNNER_DIR, file);
  if (!fs.existsSync(full)) {
    missing.push(file);
    continue;
  }
  const content = fs.readFileSync(full, 'utf8');
  if (content.includes(REPLACEMENT)) {
    already++;
    continue;
  }
  if (!content.includes(NEEDLE)) {
    // Neither the vulnerable join nor the fixed one: the package changed
    // shape. Loud, never silent — an un-patched runner on vitest 5 measures
    // nothing, and "measures nothing" is exactly the failure mode.
    console.warn(
      `[patch-stryker-vitest5-names] WARNING: ${file} has no nameParts.join() — upstream changed shape; verify vitest-5 name matching manually.`
    );
    continue;
  }
  fs.writeFileSync(full, content.replace(NEEDLE, REPLACEMENT), 'utf8');
  patched++;
}

if (patched > 0) {
  console.log(
    `[patch-stryker-vitest5-names] Patched ${patched} file(s): vitest-5 full-name separator " > " (stryker-js #6210/#6220).`
  );
} else if (already === TARGETS.length) {
  // Silent when healthy (runs after every install).
} else if (missing.length === TARGETS.length) {
  // @stryker-mutator/vitest-runner not installed (e.g. backend-only CI image).
} else {
  console.log(
    `[patch-stryker-vitest5-names] ${already} already patched, ${patched} patched now; ${missing.length} missing. ` +
      'If vitest-runner is installed, both files must end up consistent or stryker measures 0 tests per mutant.'
  );
}
