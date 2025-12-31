/**
 * Dashboard Tests for Home Security Dashboard
 *
 * Comprehensive tests for the main dashboard page including:
 * - Stats display
 * - Risk gauge functionality
 * - Camera grid interactions
 * - Activity feed behavior
 * - Loading and error states
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
import { mockGPUStats, mockSystemStats, mockEventStats } from '../fixtures';

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

  test('risk gauge section is visible', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.riskGaugeHeading).toBeVisible();
  });

  test('risk gauge shows current risk level heading', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.riskGaugeHeading).toHaveText(/Current Risk Level/i);
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

test.describe('Dashboard GPU Stats', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('GPU stats section shows utilization', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.gpuUtilization).toBeVisible({ timeout: 10000 });
  });

  test('GPU stats section shows memory', async ({ page }) => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(page.getByText(/Memory/i).first()).toBeVisible({ timeout: 10000 });
  });

  test('GPU stats section shows temperature', async ({ page }) => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(page.getByText(/Temperature/i).first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Dashboard Activity Feed', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('activity feed section is visible', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.activityFeedHeading).toBeVisible();
  });

  test('activity feed heading shows Live Activity', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.activityFeedHeading).toHaveText(/Live Activity/i);
  });
});

test.describe('Dashboard Empty State', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('shows no activity message when no events', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    const hasNoActivity = await dashboardPage.hasNoActivityMessage();
    expect(hasNoActivity).toBe(true);
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

  test('error state displays error elements', async ({ page }) => {
    await dashboardPage.goto();
    // Wait for either error state or page to render
    await page.waitForTimeout(3000);
    // Check that some error indication is visible
    const errorVisible = await dashboardPage.errorHeading.isVisible().catch(() => false);
    const reloadVisible = await dashboardPage.reloadButton.isVisible().catch(() => false);
    // At least one error indicator should be visible with error config
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
  test('page title contains Home Security', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await expect(page).toHaveTitle(/Home Security/i);
  });
});
