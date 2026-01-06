/**
 * Visual Regression Tests - System Logs Page
 *
 * These tests capture screenshots and compare against baseline images
 * to detect unintended visual changes in the Logs Dashboard page.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { LogsPage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig } from '../fixtures';

test.describe('Logs Dashboard Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('logs full page matches snapshot', async ({ page }) => {
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('logs-full-page.png', {
      fullPage: true,
      mask: [
        page.locator('[data-testid="timestamp"]'),
        page.locator('time'),
        page.locator('[data-testid="log-time"]'),
      ],
    });
  });

  test('logs stats cards match snapshot', async ({ page }) => {
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();

    await page.waitForLoadState('networkidle');

    // Stats section screenshot
    const statsSection = logsPage.statsSection;
    if (await statsSection.isVisible()) {
      await expect(statsSection).toHaveScreenshot('logs-stats-cards.png');
    }
  });

  test('logs filters expanded matches snapshot', async ({ page }) => {
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();

    // Show filters panel
    await logsPage.showFilters();
    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('logs-filters-expanded.png', {
      fullPage: true,
      mask: [page.locator('time')],
    });
  });

  test('logs table matches snapshot', async ({ page }) => {
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();

    await page.waitForLoadState('networkidle');

    // Table screenshot
    const logsTable = logsPage.logsTable;
    if (await logsTable.isVisible()) {
      await expect(logsTable).toHaveScreenshot('logs-table.png', {
        mask: [page.locator('time'), page.locator('[data-testid="log-time"]')],
      });
    }
  });

  test('logs search results match snapshot', async ({ page }) => {
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();

    // Enter search query
    await logsPage.searchLogs('error');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('logs-search-results.png', {
      fullPage: true,
      mask: [page.locator('time')],
    });
  });

  test('logs pagination matches snapshot', async ({ page }) => {
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();

    await page.waitForLoadState('networkidle');

    // Pagination area screenshot
    const paginationArea = page.locator('[class*="pagination"], [class*="Pagination"]').first();
    if (await paginationArea.isVisible()) {
      await expect(paginationArea).toHaveScreenshot('logs-pagination.png');
    }
  });
});

test.describe('Logs Dashboard Visual States', () => {
  test('logs empty state matches snapshot', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('logs-empty-state.png', {
      fullPage: true,
    });
  });

  test('logs filtered by level matches snapshot', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();

    // Filter by error level
    await logsPage.filterByLevel('error');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('logs-filtered-error.png', {
      fullPage: true,
      mask: [page.locator('time')],
    });
  });
});
