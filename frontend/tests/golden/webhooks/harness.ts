/**
 * F2.3 DO-4 golden harness — the `/webhooks` batch (F-245, F-247, F-248, F-249).
 *
 * Batch-local on purpose. Ruling 87 scopes a batch to `frontend/tests/golden/<area>/`
 * plus its own inventory rows, which rules out the OTHER precedent in this tree:
 * `data-ui/` (DO-1) owns no harness and imports `../operations/harness`. DO-2 kept
 * its harness local "so the two batches can evolve their sessions independently"
 * (notify-access/harness.ts:122-123) and this file follows that, because what DO-4
 * needs is a webhook create/teardown pair no other batch has, and borrowing
 * operations/harness.ts would mean reading a batch's file to change mine.
 *
 * What this batch had to learn the hard way, and what it therefore refuses to do:
 *
 * - NO page.route() anywhere, including as a fixture. `../guard` replaces route/
 *   unroute/routeFromHAR/routeWebSocket on every Page and Context with a throw
 *   (guard.ts:46, :51-53), so the usual way to make a health card show non-zero
 *   numbers is unavailable by design, not by oversight. Every assert in this batch
 *   is therefore against a row the spec created through the real API.
 * - The webhook row cannot be seeded, only created. The fake stack has no webhook
 *   wiring at all: `grep -rin webhook docker-compose.fake-ai.yml docker/fake-ai`
 *   is empty, and `frontend/src/mocks/handlers.ts` has no webhook handler either
 *   (measured this tick). So `createWebhook()` is the fixture, and `deleteWebhook()`
 *   in the spec's own `finally` is the cleanup invariant.
 * - The API leg runs BEFORE the UI leg (the DO-2 rule, notify-access/harness.ts:174
 *   -176): a row the backend does not have cannot pass as "deleted", and a blank
 *   screen cannot pass as "renders".
 * - `apiPath()` is EXACT-path equality after slash normalization, not endsWith().
 *   It is copied because the failure it prevents is a batch-agnostic one: a
 *   response matcher that can never fire silently skips the code that restores
 *   state (the notify F-230 leak, :240-251). DO-4 has the same shape — an
 *   absence witness ("the dismiss leg DELETEs nothing") is exactly where a
 *   predicate that cannot match looks like a passing test.
 * - No optimistic updates exist on this page, so no assert may trust a mutation
 *   response alone. `useWebhooks.ts` has no onMutate/cancelQueries/setQueryData
 *   (grep for all four: zero hits) and its header comment's claim of "Optimistic
 *   updates where appropriate" (:25) is not implemented — every visible change is
 *   a refetch of `['webhooks','list']` + `['webhooks','health']`. Specs await the
 *   refetch, and the API leg reads the store rather than trusting the widget.
 */
import { GUARD_MESSAGE, expect } from '../guard';
import type { Page } from '@playwright/test';

export interface Harness {
  ready: true;
  api: string;
  ui: string;
  admin: { username: string; password: string };
}

/** Read the harness contract defensively: any piece missing → {ready: false, why}.
 *  Collection-time code must not throw, or `npx playwright test --list` breaks for
 *  every lane outside the harness (the rule analytics-alerts/harness.ts set). */
export function readHarness(): Harness | { ready: false; why: string } {
  const need = [
    'FEATURE_CHECK_UI_URL',
    'FEATURE_CHECK_API_URL',
    'FEATURE_CHECK_ADMIN_USERNAME',
    'FEATURE_CHECK_ADMIN_PASSWORD',
  ] as const;
  const missing = need.filter((name) => !process.env[name]);
  if (missing.length) return { ready: false, why: `missing ${missing.join(', ')}` };
  return {
    ready: true,
    api: String(process.env.FEATURE_CHECK_API_URL),
    ui: String(process.env.FEATURE_CHECK_UI_URL),
    admin: {
      username: String(process.env.FEATURE_CHECK_ADMIN_USERNAME),
      password: String(process.env.FEATURE_CHECK_ADMIN_PASSWORD),
    },
  };
}

export interface Session {
  name: string;
  value: string;
}

/** A real login against the real backend — the cookie is genuine state, not a
 *  mock. Split on the FIRST '=' only: a session token can carry base64 padding. */
export async function adminSession(h: Harness): Promise<Session> {
  const response = await fetch(`${h.api}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: h.admin.username, password: h.admin.password }),
  });
  if (response.status !== 200 && response.status !== 204) {
    throw new Error(`golden admin login answered ${response.status}: ${await response.text()}`);
  }
  const pair = response.headers
    .getSetCookie()
    .map((entry) => entry.split(';')[0])
    .find((entry) => entry.includes('='));
  if (!pair) throw new Error('golden admin login set no session cookie');
  const index = pair.indexOf('=');
  return { name: pair.slice(0, index), value: pair.slice(index + 1) };
}

/** The session cookie rides into the browser on the UI origin: that origin's
 *  nginx proxies /api to the backend, so the browser authenticates the way a user
 *  who logged in through this very form would. */
export async function login(page: Page, h: Harness, session: Session): Promise<void> {
  const url = new URL(h.ui);
  await page.context().addCookies([
    {
      name: session.name,
      value: session.value,
      domain: url.hostname,
      path: '/',
      httpOnly: true,
      secure: url.protocol === 'https:',
      sameSite: 'Lax',
    },
  ]);
  await page.goto(`${h.ui}/login`, { waitUntil: 'domcontentloaded' });
}

export interface ApiResponse {
  status: number;
  body: any;
}

export interface AuthedFetch {
  getJson(urlPath: string): Promise<ApiResponse>;
  send(urlPath: string, method: string, payload?: unknown): Promise<ApiResponse>;
}

/** Backend calls with the harness admin's session. 204 has no body, so `body` is
 *  null there by contract — and the delete teardown depends on that: the route
 *  answers 204 (outbound_webhooks.py:513) and a `.json()` on it would throw.
 *  Content-Type is sent only when there IS a body: enable/disable POST with no
 *  body at all (webhookApi.ts:289-312) and a `Content-Type: application/json`
 *  with an empty body is a different request than the browser's. */
export function authedFetch(h: Harness, session: Session): AuthedFetch {
  const call = async (urlPath: string, init?: RequestInit): Promise<ApiResponse> => {
    const response = await fetch(`${h.api}${urlPath}`, {
      ...init,
      headers: {
        Cookie: `${session.name}=${session.value}`,
        ...(init?.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(init?.headers ?? {}),
      },
    });
    const body = await response.json().catch(() => null);
    return { status: response.status, body };
  };
  return {
    getJson: (urlPath) => call(urlPath),
    send: (urlPath, method, payload) =>
      call(urlPath, { method, body: payload === undefined ? undefined : JSON.stringify(payload) }),
  };
}

/** Exact-path equality after trailing-slash normalization. See the header note:
 *  an absence witness is the one place a never-matching predicate is invisible. */
export function apiPath(url: string): string {
  const p = new URL(url).pathname;
  return p.length > 1 && p.endsWith('/') ? p.slice(0, -1) : p;
}

/** End-of-spec honesty, the guard surviving the whole drive (F2.1's pin, re-armed
 *  per batch so a DO-4 spec that reached for a mock fails LOUD). */
export async function assertGuardSurvives(page: Page, h: Harness): Promise<void> {
  expect(new URL(page.url()).host).toBe(new URL(h.ui).host);
  expect(() => page.route('**/api/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
}

export const WEBHOOKS_URL = '/api/outbound-webhooks';

/** A refused loopback port, the repo's OWN established sink for a deterministic
 *  outbound failure: backend/tests/golden/external/test_webhook_deliveries.py:68
 *  uses `http://127.0.0.1:1/...` for exactly this and explains why (:20) — httpx
 *  fails it in milliseconds, so a spec never waits on a retry window.
 *
 *  Chosen over an HTTP 2xx target deliberately. A reachable sink would need
 *  another service in the fake stack (which publishes only ai-vlm:8098 and
 *  ai-gateway:8090, docker-compose.fake-ai.yml:69-70 / :97-98) and ruling 87
 *  forbids this PR from touching compose or the harness. So F-249's golden arm is
 *  the refusal, which is fully determinable here, and the success arm is left to
 *  the real tier rather than faked — which is what F2.1 forbids. */
export const REFUSED_URL = 'http://127.0.0.1:1/golden-do4-refused';

/** Create a webhook the real way — the route the F-246 form posts to
 *  (outbound_webhooks.py:342). Required fields only, read from the schema:
 *  name (min_length 1), url (HttpUrl), event_types (min_length 1)
 *  (api/schemas/outbound_webhook.py:144-148).
 *
 *  `enabled: true` and `max_retries: 0` are set explicitly rather than taken from
 *  defaults: the default IS true (schema :152) but a spec that flips it must not
 *  depend on that, and max_retries defaults to 4 (:158), which would make any
 *  delivery from this row retry for minutes. The backend golden spec pins the
 *  same reasoning at test_webhook_deliveries.py:119 (`"max_retries": 0`, whose
 *  :118 comment says "0 retries is what makes the row terminal on the first
 *  attempt") — not :116, which is the unrelated `"url": REFUSED_URL` line. */
export async function createWebhook(
  api: AuthedFetch,
  name: string,
  url: string = REFUSED_URL
): Promise<string> {
  const res = await api.send(WEBHOOKS_URL, 'POST', {
    name,
    url,
    event_types: ['alert_fired'],
    integration_type: 'generic',
    enabled: true,
    max_retries: 0,
  });
  expect(res.status, 'the batch fixture creates its row (201)').toBe(201);
  const id = String(res.body?.id ?? '');
  expect(id.length > 0, 'the create response carries the new uuid').toBeTruthy();
  return id;
}

/** Teardown: DELETE answers 204 with no body. A teardown that asserts is a
 *  teardown that reports its own failure instead of hiding a leak. */
export async function deleteWebhook(api: AuthedFetch, id: string): Promise<void> {
  const res = await api.send(`${WEBHOOKS_URL}/${id}`, 'DELETE');
  expect(res.status, 'teardown removes the row it created (204)').toBe(204);
}

/** Sorted id set of every webhook on the stack. The restore proof is SET EQUALITY
 *  against this snapshot (DO-2's rule, quiet-hours.spec.ts:76-78 / :255-257): a
 *  stack that grows a seeded webhook later must not make this batch red, and
 *  "empty" is a weaker claim than "as I found it". */
export async function webhookIds(api: AuthedFetch): Promise<string[]> {
  const res = await api.getJson(WEBHOOKS_URL);
  expect(res.status, 'GET /api/outbound-webhooks answers 200').toBe(200);
  const rows = Array.isArray(res.body?.webhooks)
    ? res.body.webhooks
    : Array.isArray(res.body)
      ? res.body
      : [];
  return rows.map((row: Record<string, unknown>) => String(row.id)).sort();
}
