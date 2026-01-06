import { defineConfig, devices } from '@playwright/test';

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
  reporter: process.env.CI
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

  // Global setup script to optimize test startup (future optimization)
  // This runs once before all tests, reducing per-test overhead
  // globalSetup: './tests/e2e/global-setup.ts',  // Uncomment when created

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
    // Base URL to use in actions like `await page.goto('/')`
    baseURL: 'http://localhost:5173',

    // Collect trace when retrying the failed test
    trace: 'on-first-retry',

    // Capture screenshot only on failure
    screenshot: 'only-on-failure',

    // Record video only on failure
    video: 'retain-on-failure',

    // Navigation timeout
    navigationTimeout: 10000,

    // Action timeout (clicks, fills, etc.)
    actionTimeout: 5000,

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
  ],

  // Run your local dev server before starting the tests
  // Uses dev:e2e which runs Vite without the API proxy, allowing Playwright's
  // page.route() to intercept API requests directly instead of Vite's proxy
  // trying to forward them to localhost:8000 (causing ECONNREFUSED in CI)
  webServer: {
    command: 'npm run dev:e2e',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
