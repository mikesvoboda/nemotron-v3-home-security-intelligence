#!/usr/bin/env node
// knip-unreachable-census.mjs — split knip's unreachable production files into what F3.2 may
// delete and what a feature row claims, reading the rows with the repo's own parser.
//
//   node scripts/knip-unreachable-census.mjs --knip knip.json
//   node scripts/knip-unreachable-census.mjs --knip knip.json --inventory-ref <ref>
//
// WHY THIS EXISTS. `F3.2` (docs/uplevel/packages/frontend.md) says to delete the unreachable
// production files "except files a **complete** feature's row claims, which stay and go on knip's
// ignore list with that row's id". knip cannot make that cut — it has no idea the inventory exists.
// And the inventory's `modules` column is repo-relative (`frontend/src/...`) while knip reports
// paths relative to its own cwd (`src/...`), so the two do not join on their own. This joins them:
// every unused file is asked which rows name it, and the answer decides its bucket.
//
// Buckets, and why each is its own:
//   UNCLAIMED  no row names the file — the inventory says no feature uses it. Deletable by F3.2.
//   COMPLETE   a row ruled `complete` (or `complete, consolidated`) claims it. Stays; needs an
//              `ignore` entry in knip.json carrying that row's id, which is what the clause asks for.
//   RETIRE     only rows ruled `retire` claim it. That is F3.1's deletion target ("Retire ruled-out
//              features, frontend part"), and ruling 255 item 5 assigns each R2a row's retirements to
//              one B3.1/F3.1 PR, so F3.2 leaves them for that PR rather than cutting them here. Listed
//              so the split is stated, not silent.
//   UNRULED    rows exist but none carries a ruling. Phase 3 deletions follow rulings (UR-66), so
//              nothing may be cut here until `R2` rules those rows.
//   MIXED      rows disagree (a split, or a complete alongside a retire). Needs a decision, not a
//              regex, so it is reported rather than resolved.
//
// Line counts are printed per bucket because the Done-when asks for "files and lines removed", and a
// figure a reviewer cannot re-produce is not evidence.
//
// The `--knip` argument is required and the file must be the JSON reporter's output
// (`knip --production --reporter json`), because the whole point is that the delete set is derived
// from a run a reader can repeat. The controls are the same reasoning as the cite-drift tool's: an
// all-clear here would otherwise be indistinguishable from a scan that joined nothing, so a census
// that classifies zero files exits non-zero, the join rate is printed on every run, and
// `--control` runs the recall test described at `recallControl`.
//
// Contract rule 3 (UR-10): a package's evidence instruments live in the repo.
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { parseInventory } from './feature-inventory-lib.mjs';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const INVENTORY = 'docs/reference/feature-inventory.md';

const argv = process.argv.slice(2);
const flag = (name) => {
  const i = argv.indexOf(name);
  return i === -1 ? null : argv[i + 1];
};
const KNIP = flag('--knip');
const INVENTORY_REF = flag('--inventory-ref'); // judge the rows as another revision wore them
const ONLY = flag('--only'); // print only this bucket's files (for a delete list)

if (!KNIP) {
  console.error(
    'usage: knip-unreachable-census.mjs --knip <knip-json> [--inventory-ref <ref>] [--only <bucket>]'
  );
  process.exit(2);
}

const report = JSON.parse(fs.readFileSync(KNIP, 'utf8'));
// `files` is knip's whole-file-unused list: strings, not objects. A `issues` entry means an unused
// export INSIDE a file that is itself reachable, which is a different edit and not this census.
const unused = report.files;
if (!Array.isArray(unused) || unused.some((f) => typeof f !== 'string')) {
  console.error('--knip does not look like `knip --reporter json` output: .files must be strings');
  process.exit(2);
}

const invText = INVENTORY_REF
  ? execFileSync('git', ['show', `${INVENTORY_REF}:${INVENTORY}`], {
      encoding: 'utf8',
      maxBuffer: 1 << 28,
      cwd: REPO,
    })
  : fs.readFileSync(path.join(REPO, INVENTORY), 'utf8');
const rows = parseInventory(invText).rows;

// Index modules -> rows. The inventory spells a path `frontend/src/x/y.ts` and knip spells it
// `src/x/y.ts`, so the join key drops the lane prefix. Both spellings are kept so a row that names a
// file OUTSIDE frontend/ (a backend or monitoring path, which knip never reports) cannot collide.
const claimants = new Map();
for (const row of rows) {
  for (const mod of row.modules) {
    for (const key of new Set([mod, mod.replace(/^frontend\//, '')])) {
      if (!claimants.has(key)) claimants.set(key, []);
      const list = claimants.get(key);
      if (!list.includes(row.id)) list.push(row.id);
    }
  }
}

const isComplete = (r) => /^complete\b/.test(r);
const isRetire = (r) => /^retire\b/.test(r);

// Every unused file is measured in the buckets' own units: a deletion report owes lines, not just
// a file count, and the buckets are what the report is cut by.
const HEAD_FILES = new Map(); // repo path -> line count at HEAD, sampled once
function lineCount(repoPath) {
  if (!HEAD_FILES.has(repoPath)) {
    let n = -1;
    try {
      n = Number(
        execFileSync('git', ['show', `HEAD:${repoPath}`], {
          encoding: 'utf8',
          maxBuffer: 1 << 28,
          cwd: REPO,
        }).split('\n').length - 1
      );
    } catch {
      n = -1; // not in HEAD: knip can list a tracked-but-uncommitted file; reported, never guessed
    }
    HEAD_FILES.set(repoPath, n);
  }
  return HEAD_FILES.get(repoPath);
}
const bucketLines = (b) =>
  buckets[b].reduce((sum, e) => sum + Math.max(lineCount(`frontend/${e.file}`), 0), 0);

const buckets = { UNCLAIMED: [], COMPLETE: [], RETIRE: [], UNRULED: [], MIXED: [] };
let joined = 0;
for (const file of unused) {
  const ids = claimants.get(file) ?? [];
  joined += ids.length ? 1 : 0;
  const ruled = ids
    .map((id) => rows.find((r) => r.id === id))
    .map((r) => ({ id: r.id, ruling: (r.ruling ?? '').trim() }))
    .filter((x) => x.ruling !== '' && !/^not ruled/.test(x.ruling));
  let bucket;
  if (ids.length === 0) bucket = 'UNCLAIMED';
  else if (ruled.length === 0) bucket = 'UNRULED';
  else {
    const kinds = new Set(
      ruled.map((x) => (isComplete(x.ruling) ? 'c' : isRetire(x.ruling) ? 'r' : 'o'))
    );
    bucket =
      kinds.size > 1 ? 'MIXED' : kinds.has('c') ? 'COMPLETE' : kinds.has('r') ? 'RETIRE' : 'MIXED';
  }
  buckets[bucket].push({ file, ids, ruled });
}

const lines = (b) =>
  buckets[b].map(
    (e) =>
      `  ${e.file.replace(/^src\//, 'frontend/src/')}  ${e.ids.join(',') || '-'}${e.ruled.length ? ` [${e.ruled.map((x) => `${x.id}:${x.ruling}`).join(' ')}]` : ''}`
  );

console.log(
  `knip unused files: ${unused.length}  claimed by >=1 inventory row: ${joined}  ` +
    `inventory rows read: ${rows.length}  inventory at: ${INVENTORY_REF ?? 'working tree'}`
);
for (const b of ['UNCLAIMED', 'COMPLETE', 'RETIRE', 'UNRULED', 'MIXED']) {
  console.log(
    `${b.padEnd(10)} ${String(buckets[b].length).padStart(4)} files  ${String(bucketLines(b)).padStart(6)} lines`
  );
}
// Run the control before any printing, so `--only` (which produces a delete list) cannot emit a list
// the census never verified. `recallControl` is a hoisted declaration, defined below with its reason.
if (argv.includes('--control') && recallControl() === 0) {
  console.error('control found 0 inventory paths naming a file that exists — it checked nothing');
  process.exit(1);
}
if (ONLY) {
  if (!buckets[ONLY]) {
    console.error(`--only must be one of UNCLAIMED COMPLETE RETIRE UNRULED MIXED`);
    process.exit(2);
  }
  for (const l of lines(ONLY)) console.log(l);
} else {
  // The detail that decides the PR: the rows that keep a file, and the rulings that say so.
  for (const b of ['COMPLETE', 'RETIRE', 'UNRULED', 'MIXED'])
    for (const l of lines(b)) console.log(`  ${b} ${l.slice(2)}`);
}

// A census that joined nothing is not a result. knip's paths and the inventory's paths differ by the
// lane prefix, so a forgotten normalise would print UNCLAIMED for everything and read as a licence
// to delete the whole frontend.
// RECALL CONTROL (`--control`). `joined === 0` catches a join that matches nothing, but it cannot
// catch a join that matches MOST things and quietly drops the few that matter: 11 of 148 files is a
// plausible-looking rate whether the other 137 are genuinely unclaimed or the matcher lost the
// complete rows' files. The failure direction is asymmetric — a missed claim reads as UNCLAIMED,
// which is the deletable bucket — so the test has to run from the other end.
//
// It walks the inventory instead of knip: every backticked path whose final segment has an extension,
// taken straight out of the text rather than through parseInventory's column map or modules()' filter.
// It deliberately accepts BOTH spellings — `frontend/src/...` and a bare `src/...` — because the
// whole point is to catch the census normalising away a path it should have kept: a control that
// required the same prefix as the code under test would share its blind spot. Each spelling is tested
// against HEAD as written and as `frontend/`-prefixed, so a row that cites a path which no longer
// exists names nothing, and one that merely dropped the lane prefix still counts. Anything ground
// truth names that the index failed to return is a recall failure, and anything that is ALSO unused
// is a file this census would have deleted out from under a ruling.
function recallControl() {
  const named = new Set();
  for (const m of invText.matchAll(/`([^`\s]+)`/g)) {
    const p = m[1];
    if (/[\w-]\.\w+$/.test(p) && /(^|\/)src\//.test(p)) named.add(p);
  }
  const inHead = new Set(
    execFileSync('git', ['ls-tree', '-r', '--name-only', 'HEAD'], {
      encoding: 'utf8',
      maxBuffer: 1 << 28,
      cwd: REPO,
    })
      .split('\n')
      .filter(Boolean)
  );
  const groundTruth = new Map(); // repo path (frontend/-prefixed) -> row ids naming it
  for (const p of named) {
    const candidates = inHead.has(p) ? [p] : inHead.has(`frontend/${p}`) ? [`frontend/${p}`] : [];
    if (!candidates.length) continue; // a row citing a dead path names nothing
    const repoPath = candidates[0];
    const ids = rows.filter((r) => r.modules.includes(p)).map((r) => r.id);
    // Merge rather than set: two rows can spell the same file differently, and overwriting the
    // first row's ids would invent a recall miss that isn't one.
    if (ids.length)
      groundTruth.set(repoPath, [...new Set([...(groundTruth.get(repoPath) ?? []), ...ids])]);
  }
  const misses = [];
  for (const [p, ids] of groundTruth) {
    const indexed = claimants.get(p.replace(/^frontend\//, '')) ?? [];
    if (!ids.every((id) => indexed.includes(id))) misses.push([p, ids, indexed]);
  }
  const unusedSet = new Set(unused);
  const danger = misses.filter(([p]) => unusedSet.has(p.replace(/^frontend\//, '')));
  const overlap = [...groundTruth.keys()].filter((p) =>
    unusedSet.has(p.replace(/^frontend\//, ''))
  );
  console.log(
    `CONTROL inventory paths: ${named.size}  exist at HEAD and named by a row: ${groundTruth.size}  ` +
      `of those also knip-unused: ${overlap.length}  join misses: ${misses.length}  ` +
      `misses that are unused (would-be deletions): ${danger.length}`
  );
  for (const [p, ids, indexed] of danger)
    console.log(`  MISS ${p} rows=${ids.join(',')} index=${indexed.join(',') || 'EMPTY'}`);
  if (danger.length) {
    console.error(
      'the join lost files a row claims and knip calls unused — the census would delete them'
    );
    process.exit(1);
  }
  if (groundTruth.size && overlap.length !== joined) {
    console.error(
      `control sees ${overlap.length} claimed-unused files, census bucketed ${joined} — they must agree`
    );
    process.exit(1);
  }
  return groundTruth.size;
}

if (argv.includes('--control') && recallControl() === 0) {
  console.error('control found 0 inventory paths naming a file that exists — it checked nothing');
  process.exit(1);
}

if (unused.length === 0) {
  console.error('knip reported 0 unused files — nothing to census; this is not a pass');
  process.exit(1);
}
if (joined === 0) {
  console.error(
    '0 of the unused files matched any row modules cell — the join is broken, not empty'
  );
  process.exit(1);
}
