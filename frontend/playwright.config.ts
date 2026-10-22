import { defineConfig, devices } from '@playwright/test';

import { E2E_BASE_URL } from './tests/e2e/base-url';

/**
 * Playwright E2E Test Configuration
 *
 * This configuration sets up comprehensive E2E tests for the Home Security Dashboard.
 * Tests run in multiple browsers: Chromium, Firefox, and WebKit.
 *
 * Browser Selection:
 * - CI: Runs each browser in parallel containers via --project flag
 * - Local: Runs all browsers by default, or specify with --project flag
 *
 * Test Tagging (NEM-1478):
 * Tests can be tagged using annotations in test titles:
 * - @smoke - Critical path tests that should run on every commit
 * - @critical - High-priority tests for core functionality
 * - @slow - Tests that take longer to execute
 * - @flaky - Tests known to be flaky (tracked for stability improvements)
 * - @network - Tests that simulate network conditions
 *
 * @example
 * # Run all browsers (local)
 * npm run test:e2e
 *
 * # Run specific browser
 * npm run test:e2e -- --project=chromium
 * npm run test:e2e -- --project=firefox
 * npm run test:e2e -- --project=webkit
 *
 * # Run mobile tests
 * npm run test:e2e -- --project=mobile-chrome
 * npm run test:e2e -- --project=mobile-safari
 *
 * # Run tests by tag (selective execution)
 * npm run test:e2e -- --grep @smoke      # Run only smoke tests
 * npm run test:e2e -- --grep @critical   # Run only critical tests
 * npm run test:e2e -- --grep-invert @slow # Exclude slow tests
 * npm run test:e2e -- --grep "@smoke|@critical" # Run smoke OR critical
 *
 * @see https://playwright.dev/docs/test-configuration
 */
/**
 * F2.1 golden-path mode (docs/uplevel/history/packages-done.md §F2.1).
 *
 * The `golden` project drives the real stack the feature-check harness brings
 * up (scripts/feature-check.sh, O2.2) with NO API mocking. Detection is either
 * the harness's FEATURE_CHECK_* env (it exports them for the golden run) or an
 * explicit --project=golden on the command line. When detected:
 *
 * - `webServer` is dropped: the harness's compose stack already serves the UI
 *   at FEATURE_CHECK_UI_URL; booting Vite beside it would be dead weight.
 * - `globalSetup` is dropped: it mocks /api/auth/* to warm the dev server —
 *   the exact thing golden paths are forbidden to do.
 * - The project is only ADDED to `projects` under golden mode, so a plain
 *   `npm run test:e2e` never runs golden specs without a stack under them.
 */
const GOLDEN_UI = process.env.FEATURE_CHECK_UI_URL;
const goldenRequested =
  process.argv.includes('--project=golden') ||
  process.argv.includes('--project=golden-seeded') ||
  (process.argv.includes('--project') &&
    ['golden', 'golden-seeded'].includes(process.argv[process.argv.indexOf('--project') + 1]));
const goldenMode = Boolean(GOLDEN_UI) || goldenRequested;

/**
 * [r282] The manifest shard's selection, forwarded by the harness as
 * FEATURE_CHECK_GOLDEN_FILES (a space-separated list of frontend-relative spec
 * paths; the harness reads frontend/golden-shards.json and picks the run's
 * shard). The golden project's testIgnore must ignore every spec NOT in the
 * selection, and Playwright's testIgnore accepts only strings and RegExps
 * (lib/runner/index.js validates the prop and throws on anything else; the
 * matcher then tests the ABSOLUTE file path against the pattern), so the
 * negated selection is compiled into one RegExp here:
 *
 * - The seeded exclusion always applies (those specs belong to golden-seeded).
 * - With a selection: ^(?!.*(?:a|b|c)$).*\.spec\.ts$ ignores every spec whose
 *   ABSOLUTE path does not END IN one of the selected frontend-relative
 *   names (the .* inside the lookahead lets the test run at the absolute
 *   path's start while each alternative anchors at the string's end -- a
 *   bare ^(?!a$|b$) would only match when the path STARTS with the
 *   selected relative name). Anchoring on the absolute path's tail with the
 *   selected relative path is sound here because testDir is
 *   ./tests/golden and the manifest rows are tests/golden/... -- a basename
 *   collision across directories would double-select, and the manifest pack
 *   never produces one (the rows are the corpus's own unique paths; the
 *   union pin in backend/tests/unit/scripts/test_golden_shard_manifest.py
 *   guards the set they come from).
 * - Unset or empty -> the RegExp is the seeded exclusion alone -> the
 *   count-based --shard split (or a whole-suite run) applies byte for byte.
 */
function escapeRegExp(s: string): string {
  // Only two characters in a manifest row can carry regex meaning -- the
  // dots in the .spec.ts extension and (never today) a directory name -- but
  // the list is DATA, so every regex metacharacter is escaped, not just the
  // ones this corpus happens to contain.
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
const GOLDEN_SHARD_SELECTION = (process.env.FEATURE_CHECK_GOLDEN_FILES ?? '')
  .split(/\s+/)
  .filter(Boolean);
const GOLDEN_SHARD_IGNORE = new RegExp(
  ['.*\\.seeded\\.spec\\.ts$']
    .concat(
      GOLDEN_SHARD_SELECTION.length
        ? [
            '^(?!.*(?:' +
              GOLDEN_SHARD_SELECTION.map((f) => escapeRegExp(f)).join('|') +
              ')$).*\\.spec\\.ts$',
          ]
        : []
    )
    .join('|')
);

export default defineConfig({
  // Test directory - includes both specs and visual test directories
  // Visual tests are matched by the visual-chromium project using testMatch
  testDir: './tests/e2e',

  // Run tests in files in parallel
  fullyParallel: true,

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry Configuration (NEM-1477: Test Retry Isolation)
  // - CI: 2 retries to catch flaky tests (especially on secondary browsers)
  // - Local: No retries for faster feedback during development
  // Each retry runs the test in complete isolation with a fresh browser context
  retries: process.env.CI ? 2 : 0,

  // Parallel workers: use 4 in CI for speed
  // For CI sharding, run: npx playwright test --shard=1/4
  workers: process.env.CI ? 4 : undefined,

  // Reporter Configuration (NEM-1477: Flaky Test Detection)
  // CI: github (annotations), html (artifacts), junit (duration auditing), json (flaky analysis)
  // The JSON reporter enables post-run analysis of flaky tests (tests that pass on retry)
  // Golden mode writes NO html report and points junit exactly where the
  // feature-check harness asked for it (PLAYWRIGHT_JUNIT_OUTPUT_FILE, set by
  // scripts/feature_check.py golden()) — that file is its per-spec artifact.
  reporter: goldenMode
    ? [
        ['list'],
        ['github'],
        ...(process.env.PLAYWRIGHT_JUNIT_OUTPUT_FILE
          ? [['junit', { outputFile: process.env.PLAYWRIGHT_JUNIT_OUTPUT_FILE }] as const]
          : []),
      ]
    : process.env.CI
      ? [
          ['github'],
          ['html', { outputFolder: 'playwright-report' }],
          ['junit', { outputFile: 'test-results/e2e-results.xml' }],
          ['json', { outputFile: 'test-results/e2e-results.json' }],
        ]
      : [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],

  // Output directory for test artifacts (screenshots, videos, traces)
  outputDir: './test-results',

  // Global timeout for each test
  timeout: 15000,

  // Global setup script - disables product tour and sets up shared state
  // This runs once before all tests, preventing Joyride overlay from blocking interactions
  // Dropped in golden mode: it mocks /api/auth/* to warm the dev server, which
  // is exactly what golden paths must not do (and there is no dev server).
  globalSetup: goldenMode ? undefined : './tests/e2e/global-setup.ts',

  // Expect timeout - keep short for fast feedback
  // Error state tests use explicit longer timeouts where needed
  expect: {
    timeout: 3000,
    // Visual regression testing configuration
    toHaveScreenshot: {
      // Allow up to 100 pixels to differ (handles anti-aliasing differences)
      maxDiffPixels: 100,
      // Per-pixel color difference threshold (0-1)
      threshold: 0.2,
      // Disable animations for consistent screenshots
      animations: 'disabled',
    },
    toMatchSnapshot: {
      // Allow up to 100 pixels to differ
      maxDiffPixels: 100,
    },
  },

  // Shared settings for all the projects below
  use: {
    // Base URL to use in actions like `await page.goto('/')`.
    // Same source the global setup's storage-state origin derives from
    // (tests/e2e/base-url.ts) — Playwright seeds localStorage per origin,
    // so a divergent literal there would leave the tour-suppression keys
    // on an origin no spec ever loads (ruling 299, Q-179). Uses HTTP to
    // avoid TLS handshake issues with self-signed certs.
    baseURL: E2E_BASE_URL,

    // Collect trace when retrying the failed test
    trace: 'on-first-retry',

    // Capture screenshot only on failure
    screenshot: 'only-on-failure',

    // Record video only on failure
    video: 'retain-on-failure',

    // Navigation timeout - increased from 10000ms to 15000ms for CI stability
    navigationTimeout: 15000,

    // Action timeout (clicks, fills, etc.)
    actionTimeout: 5000,

    // Use storage state from global setup to have product tour disabled
    // This prevents Joyride overlay from blocking pointer events in tests
    storageState: 'tests/e2e/.auth/storage-state.json',

    // Ignore HTTPS errors for self-signed certificates in tests
    ignoreHTTPSErrors: true,

    // NOTE: launchOptions with --disable-gpu moved to Chromium-specific projects
    // WebKit doesn't support these Chromium-specific flags
  },

  // Projects - Multi-browser testing configuration
  // All browsers defined; CI uses --project flag to select specific browser
  // This enables parallel browser testing in separate CI containers
  projects: [
    // Smoke tests project (NEM-1478: Selective Execution)
    // Run only tests tagged with @smoke for quick validation
    // Usage: npx playwright test --project=smoke
    {
      name: 'smoke',
      use: { ...devices['Desktop Chrome'] },
      testMatch: /specs\/.*\.spec\.ts$/,
      grep: /@smoke/,
    },
    // Critical tests project (NEM-1478: Selective Execution)
    // Run only tests tagged with @critical for core functionality validation
    // Usage: npx playwright test --project=critical
    {
      name: 'critical',
      use: { ...devices['Desktop Chrome'] },
      testMatch: /specs\/.*\.spec\.ts$/,
      grep: /@critical/,
    },
    // Visual regression tests - run only on Chromium for consistency
    // Visual tests are in tests/e2e/visual/ directory
    {
      name: 'visual-chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          args: ['--disable-gpu', '--disable-dev-shm-usage'],
        },
      },
      testMatch: /visual\/.*\.spec\.ts$/,
    },
    // Desktop browsers
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          args: ['--disable-gpu', '--disable-dev-shm-usage'],
        },
      },
      // Only run specs, exclude visual tests (run via visual-chromium project)
      testMatch: /specs\/.*\.spec\.ts$/,
    },
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        // Firefox can be slower - increase action timeout
        actionTimeout: 8000,
        // Firefox needs longer navigation timeout for page loads (NEM-1807)
        navigationTimeout: 20000,
      },
      // Firefox needs longer test timeout for complex workflows
      // (same as WebKit - runs full 433 test suite without sharding)
      timeout: 30000,
      // Only run specs, exclude visual tests
      testMatch: /specs\/.*\.spec\.ts$/,
    },
    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
        // WebKit can be slower - increase action timeout
        actionTimeout: 8000,
      },
      // WebKit needs longer test timeout for complex workflows
      // (CRUD operations, waitForResponse, etc.)
      timeout: 30000,
      // Only run specs, exclude visual tests
      testMatch: /specs\/.*\.spec\.ts$/,
    },
    // Mobile viewports (only run locally, not in CI parallel jobs)
    {
      name: 'mobile-chrome',
      use: {
        ...devices['Pixel 5'],
        launchOptions: {
          args: ['--disable-gpu', '--disable-dev-shm-usage'],
        },
      },
      // Only run specs, exclude visual tests
      testMatch: /specs\/.*\.spec\.ts$/,
    },
    {
      name: 'mobile-safari',
      use: { ...devices['iPhone 12'] },
      // Only run specs, exclude visual tests
      testMatch: /specs\/.*\.spec\.ts$/,
    },
    // Tablet viewports
    {
      name: 'tablet',
      use: { ...devices['iPad (gen 7)'] },
      // Only run specs, exclude visual tests
      testMatch: /specs\/.*\.spec\.ts$/,
    },
    // Golden-path harness (F2.1, docs/uplevel/history/packages-done.md §F2.1).
    // scripts/feature_check.py detects this project by TEXT (a regex for
    // `name: 'golden'` over this file) and then runs `--project=golden`; the
    // literal above stays present so detection works. It is only ADDED to the
    // run in golden mode (see goldenMode), so `npm run test:e2e` never runs
    // these specs against a stack that isn't there. It lives outside the
    // ./tests/e2e graph (its own testDir) so a plain e2e run can never pick it
    // up by accident, and it reuses the guard fixture, not the auto-mocking
    // e2e fixtures.
    ...(goldenMode
      ? [
          {
            name: 'golden',
            testDir: './tests/golden',
            // [r282] When the harness selected this shard's files, ignore
            // every spec NOT in the list (space-separated, frontend-relative
            // paths, forwarded as FEATURE_CHECK_GOLDEN_FILES); the list is
            // the manifest's own shard row, so a selection must never drop a
            // selected file and never admit an unselected one. Unset or
            // empty means no selection: the count-based --shard split (or a
            // whole-suite run) applies, exactly as before. The seeded
            // exclusion composes -- a selected shard still never runs the
            // seeded specs (they belong to golden-seeded).
            testIgnore: GOLDEN_SHARD_IGNORE,
            // One worker, serial: the dashboard path drops a fixture and waits
            // on the backend's content-hash dedupe window, so its wait must not
            // interleave with another spec competing for the same camera.
            fullyParallel: false,
            workers: 1,
            // The harness's stack serves the UI on an engine-assigned port;
            // point every navigation there instead of the fixed e2e baseURL.
            use: {
              ...devices['Desktop Chrome'],
              baseURL: GOLDEN_UI,
              launchOptions: { args: ['--disable-gpu', '--disable-dev-shm-usage'] },
            },
          },
          {
            name: 'golden-seeded',
            testDir: './tests/golden',
            testMatch: /.*\.seeded\.spec\.ts$/,
            fullyParallel: false,
            workers: 1,
            use: {
              ...devices['Desktop Chrome'],
              baseURL: GOLDEN_UI,
              launchOptions: { args: ['--disable-gpu', '--disable-dev-shm-usage'] },
            },
          },
        ]
      : []),
  ],

  // Run your local dev server before starting the tests
  // Uses dev:e2e which runs Vite without the API proxy, allowing Playwright's
  // page.route() to intercept API requests directly instead of Vite's proxy
  // trying to forward them to localhost:8000 (causing ECONNREFUSED in CI)
  // Dropped in golden mode: the feature-check harness's compose stack already
  // serves the UI at FEATURE_CHECK_UI_URL; booting a Vite dev server beside
  // the real thing would be 120 s of dead weight pointing at nothing.
  webServer: goldenMode
    ? undefined
    : {
        command: 'npm run dev:e2e',
        // Uses HTTP for E2E tests to avoid TLS handshake issues with self-signed certs
        url: 'http://localhost:8444',
        reuseExistingServer: !process.env.CI,
        timeout: 120000,
        stdout: 'pipe',
        stderr: 'pipe',
      },
});
