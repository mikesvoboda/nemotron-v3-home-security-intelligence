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
import type { Page } from '@playwright/test';

const REQUIRED = [
  'FEATURE_CHECK_UI_URL',
  'FEATURE_CHECK_API_URL',
  'FEATURE_CHECK_ADMIN_USERNAME',
  'FEATURE_CHECK_ADMIN_PASSWORD',
] as const;

export interface DashboardHarness {
  ready: true;
  api: string;
  ui: string;
  admin: { username: string; password: string };
}

export type HarnessState = DashboardHarness | { ready: false; why: string };

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

export interface Session {
  name: string;
  value: string;
}

/** Real POST /api/auth/login — same field names and cookie handling as F2.1/OP-1/FE-1. */
export async function adminSession(h: DashboardHarness): Promise<Session> {
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

/**
 * Seed a real session cookie onto the UI origin (the cookie is genuine state
 * from a real login — the guard does not cover addCookies; see
 * ../dashboard-drop.spec.ts for the reasoning).
 */
export async function loginAsAdmin(page: Page, h: DashboardHarness): Promise<Session> {
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

/** GET with the session attached Node-side (ground-truth reads, never the UI origin). */
export async function api<T>(h: DashboardHarness, session: Session, path: string): Promise<T> {
  const res = await fetch(`${h.api}${path}`, {
    headers: { Cookie: `${session.name}=${session.value}` },
  });
  const body = (await res.json().catch(() => null)) as T | null;
  if (res.status !== 200) {
    throw new Error(`GET ${path} answered ${res.status}: ${JSON.stringify(body)?.slice(0, 200)}`);
  }
  return body as T;
}

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
export async function seedTourDismissed(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.setItem('nemotron-tour-completed', 'true');
    localStorage.setItem('nemotron-tour-skipped', 'true');
  });
}

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
export const BOOT_QUIET_MS = 2_000;

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
export async function quietBoot(page: Page, h: DashboardHarness, path = '/'): Promise<void> {
  await driveUntilBooted(page, 'quietBoot', async () => {
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.goto(h.ui + path, { waitUntil: 'domcontentloaded' });
  });
}

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
export async function settledReload(page: Page): Promise<void> {
  await driveUntilBooted(page, 'settledReload', async () => {
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.reload({ waitUntil: 'domcontentloaded' });
  });
}

/** The tripwire closing every golden spec (F2.1's; OP-1 calls it closedByGuard). */
export function closedByGuard(page: Page): void {
  void page.route('**/api/**', () => undefined);
}
