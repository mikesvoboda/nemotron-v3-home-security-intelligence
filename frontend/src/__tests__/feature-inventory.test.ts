/**
 * The feature inventory covers the product: F2.2, docs/uplevel/20-frontend.md.
 *
 * docs/reference/feature-inventory.md is the map the owner rules from in R2
 * (UR-13). A map that silently misses a page or an API call would let a feature
 * escape the ruling and survive Phase 3 by accident, so this gate checks the map
 * against the code instead of trusting it:
 *
 * - every route `App.tsx` declares appears in some row's surface;
 * - every request a file reachable from `src/main.tsx` can send (the same
 *   claims the endpoint-contract gate reads) appears in some row's API calls,
 *   or in "Client requests no feature reaches" with the file it sits in — an
 *   exported function in a live file that nothing in production imports
 *   (knip's unused exports; the PR carries that cross-check);
 * - every production file `src/main.tsx` cannot reach is either claimed by a row
 *   or listed under "Modules serving no feature" — and nothing reachable is
 *   listed there;
 * - every row carries a status from the README vocabulary and its evidence,
 *   and every `path:line` it cites exists (a reviewer reads the lines with
 *   scripts/feature-inventory-cites.mjs);
 * - knip is configured to see unreachable files (F2.2's knip clause);
 * - F1.1's known-missing list points at inventory rows, and those rows exist —
 *   or, for a call in dead code, at "Client requests no feature reaches".
 *
 * The readers live in scripts/feature-inventory-lib.mjs and the request scan is
 * scripts/api-contract-lib.mjs's, so the two gates cannot disagree about what
 * the client sends. Both load through a computed `import()`, as in
 * api-endpoint-contract.test.ts (no `allowJs`; jsdom breaks `import.meta.url`).
 */
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

import { beforeAll, describe, expect, it } from 'vitest';

import knownMissingData from './api-endpoint-contract-known-missing.json';

interface ApiCall {
  method: string | null;
  path: string;
}

interface Row {
  id: string;
  surface: string;
  routes: string[];
  apiCalls: ApiCall[];
  status: string;
  evidence: string;
  modules: string[];
}

interface Claim {
  kind: 'rest' | 'ws';
  path: string;
  method: string | null;
  file: string;
  line: number;
}

interface InventoryLib {
  parseInventory: (markdown: string) => {
    rows: Row[];
    noFeature: { module: string; lane: string }[];
    noFeatureCalls: (ApiCall & { fn: string; file: string })[];
  };
  appRoutes: (source: string) => string[];
  reachableFiles: (options: { root: string; entry: string }) => Set<string>;
  rowProblems: (row: Row) => string[];
  rowCites: (row: Row) => { file: string; line: number }[];
  callCovers: (call: ApiCall, claim: Claim) => boolean;
}

interface ContractLib {
  scanClient: (options: { root: string; srcDir: string }) => {
    claims: Claim[];
    files: string[];
  };
}

const FRONTEND = process.cwd();
const REPO = path.resolve(FRONTEND, '..');
const INVENTORY = path.join(REPO, 'docs/reference/feature-inventory.md');

let inv: ReturnType<InventoryLib['parseInventory']>;
let lib: InventoryLib;
let claims: Claim[];
let productionFiles: string[];
let reachable: Set<string>;

beforeAll(async () => {
  const load = (rel: string) => import(pathToFileURL(path.resolve(FRONTEND, rel)).href);
  lib = (await load('scripts/feature-inventory-lib.mjs')) as InventoryLib;
  const contract = (await load('scripts/api-contract-lib.mjs')) as ContractLib;

  inv = lib.parseInventory(fs.readFileSync(INVENTORY, 'utf8'));
  const scan = contract.scanClient({ root: FRONTEND, srcDir: 'src' });
  claims = scan.claims;
  productionFiles = scan.files;
  reachable = lib.reachableFiles({ root: FRONTEND, entry: 'src/main.tsx' });
}, 120_000);

const claimText = (c: Claim) =>
  `${c.kind === 'ws' ? 'WS' : (c.method ?? '?')} ${c.path}  (${c.file}:${c.line})`;

describe('feature inventory (F2.2)', () => {
  it('has rows, each with a unique id, and parses every row the file holds', () => {
    expect(inv.rows.length).toBeGreaterThan(0);
    const raw = fs.readFileSync(INVENTORY, 'utf8').match(/^\| F-\d{3,} \|/gm) ?? [];
    expect(inv.rows.length).toBe(raw.length);
    const ids = inv.rows.map((r) => r.id);
    expect(ids.filter((id, i) => ids.indexOf(id) !== i)).toEqual([]);
  });

  it('maps every route App.tsx declares to a row', () => {
    const app = fs.readFileSync(path.join(FRONTEND, 'src/App.tsx'), 'utf8');
    const routes = lib.appRoutes(app);
    expect(routes.length).toBeGreaterThan(30);
    const covered = new Set(inv.rows.flatMap((r) => r.routes));
    expect(routes.filter((r) => !covered.has(r))).toEqual([]);
  });

  it('maps every request a reachable file can send to a row', () => {
    const live = claims.filter((c) => reachable.has(c.file));
    // Bound the check's own reach: if reachability broke and found nothing, an
    // empty `live` would pass vacuously.
    expect(live.length).toBeGreaterThan(200);
    const calls = inv.rows.flatMap((r) => r.apiCalls);
    const uncovered = live.filter(
      (c) =>
        !calls.some((call) => lib.callCovers(call, c)) &&
        !inv.noFeatureCalls.some((n) => n.file === `frontend/${c.file}` && lib.callCovers(n, c))
    );
    expect(uncovered.map(claimText)).toEqual([]);
  });

  it('lists only requests that exist under "Client requests no feature reaches"', () => {
    const stale = inv.noFeatureCalls.filter(
      (n) => !claims.some((c) => n.file === `frontend/${c.file}` && lib.callCovers(n, c))
    );
    expect(stale.map((n) => `${n.method} ${n.path} (${n.file}, ${n.fn})`)).toEqual([]);
  });

  it('gives every row a status from the vocabulary, with evidence', () => {
    expect(inv.rows.flatMap((r) => lib.rowProblems(r))).toEqual([]);
  });

  it('accounts for every production file src/main.tsx cannot reach', () => {
    const unreachable = productionFiles.filter((f) => !reachable.has(f));
    expect(unreachable.length).toBeGreaterThan(0);
    const claimed = new Set([
      ...inv.rows.flatMap((r) => r.modules),
      ...inv.noFeature.map((m) => m.module),
    ]);
    expect(unreachable.filter((f) => !claimed.has(`frontend/${f}`))).toEqual([]);
  });

  it('lists no reachable frontend file as serving no feature', () => {
    const listed = inv.noFeature
      .filter((m) => m.module.startsWith('frontend/'))
      .map((m) => m.module.slice('frontend/'.length));
    expect(listed.filter((f) => reachable.has(f))).toEqual([]);
  });

  it('cites only lines that exist', () => {
    const problems = inv.rows.flatMap((r) =>
      lib.rowCites(r).flatMap(({ file, line }) => {
        const p = path.join(REPO, file);
        // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: repo-relative paths read from a committed doc
        if (!fs.existsSync(p)) return [`${r.id}: ${file} does not exist`];
        // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: as above
        const lines = fs.readFileSync(p, 'utf8').split('\n').length;
        return line <= lines ? [] : [`${r.id}: ${file}:${line} is past the end (${lines} lines)`];
      })
    );
    expect(problems).toEqual([]);
  });

  it('names only modules that exist', () => {
    const named = [...inv.rows.flatMap((r) => r.modules), ...inv.noFeature.map((m) => m.module)];
    // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: repo-relative paths read from a committed doc
    expect(named.filter((m) => !fs.existsSync(path.join(REPO, m)))).toEqual([]);
  });
});

describe('knip sees unreachable files (F2.2)', () => {
  const knip = JSON.parse(fs.readFileSync(path.join(FRONTEND, 'knip.json'), 'utf8')) as {
    entry: string[];
    ignore: string[];
    rules: Record<string, string>;
    vitest?: unknown;
    playwright?: unknown;
  };

  it('enters only through src/main.tsx, never through tests', () => {
    expect(knip.entry).toEqual(['src/main.tsx!']);
    // A deleted plugin key would let knip auto-enable the plugin and its test entries.
    expect((knip.vitest as { entry?: unknown }).entry).toEqual([]);
    expect((knip.playwright as { entry?: unknown }).entry).toEqual([]);
  });

  it('checks exports', () => {
    expect(knip.rules.exports).toBe('error');
  });

  it('ignores no file that is gone', () => {
    const literal = knip.ignore.filter((g) => !/[*{]/.test(g));
    // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: paths read from the committed knip.json
    expect(literal.filter((f) => !fs.existsSync(path.join(FRONTEND, f)))).toEqual([]);
  });
});

describe("F1.1's known-missing list points at inventory rows (F2.2)", () => {
  const entries = (knownMissingData as { entries: { path: string; next: string }[] }).entries;

  it('names a row id in every entry, or lists its request as reaching no feature', () => {
    const ids = new Set(inv.rows.map((r) => r.id));
    const problems = entries.flatMap((e) => {
      const named = e.next.match(/F-\d{3,}/g) ?? [];
      if (named.length === 0) {
        // A call in dead code is no feature's gap: the entry says so, and the
        // inventory's "Client requests no feature reaches" table holds the path.
        const deadCode =
          e.next.includes('Client requests no feature reaches') &&
          inv.noFeatureCalls.some((n) =>
            lib.callCovers(
              { ...n, method: null },
              { kind: 'rest', method: null, path: e.path, file: '', line: 0 }
            )
          );
        return deadCode ? [] : [`${e.path}: next names no inventory row`];
      }
      return named.filter((id) => !ids.has(id)).map((id) => `${e.path}: ${id} is not a row`);
    });
    expect(problems).toEqual([]);
  });

  it("lists each entry's path in the API calls of the row it names", () => {
    const byId = new Map(inv.rows.map((r) => [r.id, r]));
    const problems = entries.flatMap((e) =>
      (e.next.match(/F-\d{3,}/g) ?? []).flatMap((id) => {
        const row = byId.get(id);
        if (!row) return [];
        const hit = row.apiCalls.some((call) =>
          lib.callCovers(
            { ...call, method: null },
            { kind: 'rest', method: null, path: e.path, file: '', line: 0 }
          )
        );
        return hit ? [] : [`${id} does not list ${e.path}`];
      })
    );
    expect(problems).toEqual([]);
  });
});
