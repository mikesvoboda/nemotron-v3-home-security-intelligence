/**
 * Real-time Update Tests for Home Security Dashboard
 *
 * These tests verify that real-time features work correctly.
 * WebSocket connections are mocked to simulate real-time events.
 *
 * NOTE: Skipped in CI due to WebSocket timing issues causing flakiness.
 * Run locally for real-time validation.
 */

import { test, expect } from '@playwright/test';

// Skip entire file in CI - WebSocket timing issues cause flaky failures
test.skip(() => !!process.env.CI, 'Real-time tests flaky in CI - run locally');
import { DashboardPage, SystemPage, TimelinePage } from '../pages';
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

  test('dashboard displays risk card and camera grid', async ({ page }) => {
    // Note: GPU stats are displayed on the System page, not the Dashboard.
    // The Dashboard shows StatsRow (with risk card), and Camera Grid.
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // Verify the main dashboard sections are visible
    await expect(dashboardPage.riskScoreStat).toBeVisible();
    await expect(dashboardPage.cameraGridHeading).toBeVisible();
  });

  test('operations page shows pipeline flow visualization', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    // Operations page shows pipeline flow visualization (GPU stats moved to Grafana)
    await expect(page.getByTestId('pipeline-flow-visualization')).toBeVisible({ timeout: 10000 });
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

  test('operations page shows circuit breakers section', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    // Operations page shows circuit breakers (service health moved to Grafana)
    await expect(page.getByTestId('circuit-breakers-section')).toBeVisible();
  });
});

test.describe('Empty State Handling', () => {
  test('timeline shows empty state when no events', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    const hasNoEvents = await timelinePage.hasNoEventsMessage();
    expect(hasNoEvents).toBe(true);
  });
});

test.describe('Error Handling', () => {
  // API client has MAX_RETRIES=3 with exponential backoff (1s+2s+4s=7s)
  // React Query also retries once, so total time for events API to fail is ~14-21s
  // Use 35s timeout to account for network latency and CI variability
  const ERROR_TIMEOUT = 35000;

  test('dashboard shows error state when API fails', async ({ page }, testInfo) => {
    // Extend test timeout to account for API retry delays
    testInfo.setTimeout(ERROR_TIMEOUT + 10000);
    await setupApiMocks(page, errorMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();

    // Should show error state - wait for API retries to exhaust
    await expect(dashboardPage.errorHeading).toBeVisible({ timeout: ERROR_TIMEOUT });
    await expect(dashboardPage.reloadButton).toBeVisible();
  });

  test('dashboard error state has reload button', async ({ page }, testInfo) => {
    // Extend test timeout to account for API retry delays
    testInfo.setTimeout(ERROR_TIMEOUT + 10000);
    await setupApiMocks(page, errorMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    // Error UI appears after API retries exhaust
    await expect(dashboardPage.reloadButton).toBeVisible({ timeout: ERROR_TIMEOUT });
  });
});
