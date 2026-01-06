/**
 * Visual Regression Tests - Analytics Page
 *
 * These tests capture screenshots and compare against baseline images
 * to detect unintended visual changes in the Analytics Dashboard page.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { AnalyticsPage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig } from '../fixtures';

test.describe('Analytics Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('analytics full page matches snapshot', async ({ page }) => {
    const analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('analytics-full-page.png', {
      fullPage: true,
      mask: [
        page.locator('[data-testid="timestamp"]'),
        page.locator('time'),
        // Mask charts as they may have slight rendering variations
        page.locator('[data-testid*="chart"]'),
        page.locator('[class*="Chart"]'),
        page.locator('svg[class*="recharts"]'),
      ],
    });
  });

  test('analytics camera selector matches snapshot', async ({ page }) => {
    const analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Camera selector screenshot
    const cameraSelector = analyticsPage.cameraSelector;
    if (await cameraSelector.isVisible()) {
      await expect(cameraSelector).toHaveScreenshot('analytics-camera-selector.png');
    }
  });

  test('analytics activity heatmap matches snapshot', async ({ page }) => {
    const analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Activity heatmap section screenshot
    const heatmapSection = analyticsPage.activityHeatmap;
    if (await heatmapSection.isVisible()) {
      await expect(heatmapSection).toHaveScreenshot('analytics-activity-heatmap.png', {
        mask: [page.locator('[data-testid*="heatmap-cell"]')],
      });
    }
  });

  test('analytics class frequency chart matches snapshot', async ({ page }) => {
    const analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Class frequency chart section screenshot
    const chartSection = analyticsPage.classFrequencyChart;
    if (await chartSection.isVisible()) {
      await expect(chartSection).toHaveScreenshot('analytics-class-frequency.png', {
        mask: [page.locator('svg[class*="recharts"]'), page.locator('[class*="BarChart"]')],
      });
    }
  });

  test('analytics anomaly config panel matches snapshot', async ({ page }) => {
    const analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Anomaly config panel screenshot
    const configPanel = analyticsPage.anomalyConfigPanel;
    if (await configPanel.isVisible()) {
      await expect(configPanel).toHaveScreenshot('analytics-anomaly-config.png');
    }
  });

  test('analytics baseline status matches snapshot', async ({ page }) => {
    const analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Baseline status area
    const baselineStatus = analyticsPage.learningStatusBadge;
    if (await baselineStatus.isVisible()) {
      await expect(baselineStatus.locator('..')).toHaveScreenshot('analytics-baseline-status.png');
    }
  });
});

test.describe('Analytics Visual States', () => {
  test('analytics empty state matches snapshot', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('analytics-empty-state.png', {
      fullPage: true,
    });
  });

  test('analytics no cameras state matches snapshot', async ({ page }) => {
    await setupApiMocks(page, {
      ...defaultMockConfig,
      cameras: [],
    });
    const analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('analytics-no-cameras.png', {
      fullPage: true,
    });
  });
});
