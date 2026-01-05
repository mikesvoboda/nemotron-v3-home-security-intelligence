/**
 * Visual Regression Tests - Settings Page
 *
 * These tests capture screenshots and compare against baseline images
 * to detect unintended visual changes in the Settings page.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { SettingsPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

test.describe('Settings Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('settings full page matches snapshot', async ({ page }) => {
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('settings-full-page.png', {
      fullPage: true,
    });
  });

  test('settings cameras tab matches snapshot', async ({ page }) => {
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();

    // Cameras tab should be default or click to it
    const isCamerasSelected = await settingsPage.isTabSelected('cameras').catch(() => false);
    if (!isCamerasSelected) {
      await settingsPage.goToCamerasTab();
    }

    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('settings-cameras-tab.png', {
      fullPage: true,
    });
  });

  test('settings processing tab matches snapshot', async ({ page }) => {
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();

    await settingsPage.goToProcessingTab();
    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('settings-processing-tab.png', {
      fullPage: true,
    });
  });

  test('settings notifications tab matches snapshot', async ({ page }) => {
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();

    await settingsPage.goToNotificationsTab();
    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('settings-notifications-tab.png', {
      fullPage: true,
    });
  });
});

test.describe('Settings Tab Navigation Visual', () => {
  test('settings tab list matches snapshot', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();

    await page.waitForLoadState('networkidle');

    // Component screenshot of tab navigation
    const tabList = settingsPage.tabList;
    await expect(tabList).toHaveScreenshot('settings-tab-list.png');
  });

  test('settings tab panel matches snapshot', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();

    await page.waitForLoadState('networkidle');

    // Component screenshot of tab panel content
    const tabPanel = settingsPage.tabPanel;
    await expect(tabPanel).toHaveScreenshot('settings-tab-panel.png');
  });
});
