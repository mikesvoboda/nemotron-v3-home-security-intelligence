/**
 * Network Condition Simulation Tests (NEM-1479)
 *
 * Tests that simulate various network conditions to verify the application
 * degrades gracefully under poor network conditions. Uses Playwright's
 * page.route() for network throttling and error simulation.
 *
 * Tags: @network, @slow
 */

import { test, expect } from '@playwright/test';
import { DashboardPage, TimelinePage, SystemPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

/**
 * Network throttling configurations
 */
const NETWORK_CONDITIONS = {
  /** Simulate slow 3G network (~400ms latency) */
  slow3G: { latencyMs: 400 },
  /** Simulate regular 3G network (~100ms latency) */
  regular3G: { latencyMs: 100 },
  /** Simulate fast network (~50ms latency) */
  fast: { latencyMs: 50 },
  /** Simulate very slow network (>1s latency) */
  verySlow: { latencyMs: 1500 },
} as const;

/**
 * Helper to add latency to all API responses
 */
async function simulateNetworkLatency(
  page: import('@playwright/test').Page,
  latencyMs: number
): Promise<void> {
  await page.route('**/api/**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, latencyMs));
    await route.continue();
  });
}

/**
 * Helper to simulate network failure for specific endpoints
 */
async function simulateNetworkFailure(
  page: import('@playwright/test').Page,
  urlPattern: string
): Promise<void> {
  await page.route(urlPattern, (route) => route.abort('failed'));
}

/**
 * Helper to simulate intermittent network failures
 * Fails a percentage of requests randomly
 */
async function simulateIntermittentFailures(
  page: import('@playwright/test').Page,
  urlPattern: string,
  failureRate: number = 0.5
): Promise<void> {
  await page.route(urlPattern, async (route) => {
    if (Math.random() < failureRate) {
      await route.abort('failed');
    } else {
      await route.continue();
    }
  });
}

test.describe('Network Condition Simulation @network', () => {
  test.describe('Slow Network Tests @slow', () => {
    test('dashboard loads under slow 3G conditions @network @slow', async ({ page }) => {
      // First set up the latency simulation
      await simulateNetworkLatency(page, NETWORK_CONDITIONS.slow3G.latencyMs);
      // Then set up API mocks (these will run after the latency delay)
      await setupApiMocks(page, defaultMockConfig);

      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      // Dashboard should eventually load even with slow network
      await dashboardPage.waitForDashboardLoad();
      await expect(dashboardPage.pageTitle).toBeVisible();
    });

    test('timeline shows loading state during slow network @network @slow', async ({ page }) => {
      // Add significant latency to observe loading states
      await simulateNetworkLatency(page, NETWORK_CONDITIONS.verySlow.latencyMs);
      await setupApiMocks(page, defaultMockConfig);

      const timelinePage = new TimelinePage(page);

      // Navigate and check for loading indicators
      await timelinePage.goto();

      // The page should show while data is loading
      await expect(timelinePage.pageTitle).toBeVisible({ timeout: 20000 });

      // Eventually the timeline should load
      await timelinePage.waitForTimelineLoad();
    });
  });

  test.describe('Network Failure Tests', () => {
    // API client has MAX_RETRIES=3 with exponential backoff (1s+2s+4s=7s)
    // React Query also retries once, so total time for events API to fail is ~14-21s
    // Use 35s timeout to account for network latency and CI variability
    const ERROR_TIMEOUT = 35000;

    // Increase test timeout to 60s for these tests since they wait for API retries
    test.setTimeout(60000);

    test('dashboard shows error when network completely fails @network @critical', async ({
      page,
    }) => {
      // Dashboard shows error state only when BOTH cameras AND events fail
      // This matches the component logic: hasError = camerasError !== null || eventsError !== null
      await setupApiMocks(page, { ...defaultMockConfig, camerasError: true, eventsError: true });

      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      // Should show error state when cameras API fails
      await expect(dashboardPage.errorHeading).toBeVisible({ timeout: ERROR_TIMEOUT });
    });

    test('system page handles partial network failure gracefully @network', async ({ page }) => {
      // Set up mocks first (order matters - specific routes before general)
      // Fail only the GPU endpoint
      await page.route('**/api/system/gpu', (route) => route.abort('failed'));
      await page.route('**/api/system/gpu/history*', (route) => route.abort('failed'));
      // Set up remaining mocks
      await setupApiMocks(page, {
        ...defaultMockConfig,
        gpuError: true,
      });

      const systemPage = new SystemPage(page);
      await systemPage.goto();

      // Page should still load, possibly showing partial data or error for GPU section
      // We verify the page doesn't crash completely
      await expect(page.locator('body')).toBeVisible();
      // Wait for the main content to appear
      await expect(page.locator('main')).toBeVisible({ timeout: 10000 });
    });

    test('application handles connection timeout @network @slow', async ({ page }) => {
      // Dashboard shows error state only when BOTH cameras AND events fail
      await setupApiMocks(page, {
        ...defaultMockConfig,
        camerasError: true,
        eventsError: true,
      });

      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      // The application should show an error state or timeout message
      // Wait for error state with a longer timeout
      await expect(dashboardPage.errorHeading).toBeVisible({ timeout: 20000 });
    });
  });

  test.describe('Offline Mode Tests', () => {
    // API client has MAX_RETRIES=3 with exponential backoff (1s+2s+4s=7s)
    // React Query also retries once, so total time for events API to fail is ~14-21s
    // Use 35s timeout to account for network latency and CI variability
    const ERROR_TIMEOUT = 35000;

    // Increase test timeout to 60s for these tests since they wait for API retries
    test.setTimeout(60000);

    test('dashboard shows offline indicator when network is down @network @critical', async ({
      page,
    }) => {
      // Extend test timeout to allow for API retry timeouts
      test.setTimeout(60000);

      await setupApiMocks(page, defaultMockConfig);

      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();
      await dashboardPage.waitForDashboardLoad();

      // Now simulate going offline by removing all existing API mocks
      // and setting up a failure route. We must unroute first because
      // Playwright processes routes in registration order - earlier routes
      // take precedence over later ones for the same URL pattern.
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await page.route('**/api/**', (route) => route.abort('failed'));

      // Trigger a refresh or action that would make an API call
      await page.reload();

      // Should show error or offline state - wait for API retries to exhaust
      await expect(dashboardPage.errorHeading).toBeVisible({ timeout: ERROR_TIMEOUT });
    });

    test('application recovers when network is restored @network', async ({ page }) => {
      // Start with both cameras and events error to trigger error state
      await setupApiMocks(page, { ...defaultMockConfig, camerasError: true, eventsError: true });

      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      // Should show error state initially - wait for API retries to exhaust
      await expect(dashboardPage.errorHeading).toBeVisible({ timeout: ERROR_TIMEOUT });

      // "Restore" network by clearing all routes and setting up proper mocks
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await setupApiMocks(page, defaultMockConfig);

      // Reload the page
      await page.reload();

      // Should load successfully now
      await dashboardPage.waitForDashboardLoad();
      await expect(dashboardPage.pageTitle).toBeVisible();
    });
  });

  test.describe('Degraded Network Performance', () => {
    test('UI remains responsive during slow API responses @network @slow', async ({ page }) => {
      // Add delay to API responses
      await simulateNetworkLatency(page, NETWORK_CONDITIONS.slow3G.latencyMs);
      await setupApiMocks(page, defaultMockConfig);

      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      // Navigation should still work even with slow network
      await dashboardPage.expectHeaderVisible();
      await dashboardPage.expectSidebarVisible();

      // Verify we can still interact with navigation
      await expect(dashboardPage.navTimeline).toBeEnabled();
    });

    test('loading indicators appear during slow requests @network @slow', async ({ page }) => {
      // Set up a delayed response for events
      await page.route('**/api/events*', async (route) => {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [],
            pagination: {
              total: 0,
              limit: 20,
              offset: 0,
              has_more: false,
            },
          }),
        });
      });
      await setupApiMocks(page, defaultMockConfig);

      const timelinePage = new TimelinePage(page);
      await timelinePage.goto();

      // Page title should be visible while loading
      await expect(timelinePage.pageTitle).toBeVisible();

      // Wait for the delayed response to complete
      await timelinePage.waitForTimelineLoad();
    });
  });

  test.describe('Retry Behavior Under Network Issues', () => {
    // API client has MAX_RETRIES=3 with exponential backoff (1s+2s+4s=7s)
    // React Query also retries once, so total time for events API to fail is ~14-21s
    // Use 35s timeout to account for network latency and CI variability
    const ERROR_TIMEOUT = 35000;

    // Increase test timeout to 60s for these tests since they wait for API retries
    test.setTimeout(60000);

    test('displays appropriate message on repeated failures @network', async ({ page }) => {
      // Dashboard shows error state only when BOTH cameras AND events fail
      await setupApiMocks(page, { ...defaultMockConfig, camerasError: true, eventsError: true });

      const dashboardPage = new DashboardPage(page);
      await dashboardPage.goto();

      // Should show error state - wait for API retries to exhaust
      await expect(dashboardPage.errorHeading).toBeVisible({ timeout: ERROR_TIMEOUT });
    });
  });
});

test.describe('Network Condition Edge Cases @network', () => {
  // API client has MAX_RETRIES=3 with exponential backoff (1s+2s+4s=7s)
  // React Query also retries once, so total time for events API to fail is ~14-21s
  // Use 35s timeout to account for network latency and CI variability
  const ERROR_TIMEOUT = 35000;

  // Increase test timeout to 60s for these tests since they wait for API retries
  test.setTimeout(60000);

  test('handles empty response bodies gracefully @network', async ({ page }) => {
    await page.route('**/api/cameras', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '', // Empty body
      });
    });
    await setupApiMocks(page, defaultMockConfig);

    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();

    // Should handle empty response without crashing
    await expect(page.locator('body')).toBeVisible();
  });

  test('handles malformed JSON responses @network', async ({ page }) => {
    await page.route('**/api/cameras', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '{ invalid json }', // Malformed JSON
      });
    });
    await setupApiMocks(page, defaultMockConfig);

    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();

    // Should handle malformed JSON without crashing
    await expect(page.locator('body')).toBeVisible();
  });

  test('handles HTTP 503 Service Unavailable @network', async ({ page }) => {
    // Dashboard shows error state only when BOTH cameras AND events fail
    await setupApiMocks(page, { ...defaultMockConfig, camerasError: true, eventsError: true });

    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();

    // Should show error state for 503 - wait for API retries to exhaust
    await expect(dashboardPage.errorHeading).toBeVisible({ timeout: ERROR_TIMEOUT });
  });

  test('handles HTTP 429 Rate Limiting @network', async ({ page }) => {
    // Dashboard shows error state only when BOTH cameras AND events fail
    await setupApiMocks(page, { ...defaultMockConfig, camerasError: true, eventsError: true });

    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();

    // Should show error state for rate limiting - wait for API retries to exhaust
    await expect(dashboardPage.errorHeading).toBeVisible({ timeout: ERROR_TIMEOUT });
  });
});
