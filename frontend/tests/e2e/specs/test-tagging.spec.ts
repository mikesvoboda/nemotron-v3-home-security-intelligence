/**
 * Test Tagging and Selective Execution (NEM-1478)
 *
 * This file demonstrates the test tagging system for selective test execution.
 * Tests are tagged using annotations in test titles:
 *
 * Tags:
 * - @smoke: Critical path tests that should run on every commit
 * - @critical: High-priority tests for core functionality
 * - @slow: Tests that take longer to execute
 * - @flaky: Tests known to be flaky (tracked for stability improvements)
 * - @network: Tests that simulate network conditions
 *
 * Usage:
 *   npx playwright test --grep @smoke           # Run only smoke tests
 *   npx playwright test --grep @critical        # Run only critical tests
 *   npx playwright test --grep-invert @slow     # Exclude slow tests
 *   npx playwright test --grep "@smoke|@critical" # Run smoke OR critical
 *   npx playwright test --project=smoke         # Use smoke project
 *   npx playwright test --project=critical      # Use critical project
 */

import { test, expect } from '@playwright/test';
import { DashboardPage, TimelinePage, AlertsPage, SystemPage, SettingsPage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig } from '../fixtures';

/**
 * Smoke Tests (@smoke)
 *
 * These are the most critical tests that verify the application's
 * basic functionality. They should:
 * - Run on every commit
 * - Complete quickly (<30 seconds total)
 * - Test critical user journeys
 */
test.describe('Smoke Tests @smoke', () => {
  test('application loads successfully @smoke @critical', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Verify core elements are visible
    await expect(dashboardPage.pageTitle).toBeVisible();
    await expect(dashboardPage.header).toBeVisible();
    await expect(dashboardPage.sidebar).toBeVisible();
  });

  test('navigation works between pages @smoke', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Navigate to Timeline
    await dashboardPage.navigateToTimeline();
    const timelinePage = new TimelinePage(page);
    await timelinePage.waitForTimelineLoad();
    await expect(timelinePage.pageTitle).toBeVisible();

    // Navigate back to Dashboard
    await timelinePage.navigateToDashboard();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.pageTitle).toBeVisible();
  });

  test('API data is displayed correctly @smoke', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Verify data from mock API is displayed
    await expect(dashboardPage.cameraGridHeading).toBeVisible();
    const cameraCount = await dashboardPage.getCameraCount();
    expect(cameraCount).toBeGreaterThan(0);
  });
});

/**
 * Critical Tests (@critical)
 *
 * High-priority tests that verify core functionality.
 * These should run on every PR merge.
 */
test.describe('Critical Tests @critical', () => {
  // API client has MAX_RETRIES=3 with exponential backoff (1s+2s+4s=7s)
  // React Query also retries once, so total time for events API to fail is ~14-21s
  // Use 35s timeout to account for network latency and CI variability
  const ERROR_TIMEOUT = 35000;

  // Increase test timeout to 60s for error state tests that wait for API retries
  test.setTimeout(60000);

  test('dashboard displays all key sections @critical', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Verify all dashboard sections
    await dashboardPage.expectAllSectionsVisible();
  });

  test('timeline displays events correctly @critical', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const timelinePage = new TimelinePage(page);

    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    const eventCount = await timelinePage.getEventCount();
    expect(eventCount).toBeGreaterThan(0);
  });

  test('system page shows health status @critical', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const systemPage = new SystemPage(page);

    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    await expect(systemPage.pageTitle).toBeVisible();
    const serviceCount = await systemPage.getServiceCount();
    expect(serviceCount).toBeGreaterThan(0);
  });

  test('error states are displayed correctly @critical', async ({ page }) => {
    await setupApiMocks(page, {
      ...defaultMockConfig,
      camerasError: true,
      eventsError: true,
    });
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();

    // Should show error state - wait for API retries to exhaust
    await expect(dashboardPage.errorHeading).toBeVisible({ timeout: ERROR_TIMEOUT });
  });
});

/**
 * Slow Tests (@slow)
 *
 * Tests that take longer to execute due to:
 * - Complex multi-step workflows
 * - Network simulation
 * - Large data handling
 *
 * These can be excluded for quick feedback:
 *   npx playwright test --grep-invert @slow
 */
test.describe('Slow Tests @slow', () => {
  test('full navigation workflow @slow', async ({ page, browserName }) => {
    // Skip on Firefox/WebKit due to sequential navigation timeout issues (NEM-1486)
    // These browsers have slower page loads and multiple sequential navigations
    // exceed even extended timeouts in CI environment
    test.skip(browserName === 'firefox' || browserName === 'webkit',
      'Sequential navigation through 8+ pages exceeds navigation timeouts');

    // This test navigates through many pages, so needs a longer timeout
    test.setTimeout(60000);

    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    // Navigate through all main pages
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Timeline
    await dashboardPage.navigateToTimeline();
    const timelinePage = new TimelinePage(page);
    await timelinePage.waitForTimelineLoad();

    // Alerts
    await timelinePage.navigateToAlerts();
    const alertsPage = new AlertsPage(page);
    await alertsPage.waitForAlertsLoad();

    // System - Firefox/WebKit may need extra time for navigation
    await alertsPage.navigateToSystem();
    const systemPage = new SystemPage(page);
    await systemPage.waitForSystemLoad();

    // Settings
    await systemPage.navigateToSettings();
    const settingsPage = new SettingsPage(page);
    await settingsPage.waitForSettingsLoad();

    // Back to Dashboard
    await settingsPage.navigateToDashboard();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.pageTitle).toBeVisible();
  });

  test('handles large dataset @slow', async ({ page }) => {
    // Create a large events dataset
    const manyEvents = Array.from({ length: 100 }, (_, i) => ({
      id: i + 1,
      event_type: 'detection',
      timestamp: new Date(Date.now() - i * 60000).toISOString(),
      camera_id: `cam-${(i % 4) + 1}`,
      camera_name: ['Front Door', 'Back Yard', 'Garage', 'Driveway'][i % 4],
      risk_level: ['low', 'medium', 'high', 'critical'][i % 4] as
        | 'low'
        | 'medium'
        | 'high'
        | 'critical',
      risk_score: (i * 10) % 100,
      summary: `Event ${i + 1} summary`,
      thumbnail_url: null,
      detections: [],
      processed: true,
    }));

    await setupApiMocks(page, {
      ...defaultMockConfig,
      events: manyEvents,
    });

    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Should handle large dataset without crashing
    const eventCount = await timelinePage.getEventCount();
    expect(eventCount).toBeGreaterThan(0);
  });
});

/**
 * Tests with Multiple Tags
 *
 * Tests can have multiple tags for fine-grained filtering.
 */
test.describe('Multi-Tagged Tests', () => {
  test('critical smoke test for dashboard @smoke @critical', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    await expect(dashboardPage.pageTitle).toBeVisible();
    await expect(dashboardPage.header).toBeVisible();
  });

  test('slow network test @slow @network', async ({ page }) => {
    // Add network latency
    await page.route('**/api/**', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 500));
      await route.continue();
    });
    await setupApiMocks(page, defaultMockConfig);

    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    await expect(dashboardPage.pageTitle).toBeVisible({ timeout: 15000 });
  });

  test('critical empty state test @critical @empty', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const timelinePage = new TimelinePage(page);

    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    const hasNoEvents = await timelinePage.hasNoEventsMessage();
    expect(hasNoEvents).toBe(true);
  });
});

/**
 * Tag Usage Documentation Tests
 *
 * These tests document and verify the tagging system works correctly.
 */
test.describe('Tag Usage Verification', () => {
  test('smoke tag is recognized @smoke', async ({ page }, testInfo) => {
    await setupApiMocks(page, defaultMockConfig);

    // This test will be included when running:
    // npx playwright test --grep @smoke
    expect(testInfo.title).toContain('@smoke');
  });

  test('critical tag is recognized @critical', async ({ page }, testInfo) => {
    await setupApiMocks(page, defaultMockConfig);

    // This test will be included when running:
    // npx playwright test --grep @critical
    expect(testInfo.title).toContain('@critical');
  });

  test('slow tag is recognized @slow', async ({ page }, testInfo) => {
    await setupApiMocks(page, defaultMockConfig);

    // This test will be excluded when running:
    // npx playwright test --grep-invert @slow
    expect(testInfo.title).toContain('@slow');
  });

  test('flaky tag is recognized @flaky', async ({ page }, testInfo) => {
    await setupApiMocks(page, defaultMockConfig);

    // Tests marked @flaky are tracked for stability analysis
    expect(testInfo.title).toContain('@flaky');

    // Add annotation for flaky tracking
    testInfo.annotations.push({
      type: 'flaky-tracking',
      description: 'Test is marked as potentially flaky',
    });
  });

  test('network tag is recognized @network', async ({ page }, testInfo) => {
    await setupApiMocks(page, defaultMockConfig);

    // This test will be included when running:
    // npx playwright test --grep @network
    expect(testInfo.title).toContain('@network');
  });
});

/**
 * Project-Based Selective Execution Tests
 *
 * These tests verify the project-based selection works.
 * Run with: npx playwright test --project=smoke
 */
test.describe('Project Selection Verification @smoke', () => {
  test('runs in smoke project @smoke', async ({ page }, testInfo) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Log project info
    console.log(`Running in project: ${testInfo.project.name}`);

    await expect(dashboardPage.pageTitle).toBeVisible();
  });
});
