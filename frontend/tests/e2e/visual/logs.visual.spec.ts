/**
 * Visual Regression Tests - System Logs Page (Grafana-embedded)
 *
 * These tests capture screenshots and compare against baseline images
 * to detect unintended visual changes in the Grafana-embedded Logs page.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { LogsPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

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

    // Mask the Grafana iframe as its content is external
    await expect(page).toHaveScreenshot('logs-full-page.png', {
      fullPage: true,
      mask: [
        page.locator('[data-testid="logs-iframe"]'),
        page.locator('time'),
      ],
    });
  });

  test('logs header matches snapshot', async ({ page }) => {
    const logsPage = new LogsPage(page);
    await logsPage.goto();
    await logsPage.waitForLogsLoad();

    await page.waitForLoadState('networkidle');

    // Header section screenshot (title and buttons)
    const header = page.locator('[data-testid="logs-page"] > div').first();
    if (await header.isVisible()) {
      await expect(header).toHaveScreenshot('logs-header.png');
    }
  });
});
