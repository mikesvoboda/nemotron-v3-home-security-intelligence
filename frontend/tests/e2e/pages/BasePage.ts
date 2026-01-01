/**
 * BasePage - Base class for all Page Objects
 *
 * Provides common selectors, wait helpers, and navigation utilities
 * that are shared across all page objects.
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';

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
  readonly pageLoadTimeout = 5000;

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
}
