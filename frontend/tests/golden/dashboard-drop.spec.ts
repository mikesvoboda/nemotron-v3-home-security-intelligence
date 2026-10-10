/**
 * F2.1 golden path 1 (20-frontend.md §F2.1): fixture image dropped into a
 * camera folder → dashboard event carrying the fake VLM's verdict → event
 * detail shows score and summary.
 *
 * Deliberately unmocked (guard.ts enforces it). Everything this spec relies on
 * is the contract the feature-check harness (O2.2) exports:
 *
 *   FEATURE_CHECK_UI_URL / _API_URL       the stack's entry points
 *   FEATURE_CHECK_CAMERA_ROOT             <run>/cameras — one folder per camera
 *   FEATURE_CHECK_CAMERAS                 cameras.json: scenario name → backend id
 *   FEATURE_CHECK_SCENARIOS               scenarios.json — the fake AI's scenario book
 *   FEATURE_CHECK_ADMIN_USERNAME/PASSWORD the first admin the harness registered
 *
 * The fake VLM answers by hashing the image bytes, so the fixture choice IS
 * the expected verdict: scenarios.json carries the verdict, risk score and
 * summary the fake answers with for each image. This spec reads them from that
 * book instead of hardcoding them — edit the book and the assertion follows it
 * instead of lying.
 *
 * Timing mirrors the harness's own smoke check (feature_check.py smoke(),
 * read at O2.2): poll GET /api/events?camera_id=<id> every 5 s until an item
 * carries verification.verdict, then expect exactly one event with the
 * scenario's verdict and risk score. The backend dedupes by content hash for
 * 300 s and each harness run gets fresh volumes, so one drop per run is
 * exactly one event.
 *
 * One test, end to end: Playwright runs collection BEFORE any runtime skip, so
 * the env reads below are defensive (a partial env self-skips instead of
 * crashing `--list`), and the whole path lives in one test body — no state
 * crosses tests, and a retry starts from a fresh drop attempt, matching the
 * dedupe window's arithmetic.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import type { Page } from '@playwright/test';

import { GUARD_MESSAGE, expect, test } from './guard';

interface Scenario {
  name: string;
  image: string;
  verdict: { verdict: string; risk_score: number; summary: string };
  reply_delay_seconds?: number;
}

interface Harness {
  ready: true;
  api: string;
  ui: string;
  cameraRoot: string;
  admin: { username: string; password: string };
  scenario: Scenario;
  scenarioImagePath: string;
  cameraId: string;
}

/**
 * Read the harness contract defensively: any piece missing → {ready: false,
 * why}. Collection-time code must not throw, or `--list` breaks outside the
 * harness; inside it, every piece exists (golden() exports the full set).
 */
function readHarness(): Harness | { ready: false; why: string } {
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
  // fast-reply scenarios only: slow-reply delays its verdict 40 s and belongs
  // to a latency golden path, not the first one; harness-smoke belongs to O2.2.
  const scenario = scenarios.find(
    (entry) =>
      !entry.reply_delay_seconds &&
      entry.verdict.verdict === 'confirmed' &&
      entry.name !== 'harness-smoke'
  );
  if (!scenario) return { ready: false, why: 'no fast confirmed scenario in the book' };
  const cameraId = cameras[scenario.name];
  if (!cameraId) {
    return { ready: false, why: `harness seeded no camera named ${scenario.name}` };
  }
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

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

// scripts/feature-check.sh lives at the repo root: three up from frontend/tests/golden.
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');

interface Session {
  name: string;
  value: string;
}

/** A real login against the real backend — the cookie is genuine state, not a mock. */
async function adminSession(h: Harness): Promise<Session> {
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
 * nginx proxies /api and /ws to the backend (frontend/nginx.conf,
 * "location ^~ /api" / "location ^~ /ws"), so the browser authenticates the way
 * a user who logged in through this very form would. The guard does not cover
 * addCookies — a cookie is state a real login legitimately produces, not
 * traffic interception.
 */
async function login(page: Page, h: Harness, session: Session): Promise<void> {
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

test.describe('golden path: camera drop to dashboard event @critical', () => {
  test.setTimeout(210_000); // 150 s pipeline wait + login + navigation

  test('a dropped fixture surfaces on the dashboard with the fake VLM verdict, and its detail shows score and summary', async ({
    page,
  }) => {
    test.info().skip(!harness.ready, harness.ready ? '' : harness.why);
    if (!harness.ready) return;
    const h = harness;
    const { scenario } = h;

    // 1. The drop, through O2.2's own helper (the documented contract —
    // docs/developer/testing.md, "Feature check" — not a bare copy, so folder
    // layout changes can't silently split from it).
    execFileSync('scripts/feature-check.sh', ['drop', h.scenarioImagePath, scenario.name], {
      cwd: repoRoot,
      env: { ...process.env, FEATURE_CHECK_CAMERA_ROOT: h.cameraRoot },
      encoding: 'utf8',
      timeout: 30_000,
    });

    // 2. The backend side, asserted before the UI on purpose: an event that
    // never arrived would otherwise only prove the dashboard renders.
    // Polling copied from feature_check.py smoke(): until an item carries a
    // verdict; 150 s < the harness's own 300 s budget.
    const session = await adminSession(h);
    const deadline = Date.now() + 150_000;
    let items: Record<string, any>[] = [];
    while (Date.now() < deadline) {
      const response = await fetch(
        `${h.api}/api/events?camera_id=${encodeURIComponent(h.cameraId)}`,
        { headers: { Cookie: `${session.name}=${session.value}` } }
      );
      const body = (await response.json().catch(() => ({}))) as { items?: Record<string, any>[] };
      items = response.status === 200 && Array.isArray(body.items) ? body.items : [];
      if (items.length && (items[0].verification ?? {}).verdict) break;
      await new Promise((resolve) => setTimeout(resolve, 5_000));
    }
    expect(items.length, `expected exactly one event for camera ${scenario.name}`).toBe(1);
    const event = items[0];
    // The harness smoke predicate, asserted here: the scenario's verdict and score.
    expect(String((event.verification ?? {}).verdict)).toBe(scenario.verdict.verdict);
    expect(Number(event.risk_score)).toBe(scenario.verdict.risk_score);
    const eventId = String(event.id);

    // 3. The dashboard, unmocked. ActivityFeed renders one card per event with
    // data-testid="detection-card-<id>", showing the risk badge (score) and the
    // summary the fake VLM wrote.
    await login(page, h, session);
    await page.goto(`${h.ui}/`, { waitUntil: 'domcontentloaded' });
    const card = page.getByTestId(`detection-card-${eventId}`);
    await expect(card, 'the dropped event surfaced on the dashboard').toBeVisible({
      timeout: 30_000,
    });
    await expect(card).toContainText(String(scenario.verdict.risk_score));
    await expect(card).toContainText(scenario.verdict.summary);

    // 4. Event detail through the dashboard's OWN click path: DashboardPage
    // navigates to /timeline?event=<id> (handleEventClick) and EventTimeline
    // opens EventDetailModal for a valid ?event= param. Score is in the modal
    // header; summary under "AI Summary" (details tab, the modal's default).
    await card.click();
    const modal = page.getByTestId('event-detail-modal');
    await expect(modal, 'the dashboard click opened the detail modal').toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId('risk-score')).toContainText(String(scenario.verdict.risk_score));
    await expect(page.getByTestId('ai-analysis-section')).toContainText(scenario.verdict.summary);

    // 5. End-to-end honesty, measured rather than asserted in faith: the page
    // we ended on is the harness's own UI (engine-assigned host:port), and the
    // guard survived the whole drive — the path never reached for a mock.
    expect(new URL(page.url()).host).toBe(new URL(h.ui).host);
    expect(() => page.route('**/api/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
  });
});
