#!/usr/bin/env node
// WP5.2: real istanbul merge for the 8-way Vitest shard fan-out.
//
// WHY THIS FILE EXISTS: frontend-coverage-merge on main is
// download -> `find | head` -> Codecov. It never merged and never measured,
// so the frontend tier has no single coverage number anywhere in CI. And the
// 8 shards each write `coverage-final.json` — upload + merge-multiple:true
// flattens same-named files, so even with --coverage on, one shard's data
// would survive and seven would silently vanish. The shard jobs now write to
// per-shard reportsDirectories; this script unions those files.
//
// Merge semantics are istanbul's: statement/function counts SUM across shards,
// branch path-count arrays sum element-wise, a branch is covered when any of
// its path counts is nonzero. Lines are derived from statementMap (each
// statement's starting line; a line is covered when its highest statement
// count is nonzero) — the same derivation istanbul's own reporters use, which
// keeps the four metrics consistent with what a single full `vitest run
// --coverage` would print.
//
// R-FEFLOOR (plan P ADDENDUM A3, parked): measured 80.00/74.61/78.44/80.93
// vs thresholds 83/77/81/84. This script COMPUTES. The threshold decision
// stays the owner's; nothing here enforces or moves a line.
//
// Stdlib-only: runs on a bare runner with just Node (no npm ci needed).
// Unit-checked by scripts/merge-shard-coverage.test.mjs (node --test), which
// CI runs in the same step before trusting the output.

import { readdirSync, readFileSync, existsSync, mkdirSync, writeFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

function findCoverageFinalFiles(root) {
  const out = [];
  const stack = [root];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const e of entries) {
      const p = join(dir, e.name);
      if (e.isDirectory()) stack.push(p);
      else if (e.isFile() && e.name === 'coverage-final.json') out.push(p);
    }
  }
  return out.sort();
}

// Coverage keys come out of vitest as ABSOLUTE paths (verified against real
// output: `/…/frontend/src/App.tsx`). Downloaded shard files come from the
// same checkout, but normalize anyway so same-file-different-prefix can never
// silently double-count.
export function normalizeKey(key) {
  const i = key.lastIndexOf('/frontend/');
  return i >= 0 ? key.slice(i + 1) : key.replace(/^\.\//, '');
}

export function mergeEntries(target, add) {
  for (const [key, entry] of Object.entries(add)) {
    const k = normalizeKey(key);
    const cur = target[k];
    if (!cur) {
      target[k] = entry;
      continue;
    }
    for (const id of Object.keys(entry.s ?? {})) cur.s[id] = (cur.s[id] ?? 0) + entry.s[id];
    for (const id of Object.keys(entry.f ?? {})) cur.f[id] = (cur.f[id] ?? 0) + entry.f[id];
    for (const id of Object.keys(entry.b ?? {})) {
      const a = cur.b[id] ?? [];
      const b = entry.b[id] ?? [];
      const n = Math.max(a.length, b.length);
      const sum = Array.from({ length: n }, (_, i) => (a[i] ?? 0) + (b[i] ?? 0));
      cur.b[id] = sum;
    }
    // Maps must stay in sync with the count objects; take whichever entry has
    // the map (they describe the same instrumented file).
    for (const m of ['statementMap', 'fnMap', 'branchMap']) {
      if (!cur[m] || Object.keys(cur[m]).length === 0) cur[m] = entry[m] ?? {};
    }
  }
  return target;
}

function metric(counts) {
  const total = Object.keys(counts).length;
  const covered = Object.values(counts).filter((c) => c > 0).length;
  return { total, covered, skipped: 0, pct: total === 0 ? 0 : round1((covered / total) * 100) };
}

function branchMetric(branches) {
  // ISTANBUL per-path counting, verified 2026-09-19 against real vitest
  // output: per-path 74.6 == the 74.61 figure A3 measured with vitest's own
  // reporter (per-SITE counting would read 85.4 and silently disagree with
  // the 77 floor, which was declared against istanbul numbers). An if/else
  // contributes ONE count per path, and each covered path counts.
  let total = 0;
  let covered = 0;
  for (const arr of Object.values(branches)) {
    total += arr.length;
    covered += arr.filter((c) => c > 0).length;
  }
  return { total, covered, skipped: 0, pct: total === 0 ? 0 : round1((covered / total) * 100) };
}

function lineMetric(file) {
  // statements -> lines: max count per starting line.
  const lineCount = new Map();
  for (const [id, count] of Object.entries(file.s ?? {})) {
    const loc = file.statementMap?.[id];
    if (!loc?.start) continue;
    const line = loc.start.line;
    lineCount.set(line, Math.max(lineCount.get(line) ?? 0, count));
  }
  const total = lineCount.size;
  const covered = [...lineCount.values()].filter((c) => c > 0).length;
  return { total, covered, skipped: 0, pct: total === 0 ? 0 : round1((covered / total) * 100) };
}

const round1 = (x) => Math.round(x * 10) / 10;

function fileMetrics(file) {
  return {
    statements: metric(file.s ?? {}),
    branches: branchMetric(file.b ?? {}),
    functions: metric(file.f ?? {}),
    lines: lineMetric(file),
  };
}

export function summarize(merged) {
  const totals = { statements: 0, branches: 0, functions: 0, lines: 0 };
  const covered = { statements: 0, branches: 0, functions: 0, lines: 0 };
  const perFile = {};
  for (const [key, file] of Object.entries(merged)) {
    const m = fileMetrics(file);
    perFile[key] = m;
    for (const k of Object.keys(totals)) {
      totals[k] += m[k].total;
      covered[k] += m[k].covered;
    }
  }
  const total = {};
  for (const k of Object.keys(totals)) {
    total[k] = {
      total: totals[k],
      covered: covered[k],
      skipped: 0,
      pct: totals[k] === 0 ? 0 : round1((covered[k] / totals[k]) * 100),
    };
  }
  return { total, ...perFile };
}

export function mergeFiles(paths) {
  let merged = {};
  for (const p of paths) {
    const data = JSON.parse(readFileSync(p, 'utf8'));
    merged = mergeEntries(merged, data);
  }
  return merged;
}

function main() {
  const argv = process.argv.slice(2);
  const outIdx = argv.indexOf('--out');
  const outDir = outIdx >= 0 ? argv[outIdx + 1] : 'coverage-merged';
  const roots = argv.filter((a, i) => !a.startsWith('--') && i !== outIdx + 1);

  const files = roots.flatMap((r) =>
    existsSync(r) && statSync(r).isDirectory() ? findCoverageFinalFiles(r) : [r],
  );
  if (files.length === 0) {
    // Same posture as the backend merges: warn loudly, never mint a fake
    // measurement silently. Zero files must never look like 0% "measured".
    console.error('::warning::merge-shard-coverage: no coverage-final.json found under ' + roots.join(', '));
    process.exit(0);
  }
  console.log(`merging ${files.length} coverage-final.json file(s)`);
  const merged = mergeFiles(files);
  const summary = summarize(merged);

  mkdirSync(outDir, { recursive: true });
  writeFileSync(join(outDir, 'coverage-final.json'), JSON.stringify(merged));
  writeFileSync(join(outDir, 'coverage-summary.json'), JSON.stringify(summary, null, 2));

  const t = summary.total;
  console.log(
    `FRONTEND_COVERAGE statements=${t.statements.pct} branches=${t.branches.pct} ` +
      `functions=${t.functions.pct} lines=${t.lines.pct} files=${Object.keys(merged).length}`,
  );
}

// Only run as a CLI, not when imported by the unit test.
if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split('/').pop())) {
  main();
}
