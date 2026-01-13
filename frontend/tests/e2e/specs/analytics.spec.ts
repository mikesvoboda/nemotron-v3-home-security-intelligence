/**
 * Analytics Page E2E Tests
 *
 * Tests for the Analytics page including:
 * - Page load and navigation
 * - Camera selector visibility
 * - Refresh button functionality
 * - Navigation from sidebar
 * - Empty state handling
 *
 * Note: The Analytics page requires baseline data from the API which
 * may cause some tests to show loading states if mocks are not properly
 * configured.
 */

import { test, expect } from '@playwright/test';
import { AnalyticsPage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig } from '../fixtures';

test.describe('Analytics Page Load', () => {
  let analyticsPage: AnalyticsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    analyticsPage = new AnalyticsPage(page);
  });

  test('analytics page loads successfully', async () => {
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();
  });

  test('analytics displays page title', async () => {
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();
    await expect(analyticsPage.pageTitle).toBeVisible();
  });

  test('analytics title says Analytics', async () => {
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();
    await expect(analyticsPage.pageTitle).toHaveText(/Analytics/i);
  });

  test('analytics displays page subtitle', async () => {
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();
    await expect(analyticsPage.pageSubtitle).toBeVisible();
  });
});

test.describe('Analytics Camera Selector', () => {
  let analyticsPage: AnalyticsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();
  });

  test('camera selector is visible', async () => {
    await expect(analyticsPage.cameraSelector).toBeVisible();
  });

  test('camera selector has options', async () => {
    const options = await analyticsPage.cameraSelector.locator('option').count();
    expect(options).toBeGreaterThan(0);
  });

  test('refresh button is visible', async () => {
    await expect(analyticsPage.refreshButton).toBeVisible();
  });
});

test.describe('Analytics Navigation', () => {
  let analyticsPage: AnalyticsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    analyticsPage = new AnalyticsPage(page);
  });

  test('can navigate to Analytics from sidebar', async ({ page }) => {
    // Start from dashboard
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Click Analytics link in sidebar
    await analyticsPage.navigateFromSidebar();

    // Verify we're on Analytics page
    await expect(analyticsPage.pageTitle).toBeVisible();
  });

  test('sidebar link is visible', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const analyticsLink = page.locator('aside a[href="/analytics"]');
    await expect(analyticsLink).toBeVisible();
  });

  test('sidebar link text says Analytics', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const analyticsLink = page.locator('aside a[href="/analytics"]');
    await expect(analyticsLink).toHaveText(/Analytics/i);
  });
});

test.describe('Analytics Empty State', () => {
  let analyticsPage: AnalyticsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    analyticsPage = new AnalyticsPage(page);
  });

  test('loads page with empty data', async () => {
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();
    // Page should load without crashing
    await expect(analyticsPage.pageTitle).toBeVisible({ timeout: 10000 });
  });

  test('shows all cameras option as default when no cameras configured', async () => {
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();
    // With empty config, "All Cameras" should be selected by default showing aggregate stats
    await expect(analyticsPage.cameraSelector).toBeVisible({ timeout: 10000 });
    // The selector should have "All Cameras" as default option
    await expect(analyticsPage.cameraSelector).toHaveText(/All Cameras/i);
  });
});
