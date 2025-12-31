/**
 * Navigation Tests for Home Security Dashboard
 *
 * These tests verify that navigation between pages works correctly.
 */

import { test, expect } from '@playwright/test';
import {
  DashboardPage,
  TimelinePage,
  AlertsPage,
  EntitiesPage,
  LogsPage,
  AuditPage,
  SystemPage,
  SettingsPage,
} from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

test.describe('Navigation Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('can navigate to dashboard from root', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
  });

  test('can navigate to timeline page', async ({ page }) => {
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('can navigate to alerts page', async ({ page }) => {
    const alertsPage = new AlertsPage(page);
    await alertsPage.goto();
    await alertsPage.waitForAlertsLoad();
  });

  test('can navigate to entities page', async ({ page }) => {
    const entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();
  });

  test('can navigate to logs page', async ({ page }) => {
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();
  });

  test('can navigate to audit page', async ({ page }) => {
    const auditPage = new AuditPage(page);
    await auditPage.goto();
    await auditPage.waitForAuditLoad();
  });

  test('can navigate to system page', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('can navigate to settings page', async ({ page }) => {
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();
  });

  test('URL reflects current page - dashboard', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/$/);
  });

  test('URL reflects current page - timeline', async ({ page }) => {
    await page.goto('/timeline');
    await expect(page).toHaveURL(/\/timeline$/);
  });

  test('URL reflects current page - alerts', async ({ page }) => {
    await page.goto('/alerts');
    await expect(page).toHaveURL(/\/alerts$/);
  });

  test('URL reflects current page - entities', async ({ page }) => {
    await page.goto('/entities');
    await expect(page).toHaveURL(/\/entities$/);
  });

  test('URL reflects current page - logs', async ({ page }) => {
    await page.goto('/logs');
    await expect(page).toHaveURL(/\/logs$/);
  });

  test('URL reflects current page - audit', async ({ page }) => {
    await page.goto('/audit');
    await expect(page).toHaveURL(/\/audit$/);
  });

  test('URL reflects current page - system', async ({ page }) => {
    await page.goto('/system');
    await expect(page).toHaveURL(/\/system$/);
  });

  test('URL reflects current page - settings', async ({ page }) => {
    await page.goto('/settings');
    await expect(page).toHaveURL(/\/settings$/);
  });

  test('page transitions preserve layout', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    const settingsPage = new SettingsPage(page);

    // Go to dashboard first
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectHeaderVisible();

    // Navigate to settings
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();
    await settingsPage.expectHeaderVisible();
  });

  test('sidebar persists across page transitions', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    const timelinePage = new TimelinePage(page);

    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectSidebarVisible();

    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    await timelinePage.expectSidebarVisible();
  });
});

test.describe('All Routes Smoke Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('all 8 routes load without error', async ({ page }) => {
    const routes = [
      { path: '/', title: /Security Dashboard/i },
      { path: '/timeline', title: /Event Timeline/i },
      { path: '/alerts', title: /Alerts/i },
      { path: '/entities', title: /Entities/i },
      { path: '/logs', title: /System Logs/i },
      { path: '/audit', title: /Audit Log/i },
      { path: '/system', title: /System Monitoring/i },
      { path: '/settings', title: /Settings/i },
    ];

    for (const route of routes) {
      await page.goto(route.path);
      await expect(page.getByRole('heading', { name: route.title }).first()).toBeVisible({
        timeout: 15000,
      });
    }
  });
});
