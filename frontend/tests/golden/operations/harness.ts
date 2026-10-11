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
import { expect, type Locator, type Page } from '@playwright/test';

const REQUIRED = [
  'FEATURE_CHECK_UI_URL',
  'FEATURE_CHECK_API_URL',
  'FEATURE_CHECK_ADMIN_USERNAME',
  'FEATURE_CHECK_ADMIN_PASSWORD',
] as const;

export interface OpsHarness {
  ready: true;
  api: string;
  ui: string;
  admin: { username: string; password: string };
}

export type HarnessState = OpsHarness | { ready: false; why: string };

export function readOpsHarness(): HarnessState {
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

export interface Session {
  name: string;
  value: string;
}

/** Real POST /api/auth/login — same field names and cookie handling as F2.1. */
export async function adminSession(h: OpsHarness): Promise<Session> {
  const res = await fetch(`${h.api}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: h.admin.username, password: h.admin.password }),
  });
  if (res.status !== 200) throw new Error(`admin login answered ${res.status}`);
  const pair = res.headers.getSetCookie().map((c) => c.split(';')[0]).find((c) => c.includes('='));
  if (!pair) throw new Error('admin login set no session cookie');
  const i = pair.indexOf('=');
  return { name: pair.slice(0, i), value: pair.slice(i + 1) };
}

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
export async function loginAsAdmin(page: Page, h: OpsHarness): Promise<Session> {
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

export function apiCookie(session: Session): Record<string, string> {
  return { Cookie: `${session.name}=${session.value}` };
}

/** Backend-state read against the real API (NOT the UI origin — never intercepted). */
export async function api<T>(h: OpsHarness, session: Session, path: string): Promise<T> {
  const res = await fetch(`${h.api}${path}`, { headers: apiCookie(session) });
  const body = (await res.json().catch(() => null)) as T | null;
  if (res.status !== 200) throw new Error(`GET ${path} answered ${res.status}: ${JSON.stringify(body)?.slice(0, 200)}`);
  return body as T;
}

export async function authPost<T>(
  h: OpsHarness,
  session: Session,
  path: string,
  body?: unknown,
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
  h: OpsHarness,
  session: Session,
  path: string,
  body?: unknown,
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
  h: OpsHarness,
  session: Session,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${h.api}${path}`, {
    method: 'DELETE',
    headers: { ...apiCookie(session), 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const parsed = (await res.json().catch(() => null)) as T | null;
  if (res.status !== 200) throw new Error(`DELETE ${path} answered ${res.status}: ${JSON.stringify(parsed)?.slice(0, 200)}`);
  return parsed as T;
}

/** Poll an API endpoint until done() holds (deadline throws with the last body). */
export async function pollApi<T>(
  h: OpsHarness,
  session: Session,
  path: string,
  done: (body: T) => boolean,
  timeoutMs: number,
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
  opts: { retryIntervalMs?: number } = {},
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
      { timeout: 60_000, intervals: [opts.retryIntervalMs ?? 1_500] },
    )
    .toBe(true);
}

/**
 * The tripwire closing every golden spec (same one F2.1 asserts): the guard
 * patches page.route to THROW SYNCHRONOUSLY, so this never produces the
 * Promise its declared type claims; `void` marks discarding a Promise the
 * guard guarantees never exists. Call site:
 * expect(() => closedByGuard(page)).toThrow(GUARD_MESSAGE).
 */
export function closedByGuard(page: Page): void {
  void page.route('**/api/**', () => undefined);
}
