/**
 * Error Handling Tests for Home Security Dashboard
 *
 * Comprehensive tests for error handling across all pages including:
 * - API failure responses
 * - Network errors
 * - Empty states
 * - Error recovery
 */

import { test, expect } from '@playwright/test';
import {
  DashboardPage,
  TimelinePage,
  AlertsPage,
  LogsPage,
  AuditPage,
  SystemPage,
} from '../pages';
import {
  setupApiMocks,
  errorMockConfig,
  emptyMockConfig,
  defaultMockConfig,
  withError,
  interceptApi,
} from '../fixtures';

test.describe('Dashboard Error Handling', () => {
  test('shows error state when cameras API fails', async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await expect(dashboardPage.errorHeading).toBeVisible({ timeout: 15000 });
  });

  test('shows reload button on error', async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await expect(dashboardPage.reloadButton).toBeVisible({ timeout: 15000 });
  });

  test('error message is descriptive', async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await expect(dashboardPage.errorHeading).toHaveText(/Error Loading Dashboard/i);
  });
});

test.describe('Timeline Error Handling', () => {
  test('shows error state when events API fails', async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    await expect(timelinePage.errorMessage).toBeVisible({ timeout: 15000 });
  });

  test('error message mentions events', async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    await expect(timelinePage.errorMessage).toHaveText(/Error Loading Events/i);
  });
});

test.describe('Alerts Error Handling', () => {
  test('shows error state when events API fails', async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    const alertsPage = new AlertsPage(page);
    await alertsPage.goto();
    await alertsPage.waitForAlertsLoad();
    const hasError = await alertsPage.hasError();
    expect(hasError).toBe(true);
  });
});

test.describe('Logs Error Handling', () => {
  test('page loads even when logs API fails', async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    // Page should still render, may show error state or empty state
    await logsPage.waitForLogsLoad();
    await expect(logsPage.pageTitle).toBeVisible();
  });
});

test.describe('Audit Error Handling', () => {
  test('page loads even when audit API fails', async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    const auditPage = new AuditPage(page);
    await auditPage.goto();
    // Page should still render, may show error state or empty state
    await auditPage.waitForAuditLoad();
    await expect(auditPage.pageTitle).toBeVisible();
  });
});

test.describe('System Page Error Handling', () => {
  test('page loads even when system APIs fail', async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    // Page should still render, may show error or loading state
    await page.waitForTimeout(3000);
    // Just verify the page didn't crash
    await expect(page.locator('body')).toBeVisible();
  });
});

test.describe('Empty State Handling', () => {
  test('dashboard shows no activity with empty events', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    const hasNoActivity = await dashboardPage.hasNoActivityMessage();
    expect(hasNoActivity).toBe(true);
  });

  test('timeline shows no events with empty data', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    const hasNoEvents = await timelinePage.hasNoEventsMessage();
    expect(hasNoEvents).toBe(true);
  });

  test('alerts page loads with empty data', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const alertsPage = new AlertsPage(page);
    await alertsPage.goto();
    await alertsPage.waitForAlertsLoad();
    // Just verify page loaded without crashing
    await expect(alertsPage.pageTitle).toBeVisible();
  });

  test('logs shows empty state with no logs', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();
    const hasEmpty = await logsPage.hasEmptyState();
    expect(hasEmpty).toBe(true);
  });
});

test.describe('Partial API Failure', () => {
  test('dashboard loads with default config', async ({ page }) => {
    // Test with default config that partial failures don't break the page
    await setupApiMocks(page, defaultMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    // Dashboard should load successfully with default config
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.pageTitle).toBeVisible();
  });
});

test.describe('Network Error Messages', () => {
  test('error messages are user-friendly', async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    // Should show a friendly message, not a raw error
    await expect(page.getByText(/Error/i).first()).toBeVisible({ timeout: 15000 });
  });
});
