/**
 * Mobile Layout Optimization Tests (NEM-1796)
 *
 * Tests for mobile-specific features:
 * - MobileBottomNav visibility and interactions
 * - Sidebar hidden on mobile viewports
 * - Safe area inset padding for iOS
 * - Touch target minimum sizes (44px)
 * - No horizontal scroll on mobile
 */

import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

const mobileViewport = { width: 375, height: 667 }; // iPhone SE

test.describe('Mobile Bottom Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await setupApiMocks(page, defaultMockConfig);
  });

  test('mobile bottom navigation is visible on mobile viewport', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Check for mobile bottom navigation
    const mobileNav = page.locator('nav[aria-label="Mobile navigation"]');
    await expect(mobileNav).toBeVisible();
  });

  test('mobile bottom navigation has 4 main icons', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Check for navigation links in mobile bottom nav
    const mobileNav = page.locator('nav[aria-label="Mobile navigation"]');
    const navLinks = mobileNav.locator('a');
    await expect(navLinks).toHaveCount(4);
  });

  test('mobile bottom navigation icons are clickable', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Click timeline icon in bottom nav
    const timelineLink = page.locator('nav[aria-label="Mobile navigation"] a[href="/timeline"]');
    await timelineLink.click();

    // Verify navigation occurred
    await expect(page).toHaveURL(/\/timeline/);
  });

  test('mobile bottom navigation has minimum touch target size', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Check that all nav links meet minimum touch target size (44px)
    const mobileNav = page.locator('nav[aria-label="Mobile navigation"]');
    const navLinks = mobileNav.locator('a');

    const count = await navLinks.count();
    for (let i = 0; i < count; i++) {
      const link = navLinks.nth(i);
      const box = await link.boundingBox();
      expect(box).not.toBeNull();
      if (box) {
        expect(box.height).toBeGreaterThanOrEqual(44);
        expect(box.width).toBeGreaterThanOrEqual(44);
      }
    }
  });

  test('sidebar is hidden on mobile viewport', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Sidebar should not be visible on mobile
    const sidebar = page.locator('[data-testid="sidebar"]');
    await expect(sidebar).not.toBeVisible();
  });

  test('main content has bottom padding for mobile nav', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Main content should have bottom padding to avoid overlap with fixed bottom nav
    const mainContent = dashboardPage.mainContent;
    const hasBottomPadding = await mainContent.evaluate((el) => {
      const styles = window.getComputedStyle(el);
      const paddingBottom = parseInt(styles.paddingBottom, 10);
      return paddingBottom >= 56; // 14 * 4 = 56px (h-14 in Tailwind)
    });

    expect(hasBottomPadding).toBe(true);
  });
});

test.describe('Mobile Layout Constraints', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await setupApiMocks(page, defaultMockConfig);
  });

  test('no horizontal scroll on mobile dashboard', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Check that page does not have horizontal overflow
    const hasHorizontalScroll = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });

    expect(hasHorizontalScroll).toBe(false);
  });

  test('content is responsive and fits viewport width', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Check main content width
    const mainContent = dashboardPage.mainContent;
    const box = await mainContent.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.width).toBeLessThanOrEqual(mobileViewport.width);
    }
  });

  test('all interactive elements meet minimum touch target size', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Check all buttons meet minimum touch target
    const buttons = page.locator('button:visible');
    const count = await buttons.count();

    // Sample first 10 buttons
    const samplesToCheck = Math.min(count, 10);
    for (let i = 0; i < samplesToCheck; i++) {
      const button = buttons.nth(i);
      const box = await button.boundingBox();
      if (box) {
        // Either height or width should be >= 44px for touch targets
        const meetsMinimum = box.height >= 44 || box.width >= 44;
        expect(meetsMinimum).toBe(true);
      }
    }
  });
});

test.describe('Mobile Navigation Transitions', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('bottom nav appears when transitioning from desktop to mobile', async ({ page }) => {
    // Start on desktop
    await page.setViewportSize({ width: 1280, height: 720 });
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Resize to mobile
    await page.setViewportSize(mobileViewport);
    await page.waitForLoadState('domcontentloaded');

    // Mobile nav should now be visible
    const mobileNav = page.locator('nav[aria-label="Mobile navigation"]');
    await expect(mobileNav).toBeVisible();

    // Sidebar should be hidden
    const sidebar = page.locator('[data-testid="sidebar"]');
    await expect(sidebar).not.toBeVisible();
  });

  test('bottom nav hides when transitioning from mobile to desktop', async ({ page }) => {
    // Start on mobile
    await page.setViewportSize(mobileViewport);
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Verify mobile nav is visible
    const mobileNav = page.locator('nav[aria-label="Mobile navigation"]');
    await expect(mobileNav).toBeVisible();

    // Resize to desktop
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.waitForLoadState('domcontentloaded');

    // Mobile nav should be hidden
    await expect(mobileNav).not.toBeVisible();

    // Sidebar should be visible
    const sidebar = page.locator('[data-testid="sidebar"]');
    await expect(sidebar).toBeVisible();
  });
});

test.describe('Mobile Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await setupApiMocks(page, defaultMockConfig);
  });

  test('mobile navigation has proper ARIA labels', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Check navigation has role and label
    const mobileNav = page.locator('nav[aria-label="Mobile navigation"]');
    await expect(mobileNav).toHaveAttribute('role', 'navigation');
    await expect(mobileNav).toHaveAttribute('aria-label');
  });

  test('mobile navigation links have descriptive labels', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    // Check each nav link has an aria-label
    const mobileNav = page.locator('nav[aria-label="Mobile navigation"]');
    const navLinks = mobileNav.locator('a');

    const count = await navLinks.count();
    for (let i = 0; i < count; i++) {
      const link = navLinks.nth(i);
      const ariaLabel = await link.getAttribute('aria-label');
      expect(ariaLabel).toBeTruthy();
      expect(ariaLabel).toMatch(/Go to/i);
    }
  });
});
