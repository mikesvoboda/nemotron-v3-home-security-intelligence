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
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import type { Page } from '@playwright/test';

import { GUARD_MESSAGE, expect } from '../guard';

export interface Scenario {
  name: string;
  image: string;
  detections: { class: string; confidence: number }[];
  verdict: { verdict: string; risk_score: number; summary: string };
  reply_delay_seconds?: number;
}

export interface Harness {
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

/** Read the harness contract defensively: any piece missing → {ready: false,
 *  why}. Collection-time code must not throw, or `--list` breaks outside the
 *  harness (the shape dashboard-drop.spec.ts established). */
export function readHarness(): Harness | { ready: false; why: string } {
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

/** scripts/feature-check.sh lives at the repo root: four up from frontend/tests/golden/analytics-alerts. */
export const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');

/** Drop this batch's fixture through O2.2's own helper (documented contract,
 *  not a bare copy — same call dashboard-drop.spec.ts uses). */
export function dropDo1Fixture(h: Harness): void {
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

export interface Session {
  name: string;
  value: string;
}

/** A real login against the real backend — the cookie is genuine state, not a mock. */
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

/**
 * The session cookie rides into the browser on the UI origin: that origin's
 * nginx proxies /api and /ws to the backend, so the browser authenticates the
 * way a user who logged in through this very form would. The guard does not
 * cover addCookies — a cookie is state a real login legitimately produces.
 */
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

export interface AuthedFetch {
  getJson(urlPath: string, init?: RequestInit): Promise<{ status: number; body: any }>;
}

/** Backend reads with the harness admin's session — the API leg every DO-1
 *  spec runs BEFORE its UI leg, so a blank screen can never pass as "renders". */
export function authedFetch(h: Harness, session: Session): AuthedFetch {
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

/** Poll this camera's events until the fixture's verdict lands. Mirrors the
 *  harness's own smoke() predicate (5 s ticks; stop when verification.verdict
 *  appears). Deadline is dashboard-drop's proven 150 s with slack; this
 *  scenario carries no reply delay (readHarness refuses a delayed one). */
export async function awaitVerdictedEvents(
  h: Harness,
  api: AuthedFetch,
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
export function assertDropEventStored(items: Record<string, any>[], h: Harness): string {
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
export function assertDropStoredItsDetection(items: Record<string, any>[], h: Harness): void {
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
  h: Harness,
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

/** End-of-spec honesty, the guard surviving the whole drive (F2.1's pin,
 *  re-armed here so a DO-1 spec that reached for a mock fails LOUD). */
export async function assertGuardSurvives(page: Page, h: Harness): Promise<void> {
  expect(new URL(page.url()).host).toBe(new URL(h.ui).host);
  expect(() => page.route('**/api/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
}
