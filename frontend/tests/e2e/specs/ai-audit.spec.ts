/**
 * AI Audit Dashboard Tests for Home Security Dashboard
 *
 * Comprehensive tests for the AI Audit Dashboard including:
 * - Page load and navigation
 * - Quality score metrics display
 * - Model contribution chart
 * - Model leaderboard
 * - Recommendations panel
 * - Empty and error states
 */

import { test, expect } from '@playwright/test';
import { AIAuditPage } from '../pages';
import {
  setupApiMocks,
  defaultMockConfig,
  emptyMockConfig,
  errorMockConfig,
} from '../fixtures';

test.describe('AI Audit Page Load', () => {
  let aiAuditPage: AIAuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    aiAuditPage = new AIAuditPage(page);
  });

  test('ai audit page loads successfully', async () => {
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();
  });

  test('ai audit displays page title', async () => {
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();
    await expect(aiAuditPage.pageTitle).toBeVisible();
  });

  test('ai audit displays page subtitle', async () => {
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();
    await expect(aiAuditPage.pageSubtitle).toBeVisible();
  });

  test('ai audit title says AI Audit Dashboard', async () => {
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();
    await expect(aiAuditPage.pageTitle).toHaveText(/AI Audit Dashboard/i);
  });
});

test.describe('AI Audit Controls', () => {
  let aiAuditPage: AIAuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();
  });

  test('refresh button is visible', async () => {
    await expect(aiAuditPage.refreshButton).toBeVisible();
  });

  test('period selector is visible', async () => {
    await expect(aiAuditPage.periodSelector).toBeVisible();
  });
});

test.describe('AI Audit Quality Metrics', () => {
  let aiAuditPage: AIAuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();
  });

  test('quality score trends section is visible', async () => {
    await aiAuditPage.waitForDataLoad();
    await expect(aiAuditPage.qualityScoreTrends).toBeVisible();
  });

  test('quality score card is visible', async () => {
    await aiAuditPage.waitForDataLoad();
    await expect(aiAuditPage.qualityScoreCard).toBeVisible();
  });

  test('consistency rate card is visible', async () => {
    await aiAuditPage.waitForDataLoad();
    await expect(aiAuditPage.consistencyRateCard).toBeVisible();
  });

  test('enrichment utilization card is visible', async () => {
    await aiAuditPage.waitForDataLoad();
    await expect(aiAuditPage.enrichmentUtilizationCard).toBeVisible();
  });

  test('evaluation coverage card is visible', async () => {
    await aiAuditPage.waitForDataLoad();
    await expect(aiAuditPage.evaluationCoverageCard).toBeVisible();
  });
});

test.describe('AI Audit Model Contribution Chart', () => {
  let aiAuditPage: AIAuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();
  });

  test('model contribution chart is visible', async () => {
    await aiAuditPage.waitForDataLoad();
    await expect(aiAuditPage.modelContributionChart).toBeVisible();
  });

  test('chart has model contribution title', async ({ page }) => {
    await aiAuditPage.waitForDataLoad();
    // Use locator.filter to find the text within the contribution chart
    const chart = page.getByTestId('model-contribution-chart');
    await expect(chart.getByText(/Contribution/i).first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe('AI Audit Model Leaderboard', () => {
  let aiAuditPage: AIAuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();
  });

  test('model leaderboard is visible', async () => {
    await aiAuditPage.waitForDataLoad();
    await expect(aiAuditPage.modelLeaderboard).toBeVisible();
  });

  test('leaderboard title says Model Leaderboard', async ({ page }) => {
    await aiAuditPage.waitForDataLoad();
    await expect(page.getByText('Model Leaderboard')).toBeVisible();
  });

  test('leaderboard has model entries', async () => {
    await aiAuditPage.waitForDataLoad();
    const modelCount = await aiAuditPage.getLeaderboardModelCount();
    expect(modelCount).toBeGreaterThan(0);
  });

  test('leaderboard shows RT-DETR model', async ({ page }) => {
    await aiAuditPage.waitForDataLoad();
    await expect(page.getByText('RT-DETR').first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe('AI Audit Recommendations Panel', () => {
  let aiAuditPage: AIAuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    aiAuditPage = new AIAuditPage(page);
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();
  });

  test('recommendations panel is visible', async () => {
    await aiAuditPage.waitForDataLoad();
    await expect(aiAuditPage.recommendationsPanel).toBeVisible({ timeout: 10000 });
  });

  test('panel has recommendations title', async ({ page }) => {
    await aiAuditPage.waitForDataLoad();
    // Use locator within the recommendations panel
    const panel = page.getByTestId('recommendations-panel');
    await expect(panel.getByText(/Recommendations/i).first()).toBeVisible({ timeout: 10000 });
  });

  test('recommendations accordion is visible when data is present', async () => {
    await aiAuditPage.waitForDataLoad();
    const hasRecommendations = await aiAuditPage.hasRecommendations();
    expect(hasRecommendations).toBe(true);
  });
});

test.describe('AI Audit Navigation', () => {
  let aiAuditPage: AIAuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    aiAuditPage = new AIAuditPage(page);
  });

  test('can navigate to AI Audit from sidebar', async ({ page }) => {
    // Start from dashboard
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Click AI Audit link in sidebar
    await aiAuditPage.navigateFromSidebar();

    // Verify we're on AI Audit page
    await expect(aiAuditPage.pageTitle).toBeVisible();
  });

  test('sidebar link is visible', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const aiAuditLink = page.locator('aside a[href="/ai-audit"]');
    await expect(aiAuditLink).toBeVisible();
  });

  test('sidebar link text says AI Audit', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const aiAuditLink = page.locator('aside a[href="/ai-audit"]');
    await expect(aiAuditLink).toHaveText(/AI Audit/i);
  });
});

test.describe('AI Audit Empty State', () => {
  let aiAuditPage: AIAuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    aiAuditPage = new AIAuditPage(page);
  });

  test('loads page with empty data', async () => {
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();
    // Page should load without error
    await expect(aiAuditPage.pageTitle).toBeVisible({ timeout: 10000 });
  });

  test('shows N/A for quality metrics when no data', async ({ page }) => {
    await aiAuditPage.goto();
    await aiAuditPage.waitForPageLoad();
    // With empty config, quality scores should show N/A
    await expect(page.getByText('N/A').first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe('AI Audit Error State', () => {
  let aiAuditPage: AIAuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    aiAuditPage = new AIAuditPage(page);
  });

  test('shows error state when API fails', async () => {
    await aiAuditPage.goto();
    // Wait for error state to appear
    await expect(aiAuditPage.errorState).toBeVisible({ timeout: 10000 });
  });

  test('error state shows retry button', async ({ page }) => {
    await aiAuditPage.goto();
    // Wait for error state first
    await expect(aiAuditPage.errorState).toBeVisible({ timeout: 10000 });
    const retryButton = page.getByRole('button', { name: /Try Again/i });
    await expect(retryButton).toBeVisible({ timeout: 5000 });
  });
});
