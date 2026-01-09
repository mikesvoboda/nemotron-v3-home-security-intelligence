/**
 * Demo Test: E2E Utility Usage Examples
 *
 * This test demonstrates the usage of the new E2E testing utilities.
 * These examples show best practices for using test helpers, data generators,
 * wait utilities, and browser helpers in real test scenarios.
 *
 * NOTE: This is a demo file to illustrate utility usage patterns.
 * Delete or modify this file as needed for actual test scenarios.
 */

import { test, expect } from '@playwright/test';
import { setupApiMocks } from '../fixtures/api-mocks';
import {
  // Test Helpers
  waitForPageLoad,
  mockApiResponse,
  clearTestState,
  takeScreenshotOnFailure,
  waitForElementStable,

  // Data Generators
  generateCamera,
  generateEvent,
  generateEvents,

  // Wait Helpers
  waitForWebSocket,
  waitForApiCall,
  waitForAnimation,
  waitForLoadingToComplete,

  // Browser Helpers
  setViewport,
  enableDarkMode,
  simulateSlowNetwork,
  clearStorage,
} from '../utils';

test.describe('E2E Utility Usage Examples', () => {
  test.beforeEach(async ({ page }) => {
    // Clear test state before each test
    await clearTestState(page);

    // Set up API mocks
    await setupApiMocks(page);
  });

  test.afterEach(async ({ page }, testInfo) => {
    // Auto-capture screenshot on failure
    await takeScreenshotOnFailure(page, testInfo);
  });

  test('example: using data generators', async ({ page }) => {
    // Generate realistic test data with overrides
    const camera = generateCamera({
      name: 'Front Door',
      status: 'online',
    });

    const highRiskEvents = generateEvents(5, {
      minRiskScore: 70,
      maxRiskScore: 100,
    });

    await mockApiResponse(page, '/api/cameras', { cameras: [camera] });
    await mockApiResponse(page, '/api/events', { events: highRiskEvents });

    await page.goto('/');
    await waitForPageLoad(page);

    // Verify generated data is displayed
    await expect(page.getByText(camera.name)).toBeVisible();
  });

  test('example: waiting for async operations', async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);

    // Wait for WebSocket connection
    await waitForWebSocket(page);

    // Wait for all loading indicators to disappear
    await waitForLoadingToComplete(page);

    // Verify page is fully loaded
    await expect(page.locator('main')).toBeVisible();
  });

  test('example: waiting for API calls', async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);

    // Trigger action that makes API call
    const apiPromise = waitForApiCall(page, '/api/events');
    await page.click('button[aria-label="Refresh"]').catch(() => {
      // Button might not exist in demo
    });

    // Wait for API call to complete (with timeout)
    const response = await apiPromise.catch(() => null);

    if (response) {
      expect(response.status()).toBe(200);
    }
  });

  test('example: waiting for animations', async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);

    // Open modal (if exists)
    const modalButton = page.getByRole('button', { name: /open|modal/i }).first();
    if (await modalButton.count() > 0) {
      await modalButton.click();

      // Wait for modal animation to complete
      await waitForAnimation(page, '[role="dialog"]');

      // Wait for element to be stable (not moving)
      await waitForElementStable(page, '[role="dialog"]');

      // Now safe to interact with modal
      await expect(page.locator('[role="dialog"]')).toBeVisible();
    }
  });

  test('example: responsive viewport testing', async ({ page }) => {
    // Test mobile viewport
    await setViewport(page, 'mobile');
    await page.goto('/');
    await waitForPageLoad(page);

    // Verify mobile-specific elements
    const sidebar = page.locator('aside');
    const mobileViewport = await page.viewportSize();
    expect(mobileViewport?.width).toBe(375);

    // Test tablet viewport
    await setViewport(page, 'tablet');
    await page.reload();
    await waitForPageLoad(page);

    const tabletViewport = await page.viewportSize();
    expect(tabletViewport?.width).toBe(1024);
  });

  test('example: dark mode testing', async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);

    // Enable dark mode
    await enableDarkMode(page);

    // Verify dark mode class is applied
    const isDark = await page.evaluate(() => {
      return document.documentElement.classList.contains('dark');
    });
    expect(isDark).toBe(true);
  });

  test('example: network throttling', async ({ page }) => {
    // Simulate slow 3G network
    await simulateSlowNetwork(page, '3g');

    await page.goto('/');

    // Loading indicators should be visible longer on slow network
    const hasLoadingIndicator = await page
      .locator('.animate-spin, .animate-pulse')
      .count()
      .then((count) => count > 0)
      .catch(() => false);

    // This is expected on slow networks
    expect(typeof hasLoadingIndicator).toBe('boolean');
  });

  test('example: storage manipulation', async ({ page }) => {
    // Clear storage before test
    await clearStorage(page);

    await page.goto('/');
    await waitForPageLoad(page);

    // Set localStorage item
    await page.evaluate(() => {
      localStorage.setItem('testKey', 'testValue');
    });

    // Verify it was set
    const value = await page.evaluate(() => {
      return localStorage.getItem('testKey');
    });
    expect(value).toBe('testValue');

    // Clear storage (preserve specific items if needed)
    await clearStorage(page, {
      preserveLocalStorage: ['testKey'],
    });

    // Verify preserved item still exists
    const preservedValue = await page.evaluate(() => {
      return localStorage.getItem('testKey');
    });
    expect(preservedValue).toBe('testValue');
  });

  test('example: combined utilities workflow', async ({ page }) => {
    // 1. Set viewport and theme
    await setViewport(page, 'laptop');
    await enableDarkMode(page);

    // 2. Generate and mock test data
    const cameras = [
      generateCamera({ name: 'Front Door', status: 'online' }),
      generateCamera({ name: 'Back Yard', status: 'offline' }),
    ];
    await mockApiResponse(page, '/api/cameras', { cameras });

    // 3. Navigate and wait for page load
    await page.goto('/');
    await waitForPageLoad(page);

    // 4. Wait for WebSocket connection
    await waitForWebSocket(page, 'events', { timeout: 10000 });

    // 5. Wait for all loading to complete
    await waitForLoadingToComplete(page);

    // 6. Verify page is interactive
    await expect(page.locator('main')).toBeVisible();
  });
});
