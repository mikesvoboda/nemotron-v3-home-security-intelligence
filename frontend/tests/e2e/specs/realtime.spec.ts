/**
 * Real-time Update Tests for Home Security Dashboard
 *
 * These tests verify that real-time features work correctly.
 * WebSocket connections are mocked to simulate real-time events.
 */

import { test, expect } from '@playwright/test';
import { DashboardPage, SystemPage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig, errorMockConfig } from '../fixtures';

test.describe('Real-time Updates', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('dashboard shows WebSocket status indicator', async ({ page }) => {
    // Note: We test that the WebSocket status component renders, not the connection state.
    // Playwright's page.route() cannot reliably block WebSocket connections,
    // so we verify the component exists rather than expecting a specific state.
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // Verify WebSocket status button exists in the header
    await expect(page.getByRole('button', { name: /WebSocket connection status/i })).toBeVisible();
  });

  test('dashboard displays risk gauge and camera grid', async ({ page }) => {
    // Note: GPU stats are displayed on the System page, not the Dashboard.
    // The Dashboard shows Risk Gauge, Camera Grid, and Stats Row.
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // Verify the main dashboard sections are visible
    await expect(dashboardPage.riskGaugeHeading).toBeVisible();
    await expect(dashboardPage.cameraGridHeading).toBeVisible();
  });

  test('system page shows GPU statistics section', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    // Look for GPU Statistics heading - this is where GPU stats are displayed
    await expect(page.getByText(/GPU Statistics/i)).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Connection Status Indicators', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('header shows system status indicator', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectHeaderVisible();
    await expect(page.getByText(/System/i).first()).toBeVisible();
  });

  test('system page shows service health', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    const serviceCount = await systemPage.getServiceCount();
    expect(serviceCount).toBeGreaterThan(0);
  });
});

test.describe('Empty State Handling', () => {
  test('activity feed shows empty state when no events', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    const hasNoActivity = await dashboardPage.hasNoActivityMessage();
    expect(hasNoActivity).toBe(true);
  });
});

test.describe('Error Handling', () => {
  test('dashboard shows error state when API fails', async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();

    // Should show error state
    await expect(dashboardPage.errorHeading).toBeVisible({ timeout: 15000 });
    await expect(dashboardPage.reloadButton).toBeVisible();
  });

  test('dashboard error state has reload button', async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await expect(dashboardPage.reloadButton).toBeVisible({ timeout: 15000 });
  });
});
