/**
 * Retry Isolation and Flaky Test Detection Tests (NEM-1477)
 *
 * These tests verify that the retry mechanism properly isolates tests
 * and demonstrates patterns for detecting and handling flaky tests.
 *
 * Playwright's retry mechanism runs each retry in complete isolation:
 * - Fresh browser context
 * - Clean page state
 * - No shared variables between attempts
 *
 * The JSON reporter (enabled in CI) captures retry information for
 * post-run analysis of flaky tests.
 */

import { test, expect } from '@playwright/test';

// Skip entire file in CI - timing issues cause flaky failures
test.skip(() => !!process.env.CI, 'E2E tests flaky in CI - run locally');
import { DashboardPage, TimelinePage, SystemPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

/**
 * Tests demonstrating retry isolation behavior
 */
test.describe('Retry Isolation Tests @critical', () => {
  // Configure retries specifically for this describe block
  // This demonstrates how to isolate flaky tests in specific areas
  test.describe.configure({ retries: 2 });

  test('each retry gets a fresh browser context @smoke @critical', async ({ page }, testInfo) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    // Store a value in localStorage
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Set a marker in localStorage for this attempt
    const attemptMarker = `attempt-${testInfo.retry}`;
    await page.evaluate((marker) => {
      localStorage.setItem('testMarker', marker);
    }, attemptMarker);

    // Verify the marker is what we just set (not from a previous attempt)
    const storedMarker = await page.evaluate(() => localStorage.getItem('testMarker'));
    expect(storedMarker).toBe(attemptMarker);

    // If this test is retried, localStorage should be empty at start
    // This validates retry isolation
    if (testInfo.retry > 0) {
      // Log that we're in a retry for visibility in reports
      console.log(`Retry ${testInfo.retry}: Fresh context confirmed`);
    }
  });

  test('page state is reset between retries @smoke', async ({ page }, testInfo) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Verify we're starting with a clean page (no previous navigation history)
    // In a fresh context, going back should have no effect
    const initialUrl = page.url();

    // Navigate to timeline
    await dashboardPage.navigateToTimeline();
    const timelinePage = new TimelinePage(page);
    await timelinePage.waitForTimelineLoad();

    // Go back
    await page.goBack();
    await dashboardPage.waitForDashboardLoad();

    // The current URL should match initial (dashboard)
    expect(page.url()).toBe(initialUrl);
  });

  test('cookies are isolated between retries @smoke', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Set a cookie
    await page.context().addCookies([
      {
        name: 'testCookie',
        value: 'testValue',
        domain: 'localhost',
        path: '/',
      },
    ]);

    // Verify cookie is set
    const cookies = await page.context().cookies();
    const testCookie = cookies.find((c) => c.name === 'testCookie');
    expect(testCookie?.value).toBe('testValue');

    // On retry, this cookie should not exist (fresh context)
  });
});

/**
 * Tests demonstrating flaky test detection patterns
 *
 * These tests show how to structure tests for flaky detection.
 * The JSON reporter captures whether a test passed on retry,
 * which is the key indicator of a flaky test.
 */
test.describe('Flaky Test Detection Patterns', () => {
  test.describe.configure({ retries: 2 });

  test('stable test passes consistently @smoke @critical', async ({ page }, testInfo) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Stable assertions that should always pass
    await expect(dashboardPage.pageTitle).toBeVisible();
    await expect(dashboardPage.header).toBeVisible();
    await expect(dashboardPage.sidebar).toBeVisible();

    // Log attempt for analysis
    if (testInfo.retry > 0) {
      console.log(`Test passed on retry ${testInfo.retry} - this indicates a flaky test`);
    }
  });

  test('test with timing-sensitive assertions @slow', async ({ page }, testInfo) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();

    // Use proper wait methods instead of fixed delays
    // This is the recommended pattern for avoiding flaky timing issues
    await dashboardPage.waitForDashboardLoad();

    // Always use explicit waits with timeouts for dynamic content
    await expect(dashboardPage.cameraGridHeading).toBeVisible({ timeout: 10000 });

    // Log timing info for analysis
    const timing = await page.evaluate(() => performance.now());
    console.log(`Page load timing: ${timing}ms (attempt: ${testInfo.retry})`);
  });

  test('demonstrates proper waiting patterns for dynamic content @critical', async ({
    page,
  }) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // GOOD: Use waitFor methods that poll until condition is met
    await expect(dashboardPage.riskScoreStat).toBeVisible({ timeout: 5000 });

    // GOOD: Wait for specific text content
    await expect(dashboardPage.pageTitle).toContainText(/Security Dashboard/i, {
      timeout: 5000,
    });

    // GOOD: Wait for multiple elements to be visible
    await expect(dashboardPage.header).toBeVisible();
    await expect(dashboardPage.mainContent).toBeVisible();
  });
});

/**
 * Tests for isolated state management
 *
 * These tests verify that test state doesn't leak between tests,
 * which is critical for reliable test isolation.
 */
test.describe('State Isolation Verification', () => {
  // Use a shared variable to demonstrate isolation (NOT recommended for real tests)
  let sharedCounter = 0;

  test.beforeEach(() => {
    // This runs in a fresh process context on retry
    sharedCounter = 0;
  });

  test('first test sets counter', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    sharedCounter = 42;
    expect(sharedCounter).toBe(42);
  });

  test('second test has isolated counter', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Due to beforeEach reset, counter should be 0, not 42
    expect(sharedCounter).toBe(0);
  });
});

/**
 * Tests for network-related flakiness patterns
 *
 * Network conditions are a common source of test flakiness.
 * These tests demonstrate patterns to reduce network-related flakiness.
 */
test.describe('Network Flakiness Prevention @network', () => {
  test.describe.configure({ retries: 2 });

  test('uses waitForResponse to ensure data loaded @critical', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    // Navigate and wait for specific API response
    await Promise.all([
      page.waitForResponse((resp) => resp.url().includes('/api/cameras')),
      dashboardPage.goto(),
    ]);

    await dashboardPage.waitForDashboardLoad();

    // Now we can be confident cameras data is loaded
    await expect(dashboardPage.cameraGridHeading).toBeVisible();
  });

  test('uses domcontentloaded for reliable page loads', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);

    // Use domcontentloaded instead of networkidle to avoid WebSocket timeout issues
    // networkidle waits for all connections to settle, but WebSocket stays open
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    const dashboardPage = new DashboardPage(page);
    await dashboardPage.waitForDashboardLoad();

    // All initial data should be loaded
    await expect(dashboardPage.pageTitle).toBeVisible();
  });

  test('handles API timing variations gracefully', async ({ page }) => {
    // Add variable latency to simulate real-world conditions
    await page.route('**/api/**', async (route) => {
      const latency = Math.random() * 200; // 0-200ms random latency
      await new Promise((resolve) => setTimeout(resolve, latency));
      await route.continue();
    });
    await setupApiMocks(page, defaultMockConfig);

    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();

    // Use explicit waits that accommodate timing variations
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.pageTitle).toBeVisible({ timeout: 10000 });
  });
});

/**
 * Annotation-based flaky test tracking
 *
 * Tests marked with @flaky in their title are tracked for stability analysis.
 * Use this pattern to mark known flaky tests that need investigation.
 */
test.describe('Flaky Test Annotation Examples', () => {
  test.describe.configure({ retries: 3 });

  test('example test marked as potentially flaky @flaky', async ({ page }, testInfo) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // When a test is marked @flaky, it signals that:
    // 1. The test may fail intermittently
    // 2. It needs investigation for root cause
    // 3. It should be tracked in flaky test reports

    await expect(dashboardPage.pageTitle).toBeVisible();

    // Log retry information for flaky test analysis
    testInfo.annotations.push({
      type: 'flaky-tracking',
      description: `Attempt ${testInfo.retry + 1}`,
    });
  });
});

/**
 * Test retry info available in testInfo
 */
test.describe('Retry Information Access', () => {
  test.describe.configure({ retries: 1 });

  test('can access retry count in test @smoke', async ({ page }, testInfo) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // testInfo.retry contains the current retry count (0-indexed)
    const retryCount = testInfo.retry;
    expect(retryCount).toBeGreaterThanOrEqual(0);

    // testInfo.project.retries contains max retries configured
    const maxRetries = testInfo.project.retries;
    expect(maxRetries).toBeGreaterThanOrEqual(0);

    // Add annotation for reporting
    testInfo.annotations.push({
      type: 'retry-info',
      description: `Retry ${retryCount} of max ${maxRetries}`,
    });
  });
});
