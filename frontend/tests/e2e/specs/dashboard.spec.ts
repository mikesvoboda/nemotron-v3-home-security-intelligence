/**
 * Dashboard Tests for Home Security Dashboard
 *
 * Comprehensive tests for the main dashboard page including:
 * - Stats display
 * - Risk gauge functionality
 * - Camera grid interactions
 * - Activity feed behavior
 * - Loading and error states
 *
 * Test Structure:
 * ---------------
 * This file is organized into 9 describe blocks, each testing a specific
 * aspect of the dashboard. Each describe block has its own beforeEach hook
 * that sets up API mocks with the appropriate configuration:
 *
 * - defaultMockConfig: Standard dashboard with cameras, events, stats
 * - emptyMockConfig: Empty state testing (no events)
 * - errorMockConfig: API failure scenarios
 * - highAlertMockConfig: High risk/alert state testing
 *
 * Performance Notes:
 * - Timeouts are tuned for CI environments (5-8 seconds max)
 * - Uses waitForLoadState instead of fixed delays where possible
 * - Each describe block is independent and can run in parallel
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages';
import {
  setupApiMocks,
  defaultMockConfig,
  emptyMockConfig,
  errorMockConfig,
  highAlertMockConfig,
} from '../fixtures';
import { mockSystemStats, mockEventStats } from '../fixtures';

test.describe('Dashboard Stats Row', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('displays active cameras stat', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.activeCamerasStat).toBeVisible();
  });

  test('displays events today stat', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.eventsTodayStat).toBeVisible();
  });

  test('displays current risk stat', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.riskScoreStat).toBeVisible();
  });

  test('displays system status stat', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.systemStatusStat).toBeVisible();
  });
});

test.describe('Dashboard Risk Gauge', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('risk score card is visible', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.riskScoreStat).toBeVisible();
  });

  test('risk score card shows risk value', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // Risk score is displayed in the StatsRow risk card
    const riskScore = await dashboardPage.getRiskScoreText();
    expect(riskScore).not.toBeNull();
  });
});

test.describe('Dashboard Camera Grid', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('camera grid section is visible', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.cameraGridHeading).toBeVisible();
  });

  test('displays Front Door camera', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    const hasFrontDoor = await dashboardPage.hasCameraByName('Front Door');
    expect(hasFrontDoor).toBe(true);
  });

  test('displays Back Yard camera', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    const hasBackYard = await dashboardPage.hasCameraByName('Back Yard');
    expect(hasBackYard).toBe(true);
  });

  test('displays Garage camera', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    const hasGarage = await dashboardPage.hasCameraByName('Garage');
    expect(hasGarage).toBe(true);
  });

  test('displays Driveway camera', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    const hasDriveway = await dashboardPage.hasCameraByName('Driveway');
    expect(hasDriveway).toBe(true);
  });
});

// Note: Activity Feed was moved from Dashboard to Timeline page in the UI redesign.
// The Live Activity tests are now covered in timeline.spec.ts

test.describe('Dashboard Empty State', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('dashboard loads with empty event data', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // Verify dashboard loads without crashing when there are no events
    await expect(dashboardPage.riskScoreStat).toBeVisible();
  });
});

test.describe('Dashboard Error State', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('shows error heading when API fails', async () => {
    await dashboardPage.goto();
    await expect(dashboardPage.errorHeading).toBeVisible({ timeout: 15000 });
  });

  test('shows reload button when API fails', async () => {
    await dashboardPage.goto();
    await expect(dashboardPage.reloadButton).toBeVisible({ timeout: 15000 });
  });

  test('error state displays error elements', async () => {
    await dashboardPage.goto();
    // Wait for error state to appear - use waitFor which properly polls for element
    // The error state shows after API calls fail, which may take a few retries
    await Promise.race([
      dashboardPage.errorHeading.waitFor({ state: 'visible', timeout: 15000 }),
      dashboardPage.reloadButton.waitFor({ state: 'visible', timeout: 15000 }),
    ]).catch(() => {
      // Ignore errors - we check visibility below
    });
    // Now check if either is visible
    const errorVisible = await dashboardPage.errorHeading.isVisible().catch(() => false);
    const reloadVisible = await dashboardPage.reloadButton.isVisible().catch(() => false);
    expect(errorVisible || reloadVisible).toBe(true);
  });
});

test.describe('Dashboard High Alert State', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, highAlertMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('dashboard loads with high alert config', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
  });
});

test.describe('Dashboard Page Title', () => {
  test('page title contains Security Dashboard', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await expect(page).toHaveTitle(/Security Dashboard/i);
  });
});
