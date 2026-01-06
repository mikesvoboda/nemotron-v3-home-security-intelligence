/**
 * BasePage - Base class for all Page Objects
 *
 * Provides common selectors, wait helpers, and navigation utilities
 * that are shared across all page objects.
 */

import type { Page, Locator, Response } from '@playwright/test';
import { expect } from '@playwright/test';

/**
 * Options for waitForApiResponse method
 */
export interface WaitForApiOptions {
  /** Timeout in milliseconds (default: 10000) */
  timeout?: number;
  /** Expected HTTP status code (default: 200) */
  status?: number;
  /** HTTP method to match (default: any) */
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
}

export class BasePage {
  readonly page: Page;

  // Common Layout Elements
  readonly header: Locator;
  readonly sidebar: Locator;
  readonly mainContent: Locator;

  // Header Elements
  readonly brandingLogo: Locator;
  readonly systemStatusIndicator: Locator;

  // Navigation Links (in sidebar)
  readonly navDashboard: Locator;
  readonly navTimeline: Locator;
  readonly navAlerts: Locator;
  readonly navEntities: Locator;
  readonly navLogs: Locator;
  readonly navAudit: Locator;
  readonly navSystem: Locator;
  readonly navSettings: Locator;

  // Common timeout for page loads
  // Increased from 5000ms to 10000ms for webkit browser compatibility
  // (webkit has slower modal animations and element stability checks)
  readonly pageLoadTimeout = 10000;

  constructor(page: Page) {
    this.page = page;

    // Layout
    this.header = page.locator('header').first();
    this.sidebar = page.locator('aside').first();
    this.mainContent = page.locator('main').first();

    // Header
    this.brandingLogo = page.getByText(/NVIDIA/i).first();
    this.systemStatusIndicator = page.getByText(/System/i).first();

    // Navigation - using aria labels or text content
    this.navDashboard = page.locator('aside a[href="/"], aside button').filter({ hasText: /dashboard/i });
    this.navTimeline = page.locator('aside a[href="/timeline"]');
    this.navAlerts = page.locator('aside a[href="/alerts"]');
    this.navEntities = page.locator('aside a[href="/entities"]');
    this.navLogs = page.locator('aside a[href="/logs"]');
    this.navAudit = page.locator('aside a[href="/audit"]');
    this.navSystem = page.locator('aside a[href="/system"]');
    this.navSettings = page.locator('aside a[href="/settings"]');
  }

  /**
   * Navigate to this page (to be overridden by subclasses)
   */
  async goto(path: string = '/'): Promise<void> {
    await this.page.goto(path, { waitUntil: 'domcontentloaded' });
  }

  /**
   * Wait for the page to be fully loaded
   */
  async waitForPageLoad(): Promise<void> {
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Block unnecessary resources to speed up page loads
   * Call this before navigation to prevent loading images, analytics, and fonts
   */
  async blockUnnecessaryResources(): Promise<void> {
    await this.page.route('**/*.{png,jpg,jpeg,gif,webp,svg}', route => route.abort());
    await this.page.route('**/*analytics*', route => route.abort());
    await this.page.route('**/fonts.googleapis.com/**', route => route.abort());
  }

  /**
   * Check if header is visible
   */
  async expectHeaderVisible(): Promise<void> {
    await expect(this.header).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Check if sidebar is visible
   */
  async expectSidebarVisible(): Promise<void> {
    await expect(this.sidebar).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Check if the layout is complete (header + sidebar visible)
   */
  async expectLayoutLoaded(): Promise<void> {
    await this.expectHeaderVisible();
    await this.expectSidebarVisible();
  }

  /**
   * Navigate to Dashboard via sidebar
   */
  async navigateToDashboard(): Promise<void> {
    await this.page.goto('/');
  }

  /**
   * Navigate to Timeline via sidebar
   */
  async navigateToTimeline(): Promise<void> {
    await this.page.goto('/timeline');
  }

  /**
   * Navigate to Alerts via sidebar
   */
  async navigateToAlerts(): Promise<void> {
    await this.page.goto('/alerts');
  }

  /**
   * Navigate to Entities via sidebar
   */
  async navigateToEntities(): Promise<void> {
    await this.page.goto('/entities');
  }

  /**
   * Navigate to Logs via sidebar
   */
  async navigateToLogs(): Promise<void> {
    await this.page.goto('/logs');
  }

  /**
   * Navigate to Audit via sidebar
   */
  async navigateToAudit(): Promise<void> {
    await this.page.goto('/audit');
  }

  /**
   * Navigate to System via sidebar
   */
  async navigateToSystem(): Promise<void> {
    await this.page.goto('/system');
  }

  /**
   * Navigate to Settings via sidebar
   */
  async navigateToSettings(): Promise<void> {
    await this.page.goto('/settings');
  }

  /**
   * Get current URL path
   */
  async getCurrentPath(): Promise<string> {
    const url = new URL(this.page.url());
    return url.pathname;
  }

  /**
   * Wait for a specific heading to appear
   */
  async waitForHeading(text: string | RegExp): Promise<void> {
    await expect(
      this.page.getByRole('heading', { name: text })
    ).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Wait for loading to complete (no loading spinners/skeletons visible)
   */
  async waitForLoadingComplete(): Promise<void> {
    // Wait for common loading indicators to disappear
    await this.page.waitForFunction(() => {
      const spinners = document.querySelectorAll('.animate-spin, .animate-pulse');
      return spinners.length === 0;
    }, { timeout: this.pageLoadTimeout }).catch(() => {
      // Ignore if loading indicators aren't found
    });
  }

  /**
   * Check if disconnected indicator is shown
   */
  async isDisconnected(): Promise<boolean> {
    const disconnected = this.page.getByText(/Disconnected/i);
    return disconnected.isVisible().catch(() => false);
  }

  /**
   * Click a button by its accessible name
   */
  async clickButton(name: string | RegExp): Promise<void> {
    await this.page.getByRole('button', { name }).click();
  }

  /**
   * Fill an input field by label
   */
  async fillInput(label: string | RegExp, value: string): Promise<void> {
    await this.page.getByLabel(label).fill(value);
  }

  /**
   * Select an option from a dropdown by label
   */
  async selectOption(label: string | RegExp, value: string): Promise<void> {
    await this.page.getByLabel(label).selectOption(value);
  }

  /**
   * Check if an element with text is visible
   */
  async hasText(text: string | RegExp): Promise<boolean> {
    return this.page.getByText(text).isVisible().catch(() => false);
  }

  /**
   * Wait for text to appear on page
   */
  async waitForText(text: string | RegExp): Promise<void> {
    await expect(this.page.getByText(text).first()).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Take a screenshot for debugging
   */
  async screenshot(name: string): Promise<void> {
    await this.page.screenshot({ path: `test-results/${name}.png` });
  }

  /**
   * Wait for a specific API endpoint to respond (NEM-1480)
   *
   * This method waits for an API request to a specific endpoint to complete,
   * with support for timeout, status code, and HTTP method matching.
   *
   * @param endpoint - The API endpoint pattern to match (e.g., '/api/cameras')
   * @param options - Optional configuration for timeout, status, and method matching
   * @returns The Response object for further inspection
   * @throws Error if the request times out or status doesn't match
   *
   * @example
   * // Wait for cameras API to respond
   * const response = await basePage.waitForApiResponse('/api/cameras');
   *
   * // Wait for events API with custom timeout
   * const response = await basePage.waitForApiResponse('/api/events', { timeout: 15000 });
   *
   * // Wait for a POST request
   * const response = await basePage.waitForApiResponse('/api/alerts/rules', { method: 'POST', status: 201 });
   *
   * // Use with action that triggers the request
   * const [response] = await Promise.all([
   *   basePage.waitForApiResponse('/api/cameras'),
   *   page.click('button.refresh'),
   * ]);
   */
  async waitForApiResponse(
    endpoint: string,
    options: WaitForApiOptions = {}
  ): Promise<Response> {
    const { timeout = 10000, status, method } = options;

    // Build the URL pattern - support both absolute and relative paths
    const urlPattern = endpoint.startsWith('*') ? endpoint : `**${endpoint}*`;

    try {
      const response = await this.page.waitForResponse(
        (res) => {
          const urlMatches = res.url().includes(endpoint.replace(/\*/g, ''));
          const methodMatches = !method || res.request().method() === method;
          return urlMatches && methodMatches;
        },
        { timeout }
      );

      // Validate status if specified
      if (status !== undefined && response.status() !== status) {
        throw new Error(
          `Expected status ${status} but got ${response.status()} for ${endpoint}`
        );
      }

      return response;
    } catch (error) {
      if (error instanceof Error && error.message.includes('Timeout')) {
        throw new Error(
          `Timeout waiting for API response from ${endpoint} after ${timeout}ms`
        );
      }
      throw error;
    }
  }

  /**
   * Wait for multiple API endpoints to respond (NEM-1480)
   *
   * Useful when a page action triggers multiple API calls simultaneously.
   *
   * @param endpoints - Array of endpoint patterns to wait for
   * @param options - Optional configuration for timeout (applies to all)
   * @returns Array of Response objects in the same order as endpoints
   *
   * @example
   * // Wait for dashboard data to load
   * const responses = await basePage.waitForMultipleApiResponses([
   *   '/api/cameras',
   *   '/api/events',
   *   '/api/system/stats',
   * ]);
   */
  async waitForMultipleApiResponses(
    endpoints: string[],
    options: WaitForApiOptions = {}
  ): Promise<Response[]> {
    const promises = endpoints.map((endpoint) =>
      this.waitForApiResponse(endpoint, options)
    );
    return Promise.all(promises);
  }

  /**
   * Perform an action and wait for the API response (NEM-1480)
   *
   * Convenience method that combines triggering an action with waiting
   * for the resulting API call.
   *
   * @param action - Async function that triggers the API call
   * @param endpoint - The API endpoint pattern to wait for
   * @param options - Optional configuration for timeout, status, and method
   * @returns The Response object
   *
   * @example
   * // Click refresh and wait for cameras to reload
   * const response = await basePage.performActionAndWaitForApi(
   *   () => page.click('button.refresh'),
   *   '/api/cameras'
   * );
   *
   * // Submit form and wait for POST
   * const response = await basePage.performActionAndWaitForApi(
   *   () => page.click('button[type="submit"]'),
   *   '/api/alerts/rules',
   *   { method: 'POST', status: 201 }
   * );
   */
  async performActionAndWaitForApi(
    action: () => Promise<void>,
    endpoint: string,
    options: WaitForApiOptions = {}
  ): Promise<Response> {
    const [response] = await Promise.all([
      this.waitForApiResponse(endpoint, options),
      action(),
    ]);
    return response;
  }
}
