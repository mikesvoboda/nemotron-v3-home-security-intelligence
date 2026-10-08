#!/usr/bin/env node
// api-contract-scan.mjs — report client paths that the backend does not serve.
//
//   node scripts/api-contract-scan.mjs            # human-readable summary
//   node scripts/api-contract-scan.mjs --json     # machine-readable
//
// Exit status: 0 when every claim matches a committed backend path or is listed
// in src/__tests__/api-endpoint-contract-known-missing.json; 1 otherwise. The
// gate itself is the Vitest test (src/__tests__/api-endpoint-contract.test.ts),
// which CI already runs in the sharded `frontend-tests` job; this CLI is the
// same check from a shell, for a PR body or a pre-push run.
//
// See scripts/api-contract-lib.mjs for how claims are extracted and matched.
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import { audit } from './api-contract-lib.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '..');
const REPO = path.resolve(FRONTEND, '..');

const specFile = process.env.OPENAPI_SPEC ?? path.join(REPO, 'docs/openapi.json');
const knownMissingFile = path.join(
  FRONTEND,
  'src/__tests__/api-endpoint-contract-known-missing.json'
);

function loadKnownMissing() {
  if (!fs.existsSync(knownMissingFile)) return [];
  return JSON.parse(fs.readFileSync(knownMissingFile, 'utf8')).entries ?? [];
}

/**
 * Run the contract scan.
 *
 * This is a thin argument-presenter for `audit()` and nothing more. It used to
 * re-implement the listed/unlisted/stale partitioning here, which meant a change
 * to the rules in one place left the other computing a different answer — the
 * exact failure mode the shared `audit()` exists to prevent. The CI gate calls
 * `audit()` directly; if you are tempted to sort findings out down here, that is
 * the signal the rule belongs in the library.
 */
export function runScan() {
  const known = loadKnownMissing();
  const result = audit({
    root: FRONTEND,
    srcDir: 'src',
    specFile,
    backendDir: path.join(REPO, 'backend'),
    knownMissing: known,
  });
  return { ...result, known };
}

const { scan, restPaths, wsRoutes, matched, mismatches, listed, unlisted, stale } = runScan();

/** `GET /api/x` for a REST claim, bare `/ws/x` for a WebSocket (which has no verb). */
const named = (m) => `${m.method ? `${m.method} ` : ''}${m.path}`;

/** The verb the scanner actually held a claim to, for the summary line. */
const verbsKnown = scan.claims.filter((c) => c.methodKnown && c.method).length;

const asJson = process.argv.includes('--json');
const result = {
  specFile: path.relative(REPO, specFile),
  scannedFiles: scan.files.length,
  restSpecPaths: restPaths.length,
  wsRoutes: wsRoutes.length,
  claims: scan.claims.length,
  claimsWithKnownMethod: verbsKnown,
  matched: matched.length,
  listedKnownMissing: listed.length,
  unlisted,
  methodMismatches: mismatches.filter((m) => m.methodMismatch).length,
  dynamic: scan.dynamic,
  unresolved: scan.unresolved,
  opaqueMethod: scan.opaqueMethod,
  nonApi: scan.nonApi,
  staleKnownMissing: stale.map((e) => (e.method ? `${e.method} ${e.path}` : e.path)),
};

if (asJson) {
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
} else {
  console.log(
    `scanned ${scan.files.length} client files against ${restPaths.length} OpenAPI paths and ${wsRoutes.length} WebSocket routes`
  );
  console.log(
    `${scan.claims.length} client claims (${verbsKnown} with a verb the scanner can hold to): ${matched.length} match, ${listed.length} on the known-missing list, ${unlisted.length} unlisted`
  );
  for (const m of unlisted) {
    const where = m.via === 'literal-or-const' || m.via === 'template' ? '' : `  (${m.via})`;
    // A method mismatch names the path it *does* exist at, so printing "nearest
    // backend path" over it would read as a second, different route.
    const hint = m.methodMismatch
      ? `  the path exists; ${m.why}`
      : `  nearest backend path ${m.nearest ?? '(none)'} — ${m.why}`;
    console.log(
      `\nUNLISTED ${m.kind === 'ws' ? 'WS' : m.method}${m.methodMismatch ? ' (method)' : ''} ${m.path}\n  ${m.file}:${m.line}${where}\n${hint}`
    );
  }
  for (const s of stale)
    console.log(
      `\nSTALE known-missing entry: ${s.method ? `${s.method} ` : ''}${s.path} (no matching client call site remains)`
    );

  console.log(
    `\nreported, not checked: ${scan.dynamic.length} URLs built at runtime, ${scan.unresolved.length} unresolvable prefixes, ${scan.opaqueMethod.length} verbs behind a pass-through options bag, ${scan.nonApi.length} same-origin paths outside /api`
  );
  if (scan.opaqueMethod.length) {
    console.log('\nopaque verbs (path checked, method not; see --json for all):');
    for (const o of scan.opaqueMethod.slice(0, 12))
      console.log(`  ${named(o)}  ${o.file}:${o.line}  ${o.reason}`);
    if (scan.opaqueMethod.length > 12) console.log(`  ... ${scan.opaqueMethod.length - 12} more`);
  }
  if (scan.unresolved.length) {
    console.log('\nunresolved prefixes (each is a coverage hole, listed so it stays visible):');
    for (const u of scan.unresolved) console.log(`  ${u.file}:${u.line}  ${u.reason}`);
  }
  if (scan.dynamic.length) {
    console.log(`\ndynamic URLs (${scan.dynamic.length}; see --json for all):`);
    for (const d of scan.dynamic.slice(0, 12)) console.log(`  ${d.file}:${d.line}  ${d.reason}`);
    if (scan.dynamic.length > 12) console.log(`  ... ${scan.dynamic.length - 12} more`);
  }
}

process.exit(unlisted.length || stale.length ? 1 : 0);
