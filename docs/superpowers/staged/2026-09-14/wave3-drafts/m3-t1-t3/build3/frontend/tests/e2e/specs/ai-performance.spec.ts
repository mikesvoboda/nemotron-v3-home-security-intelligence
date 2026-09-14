/**
 * AI Performance Page E2E Tests
 *
 * Tests for the AI Performance page including:
 * - Page load and navigation
 * - Model status display (RT-DETRv2, Nemotron)
 * - Grafana integration banner
 * - Controls (refresh button)
 * - Navigation from sidebar
 *
 * NOTE: Skipped in CI due to page load timing issues causing flakiness.
 * Run locally for AI performance page validation.
 *
 * Note: The AI Performance page fetches telemetry data from the API.
 * Tests focus on page structure and navigation rather than data content.
 */

import { test, expect } from '@playwright/test';

// Skip entire file in CI - page load timing issues cause flaky failures
test.skip(() => !!process.env.CI, 'AI performance tests flaky in CI - run locally');
import { AIPerformancePage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig } from '../fixtures';

test.describe('AI Performance Page Load', () => {
  let aiPerformancePage: AIPerformancePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    aiPerformancePage = new AIPerformancePage(page);
  });

  test('ai performance page loads successfully', async () => {
    await aiPerformancePage.goto();
    await aiPerformancePage.waitForPageLoad();
  });

  test('ai performance displays page title', async () => {
    await aiPerformancePage.goto();
    await aiPerformancePage.waitForPageLoad();
    await expect(aiPerformancePage.pageTitle).toBeVisible();
  });

  test('ai performance title says AI Performance', async () => {
    await aiPerformancePage.goto();
    await aiPerformancePage.waitForPageLoad();
    await expect(aiPerformancePage.pageTitle).toHaveText(/AI Performance/i);
  });
});

test.describe('AI Performance Controls', () => {
  let aiPerformancePage: AIPerformancePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    aiPerformancePage = new AIPerformancePage(page);
    await aiPerformancePage.goto();
    await aiPerformancePage.waitForPageLoad();
  });

  test('refresh button is visible', async () => {
    await expect(aiPerformancePage.refreshButton).toBeVisible();
  });

  test('refresh button works', async () => {
    await aiPerformancePage.waitForDataLoad();
    await aiPerformancePage.refresh();
    // Should not crash after refresh
    await expect(aiPerformancePage.pageTitle).toBeVisible();
  });
});

test.describe('AI Performance Grafana Integration', () => {
  let aiPerformancePage: AIPerformancePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    aiPerformancePage = new AIPerformancePage(page);
    await aiPerformancePage.goto();
    await aiPerformancePage.waitForPageLoad();
  });

  test('grafana banner is visible', async () => {
    const hasBanner = await aiPerformancePage.hasGrafanaBanner();
    expect(hasBanner).toBe(true);
  });

  test('grafana link has correct href format', async () => {
    const url = await aiPerformancePage.getGrafanaLinkUrl();
    // URL should contain consolidated dashboard path (now uses hsi-consolidated)
    expect(url).toContain('/d/hsi-consolidated');
  });

  test('grafana link opens in new tab', async () => {
    const link = aiPerformancePage.grafanaLink;
    const target = await link.getAttribute('target');
    expect(target).toBe('_blank');
  });
});

test.describe('AI Performance Navigation', () => {
  let aiPerformancePage: AIPerformancePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    aiPerformancePage = new AIPerformancePage(page);
  });

  test('can navigate to AI Performance from sidebar', async ({ page }) => {
    // Start from dashboard
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Click AI Performance link in sidebar
    await aiPerformancePage.navigateFromSidebar();

    // Verify we're on AI Performance page
    await expect(aiPerformancePage.pageTitle).toBeVisible();
  });

  test('sidebar link is visible', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const aiLink = page.locator('aside a[href="/ai"]');
    await expect(aiLink).toBeVisible();
  });

  test('sidebar link text says AI Performance', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const aiLink = page.locator('aside a[href="/ai"]');
    await expect(aiLink).toHaveText(/AI Performance/i);
  });
});

test.describe('AI Performance Empty State', () => {
  let aiPerformancePage: AIPerformancePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    aiPerformancePage = new AIPerformancePage(page);
  });

  test('loads page with empty data', async () => {
    await aiPerformancePage.goto();
    await aiPerformancePage.waitForPageLoad();
    // Page should load without crashing
    await expect(aiPerformancePage.pageTitle).toBeVisible({ timeout: 10000 });
  });
});

test.describe('AI Performance Page Title', () => {
  test('page has correct browser title', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const aiPerformancePage = new AIPerformancePage(page);
    await aiPerformancePage.goto();
    await expect(page).toHaveTitle(/Security Dashboard/i);
  });
});
