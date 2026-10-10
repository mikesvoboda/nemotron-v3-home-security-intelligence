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

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function globalSetup() {
  // Create the storage state file directly without needing a browser
  // This is more reliable than trying to navigate to the app during setup
  const storageState = {
    cookies: [],
    origins: [
      {
        origin: 'https://localhost:8444',
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
  };

  // Ensure the directory exists
  const authDir = path.join(__dirname, '.auth');
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
  }

  // Write the storage state file
  const storagePath = path.join(authDir, 'storage-state.json');
  fs.writeFileSync(storagePath, JSON.stringify(storageState, null, 2));

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

const E2E_BASE_URL = 'http://localhost:8444';

async function warmDevServer() {
  let browser;
  try {
    browser = await chromium.launch({
      args: ['--disable-gpu', '--disable-dev-shm-usage'],
    });
    const page = await browser.newPage();

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
