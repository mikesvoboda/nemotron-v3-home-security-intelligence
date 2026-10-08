/**
 * Unit tests for the endpoint-contract scanner (scripts/api-contract-lib.mjs).
 *
 * The gate (api-endpoint-contract.test.ts) asks the whole client a question;
 * these tests pin the rules the answer depends on, against fixtures, so that a
 * change to the scanner says *which rule moved*. The rules are the substance of
 * F1.1 — a scan that quietly stopped reading, say, the per-domain clients would
 * still report "0 unlisted" and the gate would go green on a shrinking set of
 * claims. Only the "scans the client, not a fixture" bounds guard against that
 * in the gate, and a bound is coarse by design.
 *
 * Living in src/__tests__ rather than beside the script as a `node --test` file
 * is deliberate: `.github/workflows/ci.yml`'s hot-file rule says a new check
 * gets its own job or its own workflow file, and a sibling `node --test` script
 * would need one — a test no job runs is decoration. Vitest's default include
 * already picks this up in the sharded `frontend-tests` job, and that job fails
 * on a real exit code. This directory is documented (src/__tests__/AGENTS.md) as
 * the home for build-tool and CI-configuration tests, which is what the scanner
 * is. Import is dynamic for the reason given in api-endpoint-contract.test.ts:
 * tsconfig has `include: ["src"]` and no `allowJs`.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

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

interface Scan {
  claims: Claim[];
  dynamic: { file: string; line: number; reason: string }[];
  unresolved: { file: string; line: number; reason: string }[];
  opaqueMethod: { kind: string; path: string; file: string; line: number; reason: string }[];
  nonApi: { file: string; line: number; path: string }[];
  files: string[];
}

interface KnownMissingEntry {
  path: string;
  method?: string;
}

interface Mismatch extends Claim {
  nearest: string | null;
  why: string | null;
  methodMismatch?: boolean;
}

interface Lib {
  normalisePath: (raw: string) => string;
  segments: (p: string) => string[];
  compareMethod: (method: string | null, declared: Set<string> | undefined) => string | null;
  explainMatch: (clientPath: string, specPath: string) => string | null;
  closestSpecPath: (clientPath: string, specPaths: string[]) => string | null;
  allows: (entry: KnownMissingEntry, mismatch: Mismatch) => boolean;
  entryIsLive: (entry: KnownMissingEntry, claims: Claim[]) => boolean;
  scanClient: (options: { root: string; srcDir: string }) => Scan;
  loadSpec: (specFile: string) => { paths: string[]; methods: Map<string, Set<string>> };
  compare: (options: {
    claims: Claim[];
    restPaths: string[];
    wsRoutes: string[];
    restMethods?: Map<string, Set<string>>;
  }) => { matched: Claim[]; mismatches: Mismatch[] };
}

let lib: Lib;
let fixtureRoot: string;

beforeAll(async () => {
  const url = pathToFileURL(path.resolve(process.cwd(), 'scripts/api-contract-lib.mjs')).href;
  lib = (await import(url)) as Lib;
  fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'api-contract-fixture-'));
});

afterAll(() => {
  fs.rmSync(fixtureRoot, { recursive: true, force: true });
});

/** Write one throwaway client file into a clean fixture tree and scan just it. */
function scanSource(name: string, lines: string[]): Scan {
  const dir = path.join(fixtureRoot, 'src');
  // Emptied each time: the assertions below compare whole claim arrays, so a
  // fixture left by the previous test would read as a claim of this one.
  fs.rmSync(dir, { recursive: true, force: true });
  // The scanner reads a client off disk, so a fixture has to exist as a file.
  // `security/detect-non-literal-fs-filename` is a taint heuristic, and here the
  // taint never leaves this process: fixtureRoot is this file's own mkdtemp and
  // every `name` below is a literal.
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: path under this test's own mkdtemp
  fs.mkdirSync(dir, { recursive: true });
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: path under this test's own mkdtemp
  fs.writeFileSync(path.join(dir, name), `${lines.join('\n')}\n`);
  return lib.scanClient({ root: fixtureRoot, srcDir: 'src' });
}

describe('normalisePath', () => {
  it('reduces a URL to the path the backend routes on', () => {
    expect(lib.normalisePath('/api/cameras/1/anomalies?days=7#top')).toBe(
      '/api/cameras/1/anomalies'
    );
    expect(lib.normalisePath('/api/cameras/{camera_id}/baseline/')).toBe(
      '/api/cameras/{}/baseline'
    );
    expect(lib.normalisePath('/api//cameras///x')).toBe('/api/cameras/x');
    expect(lib.normalisePath('')).toBe('/');
  });

  it('spells every path parameter the same way, whatever it is named', () => {
    expect(lib.normalisePath('/api/cameras/{camera_id}/x/{other}')).toBe('/api/cameras/{}/x/{}');
    // A client hole and a spec parameter must line up, or matching compares words
    // that are both wildcards as if they were literals.
    expect(lib.normalisePath('/api/cameras/{}/x/{}')).toBe(
      lib.normalisePath('/api/cameras/{id}/x/{y}')
    );
  });
});

describe('explainMatch', () => {
  it('matches a client hole to any concrete backend segment', () => {
    expect(
      lib.explainMatch('/api/cameras/{}/baseline', '/api/cameras/{camera_id}/baseline')
    ).toBeNull();
    expect(
      lib.explainMatch('/api/cameras/{}/baseline', '/api/cameras/front-door/baseline')
    ).toBeNull();
  });

  it('rejects a client literal where the backend declares a parameter', () => {
    // The D2 shape, one step further: the client invents a word in a slot that
    // varies. Matching it would let a client that hardcodes `/onvif` where the
    // route is `/{camera_id}` pass, which is a different bug, not this route.
    expect(lib.explainMatch('/api/cameras/anomalies', '/api/cameras/{camera_id}')).toMatch(
      'sends the literal "anomalies" where the backend declares a parameter'
    );
  });

  it('names the first segment that disagrees', () => {
    expect(lib.explainMatch('/api/zones/anomalies', '/api/cameras/anomalies')).toMatch(
      'segment 2 is "zones"'
    );
    expect(lib.explainMatch('/api/cameras/1/anomalies', '/api/cameras/1/baseline')).toMatch(
      'segment 4 is "anomalies"'
    );
    expect(lib.explainMatch('/api/cameras/{}/anomalies', '/api/system/anomaly-config')).toMatch(
      'has 3 segments'
    );
  });

  it('lets a FastAPI path converter swallow trailing client segments', () => {
    expect(lib.explainMatch('/api/static/a/b/c', '/api/static/{rest:path}')).toBeNull();
  });
});

describe('closestSpecPath', () => {
  const POOL = [
    '/api/cameras/{camera_id}/baseline/anomalies',
    '/api/cameras/{camera_id}',
    '/api/cameras/onvif/discover',
    '/api/action-events/{event_id}',
  ];

  it('prefers a route one segment longer over one of the same length', () => {
    // A length-first metric picks /api/cameras/onvif/discover (same length, two
    // wrong words) over the real route. The hint line is the most useful part of
    // the failure message, so it has to be the answer and not almost the answer.
    expect(lib.closestSpecPath('/api/cameras/{}/anomalies', POOL)).toBe(
      '/api/cameras/{camera_id}/baseline/anomalies'
    );
  });

  it('breaks a one-edit tie toward shared literal segments', () => {
    // Both are one edit from the claim; the deeper route shares "anomalies".
    expect(
      lib.closestSpecPath('/api/cameras/{}/anomalies', ['/api/cameras/{camera_id}', POOL[0]])
    ).toBe(POOL[0]);
  });
});

describe('scanClient', () => {
  it('follows a path through a local const into fetch', () => {
    const scan = scanSource('const-binding.ts', [
      "const BASE = '/api/household';",
      'export function load(id: string) {',
      '  const url = `${BASE}/members/${id}/detections`;',
      '  return fetch(url);',
      '}',
      '',
    ]);
    expect(scan.claims.map((c) => c.path)).toEqual(['/api/household/members/{}/detections']);
  });

  it('completes a per-domain client from the literals its callers pass', () => {
    // The shape every per-domain client in this repo uses. Reading the hole as a
    // path parameter instead of a caller suffix collapses all of this to
    // /api/ai-audit{}, which matches nothing and hides every route the client
    // reaches.
    const scan = scanSource('forwarder.ts', [
      'async function fetchAiAuditApi<T>(endpoint: string): Promise<T> {',
      '  const url = `/api/ai-audit${endpoint}`;',
      '  const res = await fetch(url);',
      '  return res.json() as Promise<T>;',
      '}',
      'export const stats = () => fetchAiAuditApi("/stats");',
      'export const events = (id: string) => fetchAiAuditApi(`/events/${id}`);',
      'export const unreachable = () => fetchAiAuditApi("/never-called-from-here");',
      '',
    ]);
    expect(scan.claims.map((c) => c.path)).toEqual([
      '/api/ai-audit/stats',
      '/api/ai-audit/events/{}',
      '/api/ai-audit/never-called-from-here',
    ]);
    // Recorded at the call site, with the forwarder named: the reader has to be
    // able to find the fetch that will carry the request.
    expect(scan.claims[0]).toMatchObject({
      file: 'src/forwarder.ts',
      via: 'fetchAiAuditApi() suffix',
    });
  });

  it('reports a forwarder no call site ever completes', () => {
    const scan = scanSource('dead-forwarder.ts', [
      'function fetchAlone(endpoint: string) {',
      '  return fetch(`/api/alone${endpoint}`);',
      '}',
      '',
    ]);
    expect(scan.claims).toEqual([]);
    expect(scan.dynamic.map((d) => d.reason).join('\n')).toMatch(
      'no call site passes a literal one'
    );
  });

  it('keeps two same-named constants in different scopes apart', () => {
    // A cache keyed by name alone gave the second function the first one's base,
    // so /api/prompts/history was reported as /api/ai-audit/history.
    const scan = scanSource('shadowed.ts', [
      'function fetchA(endpoint: string) {',
      '  const url = `/api/ai-audit${endpoint}`;',
      '  return fetch(url);',
      '}',
      'function fetchB(endpoint: string) {',
      '  const url = `/api/prompts${endpoint}`;',
      '  return fetch(url);',
      '}',
      'export const a = () => fetchA("/stats");',
      'export const b = () => fetchB("/history");',
      '',
    ]);
    expect(scan.claims.map((c) => c.path).sort()).toEqual([
      '/api/ai-audit/stats',
      '/api/prompts/history',
    ]);
  });

  it('treats both arms of a query-string ternary as claims', () => {
    const scan = scanSource('query-ternary.ts', [
      'export function list(query?: string) {',
      "  const url = `/api/events${query ? `?${query}` : ''}`;",
      '  return fetch(url);',
      '}',
      '',
    ]);
    expect(scan.claims.map((c) => c.path)).toEqual(['/api/events']);
  });

  it('does not invent a segment where a query string begins', () => {
    // `${params}` here is `?a=1&b=2`, never a path segment: claiming
    // /api/system/services{} would make the gate cry wolf about a fine path.
    const scan = scanSource('query-suffix.ts', [
      'export function services(params: string) {',
      '  return fetch(`/api/system/services${params}`);',
      '}',
      '',
    ]);
    expect(scan.claims.map((c) => c.path)).toEqual(['/api/system/services']);
  });

  it('reads a WebSocket path out of new WebSocket(url)', () => {
    const scan = scanSource('socket.ts', [
      'export function open() {',
      "  return new WebSocket('ws://localhost:8000/ws/events');",
      '}',
      '',
    ]);
    // The host is our own origin; the path is the contract, so scheme+host come off.
    expect(scan.claims).toEqual([
      expect.objectContaining({ kind: 'ws', path: '/ws/events', via: 'literal-or-const' }),
    ]);
  });

  it('checks an EventSource stream against the HTTP spec, not the WS surface', () => {
    const scan = scanSource('sse.ts', [
      'export function stream(batchId: string) {',
      '  return new EventSource(`/api/events/analyze/${batchId}/stream`);',
      '}',
      '',
    ]);
    expect(scan.claims.map((c) => [c.kind, c.path])).toEqual([
      ['rest', '/api/events/analyze/{}/stream'],
    ]);
  });

  it('reports a prefix it cannot resolve instead of skipping it', () => {
    // "0 unlisted" only means something while the scan read the paths; an
    // unresolvable prefix is a claim it did not make, so it has to be visible.
    const scan = scanSource('unknown-prefix.ts', [
      'export function load(baseUrl: string) {',
      '  return fetch(`${baseUrl}/api/thing`);',
      '}',
      '',
    ]);
    expect(scan.claims).toEqual([]);
    expect(scan.unresolved.map((u) => u.reason)).toEqual([
      'prefix ${baseUrl} is not statically resolvable',
    ]);
  });

  it('ignores strings that are not request URLs', () => {
    // Reading every literal would flag route-prefetch callbacks and guard
    // predicates: code that never issues a request.
    const scan = scanSource('not-a-request.ts', [
      "export const isApiPath = (p: string) => p.startsWith('/api/definitely-not-called');",
      'export function prefetch(route: string) {',
      '  return import(`./routes/${route}`);',
      '}',
      '',
    ]);
    expect(scan.claims).toEqual([]);
  });

  it('routes a same-origin path outside /api to its own list', () => {
    // /health and friends are real backend routes mounted at the root; calling
    // them /api/… is the defect, and a same-origin asset is not this contract.
    const scan = scanSource('non-api.ts', [
      'export function probe() {',
      "  return fetch('/health');",
      '}',
      '',
    ]);
    expect(scan.claims).toEqual([]);
    expect(scan.nonApi).toEqual([expect.objectContaining({ path: '/health' })]);
  });

  it('reports an absolute URL instead of dropping it', () => {
    // An absolute URL leaves this contract: it may name a CDN, and its path is
    // deliberately not checked against our spec. But dropping it silently is the
    // bug class the gate exists to catch — `fetch('http://localhost:8000/api/x')`
    // points at a real backend, reads as fine to a reviewer, and would have
    // disappeared from every bucket while the gate stayed green.
    const scan = scanSource('absolute.ts', [
      'export function probe() {',
      "  return fetch('http://localhost:8000/api/system/health');",
      '}',
      "export const cdn = () => fetch('https://cdn.example.com/api/logo.png');",
      '',
    ]);
    expect(scan.claims).toEqual([]);
    expect(scan.unresolved.map((u) => u.reason)).toEqual([
      'absolute URL leaves this contract: http://localhost:8000/api/system/health',
      'absolute URL leaves this contract: https://cdn.example.com/api/logo.png',
    ]);
  });

  it('reports a WebSocket URL that carries no path', () => {
    // Sibling branch of the rule above: the ws strip exists because
    // buildWebSocketOptions() returns an absolute URL for our own origin, so a
    // ws:// that has no path after the host is not a claim either — and it is
    // not a code shape worth losing.
    const scan = scanSource('ws-no-path.ts', [
      "export const socket = () => new WebSocket('ws://localhost:8000');",
      '',
    ]);
    expect(scan.claims).toEqual([]);
    expect(scan.unresolved.map((u) => u.reason)).toEqual([
      'WebSocket URL carries no path: ws://localhost:8000',
    ]);
  });
});

describe('method rules', () => {
  it('holds a claim to a literal verb and reports a missing one as GET', () => {
    const scan = scanSource('verbs.ts', [
      "export function create(body: string) { return fetchApi('/api/zones', { method: 'POST', body }); }",
      "export function probe() { return fetch('/api/system/health'); }",
      '',
    ]);
    expect(scan.claims.map((c) => [c.path, c.method, c.methodKnown])).toEqual([
      ['/api/zones', 'POST', true],
      ['/api/system/health', 'GET', true],
    ]);
    // Nothing to report: both verbs are facts about the code, not guesses.
    expect(scan.opaqueMethod).toEqual([]);
  });

  it('reports a verb behind a pass-through options bag instead of guessing GET', () => {
    // The decisive case for `methodKnown`. `fetchApi('/api/cameras', options)`
    // really does send GET today, but the verb was chosen by whoever passed
    // `options`; recording 'GET' and holding the call to it would report a
    // `DELETE` through that wrapper as an undeclared GET at a live path.
    const scan = scanSource('passthrough.ts', [
      'export function cameras(options?: RequestInit) {',
      "  return fetchApi('/api/cameras', options);",
      '}',
      '',
    ]);
    expect(scan.claims).toEqual([
      expect.objectContaining({ path: '/api/cameras', method: 'GET', methodKnown: false }),
    ]);
    expect(scan.opaqueMethod).toEqual([
      expect.objectContaining({ path: '/api/cameras', reason: expect.stringContaining('options') }),
    ]);
  });

  it('lets the call site that spells a verb out win over one that hides it', () => {
    // Parse order puts the opaque site first; if it won, this path would silently
    // leave the method check. The upgrade also moves the report to the literal
    // site, because that is the file a reader has to open.
    const scan = scanSource('upgrade.ts', [
      'export function viaOptions(options?: RequestInit) {',
      "  return fetchApi('/api/cameras', options);",
      '}',
      "export const viaLiteral = () => fetchApi('/api/cameras', { method: 'GET' });",
      '',
    ]);
    expect(scan.claims).toEqual([
      expect.objectContaining({
        path: '/api/cameras',
        method: 'GET',
        methodKnown: true,
        // The literal call site (line 4), not the pass-through one that parsed
        // first (line 2).
        line: 4,
      }),
    ]);
    expect(scan.opaqueMethod).toEqual([]);
  });

  it('gives a WebSocket no method and an EventSource GET', () => {
    // `new WebSocket(url, protocols)` takes a protocol list, not an options bag,
    // and `EventSourceInit` has no method field: treating either like `fetch`
    // would invent an opaque verb at every socket and SSE stream.
    const ws = scanSource('sock.ts', [
      "export const open = (protocols: string[]) => new WebSocket('ws://h/ws/events', protocols);",
      '',
    ]);
    expect(ws.claims[0]).toMatchObject({ kind: 'ws', method: null, methodKnown: true });
    expect(ws.opaqueMethod).toEqual([]);

    const sse = scanSource('sse.ts', [
      "export const stream = () => new EventSource('/api/events/analyze/1/stream');",
      '',
    ]);
    expect(sse.claims[0]).toMatchObject({ kind: 'rest', method: 'GET', methodKnown: true });
    expect(sse.opaqueMethod).toEqual([]);
  });

  it('comparesMethod only against verbs the backend declares', () => {
    expect(lib.compareMethod('GET', new Set(['GET', 'DELETE']))).toBeNull();
    expect(lib.compareMethod('GET', new Set(['POST']))).toMatch('the backend declares POST');
    // No declared set at all (a spec without verbs) asks nothing.
    expect(lib.compareMethod('GET', undefined)).toBeNull();
  });
});

describe('compare', () => {
  const claim = (kind: 'rest' | 'ws', p: string, method = 'GET'): Claim => ({
    kind,
    path: lib.normalisePath(p),
    raw: p,
    method: kind === 'ws' ? null : method,
    methodKnown: true,
    file: 'x.ts',
    line: 1,
    via: 'literal-or-const',
  });

  it('checks each kind of claim against its own source of truth', () => {
    const { matched, mismatches } = lib.compare({
      claims: [claim('rest', '/api/cameras'), claim('ws', '/ws/events')],
      restPaths: ['/api/cameras'],
      wsRoutes: ['/ws/events'],
    });
    expect(matched.map((c) => c.path)).toEqual(['/api/cameras', '/ws/events']);
    expect(mismatches).toEqual([]);
  });

  it('does not let a REST route satisfy a WebSocket claim', () => {
    // openapi.json has no /ws paths at all, so the pools cannot be merged: a
    // merged pool would either hide a dead socket or excuse a missing route.
    const { mismatches } = lib.compare({
      claims: [claim('ws', '/ws/events')],
      restPaths: ['/ws/events'],
      wsRoutes: [],
    });
    expect(mismatches[0]?.nearest).toBeNull();
  });

  it('flags a verb the backend does not declare at a path it does serve', () => {
    // The second shape of D2: the route exists, so nothing about the path is
    // wrong, and the client learns about it from a 405 at runtime.
    const methods = new Map([['/api/prompts/history/{}', new Set(['POST'])]]);
    const { matched, mismatches } = lib.compare({
      claims: [claim('rest', '/api/prompts/history/{model}', 'GET')],
      restPaths: ['/api/prompts/history/{version_id}'],
      wsRoutes: [],
      restMethods: methods,
    });
    expect(matched).toEqual([]);
    expect(mismatches[0]).toMatchObject({
      methodMismatch: true,
      method: 'GET',
      // The path that exists is the finding, so `nearest` is it rather than a
      // near miss a reader would go looking for.
      nearest: '/api/prompts/history/{}',
      why: expect.stringMatching(/^GET is not declared there — the backend declares POST$/),
    });
  });

  it('leaves an unknown verb unchecked rather than failing it', () => {
    const methods = new Map([['/api/cameras', new Set(['POST'])]]);
    const opaque = { ...claim('rest', '/api/cameras'), methodKnown: false };
    const { matched, mismatches } = lib.compare({
      claims: [opaque],
      restPaths: ['/api/cameras'],
      wsRoutes: [],
      restMethods: methods,
    });
    expect(mismatches).toEqual([]);
    expect(matched).toEqual([opaque]);
  });

  it('stays path-only when no verb map is supplied', () => {
    const { matched } = lib.compare({
      claims: [claim('rest', '/api/cameras', 'DELETE')],
      restPaths: ['/api/cameras'],
      wsRoutes: [],
    });
    expect(matched.length).toBe(1);
  });
});

describe('known-missing allowances', () => {
  const pathGap = { path: '/api/zones/trust-violations', methodMismatch: false } as never;
  const verbGap = {
    path: '/api/debug/recordings',
    method: 'DELETE',
    methodMismatch: true,
  } as never;

  it('never lets a path-only entry shelter a wrong verb', () => {
    // The D2 entries were written before verbs were checked. If `{ path }` matched
    // any finding at that path, a wrong-verb call added tomorrow at an allowed
    // path would be excused by an entry nobody re-reads.
    expect(lib.allows({ path: '/api/debug/recordings' }, verbGap)).toBe(false);
    expect(lib.allows({ path: '/api/zones/trust-violations' }, pathGap)).toBe(true);
  });

  it('scopes a method entry to its verb and to method findings', () => {
    expect(lib.allows({ path: '/api/debug/recordings', method: 'DELETE' }, verbGap)).toBe(true);
    expect(lib.allows({ path: '/api/debug/recordings', method: 'delete' }, verbGap)).toBe(true);
    expect(lib.allows({ path: '/api/debug/recordings', method: 'PUT' }, verbGap)).toBe(false);
    expect(lib.allows({ path: '/api/zones/trust-violations', method: 'GET' }, pathGap)).toBe(false);
  });

  it('goes stale when the verb it describes is fixed, even if the path lives on', () => {
    const stillPosted = [
      { kind: 'rest', path: '/api/debug/recordings', method: 'GET', methodKnown: true },
    ] as never;
    expect(lib.entryIsLive({ path: '/api/debug/recordings', method: 'DELETE' }, stillPosted)).toBe(
      false
    );
    // A path-only entry stays live while anything is called there: the gap is the
    // missing route, not one request.
    expect(lib.entryIsLive({ path: '/api/debug/recordings' }, stillPosted)).toBe(true);
  });
});
