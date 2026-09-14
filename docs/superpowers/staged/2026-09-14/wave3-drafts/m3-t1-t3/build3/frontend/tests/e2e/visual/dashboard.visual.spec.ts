/**
 * Visual Regression Tests - Dashboard Page
 *
 * These tests capture screenshots and compare against baseline images
 * to detect unintended visual changes in the Dashboard page.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig, highAlertMockConfig } from '../fixtures';

test.describe('Dashboard Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('dashboard full page matches snapshot', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Wait for any animations to settle
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Full page screenshot
    await expect(page).toHaveScreenshot('dashboard-full-page.png', {
      fullPage: true,
      // Mask dynamic content that changes between runs
      mask: [
        page.locator('[data-testid="timestamp"]'),
        page.locator('[data-testid="live-indicator"]'),
        page.locator('time'),
      ],
    });
  });

  test('dashboard stats row matches snapshot', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    await page.waitForLoadState('networkidle');

    // Component-level screenshot of stats row
    const statsRow = dashboardPage.statsRow;
    await expect(statsRow).toHaveScreenshot('dashboard-stats-row.png');
  });

  test('dashboard camera grid matches snapshot', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    await page.waitForLoadState('networkidle');

    // Component-level screenshot of camera grid
    const cameraSection = dashboardPage.cameraGridSection;
    await expect(cameraSection).toHaveScreenshot('dashboard-camera-grid.png', {
      // Mask camera images as they may vary
      mask: [page.locator('img[alt*="camera" i], img[alt*="snapshot" i]')],
    });
  });

  test('dashboard risk card matches snapshot', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    await page.waitForLoadState('networkidle');

    // Risk card screenshot
    const riskCard = dashboardPage.riskScoreStat;
    await expect(riskCard).toHaveScreenshot('dashboard-risk-card.png', {
      // Mask sparkline as it may vary slightly
      mask: [page.locator('[data-testid="risk-sparkline"]')],
    });
  });
});

test.describe('Dashboard Visual States', () => {
  test('dashboard empty state matches snapshot', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('dashboard-empty-state.png', {
      fullPage: true,
      mask: [page.locator('[data-testid="timestamp"]'), page.locator('time')],
    });
  });

  test('dashboard high alert state matches snapshot', async ({ page }) => {
    await setupApiMocks(page, highAlertMockConfig);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('dashboard-high-alert-state.png', {
      fullPage: true,
      mask: [page.locator('[data-testid="timestamp"]'), page.locator('time')],
    });
  });
});
