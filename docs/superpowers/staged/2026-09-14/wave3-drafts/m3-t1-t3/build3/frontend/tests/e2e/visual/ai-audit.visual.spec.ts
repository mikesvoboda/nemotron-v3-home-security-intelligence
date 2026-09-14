/**
 * Visual Regression Tests - AI Audit Page
 *
 * These tests capture screenshots and compare against baseline images
 * to detect unintended visual changes in the AI Audit Dashboard page.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { AIAuditPage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig } from '../fixtures';

test.describe('AI Audit Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('ai audit full page matches snapshot', async ({ page }) => {
    const aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('ai-audit-full-page.png', {
      fullPage: true,
      mask: [
        page.locator('[data-testid="timestamp"]'),
        page.locator('time'),
        // Mask charts and dynamic scores
        page.locator('[data-testid*="chart"]'),
        page.locator('[class*="Chart"]'),
        page.locator('svg[class*="recharts"]'),
        page.locator('[data-testid*="score"]'),
        page.locator('[data-testid*="trend"]'),
      ],
    });
  });

  test('ai audit quality score trends match snapshot', async ({ page }) => {
    const aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Quality score trends section screenshot
    const qualityTrends = aiAuditPage.qualityScoreTrends;
    if (await qualityTrends.isVisible()) {
      await expect(qualityTrends).toHaveScreenshot('ai-audit-quality-trends.png', {
        mask: [page.locator('svg[class*="recharts"]'), page.locator('[data-testid*="score"]')],
      });
    }
  });

  test('ai audit quality score card matches snapshot', async ({ page }) => {
    const aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Quality score card screenshot
    const qualityCard = aiAuditPage.qualityScoreCard;
    if (await qualityCard.isVisible()) {
      await expect(qualityCard).toHaveScreenshot('ai-audit-quality-card.png', {
        mask: [page.locator('[data-testid*="score"]')],
      });
    }
  });

  test('ai audit consistency rate card matches snapshot', async ({ page }) => {
    const aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Consistency rate card screenshot
    const consistencyCard = aiAuditPage.consistencyRateCard;
    if (await consistencyCard.isVisible()) {
      await expect(consistencyCard).toHaveScreenshot('ai-audit-consistency-card.png', {
        mask: [page.locator('[data-testid*="rate"]')],
      });
    }
  });

  test('ai audit enrichment utilization card matches snapshot', async ({ page }) => {
    const aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Enrichment utilization card screenshot
    const enrichmentCard = aiAuditPage.enrichmentUtilizationCard;
    if (await enrichmentCard.isVisible()) {
      await expect(enrichmentCard).toHaveScreenshot('ai-audit-enrichment-card.png', {
        mask: [page.locator('[data-testid*="utilization"]')],
      });
    }
  });

  test('ai audit recommendations panel matches snapshot', async ({ page }) => {
    const aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Recommendations panel screenshot
    const recommendationsPanel = aiAuditPage.recommendationsPanel;
    if (await recommendationsPanel.isVisible()) {
      await expect(recommendationsPanel).toHaveScreenshot('ai-audit-recommendations.png');
    }
  });

  test('ai audit period selector matches snapshot', async ({ page }) => {
    const aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Period selector screenshot
    const periodSelector = aiAuditPage.periodSelector;
    if (await periodSelector.isVisible()) {
      await expect(periodSelector).toHaveScreenshot('ai-audit-period-selector.png');
    }
  });
});

test.describe('AI Audit Visual States', () => {
  test('ai audit empty state matches snapshot', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('ai-audit-empty-state.png', {
      fullPage: true,
    });
  });

  test('ai audit with recommendations expanded matches snapshot', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();

    await page.waitForLoadState('networkidle');

    // Try to expand a recommendation category if accordion exists
    const accordion = aiAuditPage.recommendationsAccordion;
    if (await accordion.isVisible()) {
      // Click first accordion item to expand
      await accordion
        .locator('button, [role="button"]')
        .first()
        .click()
        .catch(() => {});
      await page.waitForTimeout(300);
    }

    await expect(page).toHaveScreenshot('ai-audit-recommendations-expanded.png', {
      fullPage: true,
      mask: [page.locator('time'), page.locator('[data-testid*="score"]')],
    });
  });
});
