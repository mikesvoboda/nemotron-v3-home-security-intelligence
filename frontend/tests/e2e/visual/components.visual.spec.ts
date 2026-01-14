/**
 * Visual Regression Tests - Key UI Components
 *
 * These tests capture screenshots of reusable UI components
 * to detect unintended visual changes across the application.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { DashboardPage, TimelinePage, SystemPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

test.describe('Navigation Components Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('header/navbar matches snapshot', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Capture header/navigation bar
    const header = page.getByRole('banner');
    if (await header.isVisible()) {
      await expect(header).toHaveScreenshot('component-header.png');
    }
  });

  test('sidebar navigation matches snapshot', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Capture sidebar if visible
    const sidebar = page.locator('[data-testid="sidebar"], nav[class*="Sidebar"]');
    if (await sidebar.isVisible()) {
      await expect(sidebar).toHaveScreenshot('component-sidebar.png');
    }
  });

  test('breadcrumbs matches snapshot', async ({ page }) => {
    // Navigate to a nested page
    await page.goto('/timeline');
    await page.waitForLoadState('networkidle');

    const breadcrumbs = page.locator('[aria-label="Breadcrumb"], nav[class*="breadcrumb" i]');
    if (await breadcrumbs.isVisible()) {
      await expect(breadcrumbs).toHaveScreenshot('component-breadcrumbs.png');
    }
  });
});

test.describe('Card Components Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('stat cards match snapshot', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Capture individual stat cards
    const activeCamerasStat = dashboardPage.activeCamerasStat;
    if (await activeCamerasStat.isVisible()) {
      await expect(activeCamerasStat.locator('..')).toHaveScreenshot('component-stat-card-cameras.png');
    }
  });

  test('camera card matches snapshot', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    await page.waitForLoadState('networkidle');

    // Find a camera card
    const cameraCard = page.locator('[data-testid^="camera-"], [class*="CameraCard"]').first();
    if (await cameraCard.isVisible()) {
      await expect(cameraCard).toHaveScreenshot('component-camera-card.png', {
        mask: [page.locator('img')],
      });
    }
  });
});

test.describe('Badge and Status Components Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('risk badges match snapshot', async ({ page }) => {
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    await page.waitForLoadState('networkidle');

    // Capture risk badges
    const riskBadges = timelinePage.riskBadges;
    const badgeCount = await riskBadges.count();
    if (badgeCount > 0) {
      await expect(riskBadges.first()).toHaveScreenshot('component-risk-badge.png');
    }
  });

  test('health status badges match snapshot', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    await page.waitForLoadState('networkidle');

    // Capture overall health badge
    const healthBadge = systemPage.overallHealthBadge;
    if (await healthBadge.isVisible()) {
      await expect(healthBadge).toHaveScreenshot('component-health-badge.png');
    }
  });

  test('service status rows match snapshot', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();

    await page.waitForLoadState('networkidle');

    // Capture service rows
    const serviceRows = systemPage.serviceRows;
    if ((await serviceRows.count()) > 0) {
      await expect(serviceRows.first()).toHaveScreenshot('component-service-row.png', {
        mask: [page.locator('[data-testid="response-time"]')],
      });
    }
  });
});

test.describe('Form Components Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('search input matches snapshot', async ({ page }) => {
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    await page.waitForLoadState('networkidle');

    // Capture search input
    const searchInput = timelinePage.fullTextSearchInput;
    if (await searchInput.isVisible()) {
      await expect(searchInput).toHaveScreenshot('component-search-input.png');
    }
  });

  test('filter dropdowns match snapshot', async ({ page }) => {
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    await timelinePage.showFilters();
    await page.waitForTimeout(300);

    // Capture camera filter dropdown
    const cameraFilter = timelinePage.cameraFilter;
    if (await cameraFilter.isVisible()) {
      await expect(cameraFilter).toHaveScreenshot('component-filter-dropdown.png');
    }
  });
});

test.describe('Button Components Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('primary buttons match snapshot', async ({ page }) => {
    await page.goto('/timeline');
    await page.waitForLoadState('networkidle');

    // Find a primary button
    const primaryButton = page.locator('button[class*="primary"], button[class*="Primary"]').first();
    if (await primaryButton.isVisible()) {
      await expect(primaryButton).toHaveScreenshot('component-button-primary.png');
    }
  });

  test('secondary buttons match snapshot', async ({ page }) => {
    await page.goto('/timeline');
    await page.waitForLoadState('networkidle');

    // Find a secondary button
    const secondaryButton = page.locator('button[class*="secondary"], button[class*="Secondary"]').first();
    if (await secondaryButton.isVisible()) {
      await expect(secondaryButton).toHaveScreenshot('component-button-secondary.png');
    }
  });

  test('icon buttons match snapshot', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Find an icon button
    const iconButton = page.locator('button:has(svg):not(:has-text())').first();
    if (await iconButton.isVisible()) {
      await expect(iconButton).toHaveScreenshot('component-button-icon.png');
    }
  });
});

test.describe('Loading States Visual', () => {
  test('loading skeleton matches snapshot', async ({ page }) => {
    // Navigate and capture loading state before data loads
    await page.goto('/');

    // Try to capture loading state (may be very brief)
    const skeleton = page.locator('.animate-pulse').first();
    if (await skeleton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await expect(skeleton).toHaveScreenshot('component-loading-skeleton.png');
    }
  });

  test('loading spinner matches snapshot', async ({ page }) => {
    await page.goto('/timeline');

    // Try to capture spinner
    const spinner = page.locator('.animate-spin').first();
    if (await spinner.isVisible({ timeout: 1000 }).catch(() => false)) {
      await expect(spinner).toHaveScreenshot('component-loading-spinner.png');
    }
  });
});
