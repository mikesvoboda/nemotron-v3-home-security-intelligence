/**
 * Visual Regression Tests - System Page
 *
 * These tests capture screenshots and compare against baseline images
 * to detect unintended visual changes in the System Monitoring page.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { SystemPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

test.describe('System Page Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('system full page matches snapshot', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('system-full-page.png', {
      fullPage: true,
      // Mask dynamic content that changes between runs
      mask: [
        page.locator('[data-testid="uptime"]'),
        page.locator('[data-testid="live-metrics"]'),
        page.locator('[data-testid="timestamp"]'),
        page.locator('time'),
        // Mask GPU utilization charts as they may vary
        page.locator('[data-testid*="chart"]'),
        page.locator('[class*="Chart"]'),
        page.locator('svg[class*="recharts"]'),
      ],
    });
  });

  test('system overview card matches snapshot', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    await page.waitForLoadState('networkidle');

    const overviewCard = systemPage.systemOverviewCard;
    if (await overviewCard.isVisible()) {
      await expect(overviewCard).toHaveScreenshot('system-overview-card.png', {
        mask: [page.locator('[data-testid="uptime"]')],
      });
    }
  });

  test('service health card matches snapshot', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    await page.waitForLoadState('networkidle');

    const healthCard = systemPage.serviceHealthCard;
    if (await healthCard.isVisible()) {
      await expect(healthCard).toHaveScreenshot('system-service-health-card.png', {
        mask: [page.locator('[data-testid="response-time"]')],
      });
    }
  });

  test('pipeline metrics panel matches snapshot', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    await page.waitForLoadState('networkidle');

    const pipelinePanel = systemPage.pipelineMetricsPanel;
    if (await pipelinePanel.isVisible()) {
      await expect(pipelinePanel).toHaveScreenshot('system-pipeline-metrics.png', {
        mask: [
          page.locator('[data-testid="queue-size"]'),
          page.locator('[data-testid="latency"]'),
        ],
      });
    }
  });

  test('gpu stats card matches snapshot', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    await page.waitForLoadState('networkidle');

    const gpuCard = systemPage.gpuStatsCard;
    if (await gpuCard.isVisible()) {
      await expect(gpuCard).toHaveScreenshot('system-gpu-stats.png', {
        mask: [
          page.locator('[data-testid="gpu-utilization"]'),
          page.locator('[data-testid="gpu-memory"]'),
          page.locator('[data-testid="gpu-temperature"]'),
          page.locator('[class*="AreaChart"]'),
        ],
      });
    }
  });
});

test.describe('System Page Time Range Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('time range selector matches snapshot', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    await page.waitForLoadState('networkidle');

    const timeRangeSelector = systemPage.timeRangeSelector;
    if (await timeRangeSelector.isVisible()) {
      await expect(timeRangeSelector).toHaveScreenshot('system-time-range-selector.png');
    }
  });
});

test.describe('System Page Panels Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('ai models panel matches snapshot', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    await page.waitForLoadState('networkidle');

    const aiModelsPanel = systemPage.aiModelsPanel;
    if (await aiModelsPanel.isVisible()) {
      await expect(aiModelsPanel).toHaveScreenshot('system-ai-models-panel.png', {
        mask: [page.locator('[data-testid="model-latency"]')],
      });
    }
  });

  test('databases panel matches snapshot', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    await page.waitForLoadState('networkidle');

    const databasesPanel = systemPage.databasesPanel;
    if (await databasesPanel.isVisible()) {
      await expect(databasesPanel).toHaveScreenshot('system-databases-panel.png', {
        mask: [
          page.locator('[data-testid="db-connections"]'),
          page.locator('[data-testid="db-size"]'),
        ],
      });
    }
  });

  test('host system panel matches snapshot', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    await page.waitForLoadState('networkidle');

    const hostPanel = systemPage.hostSystemPanel;
    if (await hostPanel.isVisible()) {
      await expect(hostPanel).toHaveScreenshot('system-host-panel.png', {
        mask: [
          page.locator('[data-testid="cpu-usage"]'),
          page.locator('[data-testid="memory-usage"]'),
          page.locator('[data-testid="disk-usage"]'),
        ],
      });
    }
  });
});
