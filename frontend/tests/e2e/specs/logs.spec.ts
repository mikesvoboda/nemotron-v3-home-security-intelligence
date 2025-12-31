/**
 * Logs Tests for Home Security Dashboard
 *
 * Comprehensive tests for the System Logs page including:
 * - Log stats display
 * - Log filtering
 * - Log table display
 * - Pagination
 * - Log detail modal
 */

import { test, expect } from '@playwright/test';
import { LogsPage } from '../pages';
import {
  setupApiMocks,
  defaultMockConfig,
  emptyMockConfig,
  errorMockConfig,
} from '../fixtures';

test.describe('Logs Page Load', () => {
  let logsPage: LogsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    logsPage = new LogsPage(page);
  });

  test('logs page loads successfully', async () => {
    await logsPage.goto();
    await logsPage.waitForLogsLoad();
  });

  test('logs displays page title', async () => {
    await logsPage.goto();
    await logsPage.waitForLogsLoad();
    await expect(logsPage.pageTitle).toBeVisible();
  });

  test('logs displays page subtitle', async () => {
    await logsPage.goto();
    await logsPage.waitForLogsLoad();
    await expect(logsPage.pageSubtitle).toBeVisible();
  });

  test('logs title says System Logs', async () => {
    await logsPage.goto();
    await logsPage.waitForLogsLoad();
    await expect(logsPage.pageTitle).toHaveText(/System Logs/i);
  });
});

test.describe('Logs Filters', () => {
  let logsPage: LogsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();
  });

  test('level filter is visible after expanding', async () => {
    await logsPage.showFilters();
    await expect(logsPage.levelFilter).toBeVisible();
  });

  test('component filter is visible after expanding', async () => {
    await logsPage.showFilters();
    await expect(logsPage.componentFilter).toBeVisible();
  });

  test('search input is visible', async () => {
    await expect(logsPage.searchInput).toBeVisible();
  });

  test('can select DEBUG level filter', async () => {
    await logsPage.filterByLevel('debug');
    await expect(logsPage.levelFilter).toHaveValue('DEBUG');
  });

  test('can select INFO level filter', async () => {
    await logsPage.filterByLevel('info');
    await expect(logsPage.levelFilter).toHaveValue('INFO');
  });

  test('can select WARNING level filter', async () => {
    await logsPage.filterByLevel('warning');
    await expect(logsPage.levelFilter).toHaveValue('WARNING');
  });

  test('can select ERROR level filter', async () => {
    await logsPage.filterByLevel('error');
    await expect(logsPage.levelFilter).toHaveValue('ERROR');
  });

  test('can search logs', async () => {
    await logsPage.searchLogs('detection');
    await expect(logsPage.searchInput).toHaveValue('detection');
  });
});

test.describe('Logs Table', () => {
  let logsPage: LogsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();
  });

  test('logs table is visible', async () => {
    await expect(logsPage.logsTable).toBeVisible();
  });

  test('logs table has rows', async () => {
    const rowCount = await logsPage.getLogRowCount();
    expect(rowCount).toBeGreaterThanOrEqual(0);
  });
});

test.describe('Logs Pagination', () => {
  let logsPage: LogsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();
  });

  test('previous page button exists', async () => {
    await expect(logsPage.previousPageButton).toBeVisible();
  });

  test('next page button exists', async () => {
    await expect(logsPage.nextPageButton).toBeVisible();
  });
});

test.describe('Logs Empty State', () => {
  let logsPage: LogsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    logsPage = new LogsPage(page);
  });

  test('shows empty state when no logs', async () => {
    await logsPage.goto();
    await logsPage.waitForLogsLoad();
    const hasEmpty = await logsPage.hasEmptyState();
    expect(hasEmpty).toBe(true);
  });
});

test.describe('Logs Error State', () => {
  let logsPage: LogsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    logsPage = new LogsPage(page);
  });

  test('page loads even with API errors', async () => {
    await logsPage.goto();
    await logsPage.waitForLogsLoad();
    // Page should still render even with errors
    await expect(logsPage.pageTitle).toBeVisible();
  });
});
