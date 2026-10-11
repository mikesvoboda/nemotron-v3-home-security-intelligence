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

/** Quiet (drain the shared nginx burst), then navigate the UI origin. */
export async function quietBoot(page: Page, h: DashboardHarness, path = '/'): Promise<void> {
  await page.waitForTimeout(BOOT_QUIET_MS);
  await page.goto(h.ui + path, { waitUntil: 'domcontentloaded' });
}

/** The tripwire closing every golden spec (F2.1's; OP-1 calls it closedByGuard). */
export function closedByGuard(page: Page): void {
  void page.route('**/api/**', () => undefined);
}
