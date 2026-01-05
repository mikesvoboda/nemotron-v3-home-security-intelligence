/**
 * Visual Regression Tests - Responsive Design
 *
 * These tests capture screenshots at different viewport sizes
 * to detect unintended visual changes in responsive layouts.
 *
 * Tested viewports:
 * - Desktop (1920x1080)
 * - Tablet (1024x768)
 * - Mobile (375x667)
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

// Define viewport configurations
const viewports = [
  { width: 1920, height: 1080, name: 'desktop' },
  { width: 1024, height: 768, name: 'tablet' },
  { width: 375, height: 667, name: 'mobile' },
] as const;

test.describe('Responsive Dashboard Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  for (const viewport of viewports) {
    test(`dashboard renders correctly on ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(500);

      await expect(page).toHaveScreenshot(`dashboard-${viewport.name}.png`, {
        fullPage: true,
        mask: [
          page.locator('[data-testid="timestamp"]'),
          page.locator('time'),
          page.locator('img'),
        ],
      });
    });
  }
});

test.describe('Responsive Timeline Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  for (const viewport of viewports) {
    test(`timeline renders correctly on ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto('/timeline');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(500);

      await expect(page).toHaveScreenshot(`timeline-${viewport.name}.png`, {
        fullPage: true,
        mask: [page.locator('time')],
      });
    });
  }
});

test.describe('Responsive Settings Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  for (const viewport of viewports) {
    test(`settings renders correctly on ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto('/settings');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(500);

      await expect(page).toHaveScreenshot(`settings-${viewport.name}.png`, {
        fullPage: true,
      });
    });
  }
});

test.describe('Responsive System Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  for (const viewport of viewports) {
    test(`system page renders correctly on ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto('/system');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(500);

      await expect(page).toHaveScreenshot(`system-${viewport.name}.png`, {
        fullPage: true,
        mask: [
          page.locator('[data-testid="uptime"]'),
          page.locator('[data-testid*="chart"]'),
          page.locator('svg[class*="recharts"]'),
          page.locator('time'),
        ],
      });
    });
  }
});

test.describe('Responsive Navigation Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('mobile navigation menu matches snapshot', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Look for mobile menu button/hamburger
    const menuButton = page.locator('button[aria-label*="menu" i], button:has(svg[class*="menu" i])');
    if (await menuButton.isVisible()) {
      await expect(menuButton).toHaveScreenshot('navigation-mobile-menu-button.png');

      // Click to open mobile menu
      await menuButton.click();
      await page.waitForTimeout(300);

      // Capture mobile menu
      const mobileMenu = page.locator('[class*="mobile-menu"], nav[class*="MobileNav"]');
      if (await mobileMenu.isVisible()) {
        await expect(mobileMenu).toHaveScreenshot('navigation-mobile-menu-open.png');
      }
    }
  });

  test('tablet navigation matches snapshot', async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const header = page.getByRole('banner');
    if (await header.isVisible()) {
      await expect(header).toHaveScreenshot('navigation-tablet-header.png');
    }
  });
});

test.describe('Responsive Card Layouts Visual', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('camera grid adapts to mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Capture camera grid section on mobile
    const cameraSection = page.locator('[class*="camera-grid"], [class*="CameraGrid"]').first();
    if (await cameraSection.isVisible()) {
      await expect(cameraSection).toHaveScreenshot('camera-grid-mobile.png', {
        mask: [page.locator('img')],
      });
    }
  });

  test('stats row adapts to mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Capture stats row on mobile
    const statsRow = page.locator('[class*="StatsRow"], [class*="stats-row"]').first();
    if (await statsRow.isVisible()) {
      await expect(statsRow).toHaveScreenshot('stats-row-mobile.png');
    }
  });

  test('event cards adapt to tablet', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.goto('/timeline');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Capture event grid on tablet
    const eventGrid = page.locator('[class*="event-grid"], [class*="EventGrid"]').first();
    if (await eventGrid.isVisible()) {
      await expect(eventGrid).toHaveScreenshot('event-grid-tablet.png', {
        mask: [page.locator('time')],
      });
    }
  });
});
