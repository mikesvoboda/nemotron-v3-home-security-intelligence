#!/usr/bin/env node
// feature-inventory-cites.mjs — print every `path:line` the feature inventory
// cites, beside the line it points at today.
//
//   node scripts/feature-inventory-cites.mjs            # every row
//   node scripts/feature-inventory-cites.mjs F-081      # some rows
//
// The F2.2 gate (src/__tests__/feature-inventory.test.ts) checks that each cited
// line exists; only a reader can check that it still says what the evidence
// claims. This prints both side by side for that read. Run from frontend/ or the
// repo root.
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import { parseInventory, rowCites } from './feature-inventory-lib.mjs';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const inventory = path.join(REPO, 'docs/reference/feature-inventory.md');
const wanted = new Set(process.argv.slice(2));

const { rows } = parseInventory(fs.readFileSync(inventory, 'utf8'));
const cache = new Map();
const lineOf = (file, n) => {
  if (!cache.has(file)) {
    const p = path.join(REPO, file);
    // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: repo-relative path read from the committed inventory
    cache.set(file, fs.existsSync(p) ? fs.readFileSync(p, 'utf8').split('\n') : null);
  }
  const lines = cache.get(file);
  if (!lines) return '<file missing>';
  return n <= lines.length ? lines[n - 1].trim() : '<past end of file>';
};

for (const row of rows) {
  if (wanted.size && !wanted.has(row.id)) continue;
  for (const { file, line } of rowCites(row)) {
    console.log(`${row.id}  ${file}:${line}\n        ${lineOf(file, line)}`);
  }
}
