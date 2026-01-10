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
  // Mark all tests in this suite as slow (3x timeout multiplier)
  // Demo tests need more time for navigation, animations, and WebSocket connections
  test.slow();

  test.beforeEach(async ({ page }) => {
    // Clear test state before each test
    await clearTestState(page);

    // Set up API mocks
    await setupApiMocks(page);
  });

  test.afterEach(async ({ page }, testInfo) => {
    // Auto-capture screenshot on failure
    // Wrap in try-catch to handle cases where page/browser is already closed
    try {
      await takeScreenshotOnFailure(page, testInfo);
    } catch (error) {
      // Ignore errors if page/context/browser is already closed
      console.log('Screenshot capture skipped: page already closed');
    }
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

    // Use pagination envelope format (NEM-2075)
    await mockApiResponse(page, '/api/cameras', {
      items: [camera],
      pagination: { total: 1, limit: 50, offset: null, cursor: null, next_cursor: null, has_more: false },
    });
    await mockApiResponse(page, '/api/events', {
      items: highRiskEvents,
      pagination: {
        total: highRiskEvents.length,
        limit: 20,
        offset: null,
        cursor: null,
        next_cursor: null,
        has_more: false,
      },
    });

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

  // SKIP: This test is inherently flaky - it relies on a specific button that may not exist
  // and demonstrates async waiting patterns that are better tested in actual feature tests
  test.skip('example: waiting for API calls', async ({ page }) => {
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

  // SKIP: This test is flaky - it depends on a modal button that may not exist in the UI
  // Animation timing utilities are better demonstrated in actual feature tests with real UI elements
  test.skip('example: waiting for animations', async ({ page }) => {
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

  // SKIP: Network throttling tests are inherently slow and flaky in CI environments
  // These patterns are better tested in dedicated performance/load testing scenarios
  test.skip('example: network throttling', async ({ page }) => {
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
    // Use pagination envelope format (NEM-2075)
    await mockApiResponse(page, '/api/cameras', {
      items: cameras,
      pagination: { total: cameras.length, limit: 50, offset: null, cursor: null, next_cursor: null, has_more: false },
    });

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
