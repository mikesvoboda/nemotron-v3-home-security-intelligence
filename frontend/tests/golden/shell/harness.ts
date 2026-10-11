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
import type { Page } from '@playwright/test';

const REQUIRED = [
  'FEATURE_CHECK_UI_URL',
  'FEATURE_CHECK_API_URL',
  'FEATURE_CHECK_ADMIN_USERNAME',
  'FEATURE_CHECK_ADMIN_PASSWORD',
] as const;

export interface ShellHarness {
  ready: true;
  api: string;
  ui: string;
  admin: { username: string; password: string };
}

export type HarnessState = ShellHarness | { ready: false; why: string };

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

export interface Session {
  name: string;
  value: string;
}

/** Real POST /api/auth/login — same field names and cookie handling as F2.1/OP-1. */
export async function adminSession(h: ShellHarness): Promise<Session> {
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
export async function loginAsAdmin(page: Page, h: ShellHarness): Promise<Session> {
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

/** GET with the session attached Node-side (backend-state reads, never the UI origin). */
export async function api<T>(h: ShellHarness, session: Session, path: string): Promise<T> {
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
export async function seedTourDismissed(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.setItem('nemotron-tour-completed', 'true');
    localStorage.setItem('nemotron-tour-skipped', 'true');
  });
}

/** The tripwire closing every golden spec (F2.1's; OP-1 calls it closedByGuard). */
export function closedByGuard(page: Page): void {
  void page.route('**/api/**', () => undefined);
}
