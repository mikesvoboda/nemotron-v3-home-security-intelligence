// api-contract-lib.mjs — read every HTTP/WS path the frontend client can send.
//
// Part of F1.1 (Endpoint truth, docs/uplevel/00-audit.md §3 D2). D2 survived for
// so long because every layer mocked the API, so nothing ever compared a client
// path with the backend's real surface. This library is that comparison: it
// parses the client with the TypeScript compiler and reports the paths the
// client can actually put on the wire, so
// src/__tests__/api-endpoint-contract.test.ts can assert each one exists in
// docs/openapi.json (REST) or in a backend route decorator (WebSocket).
//
// What a future editor needs to know before changing the rules here:
//
// 1. Only positions that can become a request URL are read: the first argument
//    of a known fetch-ish call, followed through local `const` bindings, and one
//    hop across functions that forward a parameter into that URL — which is how
//    `fetchWithTimeout(url, …)` and the `fetch(url)` bodies of the per-domain
//    clients (`fetchAiAuditApi`, `fetchAuditApi`, `fetchBaselineConfigApi`,
//    `fetchPromptManagementApi`, …) stay covered. Reading *every* string literal
//    instead would flag `isValidEndpoint()`'s `startsWith('/api/')` guards and
//    the `as CameraEndpoint` returns in src/types/api-endpoints.ts: code that
//    never issues a request.
// 2. A `${...}` hole becomes a `{}` segment, because the OpenAPI document spells
//    a path parameter the same way. A hole that *starts* a query string, or that
//    statically yields either `?…` or `` (the `query ? `?${query}` : ''` idiom),
//    truncates the claim instead of becoming a segment — otherwise
//    `/api/system/services${params}` would claim `/api/system/services{}` and
//    the gate would cry wolf about a path that is fine.
// 3. A hole whose value is a parameter of the enclosing function is a *suffix*,
//    not a path parameter: the claim is completed from the literals call sites
//    pass in. Failing to do this collapses `/api/ai-audit${endpoint}` to
//    `/api/ai-audit{}`, which matches nothing and hides every route that client
//    actually reaches.
// 4. `const` initialisers resolve in definition order, so
//    `const url = `${BASE_URL}/api/household/members/${id}/detections`` is
//    checkable through `fetch(url)`. `BASE_URL` resolves to the `|| ''` fallback
//    of its own `import.meta.env` definition, i.e. same-origin. A prefix that
//    cannot be pinned down makes the claim *reported*, never silently skipped —
//    and so does an absolute URL, whose host may be a CDN but may equally be
//    `http://localhost:8000`, which is this backend wearing a URL.
// 5. Matching is literal-exact after parameter normalisation (see
//    `explainMatch`): a spec route with a concrete segment where the client has a
//    hole is a mismatch even when both sides have the same number of segments.
//    The one deliberate leniency is FastAPI's `{…:path}` catch-all, which may
//    swallow trailing client segments.
// 6. A claim carries a HTTP method too, and only a *literal* one is enforced.
//    A missing options object or an options literal with no `method` is `GET`,
//    because that is what `fetch` and every wrapper here defaults to; an options
//    bag passed through by name is reported in `opaqueMethod` instead, since the
//    scanner cannot see which verb its caller put in it. Guessing `GET` there
//    would let a `DELETE` through a wrapper look like an undeclared `GET`.
import fs from 'node:fs';
import path from 'node:path';

import ts from 'typescript';

/**
 * Calls whose first argument is an HTTP path.
 *
 * `EventSource` belongs here, not with the WebSockets: server-sent events are an
 * ordinary `GET` on an ordinary route, so the SSE streams this client opens
 * (`/api/events/analyze/{batch_id}/stream`) are described by docs/openapi.json
 * and must be checked against it. A candidate pool of WebSocket decorators would
 * report every one of them as missing.
 *
 * Deliberately *not* included: `prefetch`, which in this client is
 * useRoutePrefetch's callback for a React Router route (`/settings`), not a
 * request — counting it would invent calls that never happen.
 */
export const FETCH_LIKE = new Set([
  'fetch',
  'fetchApi',
  'fetchWithTimeout',
  'fetchWithRetry',
  'EventSource',
]);

/** Calls whose first argument is a WebSocket path. */
export const WS_CALLS = new Set(['buildWebSocketOptions']);

/** Constructors (a `new` expression, not a call) whose first argument is a WebSocket path. */
export const WS_CONSTRUCTORS = new Set(['WebSocket']);

/** Files that never issue a real request: tests, mocks, generated types. */
const SKIP_PATH =
  /\.test\.tsx?$|\.d\.ts$|\.stories\.tsx?$|\/__tests__\/|\/__mocks__\/|\/mocks\/|\/mocks\b|\/test\/|\/test-utils\/|\/types\/generated\/|\/setup\//;

/** Local names whose value is a query string rather than a path segment. */
const QUERY_EXPR =
  /^(query|string|queryString|qs|params|queryParams|queryConfig|searchParams|urlSearchParams|search|body)$/;

/**
 * Placeholder for a hole whose value a *caller* supplies, so
 * `` `${BASE_URL}/api/ai-audit${endpoint}` `` reads as
 * `<suffix>/api/ai-audit<suffix>`. A claim never keeps one: a text carrying it
 * is either completed from a call-site literal or reported. Printable and
 * URL-illegal, so it stays visible in a failure message instead of reading as an
 * empty segment.
 */
const SUFFIX = '<suffix>';

const MAX_HOPS = 4;

function listSourceFiles(srcDir) {
  const out = [];
  const walk = (dir) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const p = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (!/node_modules|dist|coverage|\.vite/.test(entry.name)) walk(p);
      } else if (/\.tsx?$/.test(entry.name) && !SKIP_PATH.test(p)) {
        out.push(p);
      }
    }
  };
  walk(srcDir);
  return out.sort();
}

/** Normalise an OpenAPI path or a client URL into a comparable form. */
export function normalisePath(raw) {
  let p = String(raw).split(/[?#]/)[0] ?? '';
  p = p.replace(/\{[^{}]*\}/g, '{}');
  p = p.replace(/\/{2,}/g, '/');
  if (p.length > 1) p = p.replace(/\/+$/, '');
  return p || '/';
}

/** Segments of a normalised path. */
export function segments(p) {
  return normalisePath(p).split('/').filter(Boolean);
}

/**
 * Does the backend serve `method` at `declared`?
 *
 * `null` means yes; anything else is the reason it does not, worded for a failure
 * message. `declared` is the set of HTTP methods the spec declares for the path
 * the claim already matched, so this is asked only where the path exists — the
 * two halves of "every method and path the client calls exists in
 * docs/openapi.json" are checked one after the other, and a path mismatch
 * already says everything a method mismatch would.
 */
export function compareMethod(method, declared) {
  if (!method || !declared?.size) return null;
  return declared.has(method) ? null : `the backend declares ${[...declared].sort().join(', ')}`;
}

/**
 * Can a client path be satisfied by a spec path?
 *
 * `null` means they match; anything else is the reason they do not. Segments
 * align one to one. `{}` on the client accepts any spec segment; a concrete
 * client segment must equal a concrete spec segment — a spec *parameter* does
 * not accept a client literal, because then the client is inventing a literal
 * where the backend expects a varying value. That is exactly the shape of D2:
 * the client sends `/anomalies` where the route is `/{camera_id}/baseline/anomalies`.
 */
export function explainMatch(clientPath, specPath) {
  const c = segments(clientPath);
  const s = segments(specPath);
  const catchAll = /\{[^}]*:path\}/.test(specPath);
  if (!catchAll && c.length !== s.length)
    return `has ${s.length} segments, client sends ${c.length}`;
  for (let i = 0; i < s.length; i++) {
    const cs = c[i];
    if (cs === undefined) return 'the client path is shorter';
    if (cs === '{}') continue;
    if (s[i] === '{}') {
      if (catchAll && i === s.length - 1) return null;
      return `segment ${i + 1} sends the literal "${cs}" where the backend declares a parameter`;
    }
    if (cs !== s[i]) return `segment ${i + 1} is "${cs}", the backend has "${s[i]}"`;
  }
  return null;
}

/**
 * The nearest spec path to a client path, for the failure message.
 *
 * An edit distance over segments, not a positional diff: the usual reason a
 * claim does not match is that one side has a segment the other lacks, and a
 * positional comparison misaligns everything after that point. Substituting a
 * word costs 1, inserting or deleting one 0.6, because "anomalies is in the wrong
 * slot" is nearly always really "there is an extra `baseline` slot". A parameter
 * on either side costs 0.1, not 0: both are wildcards, but a path that only lines
 * up thanks to wildcards is not the answer.
 *
 * Distance alone still ties, and pool order then decides — which ranked
 * `/api/cameras/{camera_id}`, one deletion away, level with
 * `/api/cameras/{camera_id}/baseline/anomalies`, the actual route. So the tie
 * goes to the path sharing the most literal segments, which is what a reader
 * wants anyway. A plain length penalty gets this wrong outright: it prefers
 * `/api/cameras/onvif/discover` — same length, two wrong words — over a route
 * that is otherwise identical. The hint is the most useful line in the failure.
 */
export function closestSpecPath(clientPath, specPaths) {
  const c = segments(clientPath);
  let best = null;
  let bestKey = null;
  for (const sp of specPaths) {
    const s = segments(sp);
    const distance = pathDistance(c, s);
    const overlap = literalOverlap(c, s);
    if (
      bestKey === null ||
      distance < bestKey.distance ||
      (distance === bestKey.distance && overlap > bestKey.overlap)
    ) {
      bestKey = { distance, overlap };
      best = sp;
    }
  }
  return best;
}

/** Segments that appear literally on both sides; parameters match nothing. */
function literalOverlap(a, b) {
  const bs = new Set(b.filter((x) => x !== '{}'));
  const shared = new Set(a.filter((x) => x !== '{}' && bs.has(x)));
  return shared.size;
}

/** Segment edit distance described in `closestSpecPath`. */
function pathDistance(a, b) {
  const EDIT = 0.6;
  const WILD = 0.1;
  const prev = new Array(b.length + 1);
  const cur = new Array(b.length + 1);
  for (let j = 0; j <= b.length; j++) prev[j] = j * EDIT;
  for (let i = 1; i <= a.length; i++) {
    cur[0] = i * EDIT;
    for (let j = 1; j <= b.length; j++) {
      const av = a[i - 1];
      const bv = b[j - 1];
      const cost = av === bv ? 0 : av === '{}' || bv === '{}' ? WILD : 1;
      cur[j] = Math.min(prev[j] + EDIT, cur[j - 1] + EDIT, prev[j - 1] + cost);
    }
    for (let j = 0; j <= b.length; j++) prev[j] = cur[j];
  }
  return prev[b.length];
}

function calleeName(call) {
  return call.expression.getText().split('.').pop();
}

/**
 * A WebSocket has no HTTP verb at all, so a `ws` claim carries no method to
 * compare. `known: true` because nothing is being hidden — there is simply no
 * second argument to read: `new WebSocket(url, protocols)` takes a protocol list,
 * and `EventSourceInit` has no `method` field either (SSE is always a GET).
 */
const NO_METHOD = { method: null, known: true };

/** `EventSource` is always a GET: the SSE spec gives `EventSourceInit` no method. */
const ALWAYS_GET = { method: 'GET', known: true };

/**
 * The method a request call sends, decided by which callee it is.
 *
 * A per-domain forwarder (`fetchAiAuditApi(endpoint, options)`) spreads its
 * caller's `options` into `fetch` without naming a method, so the call site's own
 * second argument is the verb that reaches the wire — which makes the call site
 * the right place to read it from for a suffix-completed claim too.
 */
function methodForCall(short, arg) {
  if (WS_CALLS.has(short) || WS_CONSTRUCTORS.has(short)) return NO_METHOD;
  if (short === 'EventSource') return ALWAYS_GET;
  return methodOfCall(arg);
}

/**
 * Read the HTTP method a request call sends, from its second argument.
 *
 * Returns `{ method, known }`. `known: true` means the value came from a string
 * literal in this call's own options object, so `compare` may hold the call to it.
 * `known: false` means the method is a *fact we cannot see*, and `reason` says
 * why; `method` is then the best guess (`'GET'`) for reporting only, never for a
 * verdict.
 *
 * Why `GET` is a sound default when the argument is missing or has no `method`
 * property: `fetch` itself defaults to `GET`, and each wrapper in this client
 * re-states that default before touching the network — `fetchApi`'s
 * `options?.method || 'GET'` (src/services/api.ts:1340) and `fetchWithRetry`'s
 * `options.method || 'GET'` (:1263) — while every per-domain client spreads its
 * caller's `options` into `fetch` verbatim without naming a `method` of its own.
 *
 * Why a pass-through bag is *not* defaulted to `GET`: at
 * `fetch(url, fetchOptions)` inside `fetchAiAuditApi` the verb was chosen by
 * whichever call site passed `fetchOptions`, and a `DELETE` guessed as `GET`
 * would report a route that exists as undeclared. The scanner reports the hole
 * instead of answering it. (Measured across src: 202 sites with no second
 * argument, 214 with a literal verb, 35 pass-through bags, 1 spread, 0 computed
 * or conditional methods — the reported list is small because the client's
 * convention is to spell the verb out at the call.)
 */
function methodOfCall(arg) {
  if (!arg) return { method: 'GET', known: true };
  // `as RequestInit` / `satisfies` wrappers are type-only; the value underneath is
  // what reaches fetch, so read through them.
  const inner =
    ts.isAsExpression(arg) || ts.isSatisfiesExpression(arg) || ts.isParenthesizedExpression(arg)
      ? arg.expression
      : arg;
  if (!ts.isObjectLiteralExpression(inner)) {
    const what = ts.isIdentifier(inner)
      ? `${inner.getText()}`
      : ts.isCallExpression(inner)
        ? `${inner.expression.getText()}()`
        : ts.SyntaxKind[inner.kind];
    return { method: 'GET', known: false, reason: `options passed by name: ${what}` };
  }
  let spread = false;
  for (const prop of inner.properties) {
    if (ts.isSpreadAssignment(prop)) spread = true;
    if (!ts.isPropertyAssignment(prop) || prop.name.getText() !== 'method') continue;
    const v = prop.initializer;
    if (ts.isStringLiteral(v) || ts.isNoSubstitutionTemplateLiteral(v)) {
      return { method: v.text.toUpperCase(), known: true };
    }
    // e.g. `method: config.method` — a variable the scanner would have to trace
    // through a non-request position, which invariant 1 rules out.
    return {
      method: 'GET',
      known: false,
      reason: `method is computed: ${v.getText().slice(0, 40)}`,
    };
  }
  if (spread) {
    return { method: 'GET', known: false, reason: 'method may come from a spread' };
  }
  return { method: 'GET', known: true };
}

/** A `new WebSocket(url)` counts as a call for our purposes: its first argument is a URL. */
function requestCall(node) {
  return (ts.isCallExpression(node) || ts.isNewExpression(node)) && node.arguments.length > 0
    ? node
    : null;
}

function firstLine(text) {
  const one = String(text).split('\n')[0].trim();
  return one.length > 78 ? `${one.slice(0, 75)}...` : one;
}

/**
 * A param-aware URL-expression reader for one source file.
 *
 * One resolver plays both roles — reading a request URL and expanding the local
 * constants it is built from — because they have to see the same thing. An older
 * version kept two, with the constant resolver hard-wired to "no parameters",
 * and that is exactly why `` const url = `${BASE_URL}/api/ai-audit${endpoint}` ``
 * lost its suffix on the way to `fetch(url)`: inside the constant, `endpoint` was
 * no longer recognisable as a parameter, so it became a `{}` segment and the
 * per-domain client's routes all collapsed to `/api/ai-audit{}`.
 */
function makeReader(sourceFile) {
  // Every `const`/`let` with an initialiser, keyed by name and kept in source
  // order, because the same name is declared in several scopes of one file:
  // aiAuditApi.ts has `const url` in both fetchAiAuditApi and fetchPromptsApi.
  // Resolving by name alone returned whichever came first and read the other
  // client's base URL, so the lookup below is positional and lexical.
  const declarations = new Map(); // name -> [{ node, init }]
  const collect = (n) => {
    if (ts.isVariableDeclaration(n) && n.initializer && ts.isIdentifier(n.name)) {
      const name = n.name.getText();
      if (!declarations.has(name)) declarations.set(name, []);
      declarations.get(name).push({ node: n, init: n.initializer });
    }
    ts.forEachChild(n, collect);
  };
  collect(sourceFile);

  const cache = new Map(); // "declPos|params|depth" -> { ok, text, suffix }
  const chainCache = new Map(); // node -> outermost-first list of enclosing functions

  /** Enclosing functions of a node, outermost first — the scope chain. */
  function functionChain(node) {
    if (chainCache.has(node)) return chainCache.get(node);
    const chain = [];
    for (let n = node; n; n = n.parent) {
      if (ts.isFunctionDeclaration(n) || ts.isArrowFunction(n) || ts.isFunctionExpression(n))
        chain.unshift(n);
    }
    chainCache.set(node, chain);
    return chain;
  }

  /**
   * The declaration `refNode` would see: the nearest one in scope that precedes
   * it, preferring one whose scope encloses the reference over a sibling scope's
   * same-named declaration.
   */
  function lookup(name, refNode) {
    const candidates = declarations.get(name);
    if (!candidates) return null;
    const refPos = refNode.getStart(sourceFile);
    const refChain = new Set(functionChain(refNode));
    let best = null;
    for (const c of candidates) {
      const pos = c.node.getStart(sourceFile);
      if (pos > refPos) continue; // declared after the reference: out of scope
      const declChain = functionChain(c.node);
      const visible = declChain.every((f) => refChain.has(f));
      if (visible && (!best || pos > best.node.getStart(sourceFile))) best = c;
    }
    if (best) return best;
    // Nothing visible precedes it; take the last preceding declaration anyway
    // rather than losing the claim, since this is a text scanner, not a checker.
    let fallback = null;
    for (const c of candidates) {
      const pos = c.node.getStart(sourceFile);
      if (pos <= refPos && (!fallback || pos > fallback.node.getStart(sourceFile))) fallback = c;
    }
    return fallback ?? candidates[0] ?? null;
  }

  /**
   * Value of the identifier or expression `expr`, as seen from `refNode`.
   *
   * `null` means "cannot be pinned down", which is why callers test with
   * `!== null` rather than truthiness: `''` is a real and common answer — it is
   * what same-origin looks like.
   */
  function resolve(expr, params, depth = 0, refNode = sourceFile) {
    const r = read(expr, params, depth, refNode);
    return r.ok ? r.text : null;
  }

  function read(expr, params, depth, refNode) {
    const text = typeof expr === 'string' ? expr.trim() : expr.getText().trim();
    if (/^import\.meta\.env\./.test(text)) {
      return { ok: true, text: '', suffix: null }; // same-origin relative by default
    }
    if (depth > MAX_HOPS) return { ok: false, reason: 'nesting too deep' };
    const decl = lookup(text, typeof expr === 'string' ? refNode : expr);
    if (!decl) return { ok: false, reason: `"${text}" is not a file-local constant` };
    const paramsKey = params && params.size ? [...params].sort().join(',') : '-';
    const key = `${decl.node.pos}|${paramsKey}|${depth}`;
    if (cache.has(key)) return cache.get(key);
    const result = expand(decl.init);
    cache.set(key, result);
    return result;

    function expand(init) {
      if (ts.isStringLiteral(init) || ts.isNoSubstitutionTemplateLiteral(init)) {
        return { ok: true, text: init.text, suffix: null };
      }
      // `(import.meta.env.VITE_API_BASE_URL as string | undefined) || ''` — the
      // client's own same-origin default, read as the empty prefix it falls back
      // to. A configured absolute URL is out of this contract's reach, but the
      // path written after it is still the claim that matters.
      if (/import\.meta\.env/.test(init.getText())) {
        return { ok: true, text: '', suffix: null };
      }
      // Recurse through readExpression so a const's own template, concatenation
      // or nested constants are handled by the same rules as a literal argument.
      return readExpression(init, { params, depth: depth + 1, refNode: init });
    }
  }

  function readExpression(node, ctx) {
    const { params, depth, refNode = node } = ctx;
    if (depth > MAX_HOPS) return { ok: false, reason: 'nesting too deep' };
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      return { ok: true, text: node.text, suffix: null };
    }
    // `queryString ? `/stats?${queryString}` : '/stats'` — the client's dominant
    // way of saying "this path, with a query string when there is one". Both arms
    // name a real path, so both are claims: reading only the truthy arm, or
    // giving up as "built at runtime", would leave those endpoints unexamined by
    // the gate — six /api/ai-audit and /api/prompts routes were hiding this way.
    if (ts.isConditionalExpression(node)) {
      const branches = [node.whenTrue, node.whenFalse]
        .map((b) => readExpression(b, { params, depth: depth + 1, refNode: b }))
        .filter((r) => r.ok && !r.suffix);
      if (!branches.length) {
        return { ok: false, reason: `built at runtime: ${firstLine(node.getText())}` };
      }
      const [first, ...rest] = branches;
      return {
        ok: true,
        text: first.text,
        suffix: null,
        variants: [
          ...(first.variants ?? []),
          ...rest.map((r) => r.text),
          ...rest.flatMap((r) => r.variants ?? []),
        ],
      };
    }
    if (ts.isTemplateExpression(node)) {
      const nested = (t, d) => resolve(t, new Set(), d, node);
      return readTemplate(node, {
        resolve: nested,
        isParam: (t) => Boolean(params?.has(t)),
        depth,
      });
    }
    if (ts.isIdentifier(node)) {
      const name = node.getText();
      // A parameter *in argument position* is the caller's suffix. In prefix
      // position the same name would be a base URL, which no client here uses.
      if (params?.has(name)) return { ok: true, text: SUFFIX, suffix: name };
      return read(name, params, depth, node);
    }
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
      const left = readExpression(node.left, ctx);
      const right = readExpression(node.right, ctx);
      if (!left.ok || !right.ok)
        return { ok: false, reason: 'string concatenation of unresolved parts' };
      return { ok: true, text: left.text + right.text, suffix: right.suffix ?? left.suffix };
    }
    return { ok: false, reason: `built at runtime: ${firstLine(node.getText())}` };
  }

  return {
    resolve,
    readExpression,
    declares: (n) => declarations.has(n),
  };
}

/**
 * Read a template literal into path text.
 *
 * Returns `{ ok: true, text, suffix }` — `suffix` names the parameter whose
 * value a caller supplies — or `{ ok: false, reason }`.
 */
function readTemplate(node, { resolve, isParam, depth = 0 }) {
  // `node.head.text` is the text BEFORE the first hole, so a template that opens
  // with a base prefix (`` `${BASE_URL}/api/...` ``) has an empty head: its
  // prefix arrives as the first span, not as a hole inside the head.
  const spans = node.templateSpans;
  let out = node.head.text;
  let suffix = null;
  for (const [i, span] of spans.entries()) {
    if (out.includes('?')) break; // the rest is a query string
    const expr = span.expression;
    const text = expr.getText().trim();
    const bare = text.replace(/^this\./, '');
    const queryish =
      QUERY_EXPR.test(bare) ||
      (expr.kind === ts.SyntaxKind.ConditionalExpression &&
        /\?\s*['"`]\?|query|params|qs|search/i.test(expr.getText()));
    if (queryish) break;

    // A hole is the caller's suffix only when nothing follows it in the
    // template: `${BASE_URL}/api/ai-audit${endpoint}` ends here, whereas the
    // `${violationId}` in `${API_BASE}/trust-violations/${violationId}/acknowledge`
    // sits in the last span too but has `/acknowledge` after it.
    const trail = span.literal.text;
    let piece;
    if (i === 0 && out === '') {
      // Prefix position: a base URL, not a path parameter.
      const base = resolve(text, new Set(), depth);
      if (base !== null) {
        piece = base;
      } else if (isParam(bare) && trail === '') {
        piece = SUFFIX;
        suffix = bare;
      } else {
        return { ok: false, reason: `prefix \${${text}} is not statically resolvable` };
      }
    } else if (isParam(bare) && trail === '' && isJoiningSuffix(out)) {
      // `${BASE_URL}/api/ai-audit${endpoint}` — the caller's argument continues
      // this path, so the claim is completed from its call sites.
      piece = SUFFIX;
      suffix = bare;
    } else if (!isParam(bare)) {
      // Not a caller's suffix and not a parameter: possibly another constant
      // prefix composed in (`${BASE_URL}${API_PREFIX}/x`), else a hole we treat
      // as one path parameter.
      const value = resolve(text, new Set(), depth);
      piece = value ?? '{}';
    } else {
      piece = '{}';
    }
    out += piece + span.literal.text;
  }
  return { ok: true, text: out, suffix };
}

/**
 * Does a trailing hole continue the path rather than fill one?
 *
 * `${BASE_URL}/api/ai-audit${endpoint}` joins without a separator because the
 * suffix arrives already leading with `/`. `${API_BASE}/anomalies/${id}` does
 * not: the `/` before `${id}` says the value is one segment, so it is a path
 * parameter, which no scanner should try to complete from call sites — and
 * treating it as a suffix is what previously made
 * `/api/zones/trust-violations/${violationId}/acknowledge` unclaimable.
 */
function isJoiningSuffix(out) {
  return !out.endsWith('/') && !out.endsWith(SUFFIX);
}

function lineAt(p, node) {
  return p.sf.getLineAndCharacterOfPosition(node.getStart(p.sf)).line + 1;
}

/** The parameters of the function a node sits inside. */
function paramNames(node) {
  for (let n = node.parent; n; n = n.parent) {
    if (ts.isFunctionDeclaration(n) || ts.isArrowFunction(n) || ts.isFunctionExpression(n)) {
      return new Set(n.parameters.map((prm) => prm.name.getText()).filter(Boolean));
    }
  }
  return new Set();
}

/** The name and body of a function declaration or arrow assigned to a `const`. */
function declaredFunction(node) {
  if (ts.isFunctionDeclaration(node) && node.name) return { name: node.name.getText(), fn: node };
  if (ts.isVariableDeclaration(node) && node.initializer && ts.isArrowFunction(node.initializer)) {
    return { name: node.name.getText(), fn: node.initializer };
  }
  return null;
}

/**
 * Collect the client's request surface from `srcDir` under `root`.
 *
 * Returns `{ claims, dynamic, unresolved, opaqueMethod, nonApi, files }`:
 *  - `claims`: one `{ kind: 'rest'|'ws', path, method, methodKnown, file, line,
 *    via }` per (normalised path, verb) the client can send, at a call site that
 *    states it. `method` is what invariant 6 describes: enforced only when
 *    `methodKnown`, and a site that states a verb always wins over one that does
 *    not.
 *  - `dynamic`: URL positions with no statically knowable path — reported, never
 *    dropped, because a silent skip is how D2 hid.
 *  - `unresolved`: uses of a base prefix this scanner cannot pin down.
 *  - `opaqueMethod`: claims whose path was resolved but whose verb was not. Kept
 *    separate from `dynamic`, because a claim is already recorded at these sites
 *    and `dynamic` is the list of positions that produced no claim at all.
 *  - `nonApi`: same-origin paths outside `/api`, which this contract does not
 *    cover. Listed so the blind spot stays visible.
 */
export function scanClient({ root = process.cwd(), srcDir = 'src' } = {}) {
  const srcAbs = path.resolve(root, srcDir);
  const parsed = listSourceFiles(srcAbs).map((file) => {
    const text = fs.readFileSync(file, 'utf8');
    const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, /* setParentNodes */ true);
    return { file: path.relative(root, file), sf, scope: makeReader(sf) };
  });

  // Pass 1 — which functions forward one of their parameters into a request URL,
  // and what static base surrounds it? `fetchWithTimeout(url, …)` forwards the
  // whole URL with an empty base; `fetchAiAuditApi(endpoint, …)` surrounds it
  // with `/api/ai-audit`.
  const forwarders = new Map(); // name -> { base, paramIndex, file, line }
  for (const p of parsed) {
    const find = (n) => {
      const decl = declaredFunction(n);
      if (decl?.fn.parameters.length && !forwarders.has(decl.name)) {
        const params = new Set(decl.fn.parameters.map((prm) => prm.name.getText()));
        const look = (m) => {
          if (
            requestCall(m) &&
            (FETCH_LIKE.has(calleeName(m)) ||
              WS_CALLS.has(calleeName(m)) ||
              WS_CONSTRUCTORS.has(calleeName(m)))
          ) {
            const r = p.scope.readExpression(m.arguments[0], { params, depth: 0 });
            if (r.ok && r.suffix) {
              forwarders.set(decl.name, {
                base: r.text.split(SUFFIX).join(''),
                paramIndex: decl.fn.parameters.findIndex((prm) => prm.name.getText() === r.suffix),
                file: p.file,
                line: lineAt(p, m),
              });
            }
          }
          ts.forEachChild(m, look);
        };
        look(decl.fn);
      }
      ts.forEachChild(n, find);
    };
    find(p.sf);
  }

  // Pass 2 — the literals call sites pass to those parameters complete the path.
  const suffixesFor = new Map(); // forwarder name -> [{ text, file, line }]
  for (const name of forwarders.keys()) suffixesFor.set(name, []);
  if (forwarders.size) {
    for (const p of parsed) {
      const visit = (n) => {
        if (requestCall(n)) {
          const name = calleeName(n);
          const fwd = forwarders.get(name);
          if (fwd) {
            const arg = n.arguments[fwd.paramIndex] ?? n.arguments[0];
            const r = p.scope.readExpression(arg, { params: new Set(), depth: 1 });
            if (r.ok && !r.suffix && r.text.startsWith('/')) {
              suffixesFor.get(name).push({ text: r.text, file: p.file, line: lineAt(p, n) });
            }
          }
        }
        ts.forEachChild(n, visit);
      };
      visit(p.sf);
    }
  }

  const claims = [];
  const dynamic = [];
  const unresolved = [];
  const nonApi = [];
  // key -> claim, so a later call site can *upgrade* a claim it disagrees with
  // about the verb rather than being silently dropped (see `addClaim`).
  const byKey = new Map();

  // One claim per (path, verb) the client can send: the contract is a set of
  // obligations, and `GET /api/x` and `DELETE /api/x` are two of them while a
  // path called from six places is one. Keyed on the *normalised* path, so the
  // `/api/events?` and `/api/events` spellings a query-string ternary produces
  // are one obligation, not two.
  const addClaim = (kind, raw, where, via, method) => {
    const path = normalisePath(raw);
    const key = `${kind} ${path} ${method.method ?? ''}`;
    const prior = byKey.get(key);
    if (prior) {
      // An unknown verb must never shadow a known one: two call sites can reach
      // the same path with the same guess, and if the pass-through one happened
      // to parse first, keeping it would quietly drop this path from the method
      // check. Upgrade to the site that spells the verb out, and report *it*,
      // because a reader fixing a mismatch has to open that file.
      if (!prior.methodKnown && method.known) {
        Object.assign(prior, {
          raw,
          method: method.method,
          methodKnown: true,
          methodReason: undefined,
          via,
          file: where.file,
          line: where.line,
        });
      }
      return;
    }
    const claim = {
      kind,
      path,
      raw,
      method: method.method,
      methodKnown: method.known,
      methodReason: method.reason,
      file: where.file,
      line: where.line,
      via,
    };
    byKey.set(key, claim);
    claims.push(claim);
  };

  const record = (kind, text, p, node, via, method = NO_METHOD) => {
    if (kind === 'ws') {
      // buildWebSocketOptions() returns an absolute `ws://host/endpoint`, and its
      // host is window.location by default — our own origin. Only the path is the
      // contract, so the scheme and host come off rather than tripping the
      // "another host" rule below, which would report every WebSocket in the
      // app as unchecked.
      const stripped = text.replace(/^wss?:\/\/[^/]*?(?=\/|$)/i, '');
      if (!stripped.startsWith('/')) {
        unresolved.push({
          file: p.file,
          line: lineAt(p, node),
          reason: `WebSocket URL carries no path: ${firstLine(text)}`,
        });
        return;
      }
      text = stripped;
    }
    if (/^(https?|wss?):\/\//i.test(text)) {
      // Header rule 4: what the scanner cannot pin to this contract is *reported*,
      // never dropped. An absolute URL may name a foreign host (a CDN, a partner
      // service), so its path is deliberately not checked against our spec — but a
      // request that leaves the contract silently is exactly the hole this file
      // promises to list. The dangerous case is a same-origin absolute —
      // `fetch('http://localhost:8000/api/typo')` looks served, reads as fine to a
      // human, and vanished here while the gate stayed green.
      unresolved.push({
        file: p.file,
        line: lineAt(p, node),
        reason: `absolute URL leaves this contract: ${firstLine(text)}`,
      });
      return;
    }
    if (!text.startsWith('/')) {
      dynamic.push({
        file: p.file,
        line: lineAt(p, node),
        reason: `first argument is not a path: ${firstLine(text)}`,
      });
      return;
    }
    if (kind === 'rest' && !/^\/api(\/|$)/.test(text)) {
      nonApi.push({ file: p.file, line: lineAt(p, node), path: normalisePath(text) });
      return;
    }
    addClaim(
      kind,
      text,
      { file: p.file, line: lineAt(p, node) },
      via ?? (text.includes('{}') ? 'template' : 'literal-or-const'),
      method
    );
  };

  for (const p of parsed) {
    const visit = (n) => {
      if (requestCall(n)) {
        const short = calleeName(n);
        const isWs = WS_CALLS.has(short) || WS_CONSTRUCTORS.has(short);
        const fwd = forwarders.get(short);

        // Read before the path: a call whose URL the scanner cannot resolve still
        // tells us nothing about its verb, but a call whose URL it *does* resolve
        // must have its method accounted for, known or not.
        const method = methodForCall(short, n.arguments[1]);

        if (FETCH_LIKE.has(short) || isWs) {
          const r = p.scope.readExpression(n.arguments[0], { params: paramNames(n), depth: 0 });
          if (!r.ok) {
            (r.reason.startsWith('prefix') ? unresolved : dynamic).push({
              file: p.file,
              line: lineAt(p, n),
              reason: r.reason,
            });
          } else if (!r.suffix) {
            // With a suffix this call is the body of a forwarder, so the path is
            // still open; pass 2 closed it from the call sites that reached it.
            record(isWs ? 'ws' : 'rest', r.text, p, n, undefined, method);
            for (const variant of r.variants ?? [])
              record(isWs ? 'ws' : 'rest', variant, p, n, undefined, method);
          }
        } else if (fwd) {
          const arg = n.arguments[fwd.paramIndex] ?? n.arguments[0];
          const r = p.scope.readExpression(arg, { params: new Set(), depth: 1 });
          if (!r.ok || r.suffix || !r.text.startsWith('/')) {
            dynamic.push({
              file: p.file,
              line: lineAt(p, n),
              reason: `suffix for ${short}() at ${fwd.file}:${fwd.line}: ${r.ok ? 'not a literal path' : r.reason}`,
            });
          } else {
            record('rest', `${fwd.base}${r.text}`, p, n, `${short}() suffix`, method);
          }
        }
      }
      ts.forEachChild(n, visit);
    };
    visit(p.sf);
  }

  // A forwarder's own `fetch()` site carries no resolvable literal, so its paths
  // exist only where a call site supplied a suffix — which the visitor recorded.
  // A forwarder no call site completes is reported, never skipped silently.
  for (const [name, list] of suffixesFor) {
    if (list.length) continue;
    const fwd = forwarders.get(name);
    dynamic.push({
      file: fwd.file,
      line: fwd.line,
      reason: `${name}() builds "${fwd.base}" plus a caller-supplied suffix, but no call site passes a literal one`,
    });
  }

  // Derived from the claims rather than collected during the walk, so it cannot
  // drift from them: this *is* the set of claims the method check skipped, one
  // per obligation rather than one per syntactic variant of it.
  const opaqueMethod = claims
    .filter((c) => !c.methodKnown)
    .map(({ kind, path, methodReason: reason, file, line }) => ({
      kind,
      path,
      file,
      line,
      reason,
    }));

  return { claims, dynamic, unresolved, opaqueMethod, nonApi, files: parsed.map((p) => p.file) };
}

/**
 * Read the committed OpenAPI document once: its paths, and its verbs per path.
 *
 * `paths` is the document's key order (which is what the nearest-path hint pools
 * and the coverage count want); `methods` is keyed by *normalised* path so a
 * claim can look up what the backend declares without normalising the whole pool
 * again. Path-template objects like FastAPI's `{…:path}` keep their raw spelling
 * in the key, so the lookup uses the same `normalisePath` the matching uses.
 */
export function loadSpec(specFile) {
  const spec = JSON.parse(fs.readFileSync(specFile, 'utf8'));
  const paths = Object.keys(spec.paths ?? {});
  const methods = new Map();
  const VERBS = new Set(['get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace']);
  for (const [p, ops] of Object.entries(spec.paths ?? {})) {
    const declared = new Set(
      Object.keys(ops ?? {})
        .filter((op) => VERBS.has(op.toLowerCase()))
        .map((op) => op.toUpperCase())
    );
    // Two template spellings can normalise to one key (`/api/x/{a}` and
    // `/api/x/{b}`); union their verbs, since both are served.
    const key = normalisePath(p);
    const prior = methods.get(key);
    methods.set(key, prior ? new Set([...prior, ...declared]) : declared);
  }
  return { paths, methods };
}

/** Paths only — `loadSpec` for both halves of the method-and-path question. */
export function loadSpecPaths(specFile) {
  return loadSpec(specFile).paths;
}

/**
 * WebSocket routes, scraped from backend route decorators.
 *
 * docs/openapi.json describes HTTP only and src/types/generated/websocket.ts
 * carries message schemas rather than routes, so the decorators are the only
 * committed, machine-readable truth about which WS paths exist.
 */
export function scanWebsocketRoutes(backendDir) {
  const routes = new Set();
  const walk = (dir) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const p = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (!/node_modules|__pycache__|\.venv|^tests$/.test(entry.name)) walk(p);
      } else if (entry.name.endsWith('.py')) {
        const text = fs.readFileSync(p, 'utf8');
        const prefix = (text.match(/APIRouter\((?:[^)]*?)prefix=["']([^"']+)["']/) || [])[1] ?? '';
        const decorator = /\.websocket\(\s*f?["']([^"']+)["']/g;
        let m;
        while ((m = decorator.exec(text))) {
          routes.add(normalisePath(m[1].startsWith('/') ? m[1] : `${prefix}${m[1]}`));
        }
      }
    }
  };
  walk(backendDir);
  return [...routes].sort();
}

/**
 * Does a known-missing entry excuse this mismatch?
 *
 * Two shapes of allowance matched against two shapes of finding, and the
 * cross-combinations are deliberately closed:
 *  - a path-only entry (`{ path }`) excuses a *missing-path* finding only. It
 *    does not touch a method finding, so the D2 allowances written before verbs
 *    were checked cannot later hide a wrong-verb bug on the same path.
 *  - a method entry (`{ path, method: 'GET' }`) excuses only that verb's finding
 *    at that path; a missing path elsewhere is still reported.
 */
export function allows(entry, mismatch) {
  if (normalisePath(entry.path) !== mismatch.path) return false;
  const entryMethod = entry.method ? entry.method.toUpperCase() : null;
  if (!mismatch.methodMismatch) return entryMethod === null;
  return entryMethod === mismatch.method;
}

/**
 * Does a known-missing entry still describe a real client call?
 *
 * An allowance whose call site has gone is a gap that was quietly fixed and left
 * open on paper, so every entry has to point at a live claim. A method entry
 * needs a claim carrying *that verb*: fixing the `GET` while still posting to the
 * same path means its entry has gone stale even though the path is still called.
 * A path-only entry stays live while any verb is called there, because the gap it
 * describes is the absence of the route, not of one request.
 */
export function entryIsLive(entry, claims) {
  const p = normalisePath(entry.path);
  const entryMethod = entry.method ? entry.method.toUpperCase() : null;
  return claims.some((c) => c.path === p && (entryMethod === null || c.method === entryMethod));
}

/**
 * Partition client claims against the two sources of backend truth.
 *
 * `restMethods` is the `loadSpec().methods` map. When it is supplied, a claim
 * whose path exists is *still* checked for its verb, and a wrong verb becomes a
 * mismatch of its own (`methodMismatch: true`). Omitting it leaves the check
 * path-only, which is what a caller reading a spec without verbs would want.
 *
 * A method mismatch is reported with `nearest` set to the path that *does*
 * exist, because that is the whole message: the route is real, the verb is not.
 * Folding it into the path-mismatch wording would send a reader off looking for
 * a missing endpoint that is sitting right there.
 */
export function compare({ claims, restPaths, wsRoutes, restMethods }) {
  const restNormalised = new Set(restPaths.map(normalisePath));
  const wsNormalised = new Set(wsRoutes.map(normalisePath));
  const matched = [];
  const mismatches = [];
  for (const claim of claims) {
    const pool = claim.kind === 'ws' ? wsRoutes : restPaths;
    const truth = claim.kind === 'ws' ? wsNormalised : restNormalised;
    if (truth.has(claim.path)) {
      if (claim.kind === 'rest' && claim.methodKnown && restMethods) {
        const declared = restMethods.get(claim.path);
        const whyMethod = compareMethod(claim.method, declared);
        if (whyMethod) {
          mismatches.push({
            ...claim,
            methodMismatch: true,
            nearest: claim.path,
            why: `${claim.method} is not declared there — ${whyMethod}`,
          });
          continue;
        }
      }
      matched.push(claim);
      continue;
    }
    const near = closestSpecPath(claim.path, pool);
    mismatches.push({
      ...claim,
      nearest: near,
      why: near ? explainMatch(claim.path, near) : 'no comparable path exists',
    });
  }
  return { matched, mismatches };
}

/**
 * The whole contract check, in one call.
 *
 * Both the CLI (`scripts/api-contract-scan.mjs`) and the CI gate
 * (`src/__tests__/api-endpoint-contract.test.ts`) call this, so the two can
 * never disagree about what passes — a gate and a report that compute the
 * verdict differently is how a red check becomes decoration.
 *
 * A known-missing entry is `{ path, method?, … }`. Omitting `method` allows the
 * whole path, which is what the D2 findings need (no route at all). Supplying one
 * allows *that verb* at a path the backend does serve, which is the other shape of
 * D2 — a call the backend answers with 405 rather than 404. The lookup is
 * deliberately not symmetric: an entry with no `method` never excuses a method
 * mismatch, so a path-only allowance written before the verb was checked cannot
 * silently cover a new wrong-verb bug on the same path.
 *
 * An entry whose client call site has since gone is reported as `stale`: an
 * allowance nobody removes is how this gate quietly rots. For a `method` entry
 * that means the call *with that verb* has gone, not any call at the path —
 * otherwise fixing `GET /api/x` while still posting to `/api/x` would leave the
 * allowance looking live forever.
 */
export function audit({
  root = process.cwd(),
  srcDir = 'src',
  specFile,
  backendDir,
  knownMissing = [],
} = {}) {
  const scan = scanClient({ root, srcDir });
  const spec = loadSpec(specFile);
  const wsRoutes = scanWebsocketRoutes(backendDir);
  const { matched, mismatches } = compare({
    claims: scan.claims,
    restPaths: spec.paths,
    wsRoutes,
    restMethods: spec.methods,
  });

  const listed = [];
  const unlisted = [];
  for (const m of mismatches) {
    (knownMissing.some((e) => allows(e, m)) ? listed : unlisted).push(m);
  }

  const stale = knownMissing.filter((e) => !entryIsLive(e, scan.claims));

  // `restMethodPaths` exists so the gate can bound the method check's own reach:
  // a regenerated spec that lost its verbs would turn "0 method mismatches" green
  // without the check having compared anything.
  const restMethodPaths = [...spec.methods.values()].filter((m) => m.size > 0).length;

  return {
    scan,
    restPaths: spec.paths,
    restMethodPaths,
    wsRoutes,
    matched,
    mismatches,
    listed,
    unlisted,
    stale,
  };
}
