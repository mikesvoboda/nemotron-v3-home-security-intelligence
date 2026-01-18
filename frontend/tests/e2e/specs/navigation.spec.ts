/**
 * Navigation Tests for Home Security Dashboard
 *
 * These tests verify that navigation between pages works correctly.
 * All API calls are mocked, so navigation should be fast.
 *
 * Optimized with serial mode to share page state between tests,
 * reducing setup overhead for navigation-focused tests.
 */

import { test, expect, type Page, type BrowserContext } from '@playwright/test';
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
import { BasePage } from '../pages/BasePage';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

test.describe('Navigation Tests', () => {
  let page: Page;
  let context: BrowserContext;

  test.describe.configure({ mode: 'serial' });

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext();
    page = await context.newPage();

    // Disable the product tour to prevent overlay from blocking interactions
    await page.addInitScript(() => {
      localStorage.setItem('nemotron-tour-completed', 'true');
      localStorage.setItem('nemotron-tour-skipped', 'true');
    });

    await setupApiMocks(page, defaultMockConfig);
    // Block images, fonts, and analytics to speed up navigation tests
    const basePage = new BasePage(page);
    await basePage.blockUnnecessaryResources();
  });

  test.afterAll(async () => {
    await page?.close();
    await context?.close();
  });

  test('can navigate to dashboard from root', async () => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
  });

  test('can navigate to timeline page', async () => {
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('can navigate to alerts page', async () => {
    const alertsPage = new AlertsPage(page);
    await alertsPage.goto();
    await alertsPage.waitForAlertsLoad();
  });

  test('can navigate to entities page', async () => {
    const entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();
  });

  test('can navigate to logs page', async () => {
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();
  });

  test('can navigate to audit page', async () => {
    const auditPage = new AuditPage(page);
    await auditPage.goto();
    await auditPage.waitForAuditLoad();
  });

  test('can navigate to system page', async () => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('can navigate to settings page', async () => {
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();
  });

  test('URL reflects current page - dashboard', async () => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/$/);
  });

  test('URL reflects current page - timeline', async () => {
    await page.goto('/timeline');
    await expect(page).toHaveURL(/\/timeline$/);
  });

  test('URL reflects current page - alerts', async () => {
    await page.goto('/alerts');
    await expect(page).toHaveURL(/\/alerts$/);
  });

  test('URL reflects current page - entities', async () => {
    await page.goto('/entities');
    await expect(page).toHaveURL(/\/entities$/);
  });

  test('URL reflects current page - logs', async () => {
    await page.goto('/logs');
    await expect(page).toHaveURL(/\/logs$/);
  });

  test('URL reflects current page - audit', async () => {
    await page.goto('/audit');
    await expect(page).toHaveURL(/\/audit$/);
  });

  test('URL reflects current page - operations', async () => {
    await page.goto('/operations');
    await expect(page).toHaveURL(/\/operations$/);
  });

  test('URL reflects current page - settings', async () => {
    await page.goto('/settings');
    await expect(page).toHaveURL(/\/settings$/);
  });

  test('page transitions preserve layout', async () => {
    const dashboardPage = new DashboardPage(page);
    const settingsPage = new SettingsPage(page);

    // Go to dashboard first
    await dashboardPage.goto();
    // Use parallel expects for faster validation
    await Promise.all([
      dashboardPage.waitForDashboardLoad(),
      dashboardPage.expectHeaderVisible(),
    ]);

    // Navigate to settings
    await settingsPage.goto();
    await Promise.all([
      settingsPage.waitForSettingsLoad(),
      settingsPage.expectHeaderVisible(),
    ]);
  });

  test('sidebar persists across page transitions', async () => {
    const dashboardPage = new DashboardPage(page);
    const timelinePage = new TimelinePage(page);

    await dashboardPage.goto();
    // Use parallel expects for faster validation
    await Promise.all([
      dashboardPage.waitForDashboardLoad(),
      dashboardPage.expectSidebarVisible(),
    ]);

    await timelinePage.goto();
    await Promise.all([
      timelinePage.waitForTimelineLoad(),
      timelinePage.expectSidebarVisible(),
    ]);
  });
});

test.describe('All Routes Smoke Tests', () => {
  let page: Page;
  let context: BrowserContext;

  test.describe.configure({ mode: 'serial' });

  test.beforeAll(async ({ browser, browserName }) => {
    // Skip on Firefox/WebKit - individual route tests already cover these browsers,
    // and sequential navigation is slower on secondary browsers.
    test.skip(
      browserName === 'firefox' || browserName === 'webkit',
      'Sequential multi-route test too slow on secondary browsers'
    );

    context = await browser.newContext();
    page = await context.newPage();

    // Disable the product tour to prevent overlay from blocking interactions
    await page.addInitScript(() => {
      localStorage.setItem('nemotron-tour-completed', 'true');
      localStorage.setItem('nemotron-tour-skipped', 'true');
    });

    await setupApiMocks(page, defaultMockConfig);
    // Block images, fonts, and analytics to speed up navigation tests
    const basePage = new BasePage(page);
    await basePage.blockUnnecessaryResources();
  });

  test.afterAll(async () => {
    await page?.close();
    await context?.close();
  });

  /**
   * Smoke test: Verifies all 8 routes load without error.
   * This test navigates sequentially through all routes to catch any navigation failures.
   * Routes are mocked, so reduced timeouts (5s/2s) are appropriate.
   */
  test('all 8 routes load without error', async () => {
    test.setTimeout(30000); // Increase timeout for 8-route navigation

    const routes = [
      { path: '/', title: /Security Dashboard/i },
      { path: '/timeline', title: /Event Timeline/i },
      { path: '/alerts', title: /Alerts/i },
      { path: '/entities', title: /Entities/i },
      { path: '/logs', title: /System Logs/i },
      { path: '/audit', title: /Audit Log/i },
      { path: '/operations', title: /Operations/i },
      { path: '/settings', title: /Settings/i },
    ];

    // With mocked APIs and blocked resources, navigation should be fast
    // Use domcontentloaded instead of networkidle for faster page ready detection
    // Note: React 19 on Node 22 may take slightly longer to hydrate/render, so we increase
    // the visibility timeout to 5000ms to account for concurrent rendering behavior
    for (const route of routes) {
      await page.goto(route.path, { waitUntil: 'domcontentloaded', timeout: 5000 });
      await expect(page.getByRole('heading', { name: route.title }).first()).toBeVisible({
        timeout: 5000, // Increased from 2000ms to handle React 19 concurrent rendering on Node 22
      });
    }
  });
});
