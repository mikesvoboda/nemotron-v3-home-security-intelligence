/**
 * Frontend mutation harness health guard (WP: stryker-10 × vitest-5 silent-red).
 *
 * Why this file exists: the 2026-09-21 weekly-dispatch follow-up run
 * (CI run 35634327238) reported Frontend Mutation Testing SUCCESS while
 * Stryker printed "All files 0.00 | killed 0 | timeout 0 | survived 261 |
 * errors 62" and "Ran 0.00 tests per mutant on average" — the runner's
 * per-mutant test filter matched zero tests (vitest-5 name separator, see
 * scripts/patch-stryker-vitest5-names.cjs), so nothing was ever executed
 * against a mutant. continue-on-error: true on the CI job means a harness
 * that measures nothing CANNOT go red there. This guard is the red-detecting
 * layer: it is the step that fails when the score step cannot.
 *
 * Doctrine (same as scripts/mutation-score.py on the backend): a run that
 * measured nothing must be loud. The frontend score itself stays
 * informational (break: null — WP4.3 ruling), but "measured nothing" is not
 * a score, it is a broken harness.
 *
 * A report is BROKEN (exit 1) when EITHER:
 *   1. killed + timeout === 0 while survived > 0  — no mutant was ever
 *      proven caught; a real harness on real tests kills something, and
 *   2. the whole-report "Ran N tests per mutant" is 0 (from stryker json
 *      stats: testedTimesSpent/testedMutants absent is not checked here —
 *      instead derived: sum over mutants of (tests run) via coveredBy+
 *      testsCompleted if present, falling back to rule 1 alone), OR
 *   3. killed + timeout === 0 and errors > 0 with survived === 0 — every
 *      mutant errored; same verdict, different anatomy.
 *
 * Exit codes: 0 healthy report · 1 broken harness · 2 report missing/unparseable.
 *
 * Usage: node scripts/mutation-guard.mjs [path/to/mutation.json]
 *        (default: reports/mutation/mutation.json relative to frontend/)
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const reportPath = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.resolve(HERE, '..', 'reports', 'mutation', 'mutation.json');

let report;
try {
  report = JSON.parse(readFileSync(reportPath, 'utf8'));
} catch (err) {
  console.error(
    `[mutation-guard] FAIL: cannot read/parse report at ${reportPath}: ${err.message}\n` +
      'A run that produces no report measured nothing (run28 frontend signature).'
  );
  process.exit(2);
}

// stryker json report shapes across majors: { files: {name: {mutants: {id: m}}}, stats? }
const mutants = [];
if (report.files) {
  for (const [fileName, file] of Object.entries(report.files)) {
    const list = file.mutants;
    // json reporter emits mutants as an array under `mutants` in some versions,
    // object-keyed in others; accept both.
    const arr = Array.isArray(list) ? list : Object.values(list ?? {});
    for (const m of arr) mutants.push({ file: fileName, ...m });
  }
} else if (Array.isArray(report.results)) {
  // older/direct json reporter: flat results[] with status
  for (const m of report.results) mutants.push(m);
}

if (mutants.length === 0) {
  console.error(
    `[mutation-guard] FAIL: report parsed but contains 0 mutants at ${reportPath} — nothing was measured.`
  );
  process.exit(2);
}

const count = (s) => mutants.filter((m) => m.status === s).length;
const killed = count('Killed');
const timeout = count('Timeout');
const survived = count('Survived');
const errors = count('Error') + count('CompileError') + count('RuntimeError');
const noCoverage = count('NoCoverage');
const total = mutants.length;

// "tests per mutant" — stryker's own line is console-only; derive from
// testsCompleted when the json reporter provides it.
const withCompletion = mutants.filter((m) => typeof m.testsCompleted === 'number');
const avgTestsPerMutant = withCompletion.length
  ? withCompletion.reduce((a, m) => a + m.testsCompleted, 0) / withCompletion.length
  : null;

const verdict = {
  report: reportPath,
  total,
  killed,
  timeout,
  survived,
  errors,
  no_coverage: noCoverage,
  avg_tests_per_mutant: avgTestsPerMutant,
};

const caught = killed + timeout;
const reasons = [];
if (caught === 0 && survived > 0) {
  reasons.push(`0 killed across ${survived} survived mutants — the runner never executed tests against mutants (vitest-name-filter signature, see patch-stryker-vitest5-names.cjs header)`);
}
if (caught === 0 && survived === 0 && errors > 0) {
  reasons.push(`0 killed with all ${errors} non-killed mutants ERRORING — the harness could not run, that is not a score`);
}
if (avgTestsPerMutant !== null && avgTestsPerMutant === 0 && survived > 0) {
  reasons.push('Ran 0.00 tests per mutant on average');
}

console.log(`[mutation-guard] ${JSON.stringify(verdict)}`);
if (reasons.length) {
  console.error(`[mutation-guard] BROKEN HARNESS:\n  - ${reasons.join('\n  - ')}`);
  process.exit(1);
}
console.log('[mutation-guard] OK: harness measured real test executions against mutants.');
