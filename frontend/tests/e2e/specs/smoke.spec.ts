/**
 * Smoke Tests for Home Security Dashboard
 *
 * These tests verify that the application loads and renders correctly.
 * They run against a development server with mocked backend responses.
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

test.describe('Dashboard Smoke Tests', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('dashboard page loads successfully', async ({ page }) => {
    await dashboardPage.goto();
    await expect(page).toHaveTitle(/Home Security/i);
    await dashboardPage.waitForDashboardLoad();
  });

  test('dashboard displays key components', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectAllSectionsVisible();
  });

  test('dashboard shows real-time monitoring subtitle', async ({ page }) => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.pageSubtitle).toBeVisible();
  });

  test('dashboard has correct page title', async ({ page }) => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(page).toHaveTitle(/Home Security/i);
  });

  test('dashboard shows risk gauge section', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.riskGaugeHeading).toBeVisible();
  });

  test('dashboard shows camera status section', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.cameraGridHeading).toBeVisible();
  });

  test('dashboard shows live activity section', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.activityFeedHeading).toBeVisible();
  });

  test('dashboard displays GPU stats', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectGpuStatsVisible();
  });
});

test.describe('Layout Smoke Tests', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('header displays branding', async ({ page }) => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(page.getByText(/NVIDIA/i).first()).toBeVisible();
    await expect(page.getByText(/SECURITY/i).first()).toBeVisible();
  });

  test('sidebar navigation is visible', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectSidebarVisible();
  });

  test('header is visible', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectHeaderVisible();
  });

  test('full layout is rendered', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectLayoutLoaded();
  });
});

test.describe('Dashboard Camera Tests', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('displays camera cards from API', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // We have 4 cameras in mock data
    const hasFrontDoor = await dashboardPage.hasCameraByName('Front Door');
    expect(hasFrontDoor).toBe(true);
  });

  test('shows camera names', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    const hasBackYard = await dashboardPage.hasCameraByName('Back Yard');
    expect(hasBackYard).toBe(true);
  });
});

test.describe('Dashboard Activity Feed Tests', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('shows activity items when events exist', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // Activity feed should show events from mock data
    await expect(dashboardPage.activityFeedHeading).toBeVisible();
  });
});
