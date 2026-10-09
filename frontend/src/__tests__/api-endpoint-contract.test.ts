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
 * fetch directly" is really ~162 raw `fetch(` sites across ~61 files, and F1.1
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

/** A known-missing entry the audit found dead, with the half of the gap that went. */
interface StaleEntry extends KnownMissing {
  staleReason: string;
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
  stale: StaleEntry[];
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
    // An allowance is dead from either side: its call site has gone, or the
    // backend now serves what it says is missing (the direction most entries'
    // `next` fields point). `staleReason` says which, so a reader is sent to the
    // right code. A list that never shrinks is how this gate rots.
    expect(
      audit.stale
        .map(
          (e) => `${e.method ? `${e.method} ` : ''}${e.path}  (${e.calledFrom}) — ${e.staleReason}`
        )
        .join('\n'),
      `${audit.stale.length} known-missing entr(ies) no longer describe an open gap: delete them`
    ).toBe('');
  });

  it('reports the URLs it could not check instead of skipping them', () => {
    // Not an assertion about the codebase — a bound on the scan's own blind
    // spots. An unresolved URL is a claim the scan did not make, so "0 unlisted"
    // means something only while this list stays small. Two shapes land here: a
    // `${baseUrl}` prefix with no file-local value, and an absolute URL pointing
    // at some host other than this backend (see lib's record()).
    expect(
      audit.scan.unresolved.map((u) => `${u.file}:${u.line}  ${u.reason}`).join('\n'),
      `${audit.scan.unresolved.length} request URL(s) the scan cannot pin to this backend`
    ).toMatchInlineSnapshot(`
      "src/hooks/useAudioNotifications.ts:220  prefix \${soundsPath} is not statically resolvable
      src/services/alertsApi.ts:120  prefix \${baseUrl} is not statically resolvable
      src/services/alertsApi.ts:165  prefix \${baseUrl} is not statically resolvable
      src/services/authApi.ts:156  prefix \${baseUrl} is not statically resolvable
      src/services/authApi.ts:186  prefix \${baseUrl} is not statically resolvable
      src/services/authApi.ts:217  prefix \${baseUrl} is not statically resolvable
      src/services/authApi.ts:246  prefix \${baseUrl} is not statically resolvable
      src/services/authApi.ts:277  prefix \${baseUrl} is not statically resolvable"
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
      "/api/cameras  src/services/api.ts:1454  options passed by name: options
      /api/system/health  src/services/api.ts:2053  options passed by name: options
      /api/system/health/full  src/services/api.ts:2128  options passed by name: options
      /api/system/gpu  src/services/api.ts:2138  options passed by name: options
      /api/system/health/websocket  src/services/api.ts:2214  options passed by name: options
      /api/system/health/live  src/services/api.ts:2237  options passed by name: options
      /api/events  src/services/api.ts:2343  options passed by name: options
      /api/events/stats  src/services/api.ts:2378  options passed by name: options
      /api/events/clusters  src/services/api.ts:2425  options passed by name: options
      /api/events/deleted  src/services/api.ts:2608  options passed by name: options
      /api/events/search  src/services/api.ts:3873  options passed by name: options
      /api/audit  src/services/api.ts:4606  options passed by name: options
      /api/entities  src/services/api.ts:5827  options passed by name: options
      /api/entities/matches/{}  src/services/api.ts:5923  options passed by name: options
      /api/logs  src/services/api.ts:9067  options passed by name: options
      /api/reid/similar/{}  src/services/api.ts:9180  options passed by name: options"
    `);
  });

  it('reports the URLs it never claimed, and the paths outside the contract', () => {
    // The last two blind-spot buckets, pinned for the same reason as the two
    // above: the CLI prints them, but a printed list rots silently — a new
    // `fetch(url.toString())` site, or a same-origin call to a non-`/api` path,
    // is a claim this scan never made, and "0 unlisted" cannot be read without
    // these lists staying small and recognizable. `dynamic` counts constructs,
    // not lines: useWebSocketStatus.ts:138 is one line holding two `new
    // WebSocket(url, …)` constructs (the protocols ternary), so 25 entries over
    // 24 positions is the honest shape, recorded here rather than tidied away.
    // `nonApi` is the empty list with teeth: it fails the moment anything calls
    // a same-origin path this contract does not check.
    expect(
      audit.scan.dynamic.map((d) => `${d.file}:${d.line}  ${d.reason}`).join('\n'),
      `${audit.scan.dynamic.length} URL position(s) with no statically knowable path`
    ).toMatchInlineSnapshot(`
      "src/hooks/useWebSocketStatus.ts:138  "url" is not a file-local constant
      src/hooks/useWebSocketStatus.ts:138  "url" is not a file-local constant
      src/hooks/useZoneHouseholdConfig.ts:236  built at runtime: url.toString()
      src/hooks/webSocketManager.ts:503  "url" is not a file-local constant
      src/hooks/webSocketManager.ts:504  "url" is not a file-local constant
      src/services/aiAuditApi.ts:391  suffix for fetchPromptsApi() at src/services/aiAuditApi.ts:155: not a literal path
      src/services/api.ts:1606  built at runtime: getCameraSnapshotUrl(cameraId)
      src/services/api.ts:1678  built at runtime: getCameraSnapshotUrl(cameraId)
      src/services/api.ts:3390  built at runtime: isVideo
      src/services/backupApi.ts:150  suffix for fetchBackupApi() at src/services/backupApi.ts:120: not a literal path
      src/services/backupApi.ts:172  suffix for fetchBackupApi() at src/services/backupApi.ts:120: not a literal path
      src/services/detectorApi.ts:149  built at runtime: url.toString()
      src/services/errorReporting.ts:113  built at runtime: config.endpoint
      src/services/interceptors.ts:325  "url" is not a file-local constant
      src/services/llmReasoningApi.ts:233  built at runtime: url.toString()
      src/services/logger.ts:180  built at runtime: this.config.batchEndpoint
      src/services/logger.ts:198  built at runtime: this.config.endpoint
      src/services/logger.ts:263  built at runtime: this.config.batchEndpoint || this.config.endpoint
      src/services/plateReadsApi.ts:175  suffix for fetchPlateReadsApi() at src/services/plateReadsApi.ts:107: not a literal path
      src/services/promptManagementApi.ts:143  suffix for fetchPromptApi() at src/services/promptManagementApi.ts:115: not a literal path
      src/services/rum.ts:210  built at runtime: this.config.endpoint
      src/services/rum.ts:262  built at runtime: this.config.endpoint
      src/services/scheduledReportsApi.ts:154  suffix for fetchScheduledReportsApi() at src/services/scheduledReportsApi.ts:124: not a literal path
      src/services/scheduledReportsApi.ts:195  suffix for fetchScheduledReportsApi() at src/services/scheduledReportsApi.ts:124: not a literal path
      src/services/webhookApi.ts:166  suffix for fetchWebhookApi() at src/services/webhookApi.ts:134: not a literal path
      src/services/webhookApi.ts:185  suffix for fetchWebhookApi() at src/services/webhookApi.ts:134: not a literal path"
    `);
    expect(
      audit.scan.nonApi.map((n) => `${n.file}:${n.line}  ${n.path}`).join('\n'),
      `${audit.scan.nonApi.length} same-origin path(s) outside /api this contract does not check`
    ).toMatchInlineSnapshot(`""`);
  });
});
