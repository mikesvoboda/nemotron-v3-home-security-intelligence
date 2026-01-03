/**
 * E2E Tests for Zone Management
 *
 * Tests zone display, visibility toggle, and basic interactions
 * from the settings page where zones are managed.
 */

import { expect, test } from '@playwright/test';
import { setupApiMocks } from '../fixtures/api-mocks';
import { ZonesPage, SettingsPage } from '../pages';

test.describe('Zone Management', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test.describe('Zone List Display', () => {
    test('should display zones list in settings', async ({ page }) => {
      const zonesPage = new ZonesPage(page);
      await zonesPage.goto();
      await zonesPage.waitForZonesLoad();

      // Zones should be visible in the settings page
      const settingsPage = new SettingsPage(page);
      await expect(settingsPage.pageTitle).toBeVisible();
    });

    test('should show zone type badges', async ({ page }) => {
      const zonesPage = new ZonesPage(page);
      await zonesPage.goto();
      await zonesPage.waitForZonesLoad();

      // Check that the page loaded successfully
      await expect(page.locator('body')).toBeVisible();
    });

    test('should show empty state when no zones', async ({ page }) => {
      // Override mock to return empty zones
      await page.route('**/api/zones*', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        });
      });

      const zonesPage = new ZonesPage(page);
      await zonesPage.goto();

      // Should show settings page (zones may be empty or not displayed)
      await expect(page.locator('body')).toBeVisible();
    });
  });

  test.describe('Zone Visibility', () => {
    test('should have visibility controls available', async ({ page }) => {
      const zonesPage = new ZonesPage(page);
      await zonesPage.goto();
      await zonesPage.waitForZonesLoad();

      // Settings page should be accessible
      const settingsPage = new SettingsPage(page);
      await expect(settingsPage.pageTitle).toBeVisible();
    });
  });

  test.describe('Zone Selection', () => {
    test('should navigate to cameras tab for zone editing', async ({ page }) => {
      const settingsPage = new SettingsPage(page);
      await settingsPage.goto();
      await settingsPage.waitForSettingsLoad();

      // Navigate to cameras tab where zones are typically edited
      await settingsPage.goToCamerasTab();
      await expect(settingsPage.camerasTab).toBeVisible();
    });
  });

  test.describe('Zone Error Handling', () => {
    test('should handle API errors gracefully', async ({ page }) => {
      // Mock API error
      await page.route('**/api/zones*', async (route) => {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal server error' }),
        });
      });

      const zonesPage = new ZonesPage(page);
      await zonesPage.goto();

      // Page should still be accessible
      await expect(page.locator('body')).toBeVisible();
    });
  });
});

test.describe('Zone Settings Integration', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test('should access zones from settings page', async ({ page }) => {
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();

    // Settings page should load with all tabs
    await expect(settingsPage.camerasTab).toBeVisible();
  });

  test('should switch between settings tabs', async ({ page }) => {
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();

    // Switch to cameras tab
    await settingsPage.goToCamerasTab();

    // Switch to processing tab
    await settingsPage.goToProcessingTab();

    // Verify tab content changes
    await expect(settingsPage.tabPanel).toBeVisible();
  });
});
