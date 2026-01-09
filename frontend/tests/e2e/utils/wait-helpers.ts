/**
 * Wait Helper Utilities for E2E Tests
 *
 * Provides specialized wait functions for common async operations in E2E tests,
 * including WebSocket connections, API calls, animations, and element states.
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';

/**
 * WebSocket channel types
 */
export type WebSocketChannel = 'events' | 'system';

/**
 * Wait for WebSocket connection to be established
 *
 * Waits for the application to establish a WebSocket connection on the specified
 * channel. Checks for connection state indicators in the UI.
 *
 * @param page - Playwright page object
 * @param channel - WebSocket channel to wait for (default: 'events')
 * @param options - Optional configuration
 * @param options.timeout - Maximum time to wait in milliseconds (default: 10000)
 * @param options.checkIndicator - Whether to check for connection indicator in UI (default: true)
 *
 * @example
 * ```typescript
 * test('real-time updates work', async ({ page }) => {
 *   await page.goto('/');
 *   await waitForWebSocket(page);
 *
 *   // Now safe to test WebSocket-dependent features
 *   await expect(page.getByText('Connected')).toBeVisible();
 * });
 * ```
 */
export async function waitForWebSocket(
  page: Page,
  channel: WebSocketChannel = 'events',
  options: { timeout?: number; checkIndicator?: boolean } = {}
): Promise<void> {
  const { timeout = 10000, checkIndicator = true } = options;

  // Wait for WebSocket mock to be initialized (if using mocks)
  await page
    .waitForFunction(
      (ch) => {
        const mock = (window as unknown as Record<string, unknown>).__wsMock as {
          mockWebSockets?: Map<string, { readyState: number }>;
        };

        if (mock?.mockWebSockets) {
          const ws = mock.mockWebSockets.get(ch);
          return ws?.readyState === 1; // OPEN state
        }

        // If no mock, assume connection will be established by the app
        return true;
      },
      channel,
      { timeout }
    )
    .catch(() => {
      // Continue if WebSocket mock is not set up (may be using real WebSocket)
    });

  // Optionally wait for connection indicator in UI
  if (checkIndicator) {
    await page
      .waitForFunction(
        () => {
          // Check for common connection indicators
          const connectedText = document.body.textContent?.includes('Connected');
          const disconnectedText = document.body.textContent?.includes('Disconnected');
          const connectingText = document.body.textContent?.includes('Connecting');

          // Connection is ready if we see "Connected" and not "Disconnected" or "Connecting"
          return connectedText && !disconnectedText && !connectingText;
        },
        { timeout: timeout / 2 }
      )
      .catch(() => {
        // Indicator check is optional - continue if not found
      });
  }
}

/**
 * Wait for WebSocket disconnection
 *
 * @param page - Playwright page object
 * @param channel - WebSocket channel to wait for
 * @param timeout - Maximum time to wait in milliseconds (default: 10000)
 *
 * @example
 * ```typescript
 * test('handles disconnection gracefully', async ({ page }) => {
 *   await page.goto('/');
 *   await waitForWebSocket(page);
 *
 *   // Simulate disconnection
 *   await page.evaluate(() => window.__wsMock?.mockWebSockets?.get('events')?.close());
 *
 *   await waitForWebSocketDisconnect(page);
 *   await expect(page.getByText('Disconnected')).toBeVisible();
 * });
 * ```
 */
export async function waitForWebSocketDisconnect(
  page: Page,
  channel: WebSocketChannel = 'events',
  timeout: number = 10000
): Promise<void> {
  await page.waitForFunction(
    (ch) => {
      const mock = (window as unknown as Record<string, unknown>).__wsMock as {
        mockWebSockets?: Map<string, { readyState: number }>;
      };

      if (mock?.mockWebSockets) {
        const ws = mock.mockWebSockets.get(ch);
        return !ws || ws.readyState === 3; // CLOSED state or doesn't exist
      }

      return true;
    },
    channel,
    { timeout }
  );
}

/**
 * Wait for element to appear with retry logic
 *
 * Waits for an element to appear in the DOM, with built-in retry logic for
 * flaky selectors or dynamic content.
 *
 * @param page - Playwright page object
 * @param selector - CSS selector or Playwright locator
 * @param options - Optional configuration
 * @param options.timeout - Maximum time to wait in milliseconds (default: 10000)
 * @param options.state - Element state to wait for (default: 'visible')
 * @param options.retries - Number of retry attempts (default: 3)
 *
 * @returns The located element
 *
 * @example
 * ```typescript
 * test('modal appears', async ({ page }) => {
 *   await page.click('button.open-modal');
 *   const modal = await waitForElement(page, '.modal-content');
 *
 *   await expect(modal).toBeVisible();
 * });
 * ```
 */
export async function waitForElement(
  page: Page,
  selector: string | Locator,
  options: {
    timeout?: number;
    state?: 'attached' | 'detached' | 'visible' | 'hidden';
    retries?: number;
  } = {}
): Promise<Locator> {
  const { timeout = 10000, state = 'visible', retries = 3 } = options;

  const locator = typeof selector === 'string' ? page.locator(selector) : selector;

  let lastError: Error | null = null;

  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      await locator.waitFor({ state, timeout: timeout / retries });
      return locator;
    } catch (error) {
      lastError = error as Error;

      // Don't wait after last attempt
      if (attempt < retries - 1) {
        await page.waitForTimeout(500);
      }
    }
  }

  throw new Error(
    `Element ${typeof selector === 'string' ? selector : 'locator'} not found after ${retries} attempts. Last error: ${lastError?.message}`
  );
}

/**
 * Wait for a specific API call to complete
 *
 * Waits for an API request to the specified endpoint to complete successfully.
 * Useful when an action triggers an API call and you need to wait for it.
 *
 * @param page - Playwright page object
 * @param endpoint - API endpoint pattern to match (e.g., '/api/cameras')
 * @param options - Optional configuration
 * @param options.timeout - Maximum time to wait in milliseconds (default: 10000)
 * @param options.method - HTTP method to match (default: any)
 * @param options.status - Expected HTTP status code (default: 200)
 *
 * @returns The Response object
 *
 * @example
 * ```typescript
 * test('data refreshes on button click', async ({ page }) => {
 *   await page.goto('/');
 *
 *   const responsePromise = waitForApiCall(page, '/api/events');
 *   await page.click('button.refresh');
 *   const response = await responsePromise;
 *
 *   expect(response.status()).toBe(200);
 * });
 * ```
 */
export async function waitForApiCall(
  page: Page,
  endpoint: string,
  options: {
    timeout?: number;
    method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    status?: number;
  } = {}
): Promise<{ url: () => string; status: () => number; json: () => Promise<unknown> }> {
  const { timeout = 10000, method, status = 200 } = options;

  try {
    const response = await page.waitForResponse(
      (res) => {
        const urlMatches = res.url().includes(endpoint.replace(/\*/g, ''));
        const methodMatches = !method || res.request().method() === method;
        const statusMatches = res.status() === status;

        return urlMatches && methodMatches && statusMatches;
      },
      { timeout }
    );

    return response;
  } catch (error) {
    if (error instanceof Error && error.message.includes('Timeout')) {
      throw new Error(`Timeout waiting for API call to ${endpoint} after ${timeout}ms`);
    }
    throw error;
  }
}

/**
 * Wait for multiple API calls to complete
 *
 * Waits for multiple API endpoints to respond, useful for pages that load
 * data from multiple sources.
 *
 * @param page - Playwright page object
 * @param endpoints - Array of endpoint patterns to wait for
 * @param timeout - Maximum time to wait in milliseconds (default: 15000)
 *
 * @returns Array of Response objects
 *
 * @example
 * ```typescript
 * test('dashboard loads all data', async ({ page }) => {
 *   const apiPromises = waitForApiCalls(page, [
 *     '/api/cameras',
 *     '/api/events',
 *     '/api/system/stats',
 *   ]);
 *
 *   await page.goto('/');
 *   const responses = await apiPromises;
 *
 *   responses.forEach(response => {
 *     expect(response.status()).toBe(200);
 *   });
 * });
 * ```
 */
export async function waitForApiCalls(
  page: Page,
  endpoints: string[],
  timeout: number = 15000
): Promise<{ url: () => string; status: () => number; json: () => Promise<unknown> }[]> {
  const promises = endpoints.map((endpoint) => waitForApiCall(page, endpoint, { timeout }));

  return Promise.all(promises);
}

/**
 * Wait for CSS animations to complete
 *
 * Waits for all CSS animations and transitions on the specified element to finish.
 * Useful for modal animations, slide-ins, and other animated UI elements.
 *
 * @param page - Playwright page object
 * @param selector - CSS selector or Playwright locator
 * @param options - Optional configuration
 * @param options.timeout - Maximum time to wait in milliseconds (default: 5000)
 * @param options.stabilityDelay - Additional delay after animation ends (default: 100)
 *
 * @example
 * ```typescript
 * test('modal animation completes', async ({ page }) => {
 *   await page.click('button.open-modal');
 *   await waitForAnimation(page, '.modal');
 *
 *   // Now safe to interact with modal
 *   await page.click('.modal button.submit');
 * });
 * ```
 */
export async function waitForAnimation(
  page: Page,
  selector: string | Locator,
  options: { timeout?: number; stabilityDelay?: number } = {}
): Promise<void> {
  const { timeout = 5000, stabilityDelay = 100 } = options;

  const locator = typeof selector === 'string' ? page.locator(selector) : selector;

  // Wait for element to be visible first
  await expect(locator).toBeVisible({ timeout });

  // Wait for animations to complete
  await page.waitForFunction(
    (sel) => {
      const element = typeof sel === 'string' ? document.querySelector(sel) : sel;
      if (!element) return false;

      // Get computed style
      const computedStyle = window.getComputedStyle(element as Element);

      // Check if animations are running
      const animationName = computedStyle.animationName;
      const animationPlayState = computedStyle.animationPlayState;
      const transitionProperty = computedStyle.transitionProperty;

      // Element is stable if:
      // - No animation is running (or animation is 'none')
      // - Animation is paused or finished
      // - No transition is in progress (or transition is 'none')
      const noAnimation = animationName === 'none' || animationPlayState === 'paused';
      const noTransition = transitionProperty === 'none' || transitionProperty === 'all';

      return noAnimation && noTransition;
    },
    typeof selector === 'string' ? selector : null,
    { timeout }
  );

  // Additional stability delay
  if (stabilityDelay > 0) {
    await page.waitForTimeout(stabilityDelay);
  }
}

/**
 * Wait for loading indicators to disappear
 *
 * Waits for all loading spinners, skeletons, and progress indicators to disappear
 * from the page.
 *
 * @param page - Playwright page object
 * @param timeout - Maximum time to wait in milliseconds (default: 10000)
 *
 * @example
 * ```typescript
 * test('data loads successfully', async ({ page }) => {
 *   await page.goto('/');
 *   await waitForLoadingToComplete(page);
 *
 *   // All data should now be loaded
 *   await expect(page.getByRole('table')).toBeVisible();
 * });
 * ```
 */
export async function waitForLoadingToComplete(page: Page, timeout: number = 10000): Promise<void> {
  await page
    .waitForFunction(
      () => {
        // Check for common loading indicators
        const spinners = document.querySelectorAll('.animate-spin, [data-loading="true"]');
        const skeletons = document.querySelectorAll('.animate-pulse, .skeleton');
        const progressBars = document.querySelectorAll('.progress, [role="progressbar"]');
        const loadingText = Array.from(document.querySelectorAll('*')).filter((el) =>
          el.textContent?.match(/loading|loading\.\.\.|please wait/i)
        );

        return spinners.length === 0 && skeletons.length === 0 && progressBars.length === 0 && loadingText.length === 0;
      },
      { timeout }
    )
    .catch(() => {
      // Continue if no loading indicators found
    });
}

/**
 * Wait for element text to change
 *
 * Waits for the text content of an element to change from its initial value.
 * Useful for watching counters, status indicators, or dynamic text.
 *
 * @param page - Playwright page object
 * @param selector - CSS selector or Playwright locator
 * @param options - Optional configuration
 * @param options.timeout - Maximum time to wait in milliseconds (default: 10000)
 * @param options.expectedText - Specific text to wait for (default: any change)
 *
 * @example
 * ```typescript
 * test('counter increments', async ({ page }) => {
 *   await page.goto('/');
 *   const initialText = await page.locator('.event-count').textContent();
 *
 *   await page.click('button.add-event');
 *   await waitForTextChange(page, '.event-count');
 *
 *   const newText = await page.locator('.event-count').textContent();
 *   expect(newText).not.toBe(initialText);
 * });
 * ```
 */
export async function waitForTextChange(
  page: Page,
  selector: string | Locator,
  options: { timeout?: number; expectedText?: string | RegExp } = {}
): Promise<void> {
  const { timeout = 10000, expectedText } = options;

  const locator = typeof selector === 'string' ? page.locator(selector) : selector;

  // Get initial text
  const initialText = await locator.textContent().catch(() => '');

  // Wait for text to change
  await page.waitForFunction(
    ({ sel, initial, expected }) => {
      const element = typeof sel === 'string' ? document.querySelector(sel) : sel;
      if (!element) return false;

      const currentText = element.textContent || '';

      // If specific text is expected, check for match
      if (expected !== null) {
        if (typeof expected === 'string') {
          return currentText.includes(expected);
        } else if (expected instanceof RegExp) {
          return expected.test(currentText);
        }
      }

      // Otherwise, just check if text changed
      return currentText !== initial;
    },
    { sel: typeof selector === 'string' ? selector : null, initial: initialText, expected: expectedText },
    { timeout }
  );
}

/**
 * Wait for element count to change
 *
 * Waits for the number of matching elements to change. Useful for waiting
 * for lists to update, items to be added/removed, etc.
 *
 * @param page - Playwright page object
 * @param selector - CSS selector
 * @param options - Optional configuration
 * @param options.timeout - Maximum time to wait in milliseconds (default: 10000)
 * @param options.expectedCount - Specific count to wait for
 * @param options.minCount - Minimum count to wait for
 *
 * @example
 * ```typescript
 * test('items are added to list', async ({ page }) => {
 *   await page.goto('/');
 *   await page.click('button.add-item');
 *
 *   await waitForElementCount(page, '.list-item', { minCount: 1 });
 *   await expect(page.locator('.list-item')).toHaveCount(1);
 * });
 * ```
 */
export async function waitForElementCount(
  page: Page,
  selector: string,
  options: { timeout?: number; expectedCount?: number; minCount?: number } = {}
): Promise<void> {
  const { timeout = 10000, expectedCount, minCount } = options;

  await page.waitForFunction(
    ({ sel, expected, min }) => {
      const elements = document.querySelectorAll(sel);
      const count = elements.length;

      if (expected !== undefined) {
        return count === expected;
      }

      if (min !== undefined) {
        return count >= min;
      }

      return true;
    },
    { sel: selector, expected: expectedCount, min: minCount },
    { timeout }
  );
}

/**
 * Wait for network to be idle
 *
 * Waits for all network requests to complete. Useful after actions that
 * trigger multiple API calls.
 *
 * @param page - Playwright page object
 * @param options - Optional configuration
 * @param options.timeout - Maximum time to wait in milliseconds (default: 30000)
 * @param options.idleTime - Time with no network activity to consider idle (default: 500)
 *
 * @example
 * ```typescript
 * test('form submission completes', async ({ page }) => {
 *   await page.goto('/');
 *   await page.click('button[type="submit"]');
 *
 *   await waitForNetworkIdle(page);
 *   await expect(page.getByText('Success')).toBeVisible();
 * });
 * ```
 */
export async function waitForNetworkIdle(
  page: Page,
  options: { timeout?: number; idleTime?: number } = {}
): Promise<void> {
  const { timeout = 30000, idleTime = 500 } = options;

  await page.waitForLoadState('networkidle', { timeout }).catch(() => {
    // Fallback: wait for idle time manually
    return page.waitForFunction(
      (idle) => {
        return new Promise<boolean>((resolve) => {
          let timeoutId: ReturnType<typeof setTimeout>;

          const resetTimeout = () => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => resolve(true), idle);
          };

          // Listen for fetch/xhr requests
          const originalFetch = window.fetch;
          window.fetch = function (...args) {
            resetTimeout();
            return originalFetch.apply(this, args);
          };

          // Set initial timeout
          resetTimeout();
        });
      },
      idleTime,
      { timeout }
    );
  });
}

/**
 * Wait with exponential backoff
 *
 * Retries an action with exponentially increasing delays between attempts.
 * Useful for flaky operations or waiting for eventual consistency.
 *
 * @param action - Async function to retry
 * @param options - Optional configuration
 * @param options.maxAttempts - Maximum retry attempts (default: 5)
 * @param options.initialDelayMs - Initial delay in ms (default: 100)
 * @param options.maxDelayMs - Maximum delay in ms (default: 5000)
 * @param options.multiplier - Delay multiplier (default: 2)
 *
 * @returns Result of successful action
 * @throws Error if all attempts fail
 *
 * @example
 * ```typescript
 * test('eventually consistent data', async ({ page }) => {
 *   await page.goto('/');
 *
 *   const result = await waitWithBackoff(async () => {
 *     const response = await fetch('/api/status');
 *     const data = await response.json();
 *     if (data.status !== 'ready') {
 *       throw new Error('Not ready yet');
 *     }
 *     return data;
 *   });
 *
 *   expect(result.status).toBe('ready');
 * });
 * ```
 */
export async function waitWithBackoff<T>(
  action: () => Promise<T>,
  options: {
    maxAttempts?: number;
    initialDelayMs?: number;
    maxDelayMs?: number;
    multiplier?: number;
  } = {}
): Promise<T> {
  const { maxAttempts = 5, initialDelayMs = 100, maxDelayMs = 5000, multiplier = 2 } = options;

  let lastError: Error | unknown;
  let delay = initialDelayMs;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await action();
    } catch (error) {
      lastError = error;

      if (attempt < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, delay));
        delay = Math.min(delay * multiplier, maxDelayMs);
      }
    }
  }

  throw new Error(
    `Action failed after ${maxAttempts} attempts with exponential backoff. Last error: ${lastError instanceof Error ? lastError.message : String(lastError)}`
  );
}
