/**
 * Analytics Advanced E2E Tests
 *
 * Tests for the Grafana-based Analytics page advanced functionality:
 * - Page layout and responsiveness
 * - Iframe embedding and loading states
 * - Error handling for Grafana connection
 * - Refresh functionality
 *
 * Note: With the migration to Grafana, many UI-specific tests are no longer
 * applicable. The detailed metrics, charts, and interactivity are now handled
 * by the embedded Grafana dashboard.
 *
 * Linear Issue: NEM-2941 (Analytics Page Migration to Grafana)
 */

import { test, expect } from '../fixtures';
import { AnalyticsPage } from '../pages';

// Skip in CI - Grafana iframe tests are flaky
test.skip(() => !!process.env.CI, 'Analytics E2E tests require Grafana - run locally');

test.describe('Analytics Advanced - Page Structure', () => {
  let analyticsPage: AnalyticsPage;

  test.beforeEach(async ({ page }) => {
    analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();
  });

  test('displays page title with Analytics heading', async ({ page }) => {
    await expect(analyticsPage.pageTitle).toBeVisible();
    await expect(analyticsPage.pageTitle).toHaveText(/Analytics/i);
  });

  test('displays Grafana iframe container', async ({ page }) => {
    await expect(analyticsPage.grafanaIframe).toBeVisible();
  });

  test('iframe has correct title attribute for accessibility', async ({ page }) => {
    await expect(analyticsPage.grafanaIframe).toHaveAttribute('title', 'Analytics Dashboard');
  });

  test('header contains refresh and external link buttons', async ({ page }) => {
    await expect(analyticsPage.refreshButton).toBeVisible();
    await expect(analyticsPage.externalLink).toBeVisible();
  });
});

test.describe('Analytics Advanced - Controls', () => {
  let analyticsPage: AnalyticsPage;

  test.beforeEach(async ({ page }) => {
    analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();
  });

  test('refresh button refreshes the Grafana iframe', async ({ page }) => {
    // Get initial iframe src
    const initialSrc = await analyticsPage.getGrafanaUrl();
    expect(initialSrc).toBeTruthy();

    // Click refresh
    await analyticsPage.refresh();

    // Wait a moment for refresh to complete
    await page.waitForTimeout(200);

    // Iframe should still be visible after refresh
    await expect(analyticsPage.grafanaIframe).toBeVisible();
  });

  test('external link opens Grafana in new tab', async ({ page }) => {
    // Verify the link has correct attributes for opening in new tab
    await expect(analyticsPage.externalLink).toHaveAttribute('target', '_blank');

    // Get the href and verify it points to the correct dashboard
    const href = await analyticsPage.externalLink.getAttribute('href');
    expect(href).toContain('hsi-analytics');
    expect(href).toContain('orgId=1');
  });
});

test.describe('Analytics Advanced - Grafana Integration', () => {
  let analyticsPage: AnalyticsPage;

  test.beforeEach(async ({ page }) => {
    analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();
  });

  test('Grafana iframe URL includes kiosk mode', async () => {
    const src = await analyticsPage.getGrafanaUrl();
    expect(src).toContain('kiosk=1');
  });

  test('Grafana iframe URL includes dark theme', async () => {
    const src = await analyticsPage.getGrafanaUrl();
    expect(src).toContain('theme=dark');
  });

  test('Grafana iframe URL includes auto-refresh', async () => {
    const src = await analyticsPage.getGrafanaUrl();
    expect(src).toContain('refresh=30s');
  });

  test('Grafana iframe URL uses correct dashboard UID', async () => {
    const src = await analyticsPage.getGrafanaUrl();
    expect(src).toContain('/d/hsi-analytics');
  });
});

test.describe('Analytics Advanced - Responsive Layout', () => {
  let analyticsPage: AnalyticsPage;

  test('displays correctly on desktop viewport', async ({ page }) => {
    // Set desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 });

    analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();

    // Verify page elements are visible
    await expect(analyticsPage.pageTitle).toBeVisible();
    await expect(analyticsPage.grafanaIframe).toBeVisible();
    await expect(analyticsPage.refreshButton).toBeVisible();
    await expect(analyticsPage.externalLink).toBeVisible();
  });

  test('displays correctly on tablet viewport', async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });

    analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();

    // Verify core elements are visible
    await expect(analyticsPage.pageTitle).toBeVisible();
    await expect(analyticsPage.grafanaIframe).toBeVisible();
  });

  test('displays correctly on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();

    // Verify core elements are visible on mobile
    await expect(analyticsPage.pageTitle).toBeVisible();
    await expect(analyticsPage.grafanaIframe).toBeVisible();
  });
});

test.describe('Analytics Advanced - Navigation', () => {
  test('can navigate from dashboard via sidebar', async ({ page }) => {
    // Start from dashboard
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Find and click Analytics link in sidebar
    const analyticsLink = page.locator('aside a[href="/analytics"]');
    await expect(analyticsLink).toBeVisible();
    await analyticsLink.click();

    // Verify navigation to Analytics page
    await expect(page).toHaveURL(/\/analytics/);

    const analyticsPage = new AnalyticsPage(page);
    await expect(analyticsPage.pageTitle).toBeVisible();
  });

  test('URL is correct after navigation', async ({ page }) => {
    const analyticsPage = new AnalyticsPage(page);
    await analyticsPage.goto();
    await analyticsPage.waitForPageLoad();

    await expect(page).toHaveURL(/\/analytics/);
  });
});
