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
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  // Test directory - use specs subdirectory for organized test files
  testDir: './tests/e2e/specs',

  // Run tests in files in parallel
  fullyParallel: true,

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Limit workers on CI for stability
  workers: process.env.CI ? 1 : undefined,

  // Reporter configuration
  reporter: process.env.CI
    ? [['github'], ['html', { outputFolder: 'playwright-report' }]]
    : [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],

  // Output directory for test artifacts (screenshots, videos, traces)
  outputDir: './test-results',

  // Global timeout for each test
  timeout: 30000,

  // Expect timeout
  expect: {
    timeout: 5000,
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
  },

  // Projects - Multi-browser testing configuration
  // All browsers defined; CI uses --project flag to select specific browser
  // This enables parallel browser testing in separate CI containers
  projects: [
    // Desktop browsers
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    // Mobile viewports (only run locally, not in CI parallel jobs)
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'mobile-safari',
      use: { ...devices['iPhone 12'] },
    },
    // Tablet viewports
    {
      name: 'tablet',
      use: { ...devices['iPad (gen 7)'] },
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
