/**
 * The shared golden-path harness for every FE/OP area.
 *
 * Ruling 148 §1: "[r148a] merges all copies into one
 * frontend/tests/golden/harness.ts, keeping every comment that explains a fix,
 * and repoints each spec's import." The copies are what F2.3 grew while ruling
 * 87 held batches apart ("so two lanes' PRs never depend on each other's
 * merge"); that hold released with F2.3's last batch, so the 11 area files
 * fold here.
 *
 * Layout: SHARED holds names ≥2 areas defined; where the code was the same (or
 * the same once the five `<Area>Harness` spellings of one env contract were
 * unified) there is now one definition carrying the UNION of the areas'
 * docblocks, so every fix comment survives in one place. Where areas had
 * DIFFERENT code under one name — adminSession's 204 tolerance,
 * settings-cameras' 500 ms quiet-boot window, analytics-alerts'
 * scenario-carrying Harness, the 429-shed `driveUntilBooted` coat — both
 * definitions are kept under distinct names and each area's specs import the
 * one they always had: this file changes layout and import paths only, never
 * what a spec executes. The per-area sections at the bottom hold each area's
 * own exports verbatim, comments included.
 *
 * Reading the carried comments: they are preserved VERBATIM, so a few still say
 * "this file is a COPY, not an import of ../notify-access/harness.ts" or cite a
 * `../shell/harness.ts:156` line number. Those were true of the area file the
 * paragraph came from and are now historical: there is one file here, and the
 * paths they name no longer exist. Read them as provenance — which batch learned
 * the fix and where — not as a live pointer. Line-number cites are base-relative
 * to the area file that wrote them.
 *
 * Invariants inherited from every area harness: nothing is mocked (a green
 * golden run is the shipped chain answering on a live stack, and a red names
 * the endpoint that broke), every env read is defensive so `--list` survives
 * outside the stack (a missing piece yields {ready:false} instead of throwing),
 * and each spec self-skips at the top of its body rather than at import time.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { GUARD_MESSAGE, expect } from './guard';
import { type BrowserContext, type Locator, type Page } from '@playwright/test';
import path from 'node:path';

// ══ SHARED (≥2 areas define it; the refinement below decides
//    how many definitions each name needs) ══ ══════════════════

export interface ApiResponse {
  status: number;
  body: any;
}

/** No repoRoot/drop plumbing here on purpose: DO-2 drops no fixture, so the
 *  only node builtin this batch needs would be a dead import. DO-1's harness
 *  keeps its own. */
export interface Session {
  name: string;
  value: string;
}

const REQUIRED = [
  'FEATURE_CHECK_UI_URL',
  'FEATURE_CHECK_API_URL',
  'FEATURE_CHECK_ADMIN_USERNAME',
  'FEATURE_CHECK_ADMIN_PASSWORD',
] as const;

/** The URL PATH a Playwright request/response carried, normalized: origin and
 *  query stripped, ONE optional trailing slash removed.
 *
 *  Why exact-path equality and not endsWith(): a waitForResponse predicate that
 *  can never fire is worse than a wrong assert — the assert fails loudly, the
 *  matcher silently skips the code in the finally that restores state (DO-2
 *  measured exactly that in CI run 38148818888, where the preferences PUT's
 *  trailing-slash form never matched an endsWith predicate and the restore was
 *  skipped). DO-3 is more exposed to the sibling-route half of the same
 *  hazard: /api/household/members and /api/household/vehicles share the
 *  /api/household prefix, and a prefix matcher binds both. */

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

/**
 * Normalize a request/response URL to its pathname with one optional trailing
 * slash removed, preventing false negatives when endpoints include a trailing slash.
 */

/** Exact-path equality after trailing-slash normalization. See the header note:
 *  an absence witness is the one place a never-matching predicate is invisible. */
export function apiPath(url: string): string {
  const p = new URL(url).pathname;
  return p.length > 1 && p.endsWith('/') ? p.slice(0, -1) : p;
}

/**
 * The tripwire closing every golden spec (same one F2.1 asserts): the guard
 * patches page.route to THROW SYNCHRONOUSLY, so this never produces the
 * Promise its declared type claims; `void` marks discarding a Promise the
 * guard guarantees never exists. Call site:
 * expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE).
 */

/** The tripwire closing every golden spec (F2.1's; OP-1 calls it closedByGuard). */
export function closedByGuard(page: Page): void {
  void page.route('**/api/**', () => undefined);
}

/**
 * Seed the product tour's own completion/skip state before any navigation, so
 * the tour never runs during an auth/shell spec. Not a workaround for a flake:
 * measured on the probe stack, a FRESH browser context (no localStorage) gets
 * ProductTour running on /login itself — App.tsx mounts it for every route and
 * shouldShowTour (src/config/tourSteps.ts:23-29, keys nemotron-tour-completed
 * / -skipped) reads a virgin jar as "show it" — and its full-screen
 * .react-joyride__overlay intercepts pointer events over the Sign In button
 * (probe error-context: click retried for the full 5s actionTimeout against
 * div[data-test-id=overlay]). Whether the tour SHOULD start on the public
 * login page is F-021's row, decided by its own spec; the gate and 404 specs
 * here have no business racing it. The seed is the user's own stored state
 * after completing/skipping the tour — same category as F2.1's localStorage
 * seeding, written via addInitScript so it exists before the app boots.
 */

/**
 * Seed the product tour's own completion/skip state before any navigation, so
 * the tour never runs over the dashboard. Measured on the probe stack (FE-1,
 * documented in ../shell/harness.ts): a FRESH context boots ProductTour on
 * every route and its full-screen .react-joyride__overlay intercepts pointer
 * events — on the dashboard it would sit over the very Configure button the
 * F-042 path clicks. The seed is the user's own stored state after
 * completing/skipping the tour (F-021's row), written via addInitScript so it
 * exists before the app boots. Whether the tour SHOULD start here is F-021's
 * row, decided by its own spec.
 */

/**
 * Seed the product tour's own completion/skip state before any navigation, so
 * the tour never runs over the timeline. Measured on the probe stack (FE-1,
 * documented in ../shell/harness.ts): a FRESH context boots ProductTour on
 * every route and its full-screen .react-joyride__overlay intercepts pointer
 * events — on /timeline it would sit over the very filter chips and cards the
 * F-043/F-048 paths click. The seed is the user's own stored state after
 * completing/skipping the tour, written via addInitScript so it exists before
 * the app boots. Whether the tour SHOULD start here is F-021's row, not ours.
 */
export async function seedTourDismissed(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.setItem('nemotron-tour-completed', 'true');
    localStorage.setItem('nemotron-tour-skipped', 'true');
  });
}

// ══ SHARED NAMES THE REFINEMENT SPLIT (genuinely divergent) ══

// used by: identity / notify-access / settings-cameras / webhooks
/** Carried from sibling copies of this identical code:
 *  Verb-carrying leg: quiet-hours POST/DELETE and the per-camera PUT all
 *  need it; 204 responses have no body, so body is null there by contract.
 */
export interface AuthedFetch {
  getJson(urlPath: string): Promise<ApiResponse>;
  /** Verb-carrying leg. DO-3 needs this more than DO-2 did: every one of its
   *  CRUD rows must create its own fixture row (the stack seeds none) and
   *  delete it in the spec's finally. 204 responses have no body, so body is
   *  null there by contract — and DELETE legs legitimately accept 204-or-404
   *  when the 404 is itself the proof the row is gone. */
  send(urlPath: string, method: string, payload?: unknown): Promise<ApiResponse>;
}

// used by: analytics-alerts
export interface AuthedFetchAlerts {
  getJson(urlPath: string, init?: RequestInit): Promise<{ status: number; body: any }>;
}

// used by: identity / notify-access / settings-cameras / webhooks
export interface Harness {
  ready: true;
  api: string;
  ui: string;
  admin: { username: string; password: string };
}

// used by: analytics-alerts
export interface HarnessAlerts {
  ready: true;
  api: string;
  ui: string;
  cameraRoot: string;
  admin: { username: string; password: string };
  scenario: Scenario;
  scenarioImagePath: string;
  cameraId: string;
  /** The harness's own smoke scenario: its event is the one alert on the stack. */
  smokeScenario: Scenario;
  smokeCameraId: string;
}

// used by: operations
export interface HarnessOps {
  ready: true;
  api: string;
  ui: string;
  admin: { username: string; password: string };
}

// used by: dashboard / shell / timeline
export interface HarnessShell {
  ready: true;
  api: string;
  ui: string;
  admin: { username: string; password: string };
}

// used by: operations
export type HarnessStateOps = HarnessOps | { ready: false; why: string };

// used by: dashboard / shell / timeline
export type HarnessState = HarnessShell | { ready: false; why: string };

// used by: dashboard / notify-access / shell / timeline
/**
 * Boot the app through the UI origin the way a real user navigates: one lone
 * request wave arriving at a full nginx burst window.
 *
 * Why the pause is part of the harness, not decoration: the SPA is served
 * through the frontend container's nginx, which throttles /api by client IP —
 * zone=api rate=10r/s, `limit_req zone=api burst=20 nodelay`
 * (frontend/nginx.conf:24, rendered conf.d; the golden project runs ONE worker
 * over ONE client IP, so every spec's boot drains the same bucket). A suite
 * that boots the app twice a second keeps the bucket empty and nginx sheds
 * boot requests with `429 Server: nginx` (measured 2026-10-11: burst of 20 +
 * the 10/s refill passes ~22 of a 60-request flood; after a flood, 20
 * consecutive 200s return ~1.3 s later; a single boot's ~12 calls costs ~1.2
 * s of refill). A shed GET /api/auth/setup-status is not cosmetic:
 * ProtectedRoute fails closed on it (`setupRequired === null && error` →
 * Navigate to="/setup", src/components/auth/ProtectedRoute.tsx:79) and an
 * authenticated admin lands on "Create your admin account" (the F-003 row
 * carries the fragility). A human is a lone boot after quiet: 2 s of quiet at
 * 10 r/s restores the full 20-token burst, which covers a single boot's
 * ~12-call wave in one nodelay pass — the 10 s pause F-014's probe first used
 * was insurance for a drain nobody had measured yet; this constant is the
 * measured one (and the run got faster: F-014 21.9 s failing → 5.1 s green).
 */

/**
 * Boot the app through the UI origin the way a real user navigates: one lone
 * request wave arriving at a full nginx burst window. The full reasoning
 * (frontend/nginx.conf:24 zone=api rate=10r/s burst=20 nodelay; a shed
 * setup-status fail-closes ProtectedRoute to /setup) is measured and recorded
 * in ../shell/harness.ts — the constant is that measurement, and the golden
 * project's ONE worker over ONE client IP drains the same bucket for every
 * spec's boot. FE-2 boots the dashboard the most times of any batch (persist
 * checks reload), so this pause is load-bearing here, not decorative.
 */

/**
 * Quiet (drain the shared nginx burst), then navigate. BOOT_QUIET_MS is FE-2's
 * measured constant (a boot lands ~18 /api requests; burst=20 refills at
 * 10 r/s), and the golden project's single worker over a single client IP means
 * the timeline pays the same price the dashboard measured.
 */

/**
 * The measured nginx burst pause — the measurement itself lives in
 * ../shell/harness.ts (its BOOT_QUIET_MS comment: burst=20 + the 10 r/s refill
 * passes ~22 of a 60-request flood, and 2 s of quiet restores a full 20-token
 * burst; frontend/nginx.conf:24 zone=api rate=10r/s). Why DO-2 needs it at
 * all: the golden project runs ONE worker over ONE client IP, so every boot of
 * every spec drains the SAME bucket, and a DO-2 leg's two boots — login()'s
 * /login wave plus the settings wave, ~12 calls each, seconds apart — land
 * right at the burst edge. The shipped client cannot absorb the shed:
 * shouldRetry covers only 0/5xx (services/api.ts:901-903), so a shed
 * GET /api/notification/config THROWS, NotificationSettings' catch (:215-225)
 * leaves config null, and the whole config-gated block (:522) — every string
 * F-235 asserts — never mounts. That is ruling 125's F-235 red, observed twice:
 * the run-2 snapshot on #6996 renders "HTTP 429: Too Many Requests" (from
 * fetchApi's default message, services/api.ts:1209) where the guidance should
 * be, and main's run 38188266803 struck it ✘ then ✓ on retry (coordinator
 * census 6115961263). The node-API legs ride backend:8000 direct
 * (feature_check.py:1837) and never see nginx — only the BROWSER boots drain
 * the bucket, which is why the fix is a boot discipline, not an API-leg one.
 */
export const BOOT_QUIET_MS = 2_000;

// used by: settings-cameras
/**
 * Pause before browser navigations so the nginx `/api` rate-limit bucket
 * (`rate=10r/s`, `burst=20` in `frontend/nginx.conf:24`) refills between waves.
 */
export const BOOT_QUIET_MS_CAMERAS = 500;

// used by: dashboard / shell / timeline
/** Real POST /api/auth/login — same field names and cookie handling as F2.1/OP-1. */

/** Real POST /api/auth/login — same field names and cookie handling as F2.1/OP-1/FE-1. */

/** Real POST /api/auth/login — same field names and cookie handling as F2.1/FE-1/FE-2. */
export async function adminSession(h: HarnessShell): Promise<Session> {
  const res = await fetch(`${h.api}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: h.admin.username, password: h.admin.password }),
  });
  if (res.status !== 200) throw new Error(`admin login answered ${res.status}`);
  const pair = res.headers
    .getSetCookie()
    .map((c) => c.split(';')[0])
    .find((c) => c.includes('='));
  if (!pair) throw new Error('admin login set no session cookie');
  const i = pair.indexOf('=');
  return { name: pair.slice(0, i), value: pair.slice(i + 1) };
}

// used by: identity / notify-access / settings-cameras / webhooks
/** A real login against the real backend — the cookie is genuine state, not a
 *  mock. Split on the FIRST '=' only: a session token can carry base64 padding. */

/** A real login against the real backend — the cookie is genuine state, not a
 *  mock (the same call DO-1's harness uses, kept local so the two batches can
 *  evolve their sessions independently). */

/**
 * Authenticate against `POST /api/auth/login` on the real backend.
 * Splits on the first `=` so base64 padding in session cookies is preserved.
 */
export async function adminSessionId(h: Harness): Promise<Session> {
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

// used by: analytics-alerts
/** A real login against the real backend — the cookie is genuine state, not a mock. */
export async function adminSessionAlerts(h: HarnessAlerts): Promise<Session> {
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

// used by: operations
/** Real POST /api/auth/login — same field names and cookie handling as F2.1. */
export async function adminSessionOps(h: HarnessOps): Promise<Session> {
  const res = await fetch(`${h.api}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: h.admin.username, password: h.admin.password }),
  });
  if (res.status !== 200) throw new Error(`admin login answered ${res.status}`);
  const pair = res.headers
    .getSetCookie()
    .map((c) => c.split(';')[0])
    .find((c) => c.includes('='));
  if (!pair) throw new Error('admin login set no session cookie');
  const i = pair.indexOf('=');
  return { name: pair.slice(0, i), value: pair.slice(i + 1) };
}

// used by: operations
/** Backend-state read against the real API (NOT the UI origin — never intercepted). */
export async function api<T>(h: HarnessOps, session: Session, path: string): Promise<T> {
  const res = await fetch(`${h.api}${path}`, { headers: apiCookie(session) });
  const body = (await res.json().catch(() => null)) as T | null;
  if (res.status !== 200)
    throw new Error(`GET ${path} answered ${res.status}: ${JSON.stringify(body)?.slice(0, 200)}`);
  return body as T;
}

// used by: dashboard / shell / timeline
/** GET with the session attached Node-side (backend-state reads, never the UI origin). */

/** GET with the session attached Node-side (ground-truth reads, never the UI origin). */
export async function apiShell<T>(h: HarnessShell, session: Session, path: string): Promise<T> {
  const res = await fetch(`${h.api}${path}`, {
    headers: { Cookie: `${session.name}=${session.value}` },
  });
  const body = (await res.json().catch(() => null)) as T | null;
  if (res.status !== 200) {
    throw new Error(`GET ${path} answered ${res.status}: ${JSON.stringify(body)?.slice(0, 200)}`);
  }
  return body as T;
}

// used by: identity / notify-access / webhooks
/** End-of-spec honesty, the guard surviving the whole drive (F2.1's pin,
 *  re-armed per batch so a DO-3 spec that reached for a mock fails LOUD). */

/** End-of-spec honesty, the guard surviving the whole drive (F2.1's pin,
 *  re-armed per batch so a DO-2 spec that reached for a mock fails LOUD). */

/** End-of-spec honesty, the guard surviving the whole drive (F2.1's pin, re-armed
 *  per batch so a DO-4 spec that reached for a mock fails LOUD). */
export async function assertGuardSurvives(page: Page, h: Harness): Promise<void> {
  expect(new URL(page.url()).host).toBe(new URL(h.ui).host);
  expect(() => page.route('**/api/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
}

// used by: settings-cameras
/**
 * End-of-spec verification that the page stayed on the real UI origin and the
 * F2.1 route-interception guard remains armed.
 */
export async function assertGuardSurvivesCameras(page: Page, h: Harness): Promise<void> {
  const currentHost = await page.evaluate(() => window.location.host);
  expect(currentHost).toBe(new URL(h.ui).host);
  expect(() => page.route('**/api/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
}

// used by: analytics-alerts
/** End-of-spec honesty, the guard surviving the whole drive (F2.1's pin,
 *  re-armed here so a DO-1 spec that reached for a mock fails LOUD). */
export async function assertGuardSurvivesAlerts(page: Page, h: HarnessAlerts): Promise<void> {
  expect(new URL(page.url()).host).toBe(new URL(h.ui).host);
  expect(() => page.route('**/api/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
}

// used by: identity / notify-access / webhooks
/** Backend calls with the harness admin's session. Every DO-3 spec runs its
 *  API leg BEFORE its UI leg, so a blank screen can never pass as "renders"
 *  and an absent row can never pass as "deleted". */

/** Backend calls with the harness admin's session — the API leg every DO-2
 *  spec runs BEFORE its UI leg, so a blank screen can never pass as "renders"
 *  and an absent row can never pass as "deleted". */

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

// used by: analytics-alerts
/** Backend reads with the harness admin's session — the API leg every DO-1
 *  spec runs BEFORE its UI leg, so a blank screen can never pass as "renders". */
export function authedFetchAlerts(h: HarnessAlerts, session: Session): AuthedFetchAlerts {
  return {
    async getJson(urlPath, init) {
      const response = await fetch(`${h.api}${urlPath}`, {
        ...init,
        headers: { Cookie: `${session.name}=${session.value}`, ...(init?.headers ?? {}) },
      });
      const body = await response.json().catch(() => null);
      return { status: response.status, body };
    },
  };
}

// used by: settings-cameras
/**
 * Direct backend API client authenticated with the harness admin session cookie.
 * Runs against `h.api` (direct to backend:8000, bypassing nginx rate-limiting).
 */
export function authedFetchCameras(h: Harness, session: Session): AuthedFetch {
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
      call(urlPath, {
        method,
        body: payload === undefined ? undefined : JSON.stringify(payload),
      }),
  };
}

// used by: dashboard
/** Re-drive a navigation until the dashboard paints (see settleBoot). */
async function driveUntilBooted(
  page: Page,
  label: string,
  navigate: () => Promise<void>
): Promise<void> {
  let lastCoat = 'no-shed-coat(page painted something else)';
  for (let drive = 1; drive <= 4; drive++) {
    await navigate();
    const painted = await settleBoot(page);
    if (painted === 'booted') return;
    lastCoat = painted ?? lastCoat;
    await page.waitForTimeout(4_000); // one burst refill (10 r/s → 20 tokens in 2 s)
  }
  throw new Error(
    `${label}: 4 drives, none painted dashboard-layout (last shed coat: ${lastCoat}) — ` +
      'the shared nginx api bucket (rate=10r/s burst=20, default.conf:24,149) shed every ' +
      'attempt; this is stack saturation, not a widget failure'
  );
}

// used by: timeline
/** Re-drive a navigation until the timeline paints (see settleBoot). */
async function driveUntilBootedTimeline(
  page: Page,
  label: string,
  navigate: () => Promise<void>
): Promise<void> {
  let lastCoat = 'no-shed-coat(page painted something else)';
  for (let drive = 1; drive <= 4; drive++) {
    await navigate();
    const painted = await settleBootTimeline(page);
    if (painted === 'booted') return;
    lastCoat = painted ?? lastCoat;
    await page.waitForTimeout(4_000); // one burst refill (10 r/s → 20 tokens in 2 s)
  }
  throw new Error(
    `${label}: 4 drives, none painted timeline-page (last shed coat: ${lastCoat}) — ` +
      'the shared nginx api bucket (rate=10r/s burst=20, nginx.conf:24) shed every ' +
      'attempt; this is stack saturation, not a widget failure'
  );
}

// used by: identity / notify-access / settings-cameras / webhooks
/** The session cookie rides into the browser on the UI origin: that origin's
 *  nginx proxies /api to the backend, so the browser authenticates the way a
 *  user who logged in through this very form would. */

/**
 * Install the admin session cookie on the UI origin so nginx forwards it on `/api/*`.
 */

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

// used by: analytics-alerts
/**
 * The session cookie rides into the browser on the UI origin: that origin's
 * nginx proxies /api and /ws to the backend, so the browser authenticates the
 * way a user who logged in through this very form would. The guard does not
 * cover addCookies — a cookie is state a real login legitimately produces.
 */
export async function loginAlerts(page: Page, h: HarnessAlerts, session: Session): Promise<void> {
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

// used by: operations
/**
 * Auth both ways, deliberately: the cookie goes to the context for the
 * BROWSER's requests, and api()/authPost() attach it to Node-side fetches that
 * assert backend state BEFORE the UI (an endpoint that never answered would
 * otherwise only prove the page renders).
 *
 * authPost always sends Content-Type: application/json even with no body,
 * mirroring frontend/src/services/api.ts fetchApi:1353 — the backend's media-
 * type guard 415s a bodyless POST without it; a spec that omitted the header
 * would "discover" a bug that only exists in its own client.
 */
export async function loginAsAdmin(page: Page, h: HarnessOps): Promise<Session> {
  const session = await adminSessionOps(h);
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
  return session;
}

// used by: dashboard / shell / timeline
/**
 * Seed a real session cookie onto the UI origin (the cookie is genuine state
 * from a real login — the guard does not cover addCookies; see
 * ../dashboard-drop.spec.ts for the reasoning).
 */
export async function loginAsAdminShell(page: Page, h: HarnessShell): Promise<Session> {
  const session = await adminSession(h);
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
  return session;
}

// used by: timeline
/**
 * Quiet (drain the shared nginx burst), then navigate the UI origin and WAIT
 * FOR A BOOTED PAGE. Every golden timeline spec that reads rendered state boots
 * through here, because a coat makes the spec's FIRST expect() fail with a
 * locator error that reads like a FEATURE failure. A shed drive is re-driven
 * after one burst refill; a stack that never boots IS reported, naming the last
 * coat — saturation deserves a red, just not a misleading one.
 *
 * `path` defaults to the timeline; deep-link legs pass `?event=…`/`?camera=…`
 * (the row's own clause) and are judged on the SAME settled path.
 */
export async function quietBoot(page: Page, h: HarnessShell, path = '/timeline'): Promise<void> {
  await driveUntilBootedTimeline(page, 'quietBoot', async () => {
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.goto(h.ui + path, { waitUntil: 'domcontentloaded' });
  });
}

// used by: shell
/** Quiet (drain the shared nginx burst), then navigate the UI origin. */
export async function quietBootShell(page: Page, h: HarnessShell, path = '/'): Promise<void> {
  await page.waitForTimeout(BOOT_QUIET_MS);
  await page.goto(h.ui + path, { waitUntil: 'domcontentloaded' });
}

// used by: dashboard
/**
 * Quiet (drain the shared nginx burst), then navigate the UI origin and WAIT
 * FOR A BOOTTED PAGE. `burst=20` against a measured ~18 /api requests/second
 * per boot (frontend access log, 2026-10-12) means a boot that lands inside
 * another client's window gets SHED, and a shed boot renders a coat, not the
 * dashboard (shedCoat: /setup, /login, or the 429 error card). Every golden
 * spec that reads a rendered dashboard must boot through here, because a coat
 * makes the spec's FIRST expect() fail with a locator error that reads like a
 * FEATURE failure (measured: 4/4 reload legs → "First Time Setup"; CI run
 * 38189450762 → the toggle "missing" and "HTTP 429" snapshots). A shed drive
 * is re-driven after one burst refill; a stack that never boots IS reported,
 * naming the last coat — saturation deserves a red, just not a misleading one.
 */
export async function quietBootDash(page: Page, h: HarnessShell, path = '/'): Promise<void> {
  await driveUntilBooted(page, 'quietBoot', async () => {
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.goto(h.ui + path, { waitUntil: 'domcontentloaded' });
  });
}

// used by: identity / notify-access / settings-cameras / webhooks
/** Read the harness contract defensively: any piece missing → {ready: false,
 *  why}. Collection-time code must not throw, or `--list` breaks outside the
 *  harness. A spec consumes it as `test.skip(!h.ready, h.why)`. */

/** Read the harness contract defensively: any piece missing → {ready: false,
 *  why}. Collection-time code must not throw, or `--list` breaks outside the
 *  harness (the rule analytics-alerts/harness.ts established). */

/**
 * Read the harness contract defensively: any piece missing -> `{ ready: false, why }`.
 * Collection-time code must not throw, or `npx playwright test --project=golden --list`
 * breaks outside the feature-check harness.
 */

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

// used by: analytics-alerts
/** Read the harness contract defensively: any piece missing → {ready: false,
 *  why}. Collection-time code must not throw, or `--list` breaks outside the
 *  harness (the shape dashboard-drop.spec.ts established). */
export function readHarnessAlerts(): HarnessAlerts | { ready: false; why: string } {
  const need = [
    'FEATURE_CHECK_UI_URL',
    'FEATURE_CHECK_API_URL',
    'FEATURE_CHECK_CAMERA_ROOT',
    'FEATURE_CHECK_CAMERAS',
    'FEATURE_CHECK_SCENARIOS',
    'FEATURE_CHECK_ADMIN_USERNAME',
    'FEATURE_CHECK_ADMIN_PASSWORD',
  ] as const;
  const missing = need.filter((name) => !process.env[name]);
  if (missing.length) return { ready: false, why: `missing ${missing.join(', ')}` };

  const bookPath = String(process.env.FEATURE_CHECK_SCENARIOS);
  const camerasPath = String(process.env.FEATURE_CHECK_CAMERAS);
  if (!existsSync(bookPath)) return { ready: false, why: `no scenario book at ${bookPath}` };
  if (!existsSync(camerasPath)) return { ready: false, why: `no cameras file at ${camerasPath}` };
  let scenarios: Scenario[];
  let cameras: Record<string, string>;
  try {
    // Parse to unknown FIRST, then validate the shape. Reading `.scenarios`
    // inside the cast (as dashboard-drop.spec.ts does) yields undefined for a
    // file that parses but lacks the key, and the .find() below would then
    // throw OUTSIDE this try — breaking the collection-time rule this module's
    // own header states. Same for cameras: JSON.parse("null") is fine JS and a
    // null here would blow up cameras[name].
    const book = JSON.parse(readFileSync(bookPath, 'utf8')) as { scenarios?: Scenario[] };
    if (!Array.isArray(book.scenarios)) {
      return { ready: false, why: `${bookPath} has no "scenarios" array` };
    }
    scenarios = book.scenarios;
    const parsedCameras = JSON.parse(readFileSync(camerasPath, 'utf8')) as unknown;
    if (
      typeof parsedCameras !== 'object' ||
      parsedCameras === null ||
      Array.isArray(parsedCameras)
    ) {
      return { ready: false, why: `${camerasPath} is not a JSON object` };
    }
    cameras = parsedCameras as Record<string, string>;
  } catch (error) {
    return { ready: false, why: `harness JSON unreadable: ${String(error)}` };
  }
  const found = (name: string): Scenario | undefined =>
    scenarios.find((entry) => entry.name === name);

  const scenario = usableScenario(found(DO1_SCENARIO), DO1_SCENARIO);
  if (typeof scenario === 'string') return { ready: false, why: scenario };
  const smokeScenario = usableScenario(found(SMOKE_SCENARIO), SMOKE_SCENARIO);
  if (typeof smokeScenario === 'string') return { ready: false, why: smokeScenario };

  const cameraId = cameras[scenario.name];
  if (!cameraId) return { ready: false, why: `harness seeded no camera named ${scenario.name}` };
  const smokeCameraId = cameras[smokeScenario.name];
  if (!smokeCameraId)
    return { ready: false, why: `harness seeded no camera named ${smokeScenario.name}` };
  return {
    ready: true,
    api: String(process.env.FEATURE_CHECK_API_URL),
    ui: String(process.env.FEATURE_CHECK_UI_URL),
    cameraRoot: String(process.env.FEATURE_CHECK_CAMERA_ROOT),
    admin: {
      username: String(process.env.FEATURE_CHECK_ADMIN_USERNAME),
      password: String(process.env.FEATURE_CHECK_ADMIN_PASSWORD),
    },
    scenario,
    scenarioImagePath: path.join(path.dirname(bookPath), scenario.image),
    cameraId,
    smokeScenario,
    smokeCameraId,
  };
}

// used by: dashboard
/**
 * After a navigation has been issued, wait for the dashboard to PAINT,
 * detecting a shed coat instead of waiting out the full expect timeout.
 * Returns 'booted', a coat name, or null (neither within the window).
 */
async function settleBoot(page: Page): Promise<'booted' | string | null> {
  return Promise.race([
    page
      .getByTestId('dashboard-layout')
      .waitFor({ state: 'visible', timeout: 20_000 })
      .then(() => 'booted' as const),
    (async () => {
      // Poll for a shed coat while the boot settles: whichever appears first
      // wins. Swallow ANY throw (a closed page after the race resolved is the
      // normal case) — this promise floats once dashboard-layout paints.
      try {
        for (let t = 0; t < 40; t++) {
          const coat = await shedCoat(page);
          if (coat) return coat;
          await page.waitForTimeout(500);
        }
      } catch {
        /* page gone / detached — the race already resolved or the drive ends */
      }
      return null;
    })(),
  ]);
}

// used by: timeline
/**
 * After a navigation has been issued, wait for the timeline to PAINT, detecting
 * a shed coat instead of waiting out the full expect timeout. The paint marker
 * is `data-testid="timeline-page"` (EventTimeline.tsx:1093) — the page's own
 * root, present in grid, list and grouped modes alike, so it does not bias which
 * view mode a spec is about to assert.
 */
async function settleBootTimeline(page: Page): Promise<'booted' | string | null> {
  return Promise.race([
    page
      .getByTestId('timeline-page')
      .waitFor({ state: 'visible', timeout: 20_000 })
      .then(() => 'booted' as const),
    (async () => {
      // Poll for a shed coat while the boot settles: whichever appears first
      // wins. Swallow ANY throw (a closed page after the race resolved is the
      // normal case) — this promise floats once timeline-page paints.
      try {
        for (let t = 0; t < 40; t++) {
          const coat = await shedCoatTimeline(page);
          if (coat) return coat;
          await page.waitForTimeout(500);
        }
      } catch {
        /* page gone / detached — the race already resolved or the drive ends */
      }
      return null;
    })(),
  ]);
}

// used by: timeline
/** A reload that settles like quietBoot (SAME url, so localStorage + cookies ride along). */
export async function settledReload(page: Page): Promise<void> {
  await driveUntilBootedTimeline(page, 'settledReload', async () => {
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.reload({ waitUntil: 'domcontentloaded' });
  });
}

// used by: dashboard
/**
 * A reload that settles like quietBoot: quiet first, then `page.reload()`
 * (SAME url, so localStorage + cookies ride along — the persistence legs
 * depend on that and must not be rewritten as a goto), then the paint-vs-coat
 * race. config-modal.spec.ts proved the bare-quietBoot pattern is NOT enough:
 * it quietBoots and then reloads, and it was THAT boot which painted the 429
 * coat in the 2026-10-12 regression (6 reds, all of them other lanes' specs
 * hitting the same shed reload path). A test whose clause IS "reload lands on
 * X" still judges X itself; this only guarantees it judges it on a page that
 * actually booted.
 */
export async function settledReloadDash(page: Page): Promise<void> {
  await driveUntilBooted(page, 'settledReload', async () => {
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.reload({ waitUntil: 'domcontentloaded' });
  });
}

// used by: dashboard
/**
 * The three ways a SHED boot renders instead of the dashboard. All three were
 * read from the app's own pixels (Playwright aria snapshots), not inferred:
 *   • 'setup'  — a shed GET /api/auth/setup-status (query `retry: false`,
 *     AuthContext.tsx:137) leaves setupRequired null WITH an error, and the
 *     guard's fail-close redirects to /setup (`ProtectedRoute.tsx:79-80`): a
 *     logged-in admin sees heading "First Time Setup".
 *   • 'login'  — a shed current-user query (AuthContext.tsx:157-162, also
 *     `retry: false`) reads as unauthenticated → /login, heading "Welcome
 *     Back" (LoginPage.tsx:207).
 *   • 'err429' — a shed dashboard-data fetch flips DashboardPage's error
 *     branch (:434), which REPLACES the whole layout: heading "Error Loading
 *     Dashboard" + "HTTP 429: Too Many Requests". This coat also UNMOUNTS
 *     DashboardLayout, so a Configure modal open at that moment disappears
 *     with it — the CI attempt-1 "widget-toggle not found" signature.
 * A settled boot must never be judged against one of these: they are the
 * nginx bucket shedding requests, not the feature the row promises.
 */
async function shedCoat(page: Page): Promise<string | null> {
  if (
    await page
      .getByText('First Time Setup')
      .first()
      .isVisible()
      .catch(() => false)
  )
    return 'setup';
  if (
    await page
      .getByText('Welcome Back')
      .first()
      .isVisible()
      .catch(() => false)
  )
    return 'login';
  if (
    (await page
      .getByText('Error Loading Dashboard')
      .first()
      .isVisible()
      .catch(() => false)) ||
    (await page
      .getByText(/HTTP 429/)
      .first()
      .isVisible()
      .catch(() => false))
  )
    return 'err429';
  return null;
}

// used by: timeline
/**
 * The ways a SHED boot renders instead of the timeline, read from the app's own
 * pixels. Two are app-wide and shared with FE-2; two are this page's own:
 *   • 'setup'  — a shed GET /api/auth/setup-status (AuthContext.tsx:137,
 *     `retry:false`) leaves setupRequired null WITH an error and the guard
 *     fail-closes to /setup (ProtectedRoute.tsx:79-80): heading "First Time Setup".
 *   • 'login'  — a shed current-user query (AuthContext.tsx:157-162) reads as
 *     unauthenticated → /login, heading "Welcome Back".
 *   • 'err429' — EventTimeline's own error branch replaces the list with
 *     "Error Loading Events" + the thrown message (EventTimeline.tsx:1637),
 *     which is where a shed /api/events lands. This is the coat that must never
 *     be judged as "the timeline shows no events".
 *   • 'empty'  — the shipped no-results branch (EventTimeline.tsx:1643-1648,
 *     EmptyState title "No Events Found"). NOT a shed coat: it is a real render
 *     of a real state, so settleBoot does not treat it as failure. It is
 *     exported separately so a spec can say "the page booted and has no events"
 *     in one read instead of racing a locator.
 */
async function shedCoatTimeline(page: Page): Promise<string | null> {
  if (
    await page
      .getByText('First Time Setup')
      .first()
      .isVisible()
      .catch(() => false)
  )
    return 'setup';
  if (
    await page
      .getByText('Welcome Back')
      .first()
      .isVisible()
      .catch(() => false)
  )
    return 'login';
  if (
    await page
      .getByText('Error Loading Events')
      .first()
      .isVisible()
      .catch(() => false)
  )
    return 'err429';
  return null;
}

// used by: notify-access
/** The three ways a SHED boot renders instead of the settings panel. Same
 *  coats ../dashboard/harness.ts reads on the dashboard: a shed setup-status
 *  query fail-closes ProtectedRoute to /setup ("First Time Setup"), a shed
 *  current-user query reads as logged-out (/login, "Welcome Back"), and a shed
 *  config fetch flips NotificationSettings' error box (:496-500), which prints
 *  the raw "HTTP 429: Too Many Requests". A coat is the bucket shedding, not
 *  the feature — it must never be what an assert is judging. */
async function shedCoatNotify(page: Page): Promise<string | null> {
  if (
    await page
      .getByText('First Time Setup')
      .first()
      .isVisible()
      .catch(() => false)
  )
    return 'setup';
  if (
    await page
      .getByText('Welcome Back')
      .first()
      .isVisible()
      .catch(() => false)
  )
    return 'login';
  if (
    (await page
      .getByText(/HTTP 429/)
      .first()
      .isVisible()
      .catch(() => false)) ||
    (await page
      .getByText('Error Loading Dashboard')
      .first()
      .isVisible()
      .catch(() => false))
  )
    return 'err429';
  return null;
}

// used by: settings-cameras
async function shedCoatCameras(page: Page): Promise<string | null> {
  if (
    await page
      .getByText('First Time Setup')
      .first()
      .isVisible()
      .catch(() => false)
  ) {
    return 'setup';
  }
  if (
    await page
      .getByText('Welcome Back')
      .first()
      .isVisible()
      .catch(() => false)
  ) {
    return 'login';
  }
  if (
    (await page
      .getByText(/HTTP 429/)
      .first()
      .isVisible()
      .catch(() => false)) ||
    (await page
      .getByText('Error Loading Dashboard')
      .first()
      .isVisible()
      .catch(() => false))
  ) {
    return 'err429';
  }
  return null;
}

/** F2.3's four ops-side batches each spelled the same 4-member env contract as
 *  their own interface. Ruling 148 unifies the shape; these aliases keep every
 *  spec's `import { type DashboardHarness }` resolving without touching a spec's
 *  type usage. (analytics-alerts' Harness is a genuine superset — it carries
 *  cameraRoot/scenario/smoke* — so it stays its own definition, not an alias.) */
export type DashboardHarness = Harness;
export type ShellHarness = Harness;
export type OpsHarness = Harness;
export type TimelineHarness = Harness;

// ══ operations ══ ════════════════════════════════════
/**
 * Shared plumbing for the OP-1 operations golden paths (F2.3, ruling 87;
 * claim: uplevel/F2.3-ops-a-batches).
 *
 * Unmocked exactly like ../dashboard-drop.spec.ts (guard.ts enforces it), and
 * it reads the harness contract for a DIFFERENT reason than F2.1 does: an
 * operations page needs a logged-in session and the stack's entry points, not
 * a scenario book and a camera — so readOpsHarness() demands only the four
 * pieces it actually uses. The collection-time rule carries over verbatim:
 * Playwright runs COLLECTION before any runtime skip, so every env read is
 * defensive and returns {ready:false} instead of throwing, and each spec self-
 * skips at body top (`test.info().skip(...)`) the way F2.1's body does.
 */

export function readOpsHarness(): HarnessStateOps {
  const missing = REQUIRED.filter((name) => !process.env[name]);
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

export function apiCookie(session: Session): Record<string, string> {
  return { Cookie: `${session.name}=${session.value}` };
}

export async function authPost<T>(
  h: HarnessOps,
  session: Session,
  path: string,
  body?: unknown
): Promise<T> {
  const res = await fetch(`${h.api}${path}`, {
    method: 'POST',
    headers: { ...apiCookie(session), 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let parsed: unknown = null;
  try {
    parsed = JSON.parse(text) as unknown;
  } catch {
    /* non-JSON body: fall through to the raw text */
  }
  if (res.status !== 200 && res.status !== 201) {
    throw new Error(`POST ${path} answered ${res.status}: ${text.slice(0, 200)}`);
  }
  return parsed as T;
}

/** authPost for endpoints that 204 or answer non-JSON; asserts only the status. */
export async function authPostOk(
  h: HarnessOps,
  session: Session,
  path: string,
  body?: unknown
): Promise<void> {
  const res = await fetch(`${h.api}${path}`, {
    method: 'POST',
    headers: { ...apiCookie(session), 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status < 200 || res.status >= 300) {
    throw new Error(`POST ${path} answered ${res.status}: ${(await res.text()).slice(0, 200)}`);
  }
}

export async function authDelete<T>(
  h: HarnessOps,
  session: Session,
  path: string,
  body?: unknown
): Promise<T> {
  const res = await fetch(`${h.api}${path}`, {
    method: 'DELETE',
    headers: { ...apiCookie(session), 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const parsed = (await res.json().catch(() => null)) as T | null;
  if (res.status !== 200)
    throw new Error(
      `DELETE ${path} answered ${res.status}: ${JSON.stringify(parsed)?.slice(0, 200)}`
    );
  return parsed as T;
}

/** Poll an API endpoint until done() holds (deadline throws with the last body). */
export async function pollApi<T>(
  h: HarnessOps,
  session: Session,
  path: string,
  done: (body: T) => boolean,
  timeoutMs: number
): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  let last: T | null = null;
  for (;;) {
    last = await api<T>(h, session, path);
    if (done(last)) return last;
    if (Date.now() > deadline) {
      throw new Error(`poll ${path} timed out; last: ${JSON.stringify(last).slice(0, 300)}`);
    }
    await new Promise((r) => setTimeout(r, 2_000));
  }
}

/**
 * Open one /operations collapsible section and prove it is open.
 *
 * Two measured traps decide the shape here, both from the probe stack:
 *
 * 1. aria-expanded is STALE on the button and must not be read. The page
 *    wires every section CONTROLLED (SystemMonitoringPage.tsx:476-620:
 *    isOpen={sectionStates[id]} onToggle={() => toggleSection(id)}).
 *    Measured on the probe stack, the button's aria-expanded does not track
 *    the mounted section: every toggle reads "false" at boot, INCLUDING the
 *    sections the hook says are open (worker-management, gpu-history — panel
 *    present, aria "false"), and after a click that opens a closed section
 *    the fiber's memoizedProps.isOpen is already true while the DOM
 *    attribute still reads "false". Whether the cause is a stale commit or
 *    an attribute React never re-writes, a spec that reads aria decides on
 *    a value the page itself does not honor.
 * 2. The PANEL MOUNT is the live signal. The panel body unmounts when
 *    closed (CollapsibleSection.tsx Transition show={isExpanded}, ~:104) and
 *    commits carry the fresh value (probe: closed section's panel absent at
 *    boot, its content visible after one click; the state ALSO mirrors to
 *    localStorage 'system-page-sections' with fresh values).
 *
 * So: decide whether to click from a panel-mount read (never a blind click —
 * seven sections default expanded, useSystemPageSections.ts
 * DEFAULT_SECTION_STATES), then poll the same mount to prove it.
 */
export async function openSection(page: Page, sectionId: string): Promise<void> {
  // Section root is "{sectionId}-section", toggle "{sectionId}-section-toggle"
  // (CollapsibleSection.tsx:59,77 — the toggle testid is the ROOT id + suffix;
  // the button is the root's DIRECT child, the closed section's root holds
  // nothing else).
  const toggle = page.getByTestId(`${sectionId}-section-toggle`);
  const root = page.getByTestId(`${sectionId}-section`);
  await expect(toggle).toBeVisible();
  const panelMounted = async () => (await root.locator(':scope > div').count()) > 0;
  if (!(await panelMounted())) await toggle.click();
  await expect.poll(panelMounted, { timeout: 5_000 }).toBe(true);
}

/**
 * Wait for a panel that fetches its own data to reach its SUCCESS render,
 * driving the panel's built-in Retry through any transient error state.
 *
 * Why this exists (measured on the harness stack): the backend's pipeline
 * workers hammer redis (BLPOP poll_timeout=5, pipeline_workers.py:243) while
 * the otel exporter retries an OTLP endpoint this compose does not ship
 * (config.py:2108 defaults http://alloy:4317; alloy is absent), and under a
 * Playwright burst the event loop contends enough that admin GETs fail at the
 * redis middleware — the panel then sits in its error branch until ITS OWN
 * retry runs. useSupervisorStatus only self-retries on the 10 s poll
 * (useSupervisorStatus.ts, setInterval branch); PipelineLatencyHistoryPanel
 * ships an explicit Retry button (:204). A spec that asserts success with a
 * 5 s budget fails on a transient the page is designed to recover from; the
 * honest golden path is to use the product's recovery affordance and assert
 * it recovers. `error` must be a locator scoped INSIDE the panel (the latency
 * panel's error branch REUSES the root testid — page-global would collide).
 */
export async function panelRecovers(
  root: Locator,
  error: Locator,
  loading?: Locator,
  opts: { retryIntervalMs?: number } = {}
): Promise<void> {
  await expect
    .poll(
      async () => {
        if (loading && (await loading.count()) > 0) return false; // in flight — don't mistake for success
        if ((await error.count()) === 0) return true;
        const retry = root.getByRole('button', { name: 'Retry' });
        if (await retry.isVisible().catch(() => false)) await retry.click();
        return false;
      },
      { timeout: 60_000, intervals: [opts.retryIntervalMs ?? 1_500] }
    )
    .toBe(true);
}

// ══ shell ══ ═════════════════════════════════════════
/**
 * Shared plumbing for the FE-1 app-shell golden paths (F2.3, ruling 87;
 * claim: uplevel/F2.3-frontend-batches, rows F-001–F-007, F-012–F-014,
 * F-016–F-018, F-020–F-027).
 *
 * Sibling of ../operations/harness.ts (OP-1, uplevel/F2.3-ops-a-batches): the
 * same unmocked contract (guard.ts enforces it), the same collection-time rule
 * — Playwright runs COLLECTION before any runtime skip, so every env read is
 * defensive and returns {ready:false} instead of throwing, and each spec
 * self-skips at body top. It does NOT import that file: ruling 87 keeps each
 * batch's files inside its own area dir, so a shared module across batches
 * would make two lanes' PRs depend on each other's merge. The duplication is
 * the price of the file rule, same as OP-1 paid it against F2.1.
 *
 * What the app shell adds beyond OP-1's four env pieces: the shell is the
 * FIRST page the stack ever shows, so these specs care about the unauthenticated
 * state too — shellHarness exposes the bare (cookieless) entry points and a
 * login helper, and the auth-gate specs never log in at all.
 */

export function readShellHarness(): HarnessState {
  const missing = REQUIRED.filter((name) => !process.env[name]);
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

// ══ dashboard ══ ═════════════════════════════════════
/**
 * Shared plumbing for the FE-2 dashboard golden paths (F2.3, ruling 87;
 * claim #6978; rows F-028, F-029, F-031–F-034, F-038–F-040, F-042).
 *
 * Third sibling of ../shell/harness.ts (FE-1) and ../operations/harness.ts
 * (OP-1): the same unmocked contract (guard.ts enforces it), the same
 * collection-time rule — Playwright runs COLLECTION before any runtime skip,
 * so every env read is defensive and returns {ready:false} instead of
 * throwing, and each spec self-skips at body top. It does NOT import a
 * sibling's copy: ruling 87 keeps each batch's files inside its own area dir
 * so two lanes' PRs never depend on each other's merge. The duplication is
 * the price of the file rule, same as FE-1 and OP-1 paid it.
 *
 * What the dashboard adds over the shell's four env pieces: these paths are
 * DATA-MIRROR rows. The dashboard renders whatever the stack's own APIs
 * answer — camera counts, event stats, summaries — so the harness's job is
 * the Node-side ground-truth read (`api`) the UI must then mirror, not
 * scenario seeding. Every assertion here compares the DOM against a real
 * response from the same stack, so a pass means the shipped chain works and a
 * red names the exact endpoint/widget that broke.
 */

export function readDashboardHarness(): HarnessState {
  const missing = REQUIRED.filter((name) => !process.env[name]);
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

// ══ timeline ══ ══════════════════════════════════════
/**
 * Shared plumbing for the FE-3 timeline golden paths (F2.3, ruling 87;
 * claim #7049; rows F-043, F-045–F-049, F-052–F-054, F-056–F-057, F-059–F-062,
 * F-064).
 *
 * Fourth sibling of ../shell/harness.ts (FE-1), ../dashboard/harness.ts (FE-2)
 * and the ops batches: the same unmocked contract (`guard.ts` enforces it from
 * the interception call itself, UR-127), the same collection-time rule —
 * Playwright runs COLLECTION before any runtime skip, so every env read is
 * defensive and returns {ready:false} instead of throwing, and each spec
 * self-skips at body top. It does NOT import a sibling's copy: ruling 87 keeps
 * each batch's files inside its own area dir so two lanes' PRs never depend on
 * each other's merge. The duplication is the price of the file rule, same as
 * FE-1 and FE-2 paid it (`../dashboard/harness.ts:1-17` records the same
 * reasoning).
 *
 * What the timeline adds over the dashboard's data-mirror shape: these rows are
 * INTERACTION rows. The dashboard renders what an API answers; the timeline
 * lets the user change state (review a batch, save notes, export, add a face)
 * and then must SHOW that change. So this harness exports the Node-side
 * ground-truth read (`api`, a real response from the same stack) AND
 * `apiWrite`, its real write twin, so a spec can drive a mutation the way the
 * UI's own button does and then compare the DOM against a fresh read of the
 * same row. A pass means the shipped chain works; a red names the endpoint or
 * widget that broke. Nothing here mocks: `guard.ts` throws if a spec tries.
 *
 * The boot/shed machinery below is copied from ../dashboard/harness.ts because
 * the cause is stack-wide, not page-specific: frontend/nginx.conf:24 publishes
 * `zone=api rate=10r/s burst=20 nodelay`, and a golden run drives ONE client IP
 * (the golden project is one worker, serial), so every spec's boot drains the
 * same bucket. A SHED boot does not render the page — it renders a "coat" (see
 * shedCoat), and a spec that judged its first expect() against a coat would
 * read like a feature failure. Measured on the probe stack; FE-2's regression
 * run (CI 38189450762) is the witness quoted there.
 */

/** Defensive by contract: a missing env is a SKIP reason, never a collection crash. */
export function readTimelineHarness(): HarnessState {
  const missing = REQUIRED.filter((name) => !process.env[name]);
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

/**
 * The write twin of `api`. Timeline rows mutate (reviewed, notes, feedback,
 * export, face enrollment), so a spec must be able to ask the SAME question the
 * button asks and read the row back. Deliberately un-opinionated about method
 * and status: the caller names the endpoint and asserts the contract, because a
 * harness that silently accepted a 4xx would hide the very bug these rows test.
 * A non-2xx THROWS with the body, so a spec red reads as "the route answered N"
 * rather than as a locator timeout.
 */
export async function apiWrite<T>(
  h: HarnessShell,
  session: Session,
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string,
  payload?: unknown
): Promise<T> {
  const res = await fetch(`${h.api}${path}`, {
    method,
    headers: {
      Cookie: `${session.name}=${session.value}`,
      'Content-Type': 'application/json',
    },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  const body = (await res.json().catch(() => null)) as T | null;
  if (res.status < 200 || res.status >= 300) {
    throw new Error(
      `${method} ${path} answered ${res.status}: ${JSON.stringify(body)?.slice(0, 200)}`
    );
  }
  return body as T;
}

/**
 * View mode is localStorage-backed: EventTimeline.tsx:115 reads
 * `useLocalStorage<ViewMode>('timeline-view-mode', 'grid')`. A spec that flips
 * to list view and then reloads inherits that state, which is exactly what the
 * persistence legs WANT; but a spec that never intends it must not inherit it
 * from a sibling that ran earlier in the same context. This clears only that
 * one key so each spec starts on the shipped default (grid).
 */
export async function seedDefaultViewMode(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.removeItem('timeline-view-mode');
  });
}

/** The shipped empty render, checked only when a boot has already failed to paint. */
export async function timelineShowsEmpty(page: Page): Promise<boolean> {
  return page
    .getByText('No Events Found')
    .first()
    .isVisible()
    .catch(() => false);
}

/* -------------------------------------------------------------------------- */
/* The batch's event fixture — measured, not assumed.                          */
/*                                                                             */
/* FE-3's rows are browse/mutation rows: they need EVENTS to show. The naive   */
/* premise ("events come only from the VLM pipeline, ruling 90, so an          */
/* event-less stack is the honest regime") is wrong in two ways, both measured: */
/*   1. CI's feature-check harness seeds CAMERAS ONLY (feature_check.py:2098   */
/*      → run.seed_cameras(); there is no event-seed step), so a golden stack   */
/*      really does boot with 0 events — an assertion that needs rows would be  */
/*      RED at CI head, not merely here. That is not a regime to skip past.     */
/*   2. The repo ships a sanctioned way to put rows in: ops-a's merged          */
/*      data-ui/trash-restore.spec.ts:91-93 documents it for exactly this case  */
/*      ("A fresh CI golden stack can boot with zero events, so the pool is     */
/*      guaranteed via POST /api/admin/seed/events"), and operations/audit.spec */
/*      .ts:37 seeds cameras the same way. FE-3 uses the narrower tool below.   */
/*                                                                             */
/* Why POST /api/events/bulk rather than the precedent's /api/admin/seed/events: */
/* seed_events picks a RANDOM camera among all (admin.py:513), so it can drop a */
/* row on the drop spec's scenario camera — whose assertion is                  */
/* `expect(items.length).toBe(1)` (dashboard-drop.spec.ts:222) and which counts */
/* events for ITS camera only. bulk names the camera (events.py:1543-1552) and */
/* needs no admin gate, so FE-3 stays surgical: one dedicated camera, all rows   */
/* on it, nothing else's counts touched.                                        */
/* -------------------------------------------------------------------------- */

/** The batch's own camera name; the backend derives the id from it (measured). */
export const FIXTURE_CAMERA_NAME = 'fe3-timeline-probe';

/**
 * Rows FE-3 creates. Deliberately FEWER THAN THE PAGE SIZE (limit 20,
 * EventTimeline.tsx:183): with total ≤ 20 the shipped infinite query never
 * fetches a second page, so an unfiltered DOM↔API mirror is exact. A fixture
 * over 20 would make page 2 load and the unfiltered mirror would then compare
 * 40 cards to 20 rows — a false red. Infinite scroll therefore stays
 * unverified by this batch's F-043 spec and is named in the PR body.
 */
export const FIXTURE_ROWS: ReadonlyArray<{ riskScore: number; riskLevel: string }> = [
  { riskScore: 91, riskLevel: 'critical' },
  { riskScore: 80, riskLevel: 'high' },
  { riskScore: 55, riskLevel: 'medium' },
  { riskScore: 22, riskLevel: 'low' },
  { riskScore: 12, riskLevel: 'low' },
  { riskScore: 8, riskLevel: 'low' },
];

interface CameraRow {
  id: string;
  name: string;
}

interface CameraListBody {
  items?: CameraRow[];
}

interface CameraCreated {
  id: string;
  name: string;
  /** Present on the route's 409, where the existing id travels (`ensureCamera`). */
  detail?: string;
}

interface BulkResult {
  index: number;
  status: string;
  id: number | null;
  error: string | null;
}

interface BulkBody {
  total: number;
  succeeded: number;
  failed: number;
  results: BulkResult[];
}

/**
 * A camera this file just created is INVISIBLE to `GET /api/cameras` for up to a
 * minute, and that is a backend cache contract rather than a UI bug — so FE-3
 * waits it out instead of pretending it isn't there. Measured twice at head
 * `82f79a4f4`, which is what turned CI's `Feature check (fake AI)` red here:
 *
 *  - CI's own artifact: `#camera-filter` reported `""` where the fixture id was
 *    expected, and the run's aria snapshot lists the select's ONLY options as
 *    the five cameras the harness seeds (`person-at-door … harness-smoke`, which
 *    is exactly what the run's own `cameras.json` names). The DOM faithfully
 *    reported the response it got.
 *  - the probe stack, by hand: prime `GET /api/cameras` → `POST /api/cameras`
 *    (201; `GET /api/cameras/{id}` answers 200 for it, `status:"online"`) → poll
 *    the plain list: absent for ~15 s, then present once the key's TTL expired.
 *
 * Why waiting is the only lever this batch has (each fact measured; the fix
 * would live in `backend/`, which ruling 87 keeps out of this PR):
 *  - `list_cameras` is cache-aside on a 60 s entry and a HIT never touches the DB
 *    (`cameras.py:194-217`; `SHORT_TTL = 60` at `cache_service.py:60`).
 *  - The camera invalidation cannot fire: `CacheKeys` bakes the *global* prefix
 *    into the key (`hsi:cache:cameras:list:all`, `cache_service.py:752-762`)
 *    while `invalidate_pattern` prepends only `cache:` to `"cameras:*"` (`:486`,
 *    `:577`), so the SCAN pattern can never match it. Confirmed against Redis in
 *    the probe stack: exactly one key, `cache:hsi:cache:cameras:list:all`. The
 *    same mismatch defeats the product's own escape hatch — `POST
 *    /api/admin/maintenance/clear-cache` answered `{"keys_cleared":0,
 *    "cache_types":[]}` and left that key sitting at `ttl=60`.
 *  - A cache hit does NOT refresh the TTL (`redis_cluster.py:316-333` is a bare
 *    GET), which is what makes a bounded poll converge instead of livelocking:
 *    the entry expires, the next read misses, and the refill comes from the DB,
 *    which already has the row.
 *
 * Cost: one extra GET on a stack that already has the camera (the first poll
 * passes); on a fresh stack, at most one TTL window, once per file. The wait must
 * happen BEFORE the boot because `useCamerasQuery` defaults `refetchInterval` to
 * `false` (`hooks/useCamerasQuery.ts:150`) — a page booted inside the window
 * never corrects itself, which is why the failure surfaced as a locator timeout
 * and not as a recoverable re-render.
 */
const CAMERA_LIST_WAIT_BUDGET_MS = 90_000; // > SHORT_TTL (60 s) + margin
const CAMERA_LIST_POLL_MS = 3_000;

export async function waitForCameraInList(
  h: HarnessShell,
  session: Session,
  name: string
): Promise<void> {
  const deadline = Date.now() + CAMERA_LIST_WAIT_BUDGET_MS;
  let polls = 0;
  for (;;) {
    polls += 1;
    const list = await apiShell<CameraListBody>(h, session, '/api/cameras');
    if ((list.items ?? []).some((cam) => cam.name === name)) return;
    if (Date.now() >= deadline) {
      throw new Error(
        `fixture: '${name}' never appeared in GET /api/cameras within ` +
          `${CAMERA_LIST_WAIT_BUDGET_MS}ms (${polls} polls). That list is a 60 s ` +
          `cache entry that is not converging — see waitForCameraInList's note: ` +
          `the stack's cache, not the timeline UI.`
      );
    }
    await new Promise((resolve) => setTimeout(resolve, CAMERA_LIST_POLL_MS));
  }
}

/**
 * Find FE-3's own camera by name, creating it when the stack has never seen it.
 *
 * A 409 is a ROUTINE outcome here, not a failure, and must never take the file
 * down: the list read below can be the stale cached answer above, so "not in the
 * list" does not mean "not in the DB". CI's red is exactly that sequence — a
 * retry POSTed the camera its first attempt had already created, died on
 * `Camera with name 'fe3-timeline-probe' already exists (id:
 * fe3_timeline_probe)`, and every remaining test in the file reported as
 * not-run. The id travels inside that 409's own `detail` (measured) and it is
 * the DB's id, so a conflict is parsed rather than thrown and then confirmed
 * against `GET /api/cameras/{id}` — which is NOT cache-aside (`cameras.py:683-
 * 720` reads the DB). A 409 whose detail cannot be parsed still fails loudly,
 * with the route's own body in the message.
 */
async function ensureCamera(
  h: HarnessShell,
  session: Session,
  name: string,
  folderPath: string
): Promise<string> {
  const list = await apiShell<CameraListBody>(h, session, '/api/cameras');
  const known = (list.items ?? []).find((cam) => cam.name === name);
  if (known) return known.id;

  // Deliberately NOT apiWrite: its documented contract is "a non-2xx THROWS",
  // and that contract is what makes other specs' failures name the endpoint.
  // Here a 409 is an EXPECTED answer, so this one call reads its own status and
  // every other non-2xx still surfaces with the route's body in the message.
  const res = await fetch(`${h.api}/api/cameras`, {
    method: 'POST',
    headers: {
      Cookie: `${session.name}=${session.value}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name, folder_path: folderPath }),
  });
  const created = (await res.json().catch(() => null)) as CameraCreated | null;
  if (res.status >= 200 && res.status < 300) {
    const id = created?.id;
    if (!id) throw new Error(`fixture: POST /api/cameras for '${name}' 2xx had no id`);
    return id;
  }
  if (res.status !== 409) {
    throw new Error(
      `fixture: POST /api/cameras for '${name}' answered ${res.status}: ` +
        JSON.stringify(created).slice(0, 200)
    );
  }
  const detail = created?.detail ?? '';
  const found = detail.match(/already exists \(id: ([^)]+)\)/);
  const id = found ? found[1] : null;
  if (!id) {
    throw new Error(
      `fixture: POST /api/cameras for '${name}' answered 409 with an unparseable ` +
        `detail: ${detail.slice(0, 200)}`
    );
  }
  // Confirm the recovered id is real (an uncached read) before the file builds on it.
  await api<{ id: string }>(h, session, `/api/cameras/${encodeURIComponent(id)}`);
  return id;
}

export interface TimelineFixture {
  /** Backend-assigned id of FE-3's own camera (never hardcoded: derived). */
  cameraId: string;
  /** Ids of the rows this call created, in request order. */
  eventIds: number[];
  /** Every row currently on the fixture camera, from the same read a mirror uses. */
  rowsOnCamera: number;
}

/**
 * Give FE-3 a browse regime: one dedicated camera plus FIXTURE_ROWS events on
 * it. Idempotent by design — a re-run against a dirty dev stack finds the
 * existing camera instead of tripping its name-unique 409 (measured:
 * `Camera with name '…' already exists (id: …)`), and each call adds rows with
 * fresh batch ids.
 *
 * Measured contracts this helper depends on (all probed against the lane's
 * probe stack, not read off a doc):
 *  - POST /api/cameras accepts {name, folder_path} alone and does NOT probe the
 *    folder on disk (201 for a path that does not exist), and it derives the id
 *    from the name with dashes folded to underscores — so the id is READ, never
 *    assumed. CI's harness creates its cameras the same way
 *    (feature_check.py:1413-1419) and likewise reads `body["id"]`.
 *  - POST /api/events/bulk answers 207 with per-item results (events.py:1493-
 *    1509). `events.batch_id` is UNIQUE (measured UniqueViolationError), so one
 *    batch_id per row: reusing a single id lands exactly one row and poisons the
 *    session for the rest ("Transaction commit failed").
 *  - The bulk tier is rate-limited (10/min, burst 2, rate_limit.py:617-623) but
 *    the route schema allows 100 events per request (schemas/bulk.py:122-126),
 *    so ONE call per spec file is well inside the budget: 4 successive single-
 *    request calls measured ≥4×OK.
 *  - bulk_create_events does NOT broadcast on /ws/events (no EventBroadcaster
 *    call anywhere in :1526-1608), so a fixture row can never satisfy F-045's
 *    "arriving over the socket" clause. That row needs the fake VLM's drop path
 *    and is NOT unlocked by this fixture.
 *
 * It creates rows only; it never deletes anyone else's, and `clear_existing` is
 * never sent (that flag on the admin seed route wipes every event, admin.py:476-
 * 485). Cleanup lives in `softDeleteFixtureRows`.
 */
export async function createTimelineFixture(
  h: HarnessShell,
  session: Session
): Promise<TimelineFixture> {
  const cameraId = await ensureCamera(
    h,
    session,
    FIXTURE_CAMERA_NAME,
    '/cameras/fe3_timeline_probe'
  );
  // The UI's camera select is built from GET /api/cameras, whose answer can be a
  // stale cache entry (see waitForCameraInList). The page must not boot before it
  // names this camera, or F-043's deep-link legs assert against a select that
  // legitimately never saw it — which is the CI red this note records.
  await waitForCameraInList(h, session, FIXTURE_CAMERA_NAME);

  // Re-runs on a persistent stack must not accumulate rows on THIS camera, or a
  // row-count mirror would compare the DOM against a number that grew between
  // two legs of one run. Everything already on the fixture camera is FE-3's own
  // residue (the camera is FE-3's own name), so soft-delete it first — the same
  // reversible delete `softDeleteFixtureRows` performs, never a permanent one.
  const stale = await apiShell<{ items: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  await softDeleteFixtureRows(
    h,
    session,
    stale.items.map((row) => row.id)
  );

  // Distinct batch_id per row — events.batch_id is UNIQUE (measured). The suffix
  // keeps ids unique across re-runs of the same file on a persistent dev stack.
  const salt = Date.now();
  const events = FIXTURE_ROWS.map((row, i) => ({
    batch_id: `fe3-${salt}-${i}`,
    camera_id: cameraId,
    started_at: new Date(Date.UTC(2026, 9, 13, 4, i * 7)).toISOString(),
    risk_score: row.riskScore,
    risk_level: row.riskLevel,
    summary: `FE-3 fixture row ${i} (${row.riskLevel})`,
  }));
  const bulk = await apiWrite<BulkBody>(h, session, 'POST', '/api/events/bulk', { events });
  if (bulk.succeeded !== events.length) {
    throw new Error(
      `fixture: bulk create succeeded ${bulk.succeeded}/${events.length}; first error: ` +
        String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)
    );
  }
  const eventIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);

  const onCamera = await apiShell<{ items: unknown[]; pagination: { total: number } }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  return { cameraId, eventIds, rowsOnCamera: onCamera.pagination.total };
}

/**
 * Best-effort tidy-up: soft-delete the rows FE-3 created (measured: DELETE
 * /api/events/{id} answers 204 and the row lands in GET /api/events/deleted —
 * the trash, i.e. exactly where a user's own deletion goes, and reversible via
 * POST /api/events/{id}/restore).
 *
 * Deliberately NOT a permanent delete: `DELETE /api/events/bulk` is a bulk-tier
 * route (events.py:1733-1749) whose budget the fixture already spends, and
 * irreversible cleanup in a shared stack is worse than a recoverable residue.
 * Order matters for honesty: this runs in the file's afterAll, and the golden
 * project is one serial worker, so FE-3 is the LAST file to run (a --list of
 * the golden project places timeline/ 63rd of 63) — no merged spec reads the
 * trash or the camera list after these rows move.
 */
export async function softDeleteFixtureRows(
  h: HarnessShell,
  session: Session,
  eventIds: number[]
): Promise<void> {
  for (const id of eventIds) {
    // Each row is independent; a 409 (already deleted) is not worth failing an
    // afterAll over, so settle instead of using apiWrite's throwing contract.
    await fetch(`${h.api}/api/events/${id}`, {
      method: 'DELETE',
      headers: { Cookie: `${session.name}=${session.value}` },
    }).catch(() => undefined);
  }
}

/* -------------------------------------------------------------------------- */
/* The stats fixture (F-047) — a SECOND camera, on purpose.                    */
/*                                                                             */
/* F-043 may soft-delete its own rows, and GET /api/events/stats has NO        */
/* deleted_at predicate (events.py:609-623 filters dates + camera only), so    */
/* trash on a shared camera would be counted into F-047's totals. Measured:    */
/* after soft-deleting 1 of 2 rows, GET /api/events said total:1 while a stats */
/* read on a cache key never used before the delete said total_events:2. A     */
/* separate camera is therefore the cheap fix; the mismatch itself is recorded */
/* in the PR body and the inventory row's Notes, not hidden by the fixture.    */
/*                                                                             */
/* Cleanup is a HARD delete here for the same reason: `soft_delete:false` on   */
/* DELETE /api/events/bulk (events.py:1733-1803) removes the row outright, so  */
/* a later run's totals start from this file's own rows only. F-043 keeps the  */
/* reversible soft delete — its mirrors count LIVE rows, which excludes trash.  */
/* -------------------------------------------------------------------------- */

/** FE-3's stats camera: distinct from FIXTURE_CAMERA_NAME for the reason above. */
export const STATS_CAMERA_NAME = 'fe3-stats-probe';

/**
 * Rows for the stats panel: one per risk level, so the panel's four level cards
 * and the chart's bar set are each individually checkable (a fixture with two
 * `low` rows cannot tell a mislabelled card from a mislabelled bar).
 */
export const STATS_FIXTURE_ROWS: ReadonlyArray<{
  riskScore: number;
  riskLevel: 'critical' | 'high' | 'medium' | 'low';
}> = [
  { riskScore: 91, riskLevel: 'critical' },
  { riskScore: 70, riskLevel: 'high' },
  { riskScore: 45, riskLevel: 'medium' },
  { riskScore: 10, riskLevel: 'low' },
];

export interface StatsFixture {
  cameraId: string;
  eventIds: number[];
  /** The UTC calendar day (YYYY-MM-DD) every row was stamped INSIDE. The
   *  date-filter leg must pass THIS back as its range, never `new Date()` —
   *  see the stamp note below for why the runner's clock is the wrong answer. */
  day: string;
}

/**
 * One dedicated camera plus STATS_FIXTURE_ROWS on it. The rows share ONE stamp
 * so no midnight can split them, and the fixture returns that stamp's own UTC
 * day so the date-filter leg reads back the day it wrote rather than asking the
 * runner's clock for "today" (the golden suite's clock is the runner's, and a
 * boot in the first hour of a UTC day made `now - 40..55 min` land on YESTERDAY
 * — run 38488280792 at 00:06:59Z saw all four rows fall out of a
 * start=end=today range: 4 expected, 0 received).
 *
 * The stats panel applies NO default time window (`get_event_stats` filters on
 * `start_date`/`end_date` only when supplied, backend/api/routes/events.py:624)
 * and EventTimeline seeds its filter state empty (EventTimeline.tsx:101), so
 * recency is irrelevant to what renders — only the DAY the rows share matters,
 * and that day is now returned, not guessed.
 *
 * Idempotent the same way createTimelineFixture is, but the purge is a HARD one
 * — see the block header for why soft is not enough for a counts fixture.
 */
export async function createStatsFixture(h: HarnessShell, session: Session): Promise<StatsFixture> {
  const cameraId = await ensureCamera(h, session, STATS_CAMERA_NAME, '/cameras/fe3_stats_probe');
  // Same contract as the browse fixture: F-047's three legs all navigate with
  // ?camera=<id>, and a select that cannot name the camera is a boot the panel
  // never recovers from (refetchInterval is false).
  await waitForCameraInList(h, session, STATS_CAMERA_NAME);

  // Residue from an earlier run would inflate every count this file asserts.
  // Live rows first (cheap, single read), then anything already in the trash on
  // THIS camera — which only this file's own cleanup could have put there, since
  // no other spec names this camera.
  const stale = await apiShell<{ items: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  await hardDeleteFixtureRows(
    h,
    session,
    stale.items.map((row) => row.id)
  );
  // Trash on this camera, from the route ops-a's spec uses. NOTE: GET
  // /api/events/deleted takes NO limit/start param (events.py:1411-1413 — its
  // only argument is the db) and reports `pagination.limit: 1000` while ignoring
  // any query string, so this read returns the WHOLE trash and the camera filter
  // below is client-side, not a server narrowing.
  const trashed = await apiShell<{ items: { id: number; camera_id: string }[] }>(
    h,
    session,
    '/api/events/deleted'
  );
  await hardDeleteFixtureRows(
    h,
    session,
    trashed.items.filter((row) => row.camera_id === cameraId).map((row) => row.id)
  );

  const salt = Date.now();
  // ONE shared instant ~6 h ago, not a 40..55 min spread. The spread was the
  // landmine: 40-55 minutes before 00:30Z is 23:50 on the PREVIOUS UTC day, so
  // a run booting in the first hour of a day put the whole fixture outside a
  // "today" range (and a spread that wide could straddle midnight and split the
  // fixture across two days, so no single-day range could ever hold it). 6 h
  // back keeps the instant inside the scrubber's default 24 h window too, which
  // is what the panel's boot render needs.
  const instant = new Date(Date.now() - 6 * 3_600_000);
  const day = instant.toISOString().slice(0, 10);
  const events = STATS_FIXTURE_ROWS.map((row, i) => ({
    batch_id: `fe3s-${salt}-${i}`, // UNIQUE per row (measured UniqueViolationError)
    camera_id: cameraId,
    started_at: instant.toISOString(),
    risk_score: row.riskScore,
    risk_level: row.riskLevel,
    summary: `FE-3 stats fixture row ${i} (${row.riskLevel})`,
  }));
  const bulk = await apiWrite<BulkBody>(h, session, 'POST', '/api/events/bulk', { events });
  if (bulk.succeeded !== events.length) {
    throw new Error(
      `stats fixture: bulk create succeeded ${bulk.succeeded}/${events.length}; first error: ` +
        String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)
    );
  }
  const eventIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);
  return { cameraId, eventIds, day };
}

/**
 * Permanent delete via DELETE /api/events/bulk {soft_delete:false} (measured:
 * 207, `succeeded: 2, failed: 0`, and the rows disappear from stats too).
 * Chosen over the per-row soft delete ONLY where a spec asserts COUNTS, because
 * soft-deleted rows keep counting there (see the block header).
 */
export async function hardDeleteFixtureRows(
  h: HarnessShell,
  session: Session,
  eventIds: number[]
): Promise<void> {
  if (eventIds.length === 0) return;
  for (const id of eventIds) {
    // B4.4 requires an event to be in Trash before permanent purge: soft-delete
    // first (no-op 409 if already in Trash), then purge with ?permanent=true.
    // Using the per-row routes avoids spending the bulk-tier rate-limit budget.
    await fetch(`${h.api}/api/events/${id}`, {
      method: 'DELETE',
      headers: { Cookie: `${session.name}=${session.value}` },
    }).catch(() => undefined);
    await fetch(`${h.api}/api/events/${id}?permanent=true`, {
      method: 'DELETE',
      headers: { Cookie: `${session.name}=${session.value}` },
    }).catch(() => undefined);
  }
}

/**
 * Wait for the timeline's first event page to LAND, i.e. for the shipped
 * infinite query (EventTimeline.tsx:182 → useEventsQuery → GET /api/events,
 * api.ts:2292) to have resolved into rendered cards. Returns the card count.
 *
 * Returns the count rather than throwing on zero because a leg can still
 * legitimately filter to nothing (a `?verdict=confirmed` deep link on a stack
 * whose rows carry no verification — verifications are written only by the VLM
 * pipeline, ruling 90, and `bulk_create_events` writes none: a created row's
 * `verification` is null, measured). The caller then mirrors 0 against the API's
 * 0 and asserts the shipped empty render, which is a real judgement.
 */
export async function waitForEventCards(page: Page): Promise<number> {
  // The skeleton (EventCardSkeleton) is the in-flight marker; the cards are the
  // landed marker. Race them so an empty answer is not waited out at full timeout.
  const cards = page.getByTestId(/^event-card-\d+$/);
  await Promise.race([
    cards
      .first()
      .waitFor({ state: 'visible', timeout: 20_000 })
      .catch(() => undefined),
    page
      .getByText('No Events Found')
      .first()
      .waitFor({ state: 'visible', timeout: 20_000 })
      .catch(() => undefined),
  ]);
  return cards.count();
}

/* -------------------------------------------------------------------------- */
/* The detail fixture (F-056, F-057) — a THIRD camera, on purpose.             */
/*                                                                             */
/* These two rows mutate the row itself (`reviewed`, `notes`), so they cannot   */
/* share FIXTURE_CAMERA_NAME: F-043's legs mirror DOM card COUNTS against that  */
/* camera's rows, and a row this file marks reviewed is still a row — but a     */
/* later F2.3 spec that filters by `reviewed` would find this camera's rows     */
/* carrying state its own fixture never wrote. A separate camera keeps every    */
/* file's ground truth its own. (Ruling 87 also forbids touching the shared     */
/* harness the OTHER areas use, which is why each area has its own file.)       */
/*                                                                             */
/* FIVE rows, not one, and the last two are the point: `mark-reviewed` renders  */
/* only while `!event.reviewed` (EventDetailModal.tsx:1337, EventListView.tsx:  */
/* 408), so "the event shows reviewed" is a count that must go DOWN BY ONE, not  */
/* to zero. Asserting a disappearance of the whole set would pass on a UI that   */
/* blanked the list, and the untouched rows are the negative control that stops  */
/* that. Each leg owns its OWN row because the golden project is one serial      */
/* worker over a per-file fixture: a PATCH from an earlier test is still on the  */
/* row when a later test starts, so shared rows make a leg's starting state a    */
/* function of test order. The fifth row belongs to the `test.fixme` reopen leg — */
/* it stays note-free today, and when the read-back defect is repaired and the   */
/* fixme lifted that leg must still begin with nothing stored.                   */
/* -------------------------------------------------------------------------- */

/** FE-3's detail camera: distinct from the browse and stats cameras (see above). */
export const DETAIL_CAMERA_NAME = 'fe3-detail-probe';

/**
 * Rows for the detail-modal paths. Five, deliberately: four get exercised and one
 * is never touched, so a leg that marks one reviewed can assert the other rows'
 * affordances SURVIVED. `notes: null` is not settable here — the bulk route never
 * passes `notes` (events.py:1551-1560 builds Event(...) without it) and the column
 * defaults to NULL (models/event.py:78) — which is exactly the starting state
 * F-057 needs, measured: a fresh row reads `notes: None`.
 */
export const DETAIL_ROWS: ReadonlyArray<{ riskScore: number; riskLevel: string }> = [
  { riskScore: 88, riskLevel: 'critical' },
  { riskScore: 72, riskLevel: 'high' },
  { riskScore: 51, riskLevel: 'medium' },
  { riskScore: 18, riskLevel: 'low' },
  { riskScore: 33, riskLevel: 'low' },
];

export interface DetailFixture {
  cameraId: string;
  /** Row ids in request order; the spec names which leg uses which. */
  eventIds: number[];
}

/**
 * One dedicated camera plus DETAIL_ROWS on it, for the two PATCH-backed detail
 * rows. Same idempotence as the other two fixtures — `ensureCamera` absorbs the
 * name-unique 409, and `waitForCameraInList` waits out the 60 s camera-list
 * cache BEFORE any boot, because the modal's camera chip and the filter select
 * are both built from that cached list.
 *
 * Cleanup is the HARD delete: these rows accumulate mutations (`reviewed: true`,
 * a note) across re-runs, and a re-run needs its rows UNreviewed and note-free
 * for the transition to be a transition. A soft delete would leave them in the
 * trash but leave `reviewed: true` on the row a restore brings back.
 */
export async function createDetailFixture(
  h: HarnessShell,
  session: Session
): Promise<DetailFixture> {
  const cameraId = await ensureCamera(h, session, DETAIL_CAMERA_NAME, '/cameras/fe3_detail_probe');
  await waitForCameraInList(h, session, DETAIL_CAMERA_NAME);

  // Purge this camera's residue from an earlier run, hard, for the reason in the
  // block comment: only the bulk hard delete clears the mutated flags by removing
  // the row outright (events.py:1733-1803, `soft_delete:false`).
  const stale = await apiShell<{ items: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  await hardDeleteFixtureRows(
    h,
    session,
    stale.items.map((row) => row.id)
  );

  const salt = Date.now();
  const events = DETAIL_ROWS.map((row, i) => ({
    batch_id: `fe3d-${salt}-${i}`, // events.batch_id is UNIQUE (measured)
    camera_id: cameraId,
    started_at: new Date(Date.UTC(2026, 9, 13, 5, i * 11)).toISOString(),
    risk_score: row.riskScore,
    risk_level: row.riskLevel,
    summary: `FE-3 detail fixture row ${i} (${row.riskLevel})`,
  }));
  const bulk = await apiWrite<BulkBody>(h, session, 'POST', '/api/events/bulk', { events });
  if (bulk.succeeded !== events.length) {
    throw new Error(
      `detail fixture: bulk create succeeded ${bulk.succeeded}/${events.length}; first ` +
        `error: ${String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)}`
    );
  }
  const eventIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);
  if (eventIds.length !== DETAIL_ROWS.length) {
    throw new Error(
      `detail fixture: got ${eventIds.length} ids for ${DETAIL_ROWS.length} rows — ` +
        'the legs index these positionally, so a missing id must fail here.'
    );
  }
  // Every row must arrive UNreviewed and note-free, or the "transition" these two
  // rows claim is a no-op against state a previous run left behind. Asserted
  // against the uncached single-read route (`events.py:1870` takes no cache dep).
  for (const id of eventIds) {
    const row = await apiShell<{ reviewed: boolean; notes: string | null }>(
      h,
      session,
      `/api/events/${id}`
    );
    if (row.reviewed || row.notes !== null) {
      throw new Error(
        `detail fixture: row ${id} arrived reviewed=${row.reviewed} notes=${String(
          row.notes
        )} — F-056/F-057 assert a TRANSITION, so the fixture must start clean.`
      );
    }
  }
  return { cameraId, eventIds };
}

/* -------------------------------------------------------------------------- */
/* The SEARCH fixture (F-048) — a FOURTH camera, on purpose.                    */
/*                                                                              */
/* It cannot share FIXTURE_CAMERA_NAME: F-043's legs mirror DOM card counts     */
/* against that camera's rows, and F-048's purge HARD-deletes 25 rows on boot.   */
/* It also cannot reuse the DETAIL camera, whose legs assert "starts unreviewed" */
/* and "starts note-free" — a search fixture that later marks rows reviewed      */
/* would make that file's precondition a function of file order.                */
/*                                                                              */
/* TWENTY-FIVE rows is not a taste number. The search panel's own pagination    */
/* (`SearchResultsPanel.tsx:57` totalPages = ceil(total/limit)) renders its      */
/* Next/Previous buttons ONLY while totalPages > 1, and the page size is the     */
/* component's defaultLimit = 20 (EventTimeline.tsx:163-170). Twenty-five is the */
/* smallest count above 20 whose second page is non-empty, so the paging clause */
/* can be driven at all — and the second page holds exactly 5 rows, which is a   */
/* count a leg asserts rather than a count it hopes for.                        */
/*                                                                              */
/* THE VICTIM ROW'S ROLE CHANGED WITH [r211b]. One extra row is still SOFT-      */
/* deleted after seeding, but its PURPOSE inverted. Before [r211b] the search    */
/* route had no `deleted_at` predicate while browse did, so the victim was a     */
/* guaranteed search HIT that could never be in `filteredEvents` — the defect    */
/* leg clicked it. [r211b] gave search the SAME predicate browse has             */
/* (backend/services/search.py:451; browse's is events.py:421), so now BOTH      */
/* readers hide it: search total drops by the victim, and GET /api/events/{id}   */
/* still 404s. The victim is now the fixture's NEGATIVE control — createSearch-  */
/* Fixture asserts search EXCLUDES it, and the defect leg's closing line reddens */
/* if search ever re-lists it. For the page-2 live rows: search paginates        */
/* server-side while `filteredEvents` holds only browse's loaded page-1          */
/* newest-20, and post-[r211f] `useEventModalRow` resolves any selected event id */
/* outside `filteredEvents` by fetching `/api/events/{id}` on miss.              */
/* -------------------------------------------------------------------------- */

/** FE-3's search camera: distinct from the browse, stats and detail cameras. */
export const SEARCH_CAMERA_NAME = 'fe3-search-probe';

/** Live rows the search legs page through. See the block comment for why 25. */
export const SEARCH_FIXTURE_SIZE = 25;

/**
 * The shared token every fixture row's summary carries. A leg narrows to ONE row
 * with `${SEARCH_QUERY_TOKEN} alpha <i>`, and every locator derives from the
 * fixture rather than hardcoding a name — an accessible-name assertion written
 * against a literal is one summary edit away from silently matching a different
 * widget (the sidebar's "Recent threats indicator" is also a role=button).
 */
export const SEARCH_QUERY_TOKEN = 'fe3f048searchtoken';

/**
 * The victim's summary. It carries SEARCH_QUERY_TOKEN (so the query would match
 * it) but NOT the `alpha <i>` form (so no live-row locator can ever aim at it by
 * accident, and a leg can name it out loud). Declared AFTER the token it
 * interpolates: these are `const`s, so the order is a TDZ error, not a style
 * preference. Since [r211b] the search route hides soft-deleted rows, so this
 * summary no longer appears in search results — the fixture keeps the row to
 * prove THAT (`toBe(false)` in the defect leg), not to be listed.
 */
export const SEARCH_VICTIM_SUMMARY = `${SEARCH_QUERY_TOKEN} deleted-but-still-listed`;

/**
 * Rows actually seeded: the 25 live ones plus the soft-deleted victim. The victim
 * is given the OLDEST `started_at` so that, were it ever to reappear in the
 * result set (a search-route regression that un-hides soft-deleted rows), it
 * would land at the BOTTOM — on page 2 — under the live rows, leaving page 1
 * identical to the browse list's page 1. That is what keeps the modal's positive
 * control honest: a page-1 click opens the modal because the row really is in the
 * cached list, not by luck. For page 2 of the LIVE rows (`alpha 0`, the oldest
 * live row): search shows it while the browse cache does not, and post-[r211f]
 * `useEventModalRow` resolves it by fetching `/api/events/{id}` on miss (ruling
 * 221).
 */
export const SEARCH_SEED_ROWS = SEARCH_FIXTURE_SIZE + 1;

export interface SearchFixture {
  cameraId: string;
  /** The 25 live rows, in seed order. `alpha <i>` in the summary is this index. */
  eventIds: number[];
  /** The soft-deleted row: hidden by search, absent from browse, 404 by id. */
  victimId: number;
  /** What the SEARCH route calls the total for this token — the victim excluded. */
  searchTotal: number;
  /** What the BROWSE route calls the total — the victim excluded. */
  browseTotal: number;
  /** Rows the server calls `high`, so the severity leg asserts a measured number. */
  highTotal: number;
}

/**
 * One camera, SEARCH_FIXTURE_SIZE live rows, and one soft-deleted row.
 *
 * `risk_score` alternates 72/45 so `risk_level` alternates high/medium — that is
 * what makes the severity filter leg an ASSERTION (12 of 25 high) instead of a
 * restatement of the fixture. `started_at` is spread one minute apart over 3 h
 * ending now, because search's tie-break is `started_at DESC` (search.py:465, moved
 * from :432 when [r211b] inserted the predicate above it) and
 * identical timestamps would make page contents arbitrary.
 *
 * The purge is HARD (`soft_delete:false`) and it asks the SEARCH route as well as
 * the browse list for this camera's ids. Before [r211b] the two disagreed by
 * design: a run that died between the soft-delete and `afterAll` left an orphan
 * invisible to `GET /api/events` but PRESENT in search, so a browse-only purge
 * would leave it and the next run would seed 26 rows and read "of 26" where it
 * asserts "of 25". [r211b] made search hide soft-deleted rows
 * (`backend/services/search.py:451`), so that orphan is now invisible to BOTH
 * readers: the search-route read can no longer recover it, but neither can it
 * corrupt the counts — it is excluded from `total_count` and from `items`, so a
 * lingering orphan is inert. An orphan a run left BEFORE its soft-delete is fully
 * live and both readers still list and purge it.
 */
export async function createSearchFixture(
  h: HarnessShell,
  session: Session
): Promise<SearchFixture> {
  const cameraId = await ensureCamera(h, session, SEARCH_CAMERA_NAME, '/cameras/fe3_search_probe');
  // The camera <select> and the camera chip are built from the cached list, so a
  // just-created camera must age out of that 60 s entry before any boot.
  await waitForCameraInList(h, session, SEARCH_CAMERA_NAME);

  const salt = Date.now();
  const purge = async (path: string) => {
    // Best-effort on purpose: an unexpected extra row must not turn the fixture
    // red before it has tried to remove it. The count assertions below are the
    // place that mismatch becomes visible, with the number in the message.
    const stale = await apiShell<{ items?: { id: number }[]; results?: { id: number }[] }>(
      h,
      session,
      path
    ).catch(() => null);
    const ids = (stale?.items ?? stale?.results ?? []).map((row) => row.id);
    await hardDeleteFixtureRows(h, session, ids);
  };
  await purge(`/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`);
  await purge(
    `/api/events/search?q=${encodeURIComponent(SEARCH_QUERY_TOKEN)}&limit=100&camera_id=${encodeURIComponent(
      cameraId
    )}`
  );

  // Row 0 is the victim: the OLDEST timestamp in the set (see SEARCH_SEED_ROWS)
  // and a summary no live-row locator aims at. It is deliberately MEDIUM so the
  // live set is exactly HALF-1 high, which makes the severity leg's expectation
  // a number rather than a hope.
  const windowStart = Date.now() - 3 * 3_600_000;
  const events = Array.from({ length: SEARCH_SEED_ROWS }, (_, i) =>
    i === 0
      ? {
          batch_id: `fe3s-${salt}-victim`,
          camera_id: cameraId,
          started_at: new Date(windowStart).toISOString(),
          risk_score: 45,
          risk_level: 'medium',
          summary: SEARCH_VICTIM_SUMMARY,
        }
      : {
          batch_id: `fe3s-${salt}-${i}`, // events.batch_id is UNIQUE (measured)
          camera_id: cameraId,
          started_at: new Date(windowStart + i * 60_000).toISOString(),
          // 72 and 45, NOT 91: `risk_level` is a stored column (event.py:63) but
          // every reader reports `computed_risk_level`, a CASE over risk_score
          // (:393-424, ≤29 low / ≤59 medium / ≤84 high / else critical). A row
          // declared `high` with score 91 therefore REPORTS `critical` while the
          // filter still matches it as `high` — measured — which makes the count
          // this file asserts depend on which of the two you ask. These scores
          // agree with their labels, so the severity leg measures the filter
          // instead of that disagreement. The disagreement itself is F-048's own
          // `test.fixme` leg, where both fields are named on purpose.
          risk_score: i % 2 === 0 ? 72 : 45,
          risk_level: i % 2 === 0 ? 'high' : 'medium',
          summary: `${SEARCH_QUERY_TOKEN} alpha ${i - 1}`,
        }
  );
  const bulk = await apiWrite<BulkBody>(h, session, 'POST', '/api/events/bulk', { events });
  if (bulk.succeeded !== events.length) {
    throw new Error(
      `search fixture: bulk create succeeded ${bulk.succeeded}/${events.length}; first ` +
        `error: ${String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)}`
    );
  }
  const allIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);
  if (allIds.length !== events.length) {
    throw new Error(
      `search fixture: got ${allIds.length} ids for ${events.length} rows — the legs name ` +
        'rows positionally by their `alpha <i>` summary, so a missing id must fail here.'
    );
  }

  // The victim is seeded at index 0 and carries its own summary, so the live rows
  // keep the contiguous `alpha 0 … alpha 24` naming the legs use. `results` comes
  // back in request order (the assumption createDetailFixture already makes), so
  // index 0 IS the victim.
  const victimId = allIds[0];
  await apiWrite<{ succeeded: number }>(h, session, 'DELETE', '/api/events/bulk', {
    event_ids: [victimId],
    soft_delete: true,
  });

  // The fixture's own premises, asserted at creation: if the server ever starts
  // agreeing with itself about the victim, the defect leg's claim stops meaning
  // what it says and this is the place that becomes obvious.
  const searchTruth = await apiShell<{
    total_count: number;
    results: { id: number; risk_level: string }[];
  }>(
    h,
    session,
    `/api/events/search?q=${encodeURIComponent(SEARCH_QUERY_TOKEN)}&limit=100&camera_id=${encodeURIComponent(
      cameraId
    )}`
  );
  const browseTruth = await apiShell<{ items: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  const liveIds = browseTruth.items.map((row) => row.id);
  // Plain throws, not `expect`: this file is a harness, and "the stack cannot
  // supply the fixture this file needs" must never be reported as a product
  // failure. Same idiom as createDetailFixture's precondition checks.
  const requireFixture = (premise: boolean, why: string): void => {
    if (!premise) throw new Error(`search fixture: ${why}`);
  };
  requireFixture(
    !searchTruth.results.some((row) => row.id === victimId),
    'search must EXCLUDE the soft-deleted row ([r211b]: the search route filters ' +
      '`Event.deleted_at IS NULL`, backend/services/search.py:451) — the defect leg ' +
      'measures a LIVE page-2 row now, so a search route that listed the victim again ' +
      'would mean this fixture is pinning a different product than the leg claims'
  );
  requireFixture(
    !liveIds.includes(victimId),
    'the browse list must EXCLUDE it, or getModalEvent could find it and the defect ' +
      'leg would be measuring something else'
  );
  requireFixture(
    liveIds.length === SEARCH_FIXTURE_SIZE,
    `the camera must hold exactly ${SEARCH_FIXTURE_SIZE} live rows after seeding, or ` +
      `every "of ${SEARCH_FIXTURE_SIZE}" this file asserts is wrong (got ${liveIds.length})`
  );
  // Report the server's own numbers rather than the fixture's arithmetic: the
  // severity and total assertions then mirror the DOM against the instrument that
  // produced them, which is the difference between a checked count and a guess.
  return {
    cameraId,
    eventIds: allIds.slice(1), // index 0 is the victim, not a live row
    victimId,
    searchTotal: searchTruth.total_count, // excludes the victim → SEARCH_FIXTURE_SIZE
    browseTotal: liveIds.length, // excludes it → SEARCH_FIXTURE_SIZE
    highTotal: searchTruth.results.filter((row) => row.risk_level === 'high').length,
  };
}

/* -------------------------------------------------------------------------- */
/* F-060 FEEDBACK FIXTURE                                                       */
/*                                                                              */
/* Its OWN camera, for the reason the block above states about the search       */
/* camera: this feature WRITES A ROW PER EVENT, and the mutation's success path */
/* invalidates `['feedbackStats']` — a count every other FE-3 file ignores but  */
/* one they would all disturb if feedback rows accumulated on a shared camera.  */
/*                                                                              */
/* THE CASCADE IS THE WHOLE CLEANUP STRATEGY, and it is declared, not assumed:  */
/* `event_feedback.event_id` is `ForeignKey("events.id", ondelete="CASCADE")`   */
/* (backend/models/event_feedback.py:77-78), so the hard purge that             */
/* `hardDeleteFixtureRows` already performs also removes each row's feedback.   */
/* Measured on the probe stack, same run: POST /api/feedback → 201, then        */
/* DELETE /api/events/bulk {soft_delete:false} → 207 succeeded:1, then          */
/* GET /api/feedback/event/<id> → 404 (feedback row cascaded with the event).   */
/* There is NO standalone feedback-delete endpoint, and none is                 */
/* needed — which matters because a fixture that could not clear its feedback   */
/* would be unrunnable here, not merely untidy: the same UNIQUE(event_id)       */
/* (:78) that makes the second POST a 409 would make the second RUN a 409.     */
/*                                                                              */
/* FOUR ROWS, ONE PER LEG. UNIQUE(event_id) means one feedback per event, so    */
/* legs cannot share a row the way read-only legs can; the fourth is seeded     */
/* WITH feedback by this fixture so the row's "sees the saved feedback when     */
/* reopening" clause can be measured with NO UI action at all — if a leg had to */
/* POST through the UI first, a broken read-back would be indistinguishable     */
/* from a broken write, and this file needs to tell those two apart.            */
/* -------------------------------------------------------------------------- */

/** FE-3's feedback camera: distinct from the browse, stats, detail, search. */
export const FEEDBACK_CAMERA_NAME = 'fe3-feedback-probe';

/** One row per leg: quick path, notes form, derived notes, pre-seeded read-back. */
export const FEEDBACK_FIXTURE_SIZE = 4;

/** Every fixture row carries this, so a purge or a count can name the set. */
export const FEEDBACK_SUMMARY_TOKEN = 'fe3f060feedback';

/**
 * The score every row is seeded with. 45 is `medium` under BOTH implementations
 * of `risk_level` (stored column, and `computed_risk_level`'s ≤59 branch,
 * backend/models/event.py:393-424), which matters here for a reason unrelated to
 * severity: the panel renders `currentRiskScore={event.risk_score ?? undefined}`
 * (EventDetailModal.tsx:543 → :1146) and `handleSubmitWithNotes` PREFIXES the
 * typed notes with `Current score: ${currentRiskScore}. ` (:207-213). A leg that
 * asserts the STORED string therefore needs a score that is unambiguous in the
 * fixture — not one whose label another reader would contradict.
 */
export const FEEDBACK_RISK_SCORE = 45;

/** What the notes-form leg types. Kept out of the token so it is findable. */
export const FEEDBACK_TYPED_NOTES = 'the garden hose looked like a person';

/** What the fixture seeds on the read-back row, before any UI action. */
export const FEEDBACK_SEEDED_NOTES = 'seeded before this run opened the modal';

/** The calibration value seeded on that row, rendered by NO part of the card. */
export const FEEDBACK_SEEDED_THREAT_LEVEL = 'no_threat';

export interface FeedbackFixture {
  cameraId: string;
  /** The four rows in seed order; legs name them by the constants in the spec. */
  eventIds: number[];
  /** Row 3: has a feedback row already, written by the fixture rather than the UI. */
  seededEventId: number;
  /** Notes exactly as the server stored them (read back, not echoed by memory). */
  seededNotes: string;
}

/**
 * One camera, FEEDBACK_FIXTURE_SIZE rows at FEEDBACK_RISK_SCORE, and a feedback
 * row on the LAST one.
 *
 * The purge is hard and runs before seeding (a previous run that died mid-leg
 * leaves a feedback row that would 409 this run's POST), and it relies on the
 * CASCADE documented above — there is no other door.
 *
 * `requireFixture` (plain throws, same idiom as the search fixture) checks the
 * two premises the legs cannot see: that the seeded feedback is REALLY there and
 * that row 0 really has none. Without the second premise the quick leg's
 * "buttons appeared" would be a card that was already there.
 */
export async function createFeedbackFixture(
  h: HarnessShell,
  session: Session
): Promise<FeedbackFixture> {
  const cameraId = await ensureCamera(
    h,
    session,
    FEEDBACK_CAMERA_NAME,
    '/cameras/fe3_feedback_probe'
  );
  // The camera <select> is built from the 60 s cached list; see the search fixture.
  await waitForCameraInList(h, session, FEEDBACK_CAMERA_NAME);

  const stale = await apiShell<{ items?: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  ).catch(() => null);
  await hardDeleteFixtureRows(
    h,
    session,
    (stale?.items ?? []).map((row) => row.id)
  );

  const salt = Date.now();
  const windowStart = Date.now() - 3 * 3_600_000;
  const bulk = await apiWrite<BulkBody>(h, session, 'POST', '/api/events/bulk', {
    events: Array.from({ length: FEEDBACK_FIXTURE_SIZE }, (_, i) => ({
      batch_id: `fe3fb-${salt}-${i}`, // events.batch_id is UNIQUE (measured)
      camera_id: cameraId,
      started_at: new Date(windowStart + i * 60_000).toISOString(),
      risk_score: FEEDBACK_RISK_SCORE,
      risk_level: 'medium',
      summary: `${FEEDBACK_SUMMARY_TOKEN} ${i}`,
    })),
  });
  const eventIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);
  if (eventIds.length !== FEEDBACK_FIXTURE_SIZE) {
    throw new Error(
      `feedback fixture: got ${eventIds.length} ids for ${FEEDBACK_FIXTURE_SIZE} rows; ` +
        `succeeded ${bulk.succeeded}/${FEEDBACK_FIXTURE_SIZE}; first error: ` +
        String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)
    );
  }

  const seededEventId = eventIds[FEEDBACK_FIXTURE_SIZE - 1];
  await apiWrite<{ id: number }>(h, session, 'POST', '/api/feedback', {
    event_id: seededEventId,
    feedback_type: 'false_positive',
    notes: FEEDBACK_SEEDED_NOTES,
    actual_threat_level: FEEDBACK_SEEDED_THREAT_LEVEL,
  });

  const requireFixture = (premise: boolean, why: string): void => {
    if (!premise) throw new Error(`feedback fixture: ${why}`);
  };
  const live = await apiShell<{ items: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  );
  requireFixture(
    live.items.length === FEEDBACK_FIXTURE_SIZE,
    `the camera must hold exactly ${FEEDBACK_FIXTURE_SIZE} rows after seeding ` +
      `(got ${live.items.length})`
  );
  // Read the seeded row back through the SAME endpoint the panel calls, so the
  // read-back leg is measuring the panel's data source rather than the POST's
  // own response. Notes come from here, not from the constant, so a server that
  // normalises the string shows up as a leg failure with the real value in it.
  const seeded = await apiShell<{
    notes: string | null;
    feedback_type: string;
    actual_threat_level: string | null;
  }>(h, session, `/api/feedback/event/${seededEventId}`);
  requireFixture(
    seeded.notes === FEEDBACK_SEEDED_NOTES,
    `the seeded feedback must be readable at the endpoint the panel uses ` +
      `(got ${JSON.stringify(seeded.notes)})`
  );
  requireFixture(
    seeded.actual_threat_level === FEEDBACK_SEEDED_THREAT_LEVEL,
    'the calibration field must survive the round trip, or the card-omission ' +
      'leg has nothing to omit'
  );
  return { cameraId, eventIds, seededEventId, seededNotes: seeded.notes ?? '' };
}

/* -------------------------------------------------------------------------- */
/* The AUDIT fixture (F-061 / F-062) — a SIXTH camera.                          */
/*                                                                              */
/* Same isolation rule as the search fixture's block above: these legs read     */
/* counts and states that a foreign row could falsify, and this fixture's purge */
/* HARD-deletes its own rows on boot. It also cannot share the feedback camera, */
/* whose precondition is "row 0 has NO feedback row" — a shared camera would    */
/* make that a function of file order.                                          */
/* -------------------------------------------------------------------------- */

/** FE-3's audit camera: distinct from the browse, stats, detail, search, feedback. */
export const AUDIT_CAMERA_NAME = 'fe3-audit-probe';

/**
 * THE ONE NUMBER THIS FIXTURE EXISTS TO OWN.
 *
 * `POST /api/ai-audit/batch` has NO camera filter — `BatchAuditRequest`
 * (backend/api/schemas/ai_audit.py:524-526) offers only `limit`,
 * `min_risk_score`, `force_reevaluate` — so a spec that wanted to aim a batch
 * at ITS OWN row had no lever… until it counted the other rows. Every other
 * FE-3 fixture row tops out at 91 (the maximum over `FIXTURE_ROWS`,
 * `STATS_FIXTURE_ROWS`, `DETAIL_ROWS` and `FEEDBACK_RISK_SCORE`, derived below as
 * `SIBLING_MAX_RISK_SCORE`; the search fixture's inline scores max at 72), so a
 * fixture row at 99 sits strictly above every one of them and
 * `min_risk_score: 99, limit: 1` selects exactly that row.
 * Measured on the probe stack: the batch answered `total_events: 1` and NO
 * other stack row gained an audit. This constant is the whole targeting
 * mechanism, which is why it is exported and why a leg that changes it breaks
 * the isolation the fixture bought.
 */
export const AUDIT_TARGET_RISK_SCORE = 99;

/** What the fixture row's summary carries, so a purge or a count can name it. */
export const AUDIT_SUMMARY_TOKEN = 'fe3f061audit';

/**
 * The highest risk score any OTHER FE-3 fixture row carries, DERIVED from the
 * sibling fixtures' own exports rather than hard-coded, so a leg's targeting
 * bound cannot go stale when a sibling edits its rows. The search fixture's
 * scores are inline (`:1106`, `i % 2 === 0 ? 72 : 45`) and its max of 72 is below
 * every maximum below, which is why it needs no export to be covered here.
 */
const SIBLING_MAX_RISK_SCORE = Math.max(
  ...FIXTURE_ROWS.map((r) => r.riskScore),
  ...STATS_FIXTURE_ROWS.map((r) => r.riskScore),
  ...DETAIL_ROWS.map((r) => r.riskScore),
  FEEDBACK_RISK_SCORE
);

/**
 * A 404 from `/api/ai-audit/**` that the UI is documented to render verbatim.
 * Kept in the harness because BOTH spec files assert it and they must not drift
 * apart: F-061 shows the server's own string (`auditApi.ts:249` lifts FastAPI's
 * `detail` into `AuditApiError.message`, `EventDetailModal.tsx:327` renders it),
 * F-062 shows the component's OWN sentence for the same status
 * (`EventAuditDetail.tsx:186-187`), and a leg that conflated the two would pass
 * on either UI while asserting neither.
 */
export const AUDIT_NOT_FOUND_DETAIL = (eventId: number): string =>
  `No audit found for event ${eventId}`;

export interface AuditFixture {
  cameraId: string;
  /** The row at AUDIT_TARGET_RISK_SCORE — seeded with an event_audits row by running POST /api/ai-audit/batch. */
  auditedEventId: number;
  /** An unaudited row clicked by the not-found / empty-state legs. */
  targetEventId: number;
  /** A third row, never audited and never clicked: the negative control. */
  controlEventId: number;
}

/**
 * A raw GET that TOLERATES a 404, because `api`'s contract is "non-200 throws"
 * and this fixture's premise is a 404. The distinction is the point: `api` is
 * what a leg uses to demand success; this is what a fixture uses to record an
 * absence. Status AND body come back so the caller can check the shape too —
 * the same event id answers "No audit found for event N" here but
 * "Event with id N not found" for an id no row has, and the legs depend on
 * that pair being different.
 */
export async function readAuditLookup(
  h: HarnessShell,
  session: Session,
  eventId: number
): Promise<{ status: number; detail?: string; body?: Record<string, unknown> }> {
  const res = await fetch(`${h.api}/api/ai-audit/events/${eventId}`, {
    headers: { Cookie: `${session.name}=${session.value}` },
  });
  const body = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  return {
    status: res.status,
    detail: body?.detail as string | undefined,
    body: body ?? undefined,
  };
}

/**
 * One camera, one row at AUDIT_TARGET_RISK_SCORE and one control row, and a
 * PROVEN ABSENCE of `event_audits` rows for both.
 *
 * The premise check is not decoration. F-061's clause is a DISJUNCTION — "sees
 * 'Re-evaluation triggered successfully', OR 'No audit found for event N' for an
 * event no batch audit has covered" — and the half this fixture sets up is the
 * one that depends on stored state. The tier holds ZERO audit rows in the normal
 * case (measured: `GET /api/ai-audit/stats` answers `total_events: 0`), but a
 * sibling spec can drive `POST /api/ai-audit/batch` (`tests/golden/data-ui/
 * jobs-page.spec.ts:127` does exactly that, with `{limit: 1}`), and the golden
 * project is ONE serial worker over per-file fixtures — so "my row has no audit"
 * is a fact to re-assert per run, never to assume from a past measurement.
 *
 * The purge is HARD and precedes seeding: `event_audits.event_id` is
 * `ForeignKey(..., ondelete="CASCADE")` (backend/models/event_audit.py:27-28),
 * so removing the row removes its audit — and there is no audit-delete endpoint,
 * so the cascade is the only door.
 */
export async function createAuditFixture(h: HarnessShell, session: Session): Promise<AuditFixture> {
  const cameraId = await ensureCamera(h, session, AUDIT_CAMERA_NAME, '/cameras/fe3_audit_probe');
  // The camera <select> and the modal's camera chip are built from the 60 s
  // cached list; see waitForCameraInList.
  await waitForCameraInList(h, session, AUDIT_CAMERA_NAME);

  const stale = await apiShell<{ items?: { id: number }[] }>(
    h,
    session,
    `/api/events?limit=100&camera_id=${encodeURIComponent(cameraId)}`
  ).catch(() => null);
  await hardDeleteFixtureRows(
    h,
    session,
    (stale?.items ?? []).map((row) => row.id)
  );

  const salt = Date.now();
  // 99 first: AUDIT_TARGET_RISK_SCORE must be the STRICT max of the fixture set,
  // and asserting that is cheaper than trusting the ordering below.
  const rows = [
    { risk_score: AUDIT_TARGET_RISK_SCORE, risk_level: 'critical' },
    { risk_score: 44, risk_level: 'medium' },
    { risk_score: 43, risk_level: 'medium' },
  ];
  const bulk = await apiWrite<BulkBody>(h, session, 'POST', '/api/events/bulk', {
    events: rows.map((row, i) => ({
      batch_id: `fe3au-${salt}-${i}`, // events.batch_id is UNIQUE (measured)
      camera_id: cameraId,
      started_at: new Date(Date.now() - 3_600_000 * (i + 1)).toISOString(),
      risk_score: row.risk_score,
      risk_level: row.risk_level,
      summary: `${AUDIT_SUMMARY_TOKEN} ${i}`,
    })),
  });
  const eventIds = bulk.results.map((r) => r.id).filter((id): id is number => id !== null);
  if (eventIds.length !== rows.length) {
    throw new Error(
      `audit fixture: got ${eventIds.length} ids for ${rows.length} rows; succeeded ` +
        `${bulk.succeeded}/${rows.length}; first error: ` +
        String(bulk.results.find((r) => r.status !== 'success')?.error).slice(0, 200)
    );
  }
  const [auditedEventId, targetEventId, controlEventId] = eventIds;

  const requireFixture = (premise: boolean, why: string): void => {
    if (!premise) throw new Error(`audit fixture: ${why}`);
  };
  // The bound is checked HERE, at fixture time, rather than in a standalone
  // `test()` asserting a constant: a pure-logic test would (a) still appear in
  // CI's `golden paths:` dict as a "leg" that is not a feature path, and (b) keep
  // passing if a sibling fixture later raised its own rows — this throw fires the
  // moment the isolation stops being true, in the file that depends on it.
  requireFixture(
    AUDIT_TARGET_RISK_SCORE > SIBLING_MAX_RISK_SCORE,
    `the target score ${AUDIT_TARGET_RISK_SCORE} must stay STRICTLY above every ` +
      `other FE-3 fixture score (derived maximum ${SIBLING_MAX_RISK_SCORE}) or ` +
      '`min_risk_score` targeting could select a foreign row'
  );
  // The score is the batch-targeting lever (see AUDIT_TARGET_RISK_SCORE), so a
  // server that clamped or defaulted it silently disarms the isolation.
  const storedAudited = await apiShell<{ risk_score: number | null }>(
    h,
    session,
    `/api/events/${auditedEventId}`
  );
  requireFixture(
    storedAudited.risk_score === AUDIT_TARGET_RISK_SCORE,
    `the audited row must store risk_score ${AUDIT_TARGET_RISK_SCORE} for ` +
      `min_risk_score targeting to be exclusive (got ${String(storedAudited.risk_score)})`
  );
  for (const id of eventIds) {
    const probe = await readAuditLookup(h, session, id);
    requireFixture(
      probe.status === 404 && probe.detail === AUDIT_NOT_FOUND_DETAIL(id),
      `row ${id} must start with NO audit row, answered 404 with the ` +
        `"no audit" detail (got ${probe.status} ` +
        `${JSON.stringify(probe.detail)?.slice(0, 120)})`
    );
  }

  // Seed an audit on auditedEventId by running the batch audit on the fake stack
  // (ruling 212 / [r212]), while leaving targetEventId and controlEventId unaudited.
  const batchJob = await apiWrite<{
    job_id: string;
    status: string;
    total_events: number;
  }>(h, session, 'POST', '/api/ai-audit/batch', {
    limit: 10,
    min_risk_score: AUDIT_TARGET_RISK_SCORE,
    force_reevaluate: false,
  });
  requireFixture(
    batchJob.total_events >= 1,
    `batch audit targeting min_risk_score=${AUDIT_TARGET_RISK_SCORE} must queue >= 1 event (got ${batchJob.total_events})`
  );
  let jobCompleted = false;
  for (let attempt = 0; attempt < 80; attempt++) {
    const jobStatus = await apiShell<{
      status: string;
      processed_events: number;
      failed_events: number;
    }>(h, session, `/api/ai-audit/batch/${encodeURIComponent(batchJob.job_id)}`);
    if (jobStatus.status === 'completed') {
      requireFixture(
        jobStatus.processed_events >= 1 && jobStatus.failed_events === 0,
        `batch audit job ${batchJob.job_id} completed with processed=${jobStatus.processed_events}, failed=${jobStatus.failed_events}`
      );
      jobCompleted = true;
      break;
    }
    if (jobStatus.status === 'failed') {
      throw new Error(`audit fixture: batch audit job ${batchJob.job_id} failed`);
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  requireFixture(jobCompleted, `batch audit job ${batchJob.job_id} did not complete within 20s`);

  const auditedAfter = await readAuditLookup(h, session, auditedEventId);
  requireFixture(
    auditedAfter.status === 200,
    `row ${auditedEventId} must have an audit row after batch audit (got ${auditedAfter.status} ${JSON.stringify(auditedAfter.detail)?.slice(0, 120)})`
  );
  for (const id of [targetEventId, controlEventId]) {
    const probe = await readAuditLookup(h, session, id);
    requireFixture(
      probe.status === 404 && probe.detail === AUDIT_NOT_FOUND_DETAIL(id),
      `row ${id} must remain unaudited after batch audit (got ${probe.status} ${JSON.stringify(probe.detail)?.slice(0, 120)})`
    );
  }
  return { cameraId, auditedEventId, targetEventId, controlEventId };
}

// ══ identity ══ ══════════════════════════════════════
/**
 * Shared harness plumbing for the F2.3 DO-3 golden paths (claim #6996).
 * DO-3 covers the identity surfaces: zones (F-256, F-258), household
 * (F-270, F-271) and face recognition (F-275, F-277, F-278).
 *
 * Why this file is a COPY and not an import of ../notify-access/harness.ts:
 * ruling 87's file rule keeps a batch PR inside its own
 * `frontend/tests/golden/<area>/` directory plus its inventory rows, so DO-3
 * cannot import DO-2's module even though the plumbing is nearly identical.
 * That is deliberate separation — the two batches evolve their sessions
 * independently — but it means the shape below is reproduced, and every
 * comment that carried a reason in DO-2's file is reproduced here too, because
 * a copy without the reason is how the next reader reintroduces the bug.
 *
 * What DO-3 IS relative to DO-2: these are CRUD surfaces. The no-env fake-AI
 * stack seeds ONLY cameras — scripts/feature_check.py calls seed_cameras()
 * (call :1836; the def is :1284) and nothing else; grepping `household`, `known-persons`,
 * `camera_zones` and `registered_vehicles` over feature_check.py and
 * feature-check.sh returns 0 for each (positive control: `cameras` = 16 hits
 * in the same file, 0 in the .sh). The rich seeders in scripts/seed-events.py
 * (seed_household_members, seed_registered_vehicles, seed_camera_zones) are
 * NOT on the harness path. So the passive mount of every DO-3 page is its
 * EMPTY state, and any spec that wants a row must create it and delete it in
 * its own finally — the invariant DO-2's harness documents at :45-54.
 *
 * Component ground truth (verified at a195b0984 — and it is NOT what DO-2
 * trained me to expect, NOR as clean as my first draft of this comment claimed).
 * What is true: the 3 page files (ZonesPage, HouseholdPage, FaceRecognitionPage)
 * and src/components/{household,face-recognition,common}/ hold 0 non-test
 * @tremor importers. What is FALSE, and I nearly shipped it: "ZonesPage does
 * not use Tremor." src/components/zones/ has 6 non-test Tremor files and two
 * chains reach the page — ZonesPage.tsx:47 imports CrossingTrendsChart (Tremor
 * Card/Title/AreaChart/Text at its :14) and ZonesPage.tsx:46 imports
 * ComparisonTab, which imports ZoneComparisonChart at its :21. A directory-wide
 * grep also hides the reverse error: 4 of those 6 (ZoneEditorSidebar,
 * ZoneActivityHeatmap, ZoneStatusCard, ZoneOwnershipPanel) are reachable only
 * through ZoneEditor.tsx:26 + the barrel index.ts:24-30, i.e. NOT from
 * ZonesPage at all.
 *
 * So the honest rule for DO-3 is per-ELEMENT, not per-page: every locator below
 * was checked against the markup of the element it targets, because these
 * surfaces mix frameworks. The overview grid and FilterBar are native
 * (data-testid="zone-type-select" is a real <select> at ZonesPage.tsx:219-227,
 * <option>s inside), ZoneTrustMatrix is native (8 <button>s, no Tremor), and
 * the identity cards are native. The analytics/comparison tabs are not, and no
 * DO-3 spec asserts into them. Consequences for locators:
 *   - selects are NATIVE, and Playwright maps a single <select> to role
 *     `combobox` (playwright-core: multiple/size>1 → listbox, else combobox).
 *     getByRole('listbox') finds nothing here, and native <option>s are
 *     invisible to Playwright — use selectOption()/toHaveValue(), never
 *     click-then-click. DO-2's Tremor-Select limitation does NOT apply.
 *   - the only toggles are native checkboxes (toBeChecked) and
 *     aria-pressed buttons (toHaveAttribute('aria-pressed', …)). There is no
 *     Tremor Switch, so DO-2's F-020 aria-checked trap does NOT apply either.
 *   - headings are REAL <h2>/<h3> (KnownPersonsTab.tsx:213 renders <h2>Known
 *     Persons</h2>; the card titles are <h3>), so the sectionTitle() workaround
 *     DO-2 needs (Tremor <Title> renders <p>, no heading role) is deliberately
 *     absent here: importing it would assert a page shape these pages do not
 *     have.
 *   - the inventory's prose is NOT a locator source. The F-275 row says "cards
 *     with an Add Person button", but that button has no name attribute
 *     (KnownPersonsTab.tsx:218-224 is a bare <button> whose accessible name
 *     comes from its text + an aria-hidden <Plus> icon), so getByRole('button',
 *     {name:'Add Person'}) works only because of the text. Assert the text.
 *
 * Wiring facts this layout depends on (all read at this head):
 * - feature_check.py golden() (scripts/feature_check.py:1369) runs `playwright
 *   --project=golden`; the golden project is testDir ./tests/golden with
 *   workers: 1, fullyParallel: false (frontend/playwright.config.ts:282-288).
 * - `retries: process.env.CI ? 2 : 0` (playwright.config.ts:79) is NOT
 *   overridden by the golden project, so CI gives each test two attempts and a
 *   local run gives it none. junit merges a retry-absorbed failure into
 *   `passed`, and golden() reads only junit (its two junit_results calls:
 *   :1402 for the backend specs, :1459 for Playwright; junit_results itself is
 *   :834) — so a green Feature-check row can mean "passed on retry". Promotion
 *   evidence for a DO-3 row is the run's
 *   golden-playwright.log (it prints `flaky` and `(retry #1)`), not the verdict.
 * - The page/context guard comes from ../guard, never the tests/e2e fixtures
 *   (which auto-mock). addCookies (login) and the API legs below are real
 *   traffic, not interception, so the guard does not fire on them.
 */

/** The card container for a HOUSEHOLD member or vehicle, by its title.
 *
 *  The household cards are the one surface here with no testid and no role at
 *  all: a member card is a bare <div className="rounded-lg …"> at
 *  HouseholdPage.tsx:976-979 wrapping <h3>{member.name}</h3> at :982, and the
 *  vehicle card is the same shape at :1057-1059 / <h3>{vehicle.description}</h3>
 *  at :1063. So the only reachable anchor is the <h3>, and the card is whatever
 *  wraps it — hence the XPath. It is deliberately NOT used for zones or known
 *  persons, which both have better handles:
 *   - zone card: data-testid={`zone-card-${zone.id}`} at ZonesPage.tsx:307
 *     (<h3>{zone.name}</h3> at :316). Unusable as a NAME because the backend
 *     mints the id itself — `id=str(uuid.uuid4())` at
 *     backend/api/routes/zones.py:89 — so a spec can only take the testid from
 *     the POST response it just made.
 *   - known-person card: static data-testid="known-person-card" plus
 *     role="button" and aria-label={`View details for ${person.name}`}
 *     (KnownPersonsTab.tsx:60-67). Use getByRole('button', {name:
 *     `View details for …`}) — accessible, and it also pins the a11y surface.
 *
 *  Naming it after the two rows that need it keeps a later DO-3 spec from
 *  reaching for XPath where a real testid exists.
 *
 *  `exact: true` is load-bearing, not tidiness. getByRole's accessible-name
 *  match is a CASE-INSENSITIVE SUBSTRING by default, and this page renders
 *  member and vehicle <h3>s in the same role+level, so any pair of titles in a
 *  substring relation makes one call resolve to two cards — Playwright then
 *  fails the assert as a strict-mode violation while BOTH cards are on screen
 *  and correct. That is not hypothetical: F-271's owner fixture is a MEMBER
 *  named `${VEHICLE} Owner` (household.spec.ts:376), so the vehicle's own title
 *  is a prefix of the member's and the F-271 card lookup matched both — red at
 *  cc445f775 on the original plus both retries. The collision is a fixture
 *  choice, but the LANDMINE is the loose match: a real user may name a member
 *  "Bob" and register a vehicle "Bob's Truck", and renaming fixtures would fix
 *  one spec while leaving the next one to trip on it. Hence the fix sits here,
 *  for every caller. Mechanism measured, not assumed — playwright-core 1.63.0,
 *  two cards on one page exactly as HouseholdPage.tsx renders them:
 *    name='Golden DO-3 Sedan'                -> count=2   (the failure)
 *    name='Golden DO-3 Sedan', exact: true   -> count=1   (the fix)
 *    vehicle card alone, no exact            -> count=1   (proves the second
 *                                                         match was the member)
 *    member card alone, exact: true          -> count=1   (exact still finds a
 *                                                         legitimate match, so
 *                                                         F-270 stays green)
 *    newline-padded <h3>, exact: true        -> count=1   (accessible-name
 *                                                         whitespace is fine) */
export function householdCard(page: Page, title: string): Locator {
  return page
    .getByRole('heading', { name: title, level: 3, exact: true })
    .locator('xpath=ancestor::div[contains(@class,"rounded-lg")][1]');
}

// ══ notify-access ══ ═════════════════════════════════
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

/**
 * Boot a /settings page and settle it: quiet (drain the shared bucket),
 * navigate, then WAIT FOR THE CONFIG-GATED PANEL, detecting a shed coat
 * instead of waiting out the timeout — the dashboard harness's driveUntilBooted
 * (:221-239) pattern, kept in this batch's own file because ruling 87 keeps
 * batches' harnesses independent (the same reasoning as this file's header: a
 * shared module across batches would make two lanes' PRs depend on each other's
 * merge). `Global Preferences` is the boot sentinel because it lives INSIDE the
 * `!isAnyLoading && config` gate (:522) — its paint proves the config fetch
 * survived, which is exactly the fact every F-235 assert rests on. A shed drive
 * is re-driven after one burst refill; a stack that never settles IS reported,
 * naming the last coat — saturation deserves a red, just not a misleading one.
 */
export async function settledSettings(page: Page, h: Harness, path: string): Promise<void> {
  let lastCoat = 'no-shed-coat(page painted something else)';
  for (let drive = 1; drive <= 3; drive++) {
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.goto(`${h.ui}${path}`, { waitUntil: 'domcontentloaded' });
    const painted = await Promise.race([
      sectionTitle(page, 'Global Preferences')
        .waitFor({ state: 'visible', timeout: 10_000 })
        .then(() => 'booted' as const),
      (async () => {
        // Poll for a coat while the boot settles; whichever appears first wins.
        // Swallow ANY throw — a detached page after the race resolved is the
        // normal case, mirroring settleBoot's floating promise.
        try {
          for (let t = 0; t < 20; t++) {
            const coat = await shedCoatNotify(page);
            if (coat) return coat;
            await page.waitForTimeout(500);
          }
        } catch {
          /* page gone / detached — the race already resolved or the drive ends */
        }
        return null;
      })(),
    ]);
    if (painted === 'booted') return;
    lastCoat = painted ?? lastCoat;
    await page.waitForTimeout(4_000); // one burst refill (10 r/s → 20 tokens in 2 s)
  }
  throw new Error(
    `settledSettings(${path}): 3 drives, none painted the config-gated panel (last shed coat: ${lastCoat}) — ` +
      'the shared nginx api bucket (rate=10r/s nginx.conf:24, burst=20 nodelay docker-entrypoint.sh:139) shed every ' +
      'attempt; this is stack saturation, not a channel-configuration failure'
  );
}

// ══ settings-cameras ══ ══════════════════════════════
/**
 * Shared harness plumbing for Uplevel F2.3 batch FE-4 (`frontend/tests/golden/settings-cameras/`).
 *
 * Covers the 23 FE-4 inventory rows across `/settings`, `/settings/cameras`,
 * `/settings/rules`, and `/settings/processing`:
 *   - Group 1 (`settings-shell.spec.ts`, `cameras-crud.spec.ts`):
 *     F-198, F-199, F-200, F-201, F-203
 *   - Group 2 (`cameras-protocols.spec.ts`, `cameras-baseline.spec.ts`):
 *     F-204, F-205, F-206, F-207, F-209
 *   - Group 3 (`cameras-zones.spec.ts`):
 *     F-211, F-213
 *   - Group 4 (`alert-rules.spec.ts`):
 *     F-215, F-218, F-219
 *   - Group 5 (`processing-settings.spec.ts`, `processing-storage-dlq.spec.ts`):
 *     F-221, F-222, F-223, F-224, F-225, F-226, F-228, F-229
 *
 * Key architectural invariants (verified against the tree):
 * 1. Unmocked by construction (UR-127, F2.1): every spec imports `{ expect, test }`
 *    from `../guard` and ends with `assertGuardSurvives(page, h)`.
 * 2. Collection-time safety: `readHarness()` never throws when `FEATURE_CHECK_*`
 *    env vars are absent, so `npx playwright test --project=golden --list`
 *    succeeds outside the feature-check harness.
 * 3. Nginx burst discipline (`BOOT_QUIET_MS = 500`, `settledGoto`):
 *    `frontend/nginx.conf:24` limits `/api` to `rate=10r/s` with `burst=20`.
 *    `ProcessingSettings` and `CamerasSettings` fire 3–6 concurrent GETs on
 *    mount; `settledGoto` pauses before navigation and retries if the shared
 *    nginx token bucket sheds a boot request with 429.
 * 4. Camera list cache bug (`backend/services/cache_service.py:577` vs `:762`):
 *    `list_cameras` (`backend/api/routes/cameras.py:194, 259`) caches under
 *    `CacheKeys.cameras_list_by_status(None)` (`"hsi:cache:cameras:list:all"`),
 *    stored by `CacheService.set` (`:196`) as `"cache:hsi:cache:cameras:list:all"`
 *    with `SHORT_TTL = 60`s, whereas `CacheService.invalidate_cameras` (`:577`)
 *    scans `"cache:cameras:*"` (`0` keys deleted). Consequently, after
 *    `operations/test-data.spec.ts` resets the database, `GET /api/cameras` can
 *    serve stale pre-reset camera IDs (`front-door`) for up to 60s. `listCameras()`
 *    verifies each returned ID against uncached `GET /api/cameras/{id}` and waits
 *    out any stale post-reset cache window before returning.
 * 5. Shared `/tmp/runtime.env` restoration (`docker-compose.ci.yml:157`):
 *    `PATCH /api/system/config`, `PATCH /api/v1/settings`, and
 *    `PUT /api/system/severity` all read-merge-write `HSI_RUNTIME_ENV_PATH`
 *    and clear `get_settings.cache_clear()`. Every mutating test snapshots the
 *    backend state before mutating and restores it inside a `finally` block.
 */

/**
 * Sign in on both the backend API and the Playwright browser context.
 */
export async function signIn(page: Page, h: Harness): Promise<AuthedFetch> {
  const session = await adminSessionId(h);
  await login(page, h, session);
  return authedFetchCameras(h, session);
}

/**
 * Navigate to `path` on the UI origin after `BOOT_QUIET_MS`, waiting for
 * `sentinel(page)` to become visible and retrying up to 3 times if the shared
 * nginx rate-limit bucket sheds a boot request.
 */
export async function settledGoto(
  page: Page,
  h: Harness,
  path: string,
  sentinel: (p: Page) => Locator
): Promise<void> {
  let lastCoat = 'no-shed-coat(sentinel did not become visible in time)';
  for (let drive = 1; drive <= 3; drive++) {
    await page.waitForTimeout(BOOT_QUIET_MS_CAMERAS);
    await page.goto(`${h.ui}${path}`, { waitUntil: 'domcontentloaded' });
    const painted = await Promise.race([
      sentinel(page)
        .waitFor({ state: 'visible', timeout: 12_000 })
        .then(() => 'booted' as const),
      (async () => {
        try {
          for (let t = 0; t < 24; t++) {
            const coat = await shedCoatCameras(page);
            if (coat) return coat;
            await page.waitForTimeout(500);
          }
        } catch {
          /* page navigated or closed */
        }
        return null;
      })(),
    ]);
    if (painted === 'booted') return;
    lastCoat = painted ?? lastCoat;
    await page.waitForTimeout(4_000);
  }
  throw new Error(
    `settledGoto(${path}): 3 drives failed to paint sentinel (last shed coat: ${lastCoat})`
  );
}

/**
 * Format seconds as human-readable string matching `frontend/src/utils/time.ts:191-225`
 * (`formatSecondsAsHumanReadable`), used by `CamerasSettings.tsx:443-448` for F-203.
 */
export function formatSecondsAsHumanReadable(seconds: number): string {
  if (seconds < 60) {
    return seconds === 1 ? '1 second' : `${seconds} seconds`;
  }

  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  const remainingMinutes = minutes % 60;
  const remainingHours = hours % 24;

  if (days > 0) {
    if (remainingHours > 0) {
      const dayStr = days === 1 ? '1 day' : `${days} days`;
      const hourStr = remainingHours === 1 ? '1 hour' : `${remainingHours} hours`;
      return `${dayStr} ${hourStr}`;
    }
    return days === 1 ? '1 day' : `${days} days`;
  }

  if (hours > 0) {
    if (remainingMinutes > 0) {
      const hourStr = hours === 1 ? '1 hour' : `${hours} hours`;
      const minStr = remainingMinutes === 1 ? '1 minute' : `${remainingMinutes} minutes`;
      return `${hourStr} ${minStr}`;
    }
    return hours === 1 ? '1 hour' : `${hours} hours`;
  }

  return minutes === 1 ? '1 minute' : `${minutes} minutes`;
}

export interface CameraRecord {
  id: string;
  name: string;
  folder_path: string;
  status: string;
  ingestion_mode?: string;
  rtsp_url?: string | null;
  rtsp_username?: string | null;
  motion_sensitivity?: number | null;
}

/**
 * Fetch the current camera list from `GET /api/cameras` (`backend/api/routes/cameras.py:152`)
 * and filter to cameras that exist in PostgreSQL (`GET /api/cameras/{id}` === 200).
 * After `operations/test-data.spec.ts` runs `Seed Cameras` (`front-door`, etc.) and then
 * `Full Database Reset` (which wipes `front-door` and recreates the 5 harness cameras),
 * `"cache:hsi:cache:cameras:list:all"` can still contain the wiped `front-door` ID for up to
 * `SHORT_TTL = 60`s while all 5 harness cameras exist in both the cache and PostgreSQL.
 * Filtering to live PostgreSQL cameras avoids a 30-60s sleep while ensuring every returned
 * camera is both rendered by the UI and reachable at `/api/cameras/{id}/*`.
 */
export async function listCameras(api: AuthedFetch): Promise<CameraRecord[]> {
  const res = await api.getJson('/api/cameras');
  expect(res.status, 'GET /api/cameras answers 200').toBe(200);
  const items = Array.isArray(res.body?.items) ? (res.body.items as CameraRecord[]) : [];
  const liveItems: CameraRecord[] = [];
  for (const cam of items) {
    const detail = await api.getJson(`/api/cameras/${cam.id}`);
    if (detail.status === 200) {
      liveItems.push(cam);
    }
  }
  return liveItems;
}

/**
 * Delete a camera by ID if it exists (`204` or `404`), then verify uncached
 * `GET /api/cameras/{id}` returns `404`. Safe to call in `finally` blocks.
 */
export async function deleteCameraIfPresent(api: AuthedFetch, cameraId: string): Promise<void> {
  const res = await api.send(`/api/cameras/${cameraId}`, 'DELETE');
  expect([204, 404], `DELETE /api/cameras/${cameraId} answers 204 or 404`).toContain(res.status);
  const check = await api.getJson(`/api/cameras/${cameraId}`);
  expect(check.status, `GET /api/cameras/${cameraId} after delete answers 404`).toBe(404);
}

/**
 * Return sorted IDs of all alert rules from `GET /api/alerts/rules` (`backend/api/routes/alerts.py:97`).
 */
export async function alertRuleIds(api: AuthedFetch): Promise<string[]> {
  const res = await api.getJson('/api/alerts/rules');
  expect(res.status, 'GET /api/alerts/rules answers 200').toBe(200);
  const items = Array.isArray(res.body?.items) ? res.body.items : [];
  return items.map((r: Record<string, unknown>) => String(r.id)).sort();
}

/**
 * Delete an alert rule by ID if it still exists (`204` or `404`).
 */
export async function deleteAlertRuleIfPresent(api: AuthedFetch, ruleId: string): Promise<void> {
  const res = await api.send(`/api/alerts/rules/${ruleId}`, 'DELETE');
  expect([204, 404], `DELETE /api/alerts/rules/${ruleId} answers 204 or 404`).toContain(res.status);
}

// ══ analytics-alerts ══ ══════════════════════════════
/**
 * Shared harness plumbing for the F2.3 DO-1 golden paths (docs batches,
 * docs/uplevel/packages/frontend.md §F2.3; claim #6996). DO-1 covers the Analytics and Alerts
 * surfaces: inventory rows F-070 to F-075, F-077 and F-080.
 *
 * The contract this module encodes is feature-check's own (scripts/
 * feature_check.py, read at this head): golden() exports the FEATURE_CHECK_*
 * env set, golden runs serial on one worker AFTER smoke() already dropped
 * harness-smoke.jpg, and the file watcher dedupes an image by sha256 stack-wide
 * for 300 s (backend/services/dedupe.py). Consequences baked in below:
 *
 * - Fixture choice is a shared resource AND a semantic choice. The book
 *   (backend/ai_contract/fake/scenario_fixtures/scenarios.json) ships five
 *   images, each encoding a different outcome:
 *     person-at-door  — claimed by F2.1's dashboard-drop.spec.ts; a second drop
 *                       of the same bytes inside 300 s dedupes and reddens it.
 *     harness-smoke   — consumed by the harness's own smoke() ~40 s before
 *                       golden starts (measured in the 2026-10-11 CI run:
 *                       dropped 07:42:18Z, golden launched 07:42:55Z), so its
 *                       event is a fact of the stack, not something this spec
 *                       may re-drop.
 *     slow-reply      — NOT a slow success. Its reply_delay_seconds (40) is
 *                       larger than the backend's ai_vlm_read_timeout default
 *                       (25 s, backend/core/config.py:1180), so the analyzer
 *                       abandons the reply and fails closed: the book's own
 *                       module doc calls it "the slow-reply failure mode", and
 *                       the run's backend log says `vlm assess failed - event
 *                       records verification_failed`. The event then carries a
 *                       NULL score (risk_score 0 over the API) and no risk tier
 *                       — a negative fixture, not a positive one.
 *     cat-on-porch    — verdict rejected, risk 4 → `low`.
 *     car-in-driveway — nobody claims it, no reply delay, verdict `uncertain`,
 *                       risk 45 → `medium` (backend/services/severity.py tiering
 *                       against the settings defaults 29/59/84).
 *   DO-1 claims car-in-driveway. Its tier is the point: /alerts pages only
 *   `high` and `critical` (useAlertsQuery), so this drop is the NEGATIVE case
 *   that proves the band filter end to end, and its detection is the positive
 *   aggregate /analytics reads. The one alert the page must show is the
 *   harness smoke event (61 → `high`), which is real stack state golden may
 *   rely on but may not create.
 * - analytics.spec.ts drops nothing; Playwright's serial file order runs it
 *   after alerts.spec.ts. If that ever flips, its API leg fails with a named
 *   cause instead of silently passing on an empty list.
 */

export interface Scenario {
  name: string;
  image: string;
  detections: { class: string; confidence: number }[];
  verdict: { verdict: string; risk_score: number; summary: string };
  reply_delay_seconds?: number;
}

/** The scenario DO-1 claims, and the harness's own. The book decides what each proves. */
export const DO1_SCENARIO = 'car-in-driveway';

export const SMOKE_SCENARIO = 'harness-smoke';

/** Book scenarios are read as authored; the verdict word is never a gate here
 *  because it is the TIER (low/medium/high/critical) that decides which
 *  surfaces a drop may appear on, and every tier is a legitimate thing to pin. */
function usableScenario(entry: Scenario | undefined, name: string): Scenario | string {
  if (!entry) return `scenario book has no ${name}`;
  const verdict = entry.verdict?.verdict;
  if (typeof verdict !== 'string' || !verdict) return `${name} has no verdict in the book`;
  if (!entry.detections?.length) return `${name} has no detections in the book`;
  if (entry.reply_delay_seconds) {
    // Any book delay outlasts the analyzer's 25 s read budget by construction
    // (the mode exists to exercise that timeout), so it can never yield the
    // confirmed verdict a golden aggregate needs.
    return `${name} delays its reply ${entry.reply_delay_seconds}s — past the analyzer's read budget (the book's slow-reply failure mode)`;
  }
  return entry;
}

/** scripts/feature-check.sh lives at the repo root: THREE up from this file's
 *  directory, `frontend/tests/golden/` — the same depth `dashboard-drop.spec.ts`
 *  computes from the directory it shares with this file. The constant is derived
 *  from `import.meta.url`, so the depth is a property of WHERE the file sits, not
 *  of its text: it read `'../../../..'` while it lived one level deeper, in the
 *  area dir `frontend/tests/golden/analytics-alerts/`, and [r148a]'s fold moved it
 *  up, so the old depth resolved ABOVE the repo root and every `feature-check.sh
 *  drop` spawn died `ENOENT`. Carrying that literal verbatim was the wrong reading
 *  of "keep the comments" — a location-relative constant is not carried prose. */
export const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');

/** Drop this batch's fixture through O2.2's own helper (documented contract,
 *  not a bare copy — same call dashboard-drop.spec.ts uses). */
export function dropDo1Fixture(h: HarnessAlerts): void {
  execFileSync(
    path.join(repoRoot, 'scripts/feature-check.sh'),
    ['drop', h.scenarioImagePath, h.scenario.name],
    {
      cwd: repoRoot,
      env: { ...process.env, FEATURE_CHECK_CAMERA_ROOT: h.cameraRoot },
      encoding: 'utf8',
      timeout: 30_000,
    }
  );
}

/** Poll this camera's events until the fixture's verdict lands. Mirrors the
 *  harness's own smoke() predicate (5 s ticks; stop when verification.verdict
 *  appears). Deadline is dashboard-drop's proven 150 s with slack; this
 *  scenario carries no reply delay (readHarness refuses a delayed one). */
export async function awaitVerdictedEvents(
  h: HarnessAlerts,
  api: AuthedFetchAlerts,
  deadlineMs: number
): Promise<Record<string, any>[]> {
  const deadline = Date.now() + deadlineMs;
  let items: Record<string, any>[] = [];
  while (Date.now() < deadline) {
    const { status, body } = await api.getJson(
      `/api/events?camera_id=${encodeURIComponent(h.cameraId)}`
    );
    items = status === 200 && Array.isArray(body?.items) ? body.items : [];
    if (items.length && (items[0].verification ?? {}).verdict) return items;
    await new Promise((resolve) => setTimeout(resolve, 5_000));
  }
  return items;
}

/**
 * The backend fact every DO-1 UI assertion is a view of: exactly this camera's
 * one event, the book's verdict and score, and the tier that score produces —
 * car-in-driveway's 45 lands in `medium` (severity.py against the settings
 * defaults 29/59/84, read at implementation, not docstring), which is what
 * keeps it OFF /alerts. Callers assert non-emptiness first: an empty list is
 * the failure, never a vacuous pass.
 */
export function assertDropEventStored(items: Record<string, any>[], h: HarnessAlerts): string {
  expect(items.length, `expected exactly one event for camera ${h.scenario.name}`).toBe(1);
  const event = items[0];
  expect(String((event.verification ?? {}).verdict), 'the fake VLM answered the drop').toBe(
    h.scenario.verdict.verdict
  );
  expect(Number(event.risk_score), 'the score is the book value, not a placeholder').toBe(
    h.scenario.verdict.risk_score
  );
  expect(
    String(event.risk_level),
    `${h.scenario.verdict.risk_score} persists as ${expectedTier(h.scenario.verdict.risk_score)} — the tier that decides which pages may show it`
  ).toBe(expectedTier(h.scenario.verdict.risk_score));
  return String(event.id);
}

/** The tier the analyzer persists for a score: severity.risk_score_to_severity
 *  against settings defaults low_max 29 / medium_max 59 / high_max 84. DO-1's
 *  fixture is 45 → medium; the harness smoke event is 61 → high. Written out
 *  rather than imported because this is a browser-side spec — the numbers come
 *  from the sources named in this file's header, and a change to the defaults
 *  reddens the assert with this message. */
export function expectedTier(score: number): 'low' | 'medium' | 'high' | 'critical' {
  if (score <= 29) return 'low';
  if (score <= 59) return 'medium';
  if (score <= 84) return 'high';
  return 'critical';
}

/**
 * The event list from /api/events carries `detection_count` and
 * `detection_ids`, NOT a `detections` array (EventResponse,
 * backend/api/schemas/events.py — the live run's smoke-events.json shows the
 * shape). So the drop's stored detection is pinned through those two fields
 * here, and its class/confidence through the modal's own
 * GET /api/events/<id>/detections leg, which really does return them.
 */
export function assertDropStoredItsDetection(items: Record<string, any>[], h: HarnessAlerts): void {
  const event = items[0];
  expect(Number(event.detection_count ?? 0), 'the drop stored a detection row').toBe(
    h.scenario.detections.length
  );
  const ids = Array.isArray(event.detection_ids) ? event.detection_ids : [];
  expect(ids.length, 'the event names its detection ids').toBe(h.scenario.detections.length);
}

/** The alert the page must show: the harness smoke event, alone. Asserted
 *  non-empty before any equality, and the drop's own event id is asserted ABSENT
 *  — that absence is the band filter working (medium is not an alert). */
export function assertSoleAlertIsSmoke(
  high: Record<string, any>[],
  h: HarnessAlerts,
  dropEventId: string
): string {
  // This count is store-GLOBAL, and that is the spec's one real coupling to
  // stack order (named in this file's header and alerts.spec.ts's): exactly one
  // high/critical event exists because the harness smoke drop is the only
  // high-tier fixture the stack has seen by now — person-at-door is 82 → high
  // too, but dashboard-drop.spec.ts sorts AFTER this file. The message therefore
  // names both directions of the failure so a red points at its actual cause
  // instead of at the band filter.
  expect(
    high.length,
    high.length === 0
      ? 'no high/critical event at all: the harness smoke drop (61 → high) is missing — golden() is supposed to run after smoke()'
      : `${high.length} high/critical events, expected 1: another spec dropped a high-tier fixture before this one (file-order coupling named in alerts.spec.ts's header), so the "sole alert" pins cannot hold`
  ).toBe(1);
  const alert = high[0];
  expect(String(alert.id), 'the drop is not an alert').not.toBe(dropEventId);
  expect(String(alert.camera_id), 'the one alert is the harness smoke camera').toBe(
    h.smokeCameraId
  );
  expect(Number(alert.risk_score), 'the smoke event scores the book value').toBe(
    h.smokeScenario.verdict.risk_score
  );
  expect(String(alert.risk_level), 'and the smoke tier is what /alerts lists').toBe(
    expectedTier(h.smokeScenario.verdict.risk_score)
  );
  return String(alert.id);
}

// ══ webhooks ══ ══════════════════════════════════════
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
 *  against this snapshot (DO-2's rule, notify-access/quiet-hours.spec.ts:76-78 / :255-257): a
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

// ══ gpu-storage-admin ══ ═════════════════════════════
/**
 * Local helpers for the gpu-storage-admin golden batch (F2.3, ops cell A).
 *
 * Everything generic comes from ../operations/harness; the one addition here
 * is openAdminSection. Why a second opener is needed (read from the two
 * component files, not guessed): operations/harness.ts:208 openSection builds
 * its ids as `${sectionId}-section` / `${sectionId}-section-toggle`, which is
 * the scheme SystemMonitoringPage's sections use. AdminSettings passes
 * PLAIN ids to the same CollapsibleSection component —
 * `data-testid="admin-maintenance"` and the derived
 * `data-testid="admin-maintenance-toggle"` (CollapsibleSection.tsx:59,77: the
 * toggle is the root id plus `-toggle`).
 *
 * Opening is not cosmetic here: CollapsibleSection wraps its panel in
 * <Transition show={isExpanded}> (CollapsibleSection.tsx:98-114), so a closed
 * section's children are NOT in the DOM — LoggingSettings' controls and
 * OrphanCleanupPanel's sliders only exist after the toggle is clicked. The
 * helper therefore takes the testid of a child that is mounted ONLY inside
 * that section's panel and waits for it, which doubles as "the click worked"
 * (a heuristic DOM probe would be guessing at markup the suite doesn't own).
 */

/**
 * Expand an AdminSettings collapsible section by its plain data-testid and
 * wait for `mountedWhenOpenTestId` — a child that renders only while the
 * section's Disclosure.Panel is mounted. Idempotent: Feature Toggles /
 * System Config / Maintenance default to open (AdminSettings.tsx:191-193),
 * so the click is skipped when the child is already there.
 */
export async function openAdminSection(
  page: Page,
  sectionId: string,
  mountedWhenOpenTestId: string
): Promise<void> {
  const root = page.getByTestId(sectionId);
  await expect(root).toBeVisible();
  const child = root.getByTestId(mountedWhenOpenTestId);
  if ((await child.count()) === 0) {
    const toggle = page.getByTestId(`${sectionId}-toggle`);
    await expect(toggle).toBeVisible();
    await toggle.click();
  }
  await expect(child).toBeVisible({ timeout: 5_000 });
}
