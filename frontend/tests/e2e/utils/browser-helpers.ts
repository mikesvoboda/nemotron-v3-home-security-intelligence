/**
 * Browser Helper Utilities for E2E Tests
 *
 * Provides utilities for browser-level operations including viewport management,
 * theme switching, network throttling, and storage manipulation.
 */

import type { Page, BrowserContext } from '@playwright/test';

/**
 * Viewport preset configurations
 */
export const VIEWPORT_PRESETS = {
  // Desktop
  desktop: { width: 1920, height: 1080 },
  desktopSmall: { width: 1366, height: 768 },
  desktopLarge: { width: 2560, height: 1440 },

  // Laptop
  laptop: { width: 1440, height: 900 },
  laptopSmall: { width: 1280, height: 800 },

  // Tablet
  tablet: { width: 1024, height: 768 },
  tabletPortrait: { width: 768, height: 1024 },
  ipadPro: { width: 1024, height: 1366 },

  // Mobile
  mobile: { width: 375, height: 667 },
  mobileLarge: { width: 414, height: 896 },
  mobileSmall: { width: 320, height: 568 },
} as const;

/**
 * Set viewport size using preset or custom dimensions
 *
 * @param page - Playwright page object
 * @param viewport - Preset name or custom dimensions
 *
 * @example
 * ```typescript
 * test('responsive layout', async ({ page }) => {
 *   // Use preset
 *   await setViewport(page, 'tablet');
 *   await page.goto('/');
 *
 *   // Or custom dimensions
 *   await setViewport(page, { width: 800, height: 600 });
 * });
 * ```
 */
export async function setViewport(
  page: Page,
  viewport: keyof typeof VIEWPORT_PRESETS | { width: number; height: number }
): Promise<void> {
  const dimensions = typeof viewport === 'string' ? VIEWPORT_PRESETS[viewport] : viewport;

  await page.setViewportSize(dimensions);
}

/**
 * Enable dark mode
 *
 * Toggles dark mode by setting the appropriate class or theme preference.
 * Works with Tailwind's dark mode implementation.
 *
 * @param page - Playwright page object
 * @param options - Optional configuration
 * @param options.method - Method to enable dark mode (default: 'class')
 *
 * @example
 * ```typescript
 * test('dark mode styling', async ({ page }) => {
 *   await page.goto('/');
 *   await enableDarkMode(page);
 *
 *   // Verify dark mode styles
 *   const bg = await page.locator('body').evaluate(el =>
 *     window.getComputedStyle(el).backgroundColor
 *   );
 *   expect(bg).toContain('rgb(0, 0, 0)'); // Dark background
 * });
 * ```
 */
export async function enableDarkMode(
  page: Page,
  options: { method?: 'class' | 'media' | 'localStorage' } = {}
): Promise<void> {
  const { method = 'class' } = options;

  switch (method) {
    case 'class':
      // Add dark class to html element (Tailwind default)
      await page.evaluate(() => {
        document.documentElement.classList.add('dark');
      });
      break;

    case 'media':
      // Emulate prefers-color-scheme: dark
      await page.emulateMedia({ colorScheme: 'dark' });
      break;

    case 'localStorage':
      // Set theme preference in localStorage
      await page.evaluate(() => {
        localStorage.setItem('theme', 'dark');
        localStorage.setItem('color-scheme', 'dark');
        document.documentElement.classList.add('dark');
      });
      break;
  }

  // Brief wait for styles to apply
  await page.waitForTimeout(100);
}

/**
 * Disable dark mode (enable light mode)
 *
 * @param page - Playwright page object
 * @param options - Optional configuration
 *
 * @example
 * ```typescript
 * test('light mode styling', async ({ page }) => {
 *   await page.goto('/');
 *   await disableDarkMode(page);
 *
 *   // Verify light mode styles
 *   const bg = await page.locator('body').evaluate(el =>
 *     window.getComputedStyle(el).backgroundColor
 *   );
 *   expect(bg).toContain('rgb(255, 255, 255)'); // Light background
 * });
 * ```
 */
export async function disableDarkMode(
  page: Page,
  options: { method?: 'class' | 'media' | 'localStorage' } = {}
): Promise<void> {
  const { method = 'class' } = options;

  switch (method) {
    case 'class':
      await page.evaluate(() => {
        document.documentElement.classList.remove('dark');
      });
      break;

    case 'media':
      await page.emulateMedia({ colorScheme: 'light' });
      break;

    case 'localStorage':
      await page.evaluate(() => {
        localStorage.setItem('theme', 'light');
        localStorage.setItem('color-scheme', 'light');
        document.documentElement.classList.remove('dark');
      });
      break;
  }

  await page.waitForTimeout(100);
}

/**
 * Toggle dark mode
 *
 * @param page - Playwright page object
 * @returns Current theme state ('dark' | 'light')
 *
 * @example
 * ```typescript
 * test('theme toggle works', async ({ page }) => {
 *   await page.goto('/');
 *
 *   const theme = await toggleDarkMode(page);
 *   expect(theme).toBe('dark');
 *
 *   const theme2 = await toggleDarkMode(page);
 *   expect(theme2).toBe('light');
 * });
 * ```
 */
export async function toggleDarkMode(page: Page): Promise<'dark' | 'light'> {
  const isDark = await page.evaluate(() => {
    return document.documentElement.classList.contains('dark');
  });

  if (isDark) {
    await disableDarkMode(page);
    return 'light';
  } else {
    await enableDarkMode(page);
    return 'dark';
  }
}

/**
 * Network throttling presets
 */
export const NETWORK_PRESETS = {
  // Mobile networks
  '2g': { downloadThroughput: (50 * 1024) / 8, uploadThroughput: (20 * 1024) / 8, latency: 300 },
  '3g': { downloadThroughput: (1.5 * 1024 * 1024) / 8, uploadThroughput: (750 * 1024) / 8, latency: 100 },
  '4g': { downloadThroughput: (10 * 1024 * 1024) / 8, uploadThroughput: (5 * 1024 * 1024) / 8, latency: 20 },

  // Broadband
  dsl: { downloadThroughput: (2 * 1024 * 1024) / 8, uploadThroughput: (1 * 1024 * 1024) / 8, latency: 5 },
  cable: { downloadThroughput: (5 * 1024 * 1024) / 8, uploadThroughput: (1 * 1024 * 1024) / 8, latency: 5 },

  // Degraded
  slow: { downloadThroughput: (500 * 1024) / 8, uploadThroughput: (100 * 1024) / 8, latency: 200 },
  offline: { downloadThroughput: 0, uploadThroughput: 0, latency: 0 },
} as const;

/**
 * Simulate slow network conditions
 *
 * Throttles network speed to simulate various connection types.
 * Useful for testing loading states and error handling.
 *
 * @param page - Playwright page object
 * @param preset - Network preset name or custom throttling config
 *
 * @example
 * ```typescript
 * test('loading state on slow network', async ({ page }) => {
 *   await simulateSlowNetwork(page, '3g');
 *   await page.goto('/');
 *
 *   // Loading indicator should appear
 *   await expect(page.locator('.loading-spinner')).toBeVisible();
 * });
 * ```
 */
export async function simulateSlowNetwork(
  page: Page,
  preset: keyof typeof NETWORK_PRESETS | { downloadThroughput: number; uploadThroughput: number; latency: number }
): Promise<void> {
  const config = typeof preset === 'string' ? NETWORK_PRESETS[preset] : preset;

  const client = await page.context().newCDPSession(page);
  await client.send('Network.emulateNetworkConditions', {
    offline: false,
    downloadThroughput: config.downloadThroughput,
    uploadThroughput: config.uploadThroughput,
    latency: config.latency,
  });
}

/**
 * Disable network throttling
 *
 * @param page - Playwright page object
 *
 * @example
 * ```typescript
 * test.afterEach(async ({ page }) => {
 *   // Reset network conditions after each test
 *   await disableNetworkThrottling(page);
 * });
 * ```
 */
export async function disableNetworkThrottling(page: Page): Promise<void> {
  const client = await page.context().newCDPSession(page);
  await client.send('Network.emulateNetworkConditions', {
    offline: false,
    downloadThroughput: -1, // No throttling
    uploadThroughput: -1,
    latency: 0,
  });
}

/**
 * Simulate offline mode
 *
 * @param page - Playwright page object
 *
 * @example
 * ```typescript
 * test('offline error handling', async ({ page }) => {
 *   await page.goto('/');
 *   await simulateOfflineMode(page);
 *
 *   await page.click('button.refresh');
 *   await expect(page.getByText('Connection lost')).toBeVisible();
 * });
 * ```
 */
export async function simulateOfflineMode(page: Page): Promise<void> {
  await page.context().setOffline(true);
}

/**
 * Restore online mode
 *
 * @param page - Playwright page object
 */
export async function restoreOnlineMode(page: Page): Promise<void> {
  await page.context().setOffline(false);
}

/**
 * Clear browser storage (localStorage, sessionStorage, cookies)
 *
 * @param page - Playwright page object
 * @param options - Optional configuration
 * @param options.preserveCookies - Cookie names to preserve (default: [])
 * @param options.preserveLocalStorage - localStorage keys to preserve (default: [])
 *
 * @example
 * ```typescript
 * test.beforeEach(async ({ page }) => {
 *   await clearStorage(page);
 * });
 *
 * test('preserves auth tokens', async ({ page }) => {
 *   await clearStorage(page, {
 *     preserveCookies: ['session_id'],
 *     preserveLocalStorage: ['auth_token']
 *   });
 * });
 * ```
 */
export async function clearStorage(
  page: Page,
  options: { preserveCookies?: string[]; preserveLocalStorage?: string[] } = {}
): Promise<void> {
  const { preserveCookies = [], preserveLocalStorage = [] } = options;

  // Check if we're on a valid page (not about:blank)
  const url = page.url();
  if (url === 'about:blank' || url === '') {
    // Skip storage clearing - page hasn't navigated yet
    // Only clear cookies which don't require page context
  } else {
    // Clear localStorage and sessionStorage - wrap in try-catch for security restrictions
    try {
      await page.evaluate(
        (keysToPreserve) => {
          try {
            // Save values to preserve
            const savedValues: Record<string, string> = {};
            keysToPreserve.forEach((key) => {
              const value = localStorage.getItem(key);
              if (value !== null) {
                savedValues[key] = value;
              }
            });

            // Clear all storage
            localStorage.clear();
            sessionStorage.clear();

            // Restore preserved values
            Object.entries(savedValues).forEach(([key, value]) => {
              localStorage.setItem(key, value);
            });
          } catch {
            // Ignore security errors (e.g., cross-origin frames)
          }
        },
        preserveLocalStorage
      );
    } catch {
      // Ignore evaluate errors (page context issues)
    }
  }

  // Clear cookies
  const allCookies = await page.context().cookies();

  if (preserveCookies.length > 0) {
    // Remove only cookies not in preserve list
    const cookiesToRemove = allCookies.filter((cookie) => !preserveCookies.includes(cookie.name));
    await page.context().clearCookies();

    // Restore preserved cookies
    const cookiesToRestore = allCookies.filter((cookie) => preserveCookies.includes(cookie.name));
    if (cookiesToRestore.length > 0) {
      await page.context().addCookies(cookiesToRestore);
    }
  } else {
    // Clear all cookies
    await page.context().clearCookies();
  }
}

/**
 * Set localStorage item
 *
 * @param page - Playwright page object
 * @param key - Storage key
 * @param value - Storage value (will be JSON stringified)
 *
 * @example
 * ```typescript
 * test('uses saved preferences', async ({ page }) => {
 *   await setLocalStorage(page, 'theme', 'dark');
 *   await setLocalStorage(page, 'language', 'en');
 *
 *   await page.goto('/');
 *   // App should load with dark theme and English language
 * });
 * ```
 */
export async function setLocalStorage(page: Page, key: string, value: unknown): Promise<void> {
  await page.evaluate(
    ({ k, v }) => {
      localStorage.setItem(k, typeof v === 'string' ? v : JSON.stringify(v));
    },
    { k: key, v: value }
  );
}

/**
 * Get localStorage item
 *
 * @param page - Playwright page object
 * @param key - Storage key
 * @returns Storage value (parsed from JSON if applicable)
 *
 * @example
 * ```typescript
 * test('saves preferences', async ({ page }) => {
 *   await page.goto('/');
 *   await page.click('button.toggle-dark-mode');
 *
 *   const theme = await getLocalStorage(page, 'theme');
 *   expect(theme).toBe('dark');
 * });
 * ```
 */
export async function getLocalStorage(page: Page, key: string): Promise<unknown> {
  return page.evaluate((k) => {
    const value = localStorage.getItem(k);
    if (value === null) return null;

    try {
      return JSON.parse(value);
    } catch {
      return value;
    }
  }, key);
}

/**
 * Set sessionStorage item
 *
 * @param page - Playwright page object
 * @param key - Storage key
 * @param value - Storage value (will be JSON stringified)
 */
export async function setSessionStorage(page: Page, key: string, value: unknown): Promise<void> {
  await page.evaluate(
    ({ k, v }) => {
      sessionStorage.setItem(k, typeof v === 'string' ? v : JSON.stringify(v));
    },
    { k: key, v: value }
  );
}

/**
 * Get sessionStorage item
 *
 * @param page - Playwright page object
 * @param key - Storage key
 * @returns Storage value (parsed from JSON if applicable)
 */
export async function getSessionStorage(page: Page, key: string): Promise<unknown> {
  return page.evaluate((k) => {
    const value = sessionStorage.getItem(k);
    if (value === null) return null;

    try {
      return JSON.parse(value);
    } catch {
      return value;
    }
  }, key);
}

/**
 * Set cookie
 *
 * @param context - Playwright browser context
 * @param name - Cookie name
 * @param value - Cookie value
 * @param options - Optional cookie options
 *
 * @example
 * ```typescript
 * test('authenticated user', async ({ page, context }) => {
 *   await setCookie(context, 'session_id', 'abc123', {
 *     domain: 'localhost',
 *     path: '/',
 *     expires: Date.now() / 1000 + 3600 // 1 hour
 *   });
 *
 *   await page.goto('/');
 *   // User should be authenticated
 * });
 * ```
 */
export async function setCookie(
  context: BrowserContext,
  name: string,
  value: string,
  options: {
    domain?: string;
    path?: string;
    expires?: number;
    httpOnly?: boolean;
    secure?: boolean;
    sameSite?: 'Strict' | 'Lax' | 'None';
  } = {}
): Promise<void> {
  await context.addCookies([
    {
      name,
      value,
      domain: options.domain || 'localhost',
      path: options.path || '/',
      expires: options.expires,
      httpOnly: options.httpOnly || false,
      secure: options.secure || false,
      sameSite: options.sameSite || 'Lax',
    },
  ]);
}

/**
 * Get cookie by name
 *
 * @param context - Playwright browser context
 * @param name - Cookie name
 * @returns Cookie value or null if not found
 *
 * @example
 * ```typescript
 * test('session is created', async ({ page, context }) => {
 *   await page.goto('/login');
 *   await page.fill('input[name="username"]', 'user');
 *   await page.fill('input[name="password"]', 'pass');
 *   await page.click('button[type="submit"]');
 *
 *   const sessionId = await getCookie(context, 'session_id');
 *   expect(sessionId).toBeTruthy();
 * });
 * ```
 */
export async function getCookie(context: BrowserContext, name: string): Promise<string | null> {
  const cookies = await context.cookies();
  const cookie = cookies.find((c) => c.name === name);
  return cookie?.value || null;
}

/**
 * Block resources by type to speed up tests
 *
 * @param page - Playwright page object
 * @param resourceTypes - Array of resource types to block
 *
 * @example
 * ```typescript
 * test('fast test without images', async ({ page }) => {
 *   await blockResources(page, ['image', 'stylesheet', 'font']);
 *   await page.goto('/');
 *
 *   // Page loads faster without images and styles
 * });
 * ```
 */
export async function blockResources(
  page: Page,
  resourceTypes: ('document' | 'stylesheet' | 'image' | 'media' | 'font' | 'script' | 'xhr' | 'fetch')[]
): Promise<void> {
  await page.route('**/*', (route) => {
    const type = route.request().resourceType();
    if (resourceTypes.includes(type as typeof resourceTypes[number])) {
      route.abort();
    } else {
      route.continue();
    }
  });
}

/**
 * Set geolocation
 *
 * @param context - Playwright browser context
 * @param latitude - Latitude coordinate
 * @param longitude - Longitude coordinate
 * @param accuracy - Location accuracy in meters (optional)
 *
 * @example
 * ```typescript
 * test('location-based feature', async ({ page, context }) => {
 *   // Set location to San Francisco
 *   await setGeolocation(context, 37.7749, -122.4194);
 *
 *   await context.grantPermissions(['geolocation']);
 *   await page.goto('/');
 *
 *   // App should show San Francisco timezone/weather
 * });
 * ```
 */
export async function setGeolocation(
  context: BrowserContext,
  latitude: number,
  longitude: number,
  accuracy?: number
): Promise<void> {
  await context.setGeolocation({ latitude, longitude, accuracy });
}

/**
 * Set timezone
 *
 * @param context - Playwright browser context
 * @param timezoneId - IANA timezone identifier (e.g., 'America/New_York')
 *
 * @example
 * ```typescript
 * test('timezone display', async ({ page, context }) => {
 *   await setTimezone(context, 'America/New_York');
 *   await page.goto('/');
 *
 *   // Times should display in EST/EDT
 * });
 * ```
 */
export async function setTimezone(context: BrowserContext, timezoneId: string): Promise<void> {
  await context.addInitScript({ path: require.resolve('timezone-mock') });
  await context.addInitScript(
    (tz) => {
      // @ts-expect-error - timezone-mock library
      window.timezoneMock?.register?.(tz);
    },
    timezoneId
  );
}

/**
 * Take full page screenshot
 *
 * @param page - Playwright page object
 * @param path - File path to save screenshot
 *
 * @example
 * ```typescript
 * test('visual regression', async ({ page }) => {
 *   await page.goto('/');
 *   await takeFullPageScreenshot(page, 'screenshots/homepage.png');
 * });
 * ```
 */
export async function takeFullPageScreenshot(page: Page, path: string): Promise<void> {
  await page.screenshot({ path, fullPage: true });
}

/**
 * Get browser console logs
 *
 * Collects console messages from the browser.
 *
 * @param page - Playwright page object
 * @returns Promise that resolves with array of console messages
 *
 * @example
 * ```typescript
 * test('no console errors', async ({ page }) => {
 *   const logs = await getConsoleLogs(page);
 *
 *   await page.goto('/');
 *   await page.waitForTimeout(2000);
 *
 *   const messages = await logs;
 *   const errors = messages.filter(msg => msg.type === 'error');
 *   expect(errors).toHaveLength(0);
 * });
 * ```
 */
export function getConsoleLogs(page: Page): Promise<{ type: string; text: string; location?: string }[]> {
  const logs: { type: string; text: string; location?: string }[] = [];

  page.on('console', (msg) => {
    logs.push({
      type: msg.type(),
      text: msg.text(),
      location: msg.location()?.url,
    });
  });

  return Promise.resolve(logs);
}
