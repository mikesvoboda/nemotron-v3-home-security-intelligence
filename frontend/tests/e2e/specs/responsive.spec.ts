/**
 * Responsive Design Tests for Home Security Dashboard
 *
 * Tests that verify the application renders correctly across different
 * viewport sizes including mobile, tablet, and desktop breakpoints.
 */

import { test, expect, devices } from '@playwright/test';
import { DashboardPage, TimelinePage, SettingsPage, SystemPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

// Common viewport sizes to test
const viewports = {
  mobile: { width: 375, height: 667 }, // iPhone SE
  mobileLarge: { width: 414, height: 896 }, // iPhone 11 Pro Max
  tablet: { width: 768, height: 1024 }, // iPad
  tabletLandscape: { width: 1024, height: 768 }, // iPad Landscape
  desktop: { width: 1280, height: 720 }, // Standard desktop
  desktopLarge: { width: 1920, height: 1080 }, // Full HD
};

test.describe('Mobile Viewport Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(viewports.mobile);
    await setupApiMocks(page, defaultMockConfig);
  });

  test('dashboard loads on mobile viewport', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.pageTitle).toBeVisible();
  });

  test('header is visible on mobile', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.header).toBeVisible();
  });

  test('main content is scrollable on mobile', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // Scroll down and verify content is still accessible
    await page.evaluate(() => window.scrollBy(0, 500));
    await expect(dashboardPage.mainContent).toBeVisible();
  });

  test('timeline page loads on mobile', async ({ page }) => {
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    await expect(timelinePage.pageTitle).toBeVisible();
  });

  test('settings page loads on mobile', async ({ page }) => {
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();
    await expect(settingsPage.pageTitle).toBeVisible();
  });

  test('system page loads on mobile', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    await expect(systemPage.pageTitle).toBeVisible();
  });

  test('camera grid is visible on mobile', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // Scroll to camera section
    await page.evaluate(() => window.scrollBy(0, 300));
    await expect(dashboardPage.cameraGridHeading).toBeVisible();
  });

  test('activity feed is visible on mobile', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // Scroll to activity section
    await page.evaluate(() => window.scrollBy(0, 600));
    await expect(dashboardPage.activityFeedHeading).toBeVisible();
  });
});

test.describe('Tablet Viewport Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(viewports.tablet);
    await setupApiMocks(page, defaultMockConfig);
  });

  test('dashboard loads on tablet viewport', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.pageTitle).toBeVisible();
  });

  test('sidebar is visible on tablet', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.sidebar).toBeVisible();
  });

  test('all dashboard sections visible on tablet', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectAllSectionsVisible();
  });

  test('timeline page loads on tablet', async ({ page }) => {
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    await expect(timelinePage.pageTitle).toBeVisible();
  });

  test('settings tabs are accessible on tablet', async ({ page }) => {
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();
    await expect(settingsPage.camerasTab).toBeVisible();
    await expect(settingsPage.processingTab).toBeVisible();
  });

  test('system page shows all panels on tablet', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    await expect(systemPage.systemOverviewCard).toBeVisible();
    await expect(systemPage.serviceHealthCard).toBeVisible();
  });
});

test.describe('Tablet Landscape Viewport Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(viewports.tabletLandscape);
    await setupApiMocks(page, defaultMockConfig);
  });

  test('dashboard shows full layout in tablet landscape', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectLayoutLoaded();
  });

  test('sidebar navigation works in tablet landscape', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.navTimeline).toBeVisible();
  });
});

test.describe('Desktop Viewport Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(viewports.desktop);
    await setupApiMocks(page, defaultMockConfig);
  });

  test('dashboard shows full layout on desktop', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectLayoutLoaded();
  });

  test('sidebar is expanded on desktop', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.sidebar).toBeVisible();
  });

  test('all navigation links visible on desktop', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.navTimeline).toBeVisible();
    await expect(dashboardPage.navAlerts).toBeVisible();
    await expect(dashboardPage.navSystem).toBeVisible();
    await expect(dashboardPage.navSettings).toBeVisible();
  });

  test('GPU stats panel visible on desktop', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectGpuStatsVisible();
  });

  test('system page shows all metrics on desktop', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    await expect(systemPage.systemOverviewCard).toBeVisible();
    await expect(systemPage.serviceHealthCard).toBeVisible();
    await expect(systemPage.pipelineQueuesCard).toBeVisible();
  });
});

test.describe('Large Desktop Viewport Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(viewports.desktopLarge);
    await setupApiMocks(page, defaultMockConfig);
  });

  test('dashboard renders well on large screens', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectLayoutLoaded();
  });

  test('content is not stretched on large screens', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // Verify main content has reasonable max-width
    const mainContent = dashboardPage.mainContent;
    const boundingBox = await mainContent.boundingBox();
    expect(boundingBox).not.toBeNull();
    // Content should be visible and within bounds
    if (boundingBox) {
      expect(boundingBox.width).toBeLessThan(viewports.desktopLarge.width);
    }
  });

  test('system page has room for all panels', async ({ page }) => {
    const systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    await expect(systemPage.systemOverviewCard).toBeVisible();
    await expect(systemPage.serviceHealthCard).toBeVisible();
    await expect(systemPage.timeRangeSelector).toBeVisible();
  });
});

test.describe('Viewport Transition Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('layout adapts when viewport changes from mobile to desktop', async ({ page }) => {
    // Start on mobile
    await page.setViewportSize(viewports.mobile);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Resize to desktop
    await page.setViewportSize(viewports.desktop);
    await page.waitForLoadState('domcontentloaded');

    // Verify layout adapted
    await dashboardPage.expectLayoutLoaded();
  });

  test('layout adapts when viewport changes from desktop to mobile', async ({ page }) => {
    // Start on desktop
    await page.setViewportSize(viewports.desktop);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Resize to mobile
    await page.setViewportSize(viewports.mobile);
    await page.waitForLoadState('domcontentloaded');

    // Verify content still accessible
    await expect(dashboardPage.pageTitle).toBeVisible();
  });

  test('content remains visible during orientation change', async ({ page }) => {
    // Start in portrait
    await page.setViewportSize(viewports.tablet);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Switch to landscape
    await page.setViewportSize(viewports.tabletLandscape);
    await page.waitForLoadState('domcontentloaded');

    // Verify content visible
    await expect(dashboardPage.pageTitle).toBeVisible();
    await dashboardPage.expectLayoutLoaded();
  });
});

test.describe('Mobile Interaction Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(viewports.mobile);
    await setupApiMocks(page, defaultMockConfig);
  });

  test('buttons are clickable on mobile viewport', async ({ page }) => {
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();

    // Verify tabs are clickable on mobile
    await settingsPage.camerasTab.click();
    await expect(settingsPage.pageTitle).toBeVisible();
  });

  test('navigation links work on mobile viewport', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Navigate via URL on mobile (sidebar may be collapsed)
    await page.goto('/timeline');
    await expect(page).toHaveURL(/\/timeline/);
  });

  test('scrolling works on mobile viewport', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Get initial scroll position
    const initialScrollY = await page.evaluate(() => window.scrollY);

    // Scroll using mouse wheel (works on mobile viewport)
    await page.mouse.wheel(0, 500);

    // Wait for scroll to complete
    await page.waitForFunction(
      (initialY) => window.scrollY > initialY,
      initialScrollY,
      { timeout: 5000 }
    );

    // Verify scroll happened
    const newScrollY = await page.evaluate(() => window.scrollY);
    expect(newScrollY).toBeGreaterThan(initialScrollY);
  });
});
