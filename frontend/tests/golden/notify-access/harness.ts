/**
 * Shared harness plumbing for the F2.3 DO-2 golden paths (claim #6996).
 * DO-2 covers the notifications, ambient-status and access surfaces:
 * inventory rows F-230 to F-238 and F-240 to F-243.
 *
 * What DO-2 is NOT, relative to DO-1 (analytics-alerts/harness.ts): it drops
 * NO fixture. The surfaces here are settings + permission + storage surfaces,
 * and every fact they pin is either (a) a deterministic backend response in
 * the no-env CI stack (no SMTP/webhook env exists in docker-compose.ci.yml or
 * docker-compose.fake-ai.yml — grepped at implementation), (b) browser state
 * the spec itself legitimately produces (a real click, a localStorage write,
 * context.grantPermissions), or (c) the shipped stub contracts (the history
 * endpoint's empty envelope; the shipped push constants). So the scenario
 * book, the camera seed file and the 300 s dedupe discipline do not enter —
 * and the required env shrinks to UI/API/admin only.
 *
 * Wiring facts this layout depends on (all read at this head):
 * - feature_check.py golden() runs `playwright --project=golden`; the golden
 *   project is testDir ./tests/golden with workers: 1, fullyParallel: false.
 * - Playwright's default file order sorts by path, so at THIS head (this
 *   branch, which is strictly ahead of main) the golden project is 9 spec
 *   files and the run order is
 *   analytics-alerts/*, dashboard-drop.spec.ts, guard-contract.spec.ts, then
 *   notify-access/* ('a' < 'd' < 'g' < 'n' at the first path character).
 *   DO-2 sorts last TODAY and will not stay last. Read from those two PR
 *   heads (re-fetched and re-counted THIS tick, not from the last reading —
 *   the PRs can move, and both HAD moved since the reading this comment
 *   first cited): #6986 at da4bb698d adds 27 specs in ai-pages/ (1),
 *   data-ui/ (3), gpu-storage-admin/ (7) — all three sort BEFORE 'n' — and
 *   operations/ (16), which sorts after; #6978 at 675fedfc4 adds 16 specs in
 *   shell/, also after (both counts = added spec.ts files minus the 4 DO
 *   files each batch inherits — the raw ls-tree totals are 31 and 20). The
 *   union set is 52 files with notify-access at positions 16-20, so 32 specs
 *   run AFTER this lane once both batches merge.
 *   Which means "last" was never the property worth relying on, and it is not
 *   the one this lane uses. Two invariants do the work instead, and both are
 *   position-independent:
 *     (1) no client state crosses a test: every test gets a fresh context.
 *         Nothing under tests/golden calls storageState({path}) or newContext
 *         (guard.ts's own `context` fixture override wraps the built-in
 *         per-test instance rather than making one), and the single seed the
 *         config inherits (playwright.config.ts:162 ->
 *         tests/e2e/.auth/storage-state.json) carries ONLY the two
 *         nemotron-tour-* keys and an empty cookie jar — no 'settings' key —
 *         so a localStorage write dies with its context;
 *     (2) every test that sends a non-GET request restores what it created
 *         inside its OWN finally block. The two files that write do it
 *         differently and both readings are deliberate: notify.spec.ts asserts
 *         the restore's exact status (the flip-back PUT 200, the camera-row PUT
 *         200 with its prior threshold, the quiet-hours DELETE 204) and ends
 *         with a belt-and-braces DELETE whose result is swallowed, since that
 *         leg only runs when an earlier assert already threw; access.spec.ts
 *         deletes server rows whose 404 is itself the proof the row is gone, so
 *         all 7 of its legs accept 204-or-404.
 *         Why ambient and permission carry no finally: they send ZERO non-GET
 *         legs (client-only rows by their own inventory contract), so there is
 *         no SERVER row to delete. That is not the same as "no cleanup", and
 *         the two files differ here — ambient really does write the v1
 *         'security-dashboard-settings' key, and it restores that in-line (the
 *         switch-back-on leg at the end of its first test) rather than in a
 *         finally, because a finally buys nothing for state that invariant
 *         (1) already makes unobservable to the next test; permission grants
 *         browser permission on its own context and moves only in-memory
 *         React state, so it writes nothing that outlives the test at all.
 *   So (2) is what keeps a gate re-run on the SAME stack starting from the
 *   same server state, and (1) is what keeps one spec's client writes from
 *   reaching another — and both hold whether DO-2 runs last or 16th.
 * - The page/context guard comes from ../guard — never the tests/e2e fixtures,
 *   which auto-mock. addCookies (login) and grantPermissions (notifications)
 *   are real browser state, not interception, so the guard does not — and
 *   should not — block them; DO-1's login() established the precedent.
 * - Two storage keys exist for settings (useSettings.ts:108 v1
 *   'security-dashboard-settings', stores/settings-store.ts:132 a '-v2'
 *   zustand store). The MOUNTED ambient UI reads/writes v1 only; the v2 store
 *   imports no component for this surface but its migration REMOVES the v1
 *   key. F-238's reads therefore hit v1 and run before any later mount could
 *   migrate — see ambient.spec.ts.
 */
import type { BrowserContext, Locator, Page } from '@playwright/test';

import { GUARD_MESSAGE, expect } from '../guard';

export interface Harness {
  ready: true;
  api: string;
  ui: string;
  admin: { username: string; password: string };
}

/** Read the harness contract defensively: any piece missing → {ready: false,
 *  why}. Collection-time code must not throw, or `--list` breaks outside the
 *  harness (the rule analytics-alerts/harness.ts established). */
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

/** No repoRoot/drop plumbing here on purpose: DO-2 drops no fixture, so the
 *  only node builtin this batch needs would be a dead import. DO-1's harness
 *  keeps its own. */
export interface Session {
  name: string;
  value: string;
}

/** A real login against the real backend — the cookie is genuine state, not a
 *  mock (the same call DO-1's harness uses, kept local so the two batches can
 *  evolve their sessions independently). */
export async function adminSession(h: Harness): Promise<Session> {
  const response = await fetch(`${h.api}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: h.admin.username, password: h.admin.password }),
  });
  if (response.status !== 200 && response.status !== 204) {
    throw new Error(`golden admin login answered ${response.status}: ${await response.text()}`);
  }
  // Split on the first '=' only: a session token can carry base64 padding.
  const pair = response.headers
    .getSetCookie()
    .map((entry) => entry.split(';')[0])
    .find((entry) => entry.includes('='));
  if (!pair) throw new Error('golden admin login set no session cookie');
  const index = pair.indexOf('=');
  return { name: pair.slice(0, index), value: pair.slice(index + 1) };
}

/** The session cookie rides into the browser on the UI origin: that origin's
 *  nginx proxies /api to the backend, so the browser authenticates the way a
 *  user who logged in through this very form would. */
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
  /** Verb-carrying leg: quiet-hours POST/DELETE and the per-camera PUT all
   *  need it; 204 responses have no body, so body is null there by contract. */
  send(urlPath: string, method: string, payload?: unknown): Promise<ApiResponse>;
}

/** Backend calls with the harness admin's session — the API leg every DO-2
 *  spec runs BEFORE its UI leg, so a blank screen can never pass as "renders"
 *  and an absent row can never pass as "deleted". */
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

/** The v1 settings key the MOUNTED UI persists to (useSettings.ts:108 +
 *  :220-224). Read through page.evaluate so the spec sees what the page sees;
 *  returns the whole parsed object — callers reach into ambientStatus. */
export async function readV1Settings(page: Page): Promise<Record<string, any>> {
  const raw = await page.evaluate(() => localStorage.getItem('security-dashboard-settings'));
  if (raw === null) return {};
  try {
    const parsed = JSON.parse(raw) as unknown;
    expect(
      typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed),
      'the v1 settings key holds a JSON object'
    ).toBe(true);
    return parsed as Record<string, any>;
  } catch {
    // An unparseable v1 key is a real app-state finding, not a harness bug —
    // surface it as the value it is so the assert message carries context.
    return { __unparseable: raw };
  }
}

/** Real browser permission state for the Notifications API — the only
 *  deterministic route to the granted arm of the push/desktop badges
 *  (F-234). grantPermissions is state a user can genuinely produce; it is not
 *  route interception, so the guard leaves it alone (same footing as the
 *  login cookie).
 *
 *  Measured caveat, this tick: in the feature-check image's Chromium the
 *  grant does NOT take — CI run 38148818888's granted-test accessibility
 *  snapshot paints Denied (error-context lines 160-164), and the frontend
 *  lane's solo probe stack reproduced it with the per-origin variant
 *  (grantPermissions(['notifications'], { origin })) too. permission.spec.ts
 *  therefore MEASURES Notification.permission after granting and self-skips
 *  with that measurement when the runner cannot enter the granted world —
 *  stated, not faked, not left red (the self-skip law of owner note
 *  6103539478: a batch spec that hard-fails outside the harness breaks
 *  --list for every lane). */
export async function grantNotifications(context: BrowserContext): Promise<void> {
  await context.grantPermissions(['notifications']);
}

/** The URL PATH a Playwright request/response carried, normalized: origin and
 *  query stripped, ONE optional trailing slash removed.
 *
 *  Why a primitive instead of endsWith(): the shipped preferences PUT is
 *  fetchApi('/api/notification-preferences/', …) (api.ts:4381) and fetchApi
 *  concatenates BASE_URL + endpoint verbatim (:1348), so the browser really
 *  sends the TRAILING-SLASH form. A waitForResponse predicate of
 *  endsWith('/api/notification-preferences') can therefore NEVER fire — it
 *  timed out in CI (run 38148818888, notify F-230), left flipped=false, and
 *  the finally skipped the restore, leaking the flip into the retry. A
 *  matcher that can never match is worse than a wrong assert: the assert
 *  fails loudly, the matcher silently skips the code that restores state.
 *  Exact-path equality after normalization is immune to either slash shape
 *  AND cannot suffix-match the sibling routes (/…/cameras, /…/quiet-hours)
 *  the same prefix owns. */
export function apiPath(url: string): string {
  const p = new URL(url).pathname;
  return p.length > 1 && p.endsWith('/') ? p.slice(0, -1) : p;
}

/** End-of-spec honesty, the guard surviving the whole drive (F2.1's pin,
 *  re-armed per batch so a DO-2 spec that reached for a mock fails LOUD). */
export async function assertGuardSurvives(page: Page, h: Harness): Promise<void> {
  expect(new URL(page.url()).host).toBe(new URL(h.ui).host);
  expect(() => page.route('**/api/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
}

/** A settings-section TITLE, by the text it really paints.
 *
 *  NOT getByRole('heading'). Both DO-2 section titles are Tremor <Title>
 *  (NotificationSettings.tsx:484-487, AmbientStatusSettings.tsx:64) and
 *  Tremor's Title renders a <p>, so neither carries a heading role; the
 *  snapshot in the feature-check artifact for the failing run shows the ONLY
 *  heading on /settings/<tab> is the tab shell's own <h1>Settings</h1>. CI
 *  proved this the hard way: the first real execution of these specs (run
 *  38145962360) failed five tests (ambient ×2, permission ×2, notify F-230
 *  ×1) on exactly this locator family and on nothing else, while this file's
 *  own in-page getByText leg in the SAME test passed seconds earlier — so the
 *  panel rendered and only the role was wrong.
 *
 *  exact: true is load-bearing, not tidiness. getByText() is a substring
 *  match, and the notification tab mount also paints "Audio Notification
 *  Settings" (:723) — a substring locator for "Notification Settings" binds
 *  BOTH and dies on Playwright strict mode. The same snapshot shows each
 *  exact string occurs once.
 *
 *  Why not the data-testid instead: AmbientStatusSettings.tsx:60 has one
 *  (ambient-status-settings) and NotificationSettings has none, and ruling 87
 *  keeps this PR out of src/, so a shared helper cannot lean on it. */
export function sectionTitle(page: Page, text: string): Locator {
  return page.getByText(text, { exact: true });
}
