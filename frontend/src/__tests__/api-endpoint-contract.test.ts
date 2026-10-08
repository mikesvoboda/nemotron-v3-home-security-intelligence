/**
 * Endpoint truth: every path the client can put on the wire exists on the backend.
 *
 * F1.1, docs/uplevel/00-audit.md §3 D2. D2 is the defect where the frontend calls
 * endpoints the backend never served — `/api/cameras/{id}/anomalies` while the
 * route is `/api/cameras/{id}/baseline/anomalies` — and stayed green for years
 * because every layer mocked the API. No runtime test can see that: a mock
 * answers whatever the caller asked for. The check has to compare the client's
 * paths with the backend's real surface, which is what this file does.
 *
 * Mechanism, decided here rather than inherited (see the PR body for the
 * reasoning): a static scan of request-URL positions, not a compile-time
 * `keyof paths` on `fetchApi`. A typed client would catch less than this does —
 * roughly 155 paths go through `fetchApi`, while the audit's "~24 hooks calling
 * fetch directly" is really ~162 raw `fetch(` sites across ~74 files, and F1.1
 * names those as in scope. Folding them in is FB.1's consolidation package, not
 * F1.1's check.
 *
 * The scan and the verdict live in scripts/api-contract-lib.mjs, which the
 * CLI scripts/api-contract-scan.mjs calls too, so a shell run and this gate
 * cannot report different answers. That library is read through a dynamic
 * import rather than a static one: tsconfig.json has `include: ["src"]` and no
 * `allowJs`, so a static `import … from '../../scripts/….mjs'` would fail
 * `npm run typecheck` — and the point of a contract test is that it fails for
 * the right reason. A computed specifier is invisible to `tsc`, so the file
 * stays type-clean. `import.meta.url` is useless here (jsdom makes it an
 * `http:` URL, which `import()` refuses), hence `process.cwd()`: CI runs Vitest
 * from frontend/ after `cd frontend` (.github/workflows/ci.yml), which is also
 * where `npm test` runs.
 */
import path from 'node:path';
import { pathToFileURL } from 'node:url';

import { beforeAll, describe, expect, it } from 'vitest';

import knownMissingData from './api-endpoint-contract-known-missing.json';

interface Claim {
  kind: 'rest' | 'ws';
  path: string;
  raw: string;
  method: string | null;
  methodKnown: boolean;
  file: string;
  line: number;
  via: string;
}

interface Mismatch extends Claim {
  nearest: string | null;
  why: string | null;
  methodMismatch?: boolean;
}

interface KnownMissing {
  path: string;
  /** Omit to allow the whole path; set to allow one verb at a served path. */
  method?: string;
  calledFrom: string;
  cited: string;
  backend: string;
  next: string;
}

interface Audit {
  scan: {
    files: string[];
    claims: Claim[];
    dynamic: { file: string; line: number; reason: string }[];
    unresolved: { file: string; line: number; reason: string }[];
    opaqueMethod: { kind: string; path: string; file: string; line: number; reason: string }[];
    nonApi: { file: string; line: number; path: string }[];
  };
  restPaths: string[];
  /** Paths where the spec declares at least one verb — see the bound in test 1. */
  restMethodPaths: number;
  wsRoutes: string[];
  matched: Claim[];
  mismatches: Mismatch[];
  listed: Mismatch[];
  unlisted: Mismatch[];
  stale: KnownMissing[];
}

let audit: Audit;

beforeAll(async () => {
  const libUrl = pathToFileURL(path.resolve(process.cwd(), 'scripts/api-contract-lib.mjs')).href;
  const lib = (await import(libUrl)) as {
    audit: (options: {
      root: string;
      srcDir: string;
      specFile: string;
      backendDir: string;
      knownMissing: KnownMissing[];
    }) => Audit;
  };

  const repo = path.resolve(process.cwd(), '..');
  audit = lib.audit({
    root: process.cwd(),
    srcDir: 'src',
    // The committed spec is the contract; OPENAPI_SPEC lets a regeneration run
    // check against a fresh dump without editing this file.
    specFile: process.env.OPENAPI_SPEC ?? path.join(repo, 'docs/openapi.json'),
    backendDir: path.join(repo, 'backend'),
    knownMissing: (knownMissingData as { entries: KnownMissing[] }).entries,
  });
}, 120_000);

/** A failure line a reader can act on: where, what, and the nearest real route. */
function describeMismatch(m: Mismatch) {
  // `WS /ws/x` for a socket (a WebSocket has no verb), `GET /api/x` for HTTP, and
  // a `(method)` marker where the path is fine and only the verb is wrong.
  const subject = m.kind === 'ws' ? `WS ${m.path}` : `${m.method} ${m.path}`;
  return [
    `${subject}${m.methodMismatch ? '  (method)' : ''}`,
    `  (${m.file}:${m.line}${m.via ? ` via ${m.via}` : ''})`,
    // A method mismatch carries `nearest` = the path that does exist, so the usual
    // "nearest backend path" wording would read as a second, different route. The
    // finding is that this path is real and the verb is not.
    m.methodMismatch
      ? `    ${m.path} IS served; ${m.why}`
      : `    nearest backend path ${m.nearest ?? '(none)'} — ${m.why ?? 'no comparable path exists'}`,
    m.kind === 'rest'
      ? '    fix the call site, or add an entry to api-endpoint-contract-known-missing.json citing where the gap is ruled on'
      : '    the WebSocket surface is backend route decorators, not openapi.json',
  ].join('\n');
}

describe('endpoint contract (D2)', () => {
  it('scans the client, not a fixture', () => {
    // Guards against the scan silently matching nothing, which is how a contract
    // test becomes decoration: green because it found no claims.
    expect(audit.scan.files.length).toBeGreaterThan(800);
    expect(audit.scan.claims.length).toBeGreaterThan(300);
    expect(audit.restPaths.length).toBeGreaterThan(300);
    expect(audit.matched.length).toBeGreaterThan(300);
    // And the same guard for the verb half of the check: if a regenerated
    // docs/openapi.json ever ships paths without operations, "no method
    // mismatches" goes green while `compare` compares nothing. This is the only
    // thing that notices.
    expect(audit.restMethodPaths).toBeGreaterThan(300);
    expect(audit.scan.claims.filter((c) => c.methodKnown && c.method).length).toBeGreaterThan(250);
  });

  it('finds no client request the backend does not serve', () => {
    // Both shapes of D2: a path with no route, and a path served under a verb the
    // client does not use (which answers 405, not 404).
    expect(
      audit.unlisted.map(describeMismatch).join('\n\n'),
      `${audit.unlisted.length} client request(s) match no backend route+method and are not on the known-missing list`
    ).toBe('');
  });

  it('keeps the known-missing list honest', () => {
    // An allowance whose call site has gone is a gap that was quietly fixed and
    // left open on paper; a list that never shrinks is how this gate rots.
    expect(
      audit.stale
        .map(
          (e) =>
            `${e.method ? `${e.method} ` : ''}${e.path}  (${e.calledFrom}) — no matching client call site remains`
        )
        .join('\n'),
      `${audit.stale.length} known-missing entr(ies) no longer have a call site: delete them`
    ).toBe('');
  });

  it('reports the URLs it could not check instead of skipping them', () => {
    // Not an assertion about the codebase — a bound on the scan's own blind
    // spots. A prefix the scan cannot resolve is a claim it did not make, so
    // "0 unlisted" means something only while this number stays small.
    expect(
      audit.scan.unresolved.map((u) => `${u.file}:${u.line}  ${u.reason}`).join('\n'),
      `${audit.scan.unresolved.length} request URL(s) sit behind a prefix the scan cannot resolve`
    ).toMatchInlineSnapshot(`
      "src/hooks/useAudioNotifications.ts:220  prefix \${soundsPath} is not statically resolvable
      src/services/alertsApi.ts:120  prefix \${baseUrl} is not statically resolvable
      src/services/alertsApi.ts:165  prefix \${baseUrl} is not statically resolvable
      src/services/authApi.ts:146  prefix \${baseUrl} is not statically resolvable
      src/services/authApi.ts:176  prefix \${baseUrl} is not statically resolvable
      src/services/authApi.ts:207  prefix \${baseUrl} is not statically resolvable
      src/services/authApi.ts:236  prefix \${baseUrl} is not statically resolvable
      src/services/authApi.ts:267  prefix \${baseUrl} is not statically resolvable"
    `);
  });

  it('reports the verbs it could not check instead of assuming GET', () => {
    // The method half has its own blind spot: a verb behind a pass-through
    // options bag. Every entry below is the same shape — an exported wrapper that
    // takes `options?: { signal?: AbortSignal }` and forwards it — and in each
    // case the *type* says only a signal rides along. That is not evidence this
    // scan accepts: D2 survived precisely because compile-time layers said the
    // call was fine, so the scanner reads what the code does, and what it does is
    // send a verb it picked up somewhere else. These claims still had their path
    // checked, so this is not a hole in the path gate; it is the list of requests
    // whose 405-vs-200 question this scan cannot answer. Snapshotted so a new
    // pass-through wrapper shows up as a diff here rather than as lost coverage.
    expect(
      audit.scan.opaqueMethod.map((o) => `${o.path}  ${o.file}:${o.line}  ${o.reason}`).join('\n'),
      `${audit.scan.opaqueMethod.length} claim(s) send a verb the scan cannot read`
    ).toMatchInlineSnapshot(`
      "/api/cameras  src/services/api.ts:1400  options passed by name: options
      /api/system/health  src/services/api.ts:1999  options passed by name: options
      /api/system/health/full  src/services/api.ts:2074  options passed by name: options
      /api/system/gpu  src/services/api.ts:2084  options passed by name: options
      /api/system/health/websocket  src/services/api.ts:2160  options passed by name: options
      /api/system/health/live  src/services/api.ts:2183  options passed by name: options
      /api/events  src/services/api.ts:2289  options passed by name: options
      /api/events/stats  src/services/api.ts:2324  options passed by name: options
      /api/events/clusters  src/services/api.ts:2371  options passed by name: options
      /api/events/deleted  src/services/api.ts:2554  options passed by name: options
      /api/events/search  src/services/api.ts:3819  options passed by name: options
      /api/audit  src/services/api.ts:4552  options passed by name: options
      /api/entities/matches/{}  src/services/api.ts:5869  options passed by name: options
      /api/logs  src/services/api.ts:9013  options passed by name: options
      /api/reid/similar/{}  src/services/api.ts:9126  options passed by name: options"
    `);
  });
});
