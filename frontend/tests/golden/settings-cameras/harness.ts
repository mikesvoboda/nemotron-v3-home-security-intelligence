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
 * 3. Nginx burst discipline (`BOOT_QUIET_MS = 2_000`, `settledGoto`):
 *    `frontend/nginx.conf:24` limits `/api` to `rate=10r/s` with `burst=20`.
 *    `ProcessingSettings` and `CamerasSettings` fire 3–6 concurrent GETs on
 *    mount; `settledGoto` pauses before navigation and retries if the shared
 *    nginx token bucket sheds a boot request with 429.
 * 4. Background camera-cache invalidation (`backend/api/routes/cameras.py:815-819`,
 *    `:913-917`, `:992-996`): `POST /api/cameras`, `PATCH /api/cameras/{id}`,
 *    and `DELETE /api/cameras/{id}` schedule `_invalidate_cameras_cache_background`
 *    via FastAPI `BackgroundTasks`. Helpers `waitCameraPresent` and
 *    `waitCameraAbsent` poll `GET /api/cameras` until the Redis list cache
 *    reflects the write.
 * 5. Shared `/tmp/runtime.env` restoration (`docker-compose.ci.yml:157`):
 *    `PATCH /api/system/config`, `PATCH /api/v1/settings`, and
 *    `PUT /api/system/severity` all read-merge-write `HSI_RUNTIME_ENV_PATH`
 *    and clear `get_settings.cache_clear()`. Every mutating test snapshots the
 *    backend state before mutating and restores it inside a `finally` block.
 */
import { GUARD_MESSAGE, expect } from '../guard';

import type { Locator, Page } from '@playwright/test';

export interface Harness {
  ready: true;
  api: string;
  ui: string;
  admin: { username: string; password: string };
}

/**
 * Read the harness contract defensively: any piece missing -> `{ ready: false, why }`.
 * Collection-time code must not throw, or `npx playwright test --project=golden --list`
 * breaks outside the feature-check harness.
 */
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

/**
 * Authenticate against `POST /api/auth/login` on the real backend.
 * Splits on the first `=` so base64 padding in session cookies is preserved.
 */
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

/**
 * Install the admin session cookie on the UI origin so nginx forwards it on `/api/*`.
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

export interface ApiResponse {
  status: number;
  body: any;
}

export interface AuthedFetch {
  getJson(urlPath: string): Promise<ApiResponse>;
  send(urlPath: string, method: string, payload?: unknown): Promise<ApiResponse>;
}

/**
 * Direct backend API client authenticated with the harness admin session cookie.
 * Runs against `h.api` (direct to backend:8000, bypassing nginx rate-limiting).
 */
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
      call(urlPath, {
        method,
        body: payload === undefined ? undefined : JSON.stringify(payload),
      }),
  };
}

/**
 * Sign in on both the backend API and the Playwright browser context.
 */
export async function signIn(page: Page, h: Harness): Promise<AuthedFetch> {
  const session = await adminSession(h);
  await login(page, h, session);
  return authedFetch(h, session);
}

/**
 * Normalize a request/response URL to its pathname with one optional trailing
 * slash removed, preventing false negatives when endpoints include a trailing slash.
 */
export function apiPath(url: string): string {
  const p = new URL(url).pathname;
  return p.length > 1 && p.endsWith('/') ? p.slice(0, -1) : p;
}

/**
 * End-of-spec verification that the page stayed on the real UI origin and the
 * F2.1 route-interception guard remains armed.
 */
export async function assertGuardSurvives(page: Page, h: Harness): Promise<void> {
  const currentHost = await page.evaluate(() => window.location.host);
  expect(currentHost).toBe(new URL(h.ui).host);
  expect(() => page.route('**/api/**', (route) => route.abort())).toThrow(GUARD_MESSAGE);
}

/**
 * Pause before browser navigations so the nginx `/api` rate-limit bucket
 * (`rate=10r/s`, `burst=20` in `frontend/nginx.conf:24`) refills between waves.
 */
export const BOOT_QUIET_MS = 2_000;

async function shedCoat(page: Page): Promise<string | null> {
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
    await page.waitForTimeout(BOOT_QUIET_MS);
    await page.goto(`${h.ui}${path}`, { waitUntil: 'domcontentloaded' });
    const painted = await Promise.race([
      sentinel(page)
        .waitFor({ state: 'visible', timeout: 12_000 })
        .then(() => 'booted' as const),
      (async () => {
        try {
          for (let t = 0; t < 24; t++) {
            const coat = await shedCoat(page);
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
 * Fetch the current camera list from `GET /api/cameras` (`backend/api/routes/cameras.py:152`).
 */
export async function listCameras(api: AuthedFetch): Promise<CameraRecord[]> {
  const res = await api.getJson('/api/cameras');
  expect(res.status, 'GET /api/cameras answers 200').toBe(200);
  return Array.isArray(res.body?.items) ? (res.body.items as CameraRecord[]) : [];
}

/**
 * Poll `GET /api/cameras` until `cameraId` appears in `items` (handles background
 * Redis cache invalidation in `_invalidate_cameras_cache_background`, `cameras.py:815-819`).
 */
export async function waitCameraPresent(
  api: AuthedFetch,
  cameraId: string
): Promise<CameraRecord | undefined> {
  let found: CameraRecord | undefined;
  await expect
    .poll(
      async () => {
        const items = await listCameras(api);
        found = items.find((c) => c.id === cameraId);
        return Boolean(found);
      },
      { timeout: 10_000, intervals: [200, 400, 800] }
    )
    .toBe(true);
  return found;
}

/**
 * Poll `GET /api/cameras` until `cameraId` is absent from `items` (handles background
 * Redis cache invalidation in `_invalidate_cameras_cache_background`, `cameras.py:992-996`).
 */
export async function waitCameraAbsent(api: AuthedFetch, cameraId: string): Promise<void> {
  await expect
    .poll(
      async () => {
        const items = await listCameras(api);
        return items.some((c) => c.id === cameraId);
      },
      { timeout: 10_000, intervals: [200, 400, 800] }
    )
    .toBe(false);
}

/**
 * Delete a camera by ID if it exists (`204` or `404`), then wait for the list cache
 * to stop returning it. Safe to call in `finally` blocks regardless of where a test failed.
 */
export async function deleteCameraIfPresent(api: AuthedFetch, cameraId: string): Promise<void> {
  const res = await api.send(`/api/cameras/${cameraId}`, 'DELETE');
  expect([204, 404], `DELETE /api/cameras/${cameraId} answers 204 or 404`).toContain(res.status);
  await waitCameraAbsent(api, cameraId);
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
