/**
 * Visual Regression Tests - AI Performance Page
 *
 * These tests capture screenshots and compare against baseline images
 * to detect unintended visual changes in the AI Performance Dashboard page.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { AIPerformancePage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig, errorMockConfig } from '../fixtures';

test.describe('AI Performance Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('ai performance full page matches snapshot', async ({ page }) => {
    const aiPage = new AIPerformancePage(page);
    await aiPage.goto();
    await aiPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('ai-performance-full-page.png', {
      fullPage: true,
      mask: [
        page.locator('[data-testid="timestamp"]'),
        page.locator('time'),
        page.locator('[data-testid="uptime"]'),
        // Mask charts and dynamic metrics
        page.locator('[data-testid*="chart"]'),
        page.locator('[class*="Chart"]'),
        page.locator('svg[class*="recharts"]'),
        page.locator('[data-testid="detection-latency"]'),
        page.locator('[data-testid="analysis-latency"]'),
        page.locator('[data-testid="pipeline-latency"]'),
        page.locator('[data-testid="queue-depth"]'),
      ],
    });
  });

  test('ai performance summary row matches snapshot', async ({ page }) => {
    const aiPage = new AIPerformancePage(page);
    await aiPage.goto();
    await aiPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Summary row screenshot
    const summaryRow = aiPage.summaryRow;
    if (await summaryRow.isVisible()) {
      await expect(summaryRow).toHaveScreenshot('ai-performance-summary-row.png', {
        mask: [page.locator('[data-testid*="latency"]'), page.locator('[data-testid*="count"]')],
      });
    }
  });

  test('ai performance model status cards match snapshot', async ({ page }) => {
    const aiPage = new AIPerformancePage(page);
    await aiPage.goto();
    await aiPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Model status cards screenshot
    const modelCards = aiPage.modelStatusCards;
    if (await modelCards.isVisible()) {
      await expect(modelCards).toHaveScreenshot('ai-performance-model-cards.png', {
        mask: [page.locator('[data-testid*="latency"]'), page.locator('[data-testid*="uptime"]')],
      });
    }
  });

  test('ai performance latency panel matches snapshot', async ({ page }) => {
    const aiPage = new AIPerformancePage(page);
    await aiPage.goto();
    await aiPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Latency panel screenshot
    const latencyPanel = aiPage.latencyPanel;
    if (await latencyPanel.isVisible()) {
      await expect(latencyPanel).toHaveScreenshot('ai-performance-latency-panel.png', {
        mask: [page.locator('[data-testid*="latency"]')],
      });
    }
  });

  test('ai performance pipeline health panel matches snapshot', async ({ page }) => {
    const aiPage = new AIPerformancePage(page);
    await aiPage.goto();
    await aiPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Pipeline health panel screenshot
    const healthPanel = aiPage.pipelineHealthPanel;
    if (await healthPanel.isVisible()) {
      await expect(healthPanel).toHaveScreenshot('ai-performance-pipeline-health.png', {
        mask: [page.locator('[data-testid*="queue"]'), page.locator('[data-testid*="count"]')],
      });
    }
  });

  test('ai performance insights charts match snapshot', async ({ page }) => {
    const aiPage = new AIPerformancePage(page);
    await aiPage.goto();
    await aiPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Insights charts screenshot
    const insightsCharts = aiPage.insightsCharts;
    if (await insightsCharts.isVisible()) {
      await expect(insightsCharts).toHaveScreenshot('ai-performance-insights-charts.png', {
        mask: [page.locator('svg[class*="recharts"]'), page.locator('[class*="Chart"]')],
      });
    }
  });

  test('ai performance model zoo section matches snapshot', async ({ page }) => {
    const aiPage = new AIPerformancePage(page);
    await aiPage.goto();
    await aiPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Model zoo section screenshot
    const modelZoo = aiPage.modelZooSection;
    if (await modelZoo.isVisible()) {
      await expect(modelZoo).toHaveScreenshot('ai-performance-model-zoo.png');
    }
  });
});

test.describe('AI Performance Visual States', () => {
  test('ai performance empty state matches snapshot', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const aiPage = new AIPerformancePage(page);
    await aiPage.goto();
    await aiPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('ai-performance-empty-state.png', {
      fullPage: true,
    });
  });

  test('ai performance with grafana banner matches snapshot', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const aiPage = new AIPerformancePage(page);
    await aiPage.goto();
    await aiPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Grafana banner if visible
    const grafanaBanner = aiPage.grafanaBanner;
    if (await grafanaBanner.isVisible()) {
      await expect(grafanaBanner).toHaveScreenshot('ai-performance-grafana-banner.png');
    }
  });
});
