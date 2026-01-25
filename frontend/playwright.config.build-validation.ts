import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright Configuration for Build Validation Tests
 *
 * This configuration is specifically for build validation tests that analyze
 * the production build output (dist/ directory) for circular dependency issues.
 *
 * Unlike the main playwright.config.ts which starts a dev server, this config:
 * - Uses vite preview to serve the production build
 * - Runs on port 4173 (standard Vite preview port)
 * - Only runs on Chromium for consistent results
 * - Skips in CI if reuseExistingServer is enabled
 *
 * Usage:
 *   npm run build
 *   npx playwright test --config playwright.config.build-validation.ts
 */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: /specs\/build-validation\.spec\.ts$/,

  // Run tests in sequence (build validation doesn't need parallelism)
  fullyParallel: false,
  workers: 1,

  // No retries needed for build validation (deterministic)
  retries: 0,

  // Fail on test.only
  forbidOnly: !!process.env.CI,

  // Reporter
  reporter: process.env.CI
    ? [
        ['github'],
        ['html', { outputFolder: 'playwright-report-build' }],
      ]
    : [['list'], ['html', { outputFolder: 'playwright-report-build', open: 'never' }]],

  // Output directory
  outputDir: './test-results-build',

  // Timeouts
  timeout: 30000,
  expect: {
    timeout: 5000,
  },

  // Shared settings
  use: {
    baseURL: 'http://localhost:4173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    navigationTimeout: 15000,
    actionTimeout: 5000,
  },

  // Only Chromium for build validation (consistent environment)
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          args: ['--disable-gpu', '--disable-dev-shm-usage'],
        },
      },
    },
  ],

  // Preview server serves the production build from dist/
  webServer: {
    command: 'npm run preview',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
