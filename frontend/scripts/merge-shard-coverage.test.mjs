// WP5.2: unit checks for merge-shard-coverage.mjs, run with `node --test`
// from the CI merge step BEFORE the script's numbers are trusted.
//
// Fixtures mirror the real @vitest/coverage-v8 output shape (verified against
// frontend/coverage/coverage-final.json on disk: absolute-path keys, s/f
// numeric counts, b path-count arrays, statementMap with loc.start.line).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { mergeEntries, normalizeKey, summarize } from './merge-shard-coverage.mjs';

const fileA = {
  path: '/abs/frontend/src/a.tsx',
  statementMap: {
    0: { start: { line: 1 }, end: { line: 1 } },
    1: { start: { line: 2 }, end: { line: 2 } },
    2: { start: { line: 3 }, end: { line: 3 } },
  },
  fnMap: { 0: { name: 'f' }, 1: { name: 'g' } },
  branchMap: { 0: { type: 'if' } },
  s: { 0: 1, 1: 0, 2: 0 },
  f: { 0: 1, 1: 0 },
  b: { 0: [1, 0] },
};
const fileA_otherShard = {
  path: '/abs/frontend/src/a.tsx',
  statementMap: fileA.statementMap,
  fnMap: fileA.fnMap,
  branchMap: fileA.branchMap,
  // same file from a shard where a DIFFERENT statement ran
  s: { 0: 0, 1: 3, 2: 0 },
  f: { 0: 0, 1: 1 },
  b: { 0: [0, 2] },
};

test('normalizeKey collapses /frontend/ absolute prefixes to one identity', () => {
  assert.equal(normalizeKey('/home/runner/w/frontend/src/App.tsx'), 'frontend/src/App.tsx');
  assert.equal(normalizeKey('./src/App.tsx'), 'src/App.tsx');
  assert.equal(normalizeKey('/other/root/src/x.ts'), '/other/root/src/x.ts');
});

test('same file from two shards sums counts and unions coverage', () => {
  let merged = mergeEntries({}, { [fileA.path]: structuredClone(fileA) });
  merged = mergeEntries(merged, { [fileA_otherShard.path]: structuredClone(fileA_otherShard) });
  const key = Object.keys(merged);
  assert.equal(key.length, 1, 'same normalized path must not double-count as two files');
  const f = merged['frontend/src/a.tsx'];
  assert.deepEqual(f.s, { 0: 1, 1: 3, 2: 0 }, 'statement counts sum');
  assert.deepEqual(f.f, { 0: 1, 1: 1 }, 'function counts sum');
  assert.deepEqual(f.b, { 0: [1, 2] }, 'branch path counts sum element-wise');
});

test('branch covered iff any path count nonzero after merge', () => {
  let merged = mergeEntries({}, { 'frontend/src/a.tsx': structuredClone(fileA) });
  merged = mergeEntries(merged, { 'frontend/src/a.tsx': structuredClone(fileA_otherShard) });
  const m = summarize(merged)['frontend/src/a.tsx'];
  assert.equal(m.branches.covered, 1);
  assert.equal(m.branches.total, 1);
  // s: 2 of 3 statements covered, f: 2 of 2 covered, lines: 2 of 3 (line 3 never ran)
  assert.equal(m.statements.pct, 66.7);
  assert.equal(m.functions.pct, 100);
  assert.equal(m.lines.pct, 66.7);
});

test('distinct files across shards both appear and aggregate into total', () => {
  const fileB = structuredClone(fileA);
  fileB.path = '/abs/frontend/src/b.tsx';
  let merged = mergeEntries({}, { [fileA.path]: structuredClone(fileA) });
  merged = mergeEntries(merged, { 'x/frontend/src/b.tsx': fileB });
  const s = summarize(merged);
  assert.equal(Object.keys(s).length, 3); // total + 2 files
  assert.equal(s.total.statements.total, 6);
  // each shard-side file is fileA's map (1 of 3 statements executed) —
  // DISTINCT files must not union with each other the way shards of the SAME
  // file do (that case is the test above)
  assert.equal(s.total.statements.covered, 2);
});

test('missing maps degrade to zero, never crash', () => {
  const s = summarize({ 'frontend/src/empty.ts': { s: {}, f: {}, b: {} } });
  assert.equal(s.total.statements.pct, 0);
  assert.equal(s['frontend/src/empty.ts'].lines.pct, 0);
});

test('CLI end-to-end on temp dirs prints FRONTEND_COVERAGE line', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'wp52-'));
  try {
    const s1 = join(dir, 'shard1');
    const s2 = join(dir, 'shard2');
    for (const [d, payload] of [
      [s1, { [fileA.path]: fileA }],
      [s2, { [fileA_otherShard.path]: fileA_otherShard }],
    ]) {
      mkdirSync(d, { recursive: true });
      writeFileSync(join(d, 'coverage-final.json'), JSON.stringify(payload));
    }
    const { execFileSync } = await import('node:child_process');
    const out = execFileSync('node', [new URL('./merge-shard-coverage.mjs', import.meta.url).pathname, s1, s2, '--out', join(dir, 'out')], {
      encoding: 'utf8',
    });
    assert.match(out, /FRONTEND_COVERAGE statements=66\.7 branches=100 functions=100 lines=66\.7 files=1/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
