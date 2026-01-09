/**
 * Common Test Helper Functions for E2E Tests
 *
 * Provides reusable test utilities for page load verification, API mocking,
 * state management, and screenshot capture on failure.
 */

import type { Page, TestInfo, Route } from '@playwright/test';
import { expect } from '@playwright/test';

/**
 * Wait for page hydration to complete
 *
 * Waits for React to finish hydrating the DOM and removes loading indicators.
 * This ensures elements are interactive and stable before interacting.
 *
 * @param page - Playwright page object
 * @param options - Optional configuration
 * @param options.timeout - Maximum time to wait in milliseconds (default: 10000)
 * @param options.waitForNetworkIdle - Whether to wait for network idle (default: false)
 *
 * @example
 * ```typescript
 * test('dashboard loads correctly', async ({ page }) => {
 *   await page.goto('/');
 *   await waitForPageLoad(page);
 *
 *   // Now safe to interact with elements
 *   await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
 * });
 * ```
 */
export async function waitForPageLoad(
  page: Page,
  options: { timeout?: number; waitForNetworkIdle?: boolean } = {}
): Promise<void> {
  const { timeout = 10000, waitForNetworkIdle = false } = options;

  // Wait for DOM content to load
  await page.waitForLoadState('domcontentloaded', { timeout });

  // Optionally wait for network idle (useful for initial page load)
  if (waitForNetworkIdle) {
    await page.waitForLoadState('networkidle', { timeout }).catch(() => {
      // Ignore timeout - network might not idle in CI environments
    });
  }

  // Wait for React hydration by checking for loading indicators to disappear
  await page
    .waitForFunction(
      () => {
        // Check for common loading indicators
        const spinners = document.querySelectorAll('.animate-spin');
        const skeletons = document.querySelectorAll('.animate-pulse');
        const loadingText = document.querySelectorAll('[data-loading="true"]');

        return spinners.length === 0 && skeletons.length === 0 && loadingText.length === 0;
      },
      { timeout }
    )
    .catch(() => {
      // Continue if loading indicators aren't found
    });

  // Wait for main content area to be visible
  await expect(page.locator('main').first()).toBeVisible({ timeout });
}

/**
 * Mock a specific API endpoint response
 *
 * Intercepts requests to the specified endpoint and returns the mock response.
 * Useful for testing specific scenarios without full mock setup.
 *
 * @param page - Playwright page object
 * @param endpoint - API endpoint pattern to match (e.g., '/api/cameras')
 * @param response - Response data to return (will be JSON stringified)
 * @param options - Optional configuration
 * @param options.status - HTTP status code (default: 200)
 * @param options.delay - Delay before responding in milliseconds (default: 0)
 * @param options.method - HTTP method to match (default: any)
 *
 * @example
 * ```typescript
 * test('handles API errors', async ({ page }) => {
 *   await mockApiResponse(page, '/api/cameras', { detail: 'Service unavailable' }, {
 *     status: 500
 *   });
 *   await page.goto('/');
 *
 *   await expect(page.getByText('Failed to load cameras')).toBeVisible();
 * });
 * ```
 */
export async function mockApiResponse(
  page: Page,
  endpoint: string,
  response: unknown,
  options: { status?: number; delay?: number; method?: string } = {}
): Promise<void> {
  const { status = 200, delay = 0, method } = options;

  const urlPattern = endpoint.startsWith('*') ? endpoint : `**${endpoint}*`;

  await page.route(urlPattern, async (route: Route) => {
    // Check if method matches (if specified)
    if (method && route.request().method() !== method) {
      await route.continue();
      return;
    }

    // Apply delay if specified
    if (delay > 0) {
      await new Promise((resolve) => setTimeout(resolve, delay));
    }

    await route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(response),
    });
  });
}

/**
 * Clear test state between tests
 *
 * Resets browser state including localStorage, sessionStorage, cookies,
 * and IndexedDB. Call this in beforeEach or afterEach hooks.
 *
 * @param page - Playwright page object
 * @param options - Optional configuration
 * @param options.preserveAuth - Whether to preserve authentication state (default: false)
 * @param options.clearIndexedDB - Whether to clear IndexedDB (default: true)
 *
 * @example
 * ```typescript
 * test.beforeEach(async ({ page }) => {
 *   await clearTestState(page);
 *   await setupApiMocks(page);
 * });
 * ```
 */
export async function clearTestState(
  page: Page,
  options: { preserveAuth?: boolean; clearIndexedDB?: boolean } = {}
): Promise<void> {
  const { preserveAuth = false, clearIndexedDB = true } = options;

  // Clear storage
  await page.evaluate(
    ({ keepAuth, clearIDB }) => {
      // Clear localStorage
      if (!keepAuth) {
        localStorage.clear();
      } else {
        // Preserve auth tokens if needed
        const authToken = localStorage.getItem('auth_token');
        localStorage.clear();
        if (authToken) {
          localStorage.setItem('auth_token', authToken);
        }
      }

      // Clear sessionStorage
      sessionStorage.clear();

      // Clear IndexedDB
      if (clearIDB && window.indexedDB) {
        indexedDB.databases().then((databases) => {
          databases.forEach((db) => {
            if (db.name) {
              indexedDB.deleteDatabase(db.name);
            }
          });
        });
      }
    },
    { keepAuth: preserveAuth, clearIDB: clearIndexedDB }
  );

  // Clear cookies
  const cookies = await page.context().cookies();
  await page.context().clearCookies();

  // Optionally restore auth cookie
  if (preserveAuth) {
    const authCookie = cookies.find((c) => c.name === 'session' || c.name === 'auth_token');
    if (authCookie) {
      await page.context().addCookies([authCookie]);
    }
  }
}

/**
 * Take screenshot on test failure
 *
 * Automatically captures a screenshot when a test fails. This should be called
 * in test.afterEach() hooks.
 *
 * @param page - Playwright page object
 * @param testInfo - Playwright TestInfo object from test context
 *
 * @example
 * ```typescript
 * test.afterEach(async ({ page }, testInfo) => {
 *   await takeScreenshotOnFailure(page, testInfo);
 * });
 * ```
 */
export async function takeScreenshotOnFailure(page: Page, testInfo: TestInfo): Promise<void> {
  if (testInfo.status !== 'passed') {
    // Generate screenshot path
    const screenshotPath = testInfo.outputPath(`failure-${Date.now()}.png`);

    // Capture full page screenshot
    await page.screenshot({
      path: screenshotPath,
      fullPage: true,
      timeout: 5000,
    }).catch((error) => {
      console.error('Failed to capture screenshot:', error);
    });

    // Attach to test report
    await testInfo.attach('screenshot', {
      path: screenshotPath,
      contentType: 'image/png',
    });

    // Also capture HTML snapshot for debugging
    const htmlPath = testInfo.outputPath(`failure-${Date.now()}.html`);
    const html = await page.content().catch(() => '<html><body>Failed to capture HTML</body></html>');
    await require('fs').promises.writeFile(htmlPath, html);

    await testInfo.attach('html-snapshot', {
      path: htmlPath,
      contentType: 'text/html',
    });
  }
}

/**
 * Wait for element to be stable (not animating or moving)
 *
 * Waits for an element to stop moving before interacting with it.
 * Useful for modals, dropdowns, and animated elements.
 *
 * @param page - Playwright page object
 * @param selector - CSS selector or Playwright locator
 * @param options - Optional configuration
 * @param options.timeout - Maximum time to wait in milliseconds (default: 5000)
 * @param options.stabilityThreshold - Time element must be stable in ms (default: 100)
 *
 * @example
 * ```typescript
 * test('interacts with modal', async ({ page }) => {
 *   await page.click('button.open-modal');
 *   await waitForElementStable(page, '.modal-content');
 *
 *   // Now safe to interact with modal
 *   await page.click('.modal-content button.submit');
 * });
 * ```
 */
export async function waitForElementStable(
  page: Page,
  selector: string,
  options: { timeout?: number; stabilityThreshold?: number } = {}
): Promise<void> {
  const { timeout = 5000, stabilityThreshold = 100 } = options;

  const locator = typeof selector === 'string' ? page.locator(selector) : selector;

  // Wait for element to be visible first
  await expect(locator).toBeVisible({ timeout });

  // Wait for element to stop moving
  await page.waitForFunction(
    ({ sel, threshold }) => {
      const element = document.querySelector(sel);
      if (!element) return false;

      const rect = element.getBoundingClientRect();

      return new Promise<boolean>((resolve) => {
        let lastTop = rect.top;
        let lastLeft = rect.left;
        let stableCount = 0;
        const requiredStableChecks = Math.ceil(threshold / 50);

        const checkInterval = setInterval(() => {
          const currentRect = element.getBoundingClientRect();

          if (currentRect.top === lastTop && currentRect.left === lastLeft) {
            stableCount++;
            if (stableCount >= requiredStableChecks) {
              clearInterval(checkInterval);
              resolve(true);
            }
          } else {
            stableCount = 0;
            lastTop = currentRect.top;
            lastLeft = currentRect.left;
          }
        }, 50);

        // Timeout fallback
        setTimeout(() => {
          clearInterval(checkInterval);
          resolve(true);
        }, threshold * 2);
      });
    },
    { sel: selector, threshold: stabilityThreshold },
    { timeout }
  );
}

/**
 * Fill form field and wait for validation
 *
 * Fills a form field and waits for validation to complete before proceeding.
 * Useful for forms with async validation.
 *
 * @param page - Playwright page object
 * @param label - Field label or selector
 * @param value - Value to fill
 * @param options - Optional configuration
 * @param options.waitForValidation - Whether to wait for validation (default: true)
 * @param options.validationTimeout - Validation timeout in ms (default: 2000)
 *
 * @example
 * ```typescript
 * test('submits form with validation', async ({ page }) => {
 *   await fillFormField(page, 'Email', 'test@example.com');
 *   await fillFormField(page, 'Password', 'secure123');
 *   await page.click('button[type="submit"]');
 * });
 * ```
 */
export async function fillFormField(
  page: Page,
  label: string,
  value: string,
  options: { waitForValidation?: boolean; validationTimeout?: number } = {}
): Promise<void> {
  const { waitForValidation = true, validationTimeout = 2000 } = options;

  // Fill the field
  const field = page.getByLabel(label);
  await field.fill(value);

  // Trigger blur event to start validation
  await field.blur();

  // Wait for validation indicators to appear and stabilize
  if (waitForValidation) {
    await page.waitForTimeout(100); // Brief delay for validation to start

    // Wait for validation indicators to disappear or error messages to appear
    await page
      .waitForFunction(
        () => {
          const validatingSpinners = document.querySelectorAll('.validating, [data-validating="true"]');
          return validatingSpinners.length === 0;
        },
        { timeout: validationTimeout }
      )
      .catch(() => {
        // Continue if no validation indicators found
      });
  }
}

/**
 * Retry an action until it succeeds or times out
 *
 * Useful for flaky interactions or waiting for conditions to become true.
 *
 * @param action - Async function to retry
 * @param options - Optional configuration
 * @param options.maxAttempts - Maximum retry attempts (default: 3)
 * @param options.delayMs - Delay between retries in ms (default: 1000)
 * @param options.timeout - Total timeout in ms (default: 10000)
 *
 * @returns Result of the successful action
 * @throws Error if all attempts fail
 *
 * @example
 * ```typescript
 * test('waits for dynamic content', async ({ page }) => {
 *   await retryAction(
 *     async () => {
 *       const text = await page.locator('.dynamic-content').textContent();
 *       if (!text || text.includes('Loading')) {
 *         throw new Error('Content not loaded yet');
 *       }
 *       return text;
 *     },
 *     { maxAttempts: 5, delayMs: 500 }
 *   );
 * });
 * ```
 */
export async function retryAction<T>(
  action: () => Promise<T>,
  options: { maxAttempts?: number; delayMs?: number; timeout?: number } = {}
): Promise<T> {
  const { maxAttempts = 3, delayMs = 1000, timeout = 10000 } = options;

  const startTime = Date.now();
  let lastError: Error | unknown;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    // Check timeout
    if (Date.now() - startTime > timeout) {
      throw new Error(
        `Action timed out after ${timeout}ms. Last error: ${lastError instanceof Error ? lastError.message : String(lastError)}`
      );
    }

    try {
      return await action();
    } catch (error) {
      lastError = error;

      // Don't delay after last attempt
      if (attempt < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    }
  }

  throw new Error(
    `Action failed after ${maxAttempts} attempts. Last error: ${lastError instanceof Error ? lastError.message : String(lastError)}`
  );
}

/**
 * Check if browser is running in headed mode
 *
 * @param page - Playwright page object
 * @returns True if browser is headed (visible)
 *
 * @example
 * ```typescript
 * test('conditional test', async ({ page }) => {
 *   if (isHeadedMode(page)) {
 *     // Only run visual checks in headed mode
 *     await expect(page).toHaveScreenshot();
 *   }
 * });
 * ```
 */
export function isHeadedMode(page: Page): boolean {
  return !page.context().browser()?.isConnected();
}

/**
 * Get browser name (chromium, firefox, webkit)
 *
 * @param page - Playwright page object
 * @returns Browser name or 'unknown'
 *
 * @example
 * ```typescript
 * test('browser-specific behavior', async ({ page }) => {
 *   const browser = getBrowserName(page);
 *
 *   if (browser === 'webkit') {
 *     // WebKit-specific timeout
 *     await page.waitForTimeout(2000);
 *   }
 * });
 * ```
 */
export function getBrowserName(page: Page): string {
  return page.context().browser()?.browserType().name() || 'unknown';
}

/**
 * Wait for console message matching pattern
 *
 * Useful for debugging or verifying console output in tests.
 *
 * @param page - Playwright page object
 * @param pattern - String or RegExp to match console message
 * @param options - Optional configuration
 * @param options.timeout - Maximum time to wait in milliseconds (default: 5000)
 * @param options.type - Console message type to match (default: any)
 *
 * @returns The matched console message
 *
 * @example
 * ```typescript
 * test('logs debug message', async ({ page }) => {
 *   const messagePromise = waitForConsoleMessage(page, /API request completed/);
 *
 *   await page.click('button.fetch');
 *   const message = await messagePromise;
 *
 *   expect(message.text()).toContain('200 OK');
 * });
 * ```
 */
export async function waitForConsoleMessage(
  page: Page,
  pattern: string | RegExp,
  options: { timeout?: number; type?: 'log' | 'info' | 'warn' | 'error' } = {}
): Promise<{ text: () => string; type: () => string }> {
  const { timeout = 5000, type } = options;

  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      page.off('console', handler);
      reject(new Error(`Console message matching ${pattern} not found within ${timeout}ms`));
    }, timeout);

    const handler = (msg: { text: () => string; type: () => string }) => {
      const messageText = msg.text();
      const messageType = msg.type();

      // Check type filter
      if (type && messageType !== type) {
        return;
      }

      // Check pattern match
      const matches = pattern instanceof RegExp ? pattern.test(messageText) : messageText.includes(pattern);

      if (matches) {
        clearTimeout(timeoutId);
        page.off('console', handler);
        resolve(msg);
      }
    };

    page.on('console', handler);
  });
}
