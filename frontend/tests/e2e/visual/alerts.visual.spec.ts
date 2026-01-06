/**
 * Visual Regression Tests - Alerts Page
 *
 * These tests capture screenshots and compare against baseline images
 * to detect unintended visual changes in the Alerts page.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { AlertsPage } from '../pages';
import {
  setupApiMocks,
  defaultMockConfig,
  emptyMockConfig,
  highAlertMockConfig,
} from '../fixtures';

test.describe('Alerts Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('alerts full page matches snapshot', async ({ page }) => {
    const alertsPage = new AlertsPage(page);
    await alertsPage.goto();
    await alertsPage.waitForAlertsLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('alerts-full-page.png', {
      fullPage: true,
      mask: [
        page.locator('[data-testid="timestamp"]'),
        page.locator('time'),
        page.locator('[data-testid="relative-time"]'),
      ],
    });
  });

  test('alerts filter section matches snapshot', async ({ page }) => {
    const alertsPage = new AlertsPage(page);
    await alertsPage.goto();
    await alertsPage.waitForAlertsLoad();

    await page.waitForLoadState('networkidle');

    // Filter section screenshot
    const filterSection = page.locator('select#risk-filter').locator('..');
    if (await filterSection.isVisible()) {
      await expect(filterSection).toHaveScreenshot('alerts-filter-section.png');
    }
  });

  test('alerts card matches snapshot', async ({ page }) => {
    const alertsPage = new AlertsPage(page);
    await alertsPage.goto();
    await alertsPage.waitForAlertsLoad();

    await page.waitForLoadState('networkidle');

    // Get first alert card for component screenshot
    const alertCard = alertsPage.alertCards.first();
    if (await alertCard.isVisible()) {
      await expect(alertCard).toHaveScreenshot('alerts-card.png', {
        mask: [page.locator('time'), page.locator('[data-testid="event-time"]')],
      });
    }
  });

  test('alerts pagination matches snapshot', async ({ page }) => {
    const alertsPage = new AlertsPage(page);
    await alertsPage.goto();
    await alertsPage.waitForAlertsLoad();

    await page.waitForLoadState('networkidle');

    // Pagination area screenshot
    const paginationArea = page.locator('[class*="pagination"], [class*="Pagination"]').first();
    if (await paginationArea.isVisible()) {
      await expect(paginationArea).toHaveScreenshot('alerts-pagination.png');
    }
  });
});

test.describe('Alerts Visual States', () => {
  test('alerts empty state matches snapshot', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const alertsPage = new AlertsPage(page);
    await alertsPage.goto();
    await alertsPage.waitForAlertsLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('alerts-empty-state.png', {
      fullPage: true,
    });
  });

  test('alerts high alert state matches snapshot', async ({ page }) => {
    await setupApiMocks(page, highAlertMockConfig);
    const alertsPage = new AlertsPage(page);
    await alertsPage.goto();
    await alertsPage.waitForAlertsLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('alerts-high-alert-state.png', {
      fullPage: true,
      mask: [page.locator('[data-testid="timestamp"]'), page.locator('time')],
    });
  });

  test('alerts filtered by critical matches snapshot', async ({ page }) => {
    await setupApiMocks(page, highAlertMockConfig);
    const alertsPage = new AlertsPage(page);
    await alertsPage.goto();
    await alertsPage.waitForAlertsLoad();

    // Filter by critical severity
    await alertsPage.filterBySeverity('critical');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('alerts-filtered-critical.png', {
      fullPage: true,
      mask: [page.locator('time')],
    });
  });
});
