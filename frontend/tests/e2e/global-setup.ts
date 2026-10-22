/**
 * Global Setup for E2E Tests
 *
 * Runs once before all tests. Used for:
 * - Setting up shared state
 * - Disabling UI elements that interfere with tests (like product tour)
 * - Warming the dev server's module graph (ruling 58) so no test pays it
 *
 * @see https://playwright.dev/docs/test-global-setup-teardown
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

import { chromium } from '@playwright/test';

import { E2E_STORAGE_STATE_ORIGIN, resolveE2eBaseUrl } from './base-url';
import { setupApiMocks } from './fixtures/api-mocks';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * The storage state global setup writes: no cookies, one origin — the origin
 * the specs actually run at (tests/e2e/base-url.ts) — carrying exactly the
 * two tour-suppression keys.
 *
 * Serialization is fixed deliberately (2-space indent, trailing newline) so
 * the output is byte-identical to the committed seed
 * tests/e2e/.auth/storage-state.json: the committed file stays in the tree
 * (see the DECIDE in the PR) because golden runs and
 * concurrent-operations.spec.ts read it WITHOUT running global setup first,
 * and byte-stability means a non-golden run never dirties the working tree.
 */
export function buildStorageStateJson(): string {
  return `${JSON.stringify(
    {
      cookies: [],
      origins: [
        {
          origin: E2E_STORAGE_STATE_ORIGIN,
          localStorage: [
            {
              name: 'nemotron-tour-completed',
              value: 'true',
            },
            {
              name: 'nemotron-tour-skipped',
              value: 'true',
            },
          ],
        },
      ],
    },
    null,
    2
  )}\n`;
}

/**
 * Write the tour-suppression storage state to the given path; returns the
 * path so callers (and the pinning test) can read back what was written.
 * Exported for the [r299] pin under tests/pinning/.
 */
export function writeTourSuppressionState(storagePath: string): string {
  // Ensure the directory exists
  fs.mkdirSync(path.dirname(storagePath), { recursive: true });
  fs.writeFileSync(storagePath, buildStorageStateJson());
  return storagePath;
}

async function globalSetup() {
  // Create the storage state file directly without needing a browser.
  // This is more reliable than trying to navigate to the app during setup.
  // The origin comes from tests/e2e/base-url.ts — the same base URL the
  // Playwright config hands every spec — not from a literal (ruling 299,
  // Q-179: the old literal was https:// while the specs run http://, and
  // Playwright applies localStorage per origin, so the tour keys never
  // landed).
  writeTourSuppressionState(path.join(__dirname, '.auth', 'storage-state.json'));

  console.log('Global setup: Product tour disabled via storage state');

  // Ruling 58: warm the dev server's module graph once, outside every test.
  // Measured on this branch (timestamps in the PR): a cold first navigation
  // pays ~9.9s for vite's on-request transform of the app graph, and the
  // serial probe proved the cost is per server boot, not per test — a second
  // spec in the same boot navigates in ~1.9s. Since CI self-skips leave
  // verdict-engine-banner as the shard's first real navigation, that one-time
  // boot cost lands on ITS timed junit row and trips the 10.0s duration
  // audit. Paying it here (globalSetup runs after the webServer is up and
  // outside every test's timed window) charges it to no spec. If the warm-up
  // itself fails we log and continue: the suite still passes, just slower,
  // and the duration audit stays the fail-closed backstop.
  await warmDevServer();
}

const E2E_BASE_URL = resolveE2eBaseUrl();

/**
 * Ruling 58: warm the dev server's module graph once, outside every test.
 *
 * Exposed for the [r299] pin (tests/pinning/) so the pin exercises the real
 * export surface; see the module comment there.
 */
export async function warmDevServer(): Promise<void> {
  let browser;
  try {
    browser = await chromium.launch({
      args: ['--disable-gpu', '--disable-dev-shm-usage'],
    });
    const page = await browser.newPage();

    // Register the full E2E API mock suite before the auth overrides so
    // DashboardPage's child queries (/api/cameras, /api/events, /api/system/*)
    // resolve during warmup instead of failing ECONNREFUSED, warming the lazy
    // dashboard chunks too.
    await setupApiMocks(page);

    // Same auth posture the specs use, so the warm navigation reaches INSIDE
    // ProtectedRoute (Layout renders `main-content`): that is the point where
    // the module graph has actually been transformed. Unmocked, /api/auth/me
    // 404s and the app stops at /login with most chunks never requested.
    await page.route('**/api/auth/setup-status', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ setup_required: false }),
      })
    );
    await page.route('**/api/auth/me', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          username: 'e2e-warmup',
          email: 'e2e-warmup@example.com',
          is_active: true,
          is_admin: true,
          created_at: '2026-01-01T00:00:00Z',
          last_login_at: null,
        }),
      })
    );
    await page.route('**/api/system/health/ready', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ready: true,
          workers: [],
          timestamp: new Date().toISOString(),
          verdict_engine: { state: 'available', since: null, reason: null },
        }),
      })
    );

    await page.goto(`${E2E_BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="main-content"]', { timeout: 60_000 });
    console.log('Global setup: dev server module graph warmed');
  } catch (err) {
    console.warn(`Global setup: dev-server warm-up FAILED (tests still run, slower): ${err}`);
  } finally {
    await browser?.close();
  }
}

export default globalSetup;
