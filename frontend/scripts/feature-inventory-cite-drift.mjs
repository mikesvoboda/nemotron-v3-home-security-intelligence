#!/usr/bin/env node
// feature-inventory-cite-drift.mjs — check that a `path:line` cite still lands on the
// text it named before a move, across a base ref.
//
//   node scripts/feature-inventory-cite-drift.mjs --base 9238161a0
//   node scripts/feature-inventory-cite-drift.mjs --base 9238161a0 --inventory-ref 9238161a0
//   node scripts/feature-inventory-cite-drift.mjs --base <ref> --target-ref <ref>
//
// WHY THIS EXISTS. The F2.2 gate (src/__tests__/feature-inventory.test.ts) judges a cite by
// existence and range only: the named file exists, the line number is within it. A merge that
// moves code therefore passes that gate while stranding evidence two ways. One way it sees —
// a cited file deleted out from under the row. The way it cannot see is a cite that shifts and
// stays in range: green, and pointing at unrelated code. #7241 (ruling 148 §1, folding 11 golden
// area harnesses into one tests/golden/harness.ts) produced exactly both, so the re-anchor was
// driven by this stricter read: group every inventory cite by `rowId|file`, then require the
// TARGET line's text to equal the BASE line's text. A cite is accepted only if it still names
// what it originally named, not merely something.
//
// The second form above is the control, and it is the load-bearing one: an instrument that
// prints `0 drift` is indistinguishable from one that checked nothing, so point it at the
// broken state (the inventory ref from before the repair) and require it to report the shift
// and the dead target. The corpus counts print on every run for the same reason — an empty
// scan must read as an empty scan, never as a pass.
//
// Contract rule 3 (UR-10): a package's evidence instruments live in the repo. This file exists
// because #7241's cite census was first run from /tmp, where it cannot be re-run by a reader.
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { parseInventory, rowCites, lineCount } from './feature-inventory-lib.mjs';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const INVENTORY = 'docs/reference/feature-inventory.md';

const argv = process.argv.slice(2);
const flag = (name) => {
  const i = argv.indexOf(name);
  return i === -1 ? null : argv[i + 1];
};
const BASE = flag('--base');
const INVENTORY_REF = flag('--inventory-ref'); // judge an inventory other than the target's (the control)
const TARGET_REF = flag('--target-ref'); // null => the working tree

if (!BASE) {
  console.error(
    'usage: feature-inventory-cite-drift.mjs --base <ref> [--inventory-ref <ref>] [--target-ref <ref>]'
  );
  process.exit(2);
}

// Read a file at a ref, or from the working tree when ref is null. A missing file returns null
// rather than throwing, because "the cite points at a file this merge deleted" is a finding this
// tool reports, not an error it aborts on.
const readAt = (ref, file) => {
  try {
    return ref
      ? execFileSync('git', ['show', `${ref}:${file}`], {
          encoding: 'utf8',
          maxBuffer: 1 << 28,
          cwd: REPO,
        })
      : fs.readFileSync(path.join(REPO, file), 'utf8');
  } catch {
    return null;
  }
};
const textAt = (ref, file, line) => {
  const txt = cacheGet(ref, file);
  if (txt === null) return null;
  const lines = txt.split('\n');
  // `lineCount`, not `lines.length`: the split yields a trailing empty element on every
  // newline-terminated file, so indexing by it would print a blank line for a cite just past the
  // end and let line 0 index lines[-1]. Same reasoning as feature-inventory-cites.mjs.
  if (line < 1 || line > lineCount(txt)) return null;
  return (lines[line - 1] ?? '').trim();
};
const cache = new Map();
const cacheGet = (ref, file) => {
  const k = `${ref ?? 'WORKTREE'}\u0000${file}`;
  if (!cache.has(k)) cache.set(k, readAt(ref, file));
  return cache.get(k);
};

// Which files the change touched: a cite in a row whose target file was untouched cannot have
// moved, so it is out of scope here (and this tool stays quiet on the 1,500-odd cites it must
// not re-litigate).
const changedFiles = new Set(
  execFileSync('git', ['diff', '--name-status', '--format=', BASE, TARGET_REF ?? 'HEAD'], {
    encoding: 'utf8',
    cwd: REPO,
  })
    .trim()
    .split('\n')
    .filter(Boolean)
    .map((l) => l.split('\t').pop())
);

const citesOf = (txt) => {
  const out = [];
  for (const row of parseInventory(txt).rows)
    for (const c of rowCites(row)) out.push({ id: row.id, ...c });
  return out;
};
// Keyed by rowId|file, order of occurrence preserved, so the i-th cite of one key at base is
// paired with the i-th at target — the pairing a re-anchor edit preserves.
const group = (list) => {
  const m = new Map();
  for (const c of list) {
    const k = `${c.id}|${c.file}`;
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(c.line);
  }
  return m;
};

const targetInventoryText = INVENTORY_REF
  ? readAt(INVENTORY_REF, INVENTORY)
  : fs.readFileSync(path.join(REPO, INVENTORY), 'utf8');
const baseInventoryText = readAt(BASE, INVENTORY);
if (targetInventoryText === null || baseInventoryText === null) {
  console.error('cannot read the inventory at one of the given refs');
  process.exit(2);
}
const gTarget = group(citesOf(targetInventoryText));
const gBase = group(citesOf(baseInventoryText));
const inventoryRows = parseInventory(targetInventoryText).rows.length;

let checked = 0;
let same = 0;
let pairsConsidered = 0;
const drift = [];
const dead = [];
for (const [key, targetLines] of gTarget) {
  const [id, file] = key.split('|');
  const baseLines = gBase.get(key);
  if (!baseLines) continue; // a cite this change introduced — nothing at base to pair it with
  if (!changedFiles.has(file)) continue; // untouched target: the cite cannot have moved
  pairsConsidered++;
  if (cacheGet(TARGET_REF, file) === null) {
    dead.push(`${id} ${file} — cited file is absent at the target`);
    continue;
  }
  const n = Math.min(targetLines.length, baseLines.length);
  if (targetLines.length !== baseLines.length) {
    drift.push(
      `${id} ${file} — cite count changed ${baseLines.length} -> ${targetLines.length}; compared ${n}`
    );
  }
  for (let i = 0; i < n; i++) {
    const tt = textAt(TARGET_REF, file, targetLines[i]);
    const bt = textAt(BASE, file, baseLines[i]);
    checked++;
    if (tt === null || bt === null) {
      drift.push(`${id} ${file}: base :${baseLines[i]} -> target :${targetLines[i]} MISSING LINE`);
      continue;
    }
    if (tt === bt) same++;
    else
      drift.push(
        `${id} ${file}: base :${baseLines[i]} != target :${targetLines[i]}\n    base| ${bt.slice(0, 110)}\n    target| ${tt.slice(0, 110)}`
      );
  }
}

console.log(
  `inventory rows: ${inventoryRows}  cite keys in changed files: ${pairsConsidered}  ` +
    `lines compared: ${checked}  same-text: ${same}  DRIFT: ${drift.length}  dead-target: ${dead.length}`
);
for (const d of drift) console.log('  DRIFT', d);
for (const g of dead) console.log('  DEAD ', g);
// A scan that compared nothing is not a pass. Exit non-zero so a caller cannot mistake it for one.
if (checked === 0) {
  console.error('compared 0 lines — nothing was checked; this is not a pass');
  process.exit(1);
}
process.exit(drift.length + dead.length ? 1 : 0);
