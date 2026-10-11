/**
 * Shared harness plumbing for the F2.3 DO-1 golden paths (docs batches,
 * 20-frontend.md §F2.3; claim #6996). DO-1 covers the Analytics and Alerts
 * surfaces: inventory rows F-070 to F-075, F-077 and F-080.
 *
 * The contract this module encodes is feature-check's own (scripts/
 * feature_check.py, read at this head): golden() exports the FEATURE_CHECK_*
 * env set, golden runs serial on one worker after smoke() already consumed
 * harness-smoke.jpg, and the file watcher dedupes an image by sha256 stack-wide
 * for 300 s (backend/services/dedupe.py). Consequences baked in below:
 *
 * - Fixture choice is a shared resource. person-at-door.jpg belongs to F2.1's
 *   dashboard-drop spec (a second drop < 300 s later dedupes and its spec
 *   reddens), harness-smoke.jpg is already in the DB when golden starts. DO-1
 *   drops slow-reply.jpg: nobody else claims it, its verdict is confirmed, and
 *   risk_score 70 lands in the `high` band (backend/services/severity.py,
 *   settings defaults 29/59/84), which is exactly what /alerts lists.
 * - slow-reply delays the verdict 40 s, so the poll deadline adds that delay to
 *   the 150 s budget dashboard-drop proved against the same pipeline.
 * - analytics.spec.ts drops nothing and asserts these surfaces carry the alert
 *   spec's event. That order is Playwright's, not hope: workers=1 plus default
 *   sort order 'file' (playwright.config.ts sets neither) runs analytics.spec.ts
 *   after alerts.spec.ts. If that ever flips, assertEventOnAlerts fails with a
 *   named cause instead of silently passing on an empty list.
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
}

/** The scenario DO-1 claims. The book, not this file, decides what it proves. */
export const DO1_SCENARIO = 'slow-reply';

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
    scenarios = (JSON.parse(readFileSync(bookPath, 'utf8')) as { scenarios: Scenario[] }).scenarios;
    cameras = JSON.parse(readFileSync(camerasPath, 'utf8')) as Record<string, string>;
  } catch (error) {
    return { ready: false, why: `harness JSON unreadable: ${String(error)}` };
  }
  const scenario = scenarios.find((entry) => entry.name === DO1_SCENARIO);
  if (!scenario) return { ready: false, why: `scenario book has no ${DO1_SCENARIO}` };
  if (scenario.verdict.verdict !== 'confirmed') {
    return { ready: false, why: `${DO1_SCENARIO} is no longer a confirmed scenario` };
  }
  const cameraId = cameras[scenario.name];
  if (!cameraId) return { ready: false, why: `harness seeded no camera named ${scenario.name}` };
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
 *  appears). Deadline = dashboard-drop's proven 150 s + slow-reply's 40 s
 *  reply delay, both read from the sources that own them. */
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
 * one event, confirmed, score from the book (70), persisted risk_level 'high'
 * (severity.py against settings defaults 29/59/84 — the tier is measured
 * through risk_score_to_severity's implementation, not the docstring), and the
 * book's detection (class + rounded confidence) now stored — the rows /analytics
 * aggregates read. Callers assert non-emptiness first: an empty list is the
 * failure, never a vacuous pass.
 */
export function assertEventOnAlerts(items: Record<string, any>[], h: Harness): string {
  expect(items.length, `expected exactly one event for camera ${h.scenario.name}`).toBe(1);
  const event = items[0];
  expect(String((event.verification ?? {}).verdict), 'the fake VLM confirmed the drop').toBe(
    h.scenario.verdict.verdict
  );
  expect(Number(event.risk_score), 'the score is the book value, not a placeholder').toBe(
    h.scenario.verdict.risk_score
  );
  expect(String(event.risk_level), '70 persists as high — what /alerts pages').toBe('high');
  return String(event.id);
}

export function assertStoredDetections(items: Record<string, any>[], h: Harness): void {
  const expected = h.scenario.detections[0];
  const stored = items[0]?.detections ?? [];
  expect(stored.length, 'the drop stored its detection row').toBeGreaterThanOrEqual(1);
  const match = stored.find((d: any) => String(d.object_type) === expected.class);
  expect(match, `stored detections carry the book's class ${expected.class}`).toBeTruthy();
  expect(
    Math.round(Number(match.confidence) * 100),
    'confidence round-trips at UI rounding (0.91)'
  ).toBe(Math.round(expected.confidence * 100));
}

/** End-of-spec honesty, the guard surviving the whole drive (F2.1's pin,
 *  re-armed here so a DO-1 spec that reached for a mock fails LOUD). */
export async function assertGuardSurvives(page: Page, h: Harness): Promise<void> {
  expect(new URL(page.url()).host).toBe(new URL(h.ui).host);
  expect(() => page.route('**/api/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
}
