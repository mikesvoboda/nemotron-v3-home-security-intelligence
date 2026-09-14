/**
 * AIPerformancePage - Page Object for the AI Performance Dashboard
 *
 * The AI Performance page now embeds a Grafana iframe for all metrics.
 * This page object provides selectors and interactions for:
 * - Page title and header
 * - Grafana external link
 * - Refresh button
 * - Grafana iframe
 * - Loading/error states
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class AIPerformancePage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;

  // Controls
  readonly refreshButton: Locator;

  // Grafana integration
  readonly grafanaExternalLink: Locator;
  readonly grafanaLink: Locator; // Alias for backwards compatibility
  readonly grafanaIframe: Locator;

  // Error state
  readonly errorBanner: Locator;

  // Loading/Error States
  readonly loadingState: Locator;
  readonly errorState: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /AI Performance/i });

    // Controls
    this.refreshButton = page.getByTestId('ai-performance-refresh-button');

    // Grafana integration - now uses external link and iframe
    this.grafanaExternalLink = page.getByTestId('grafana-external-link');
    this.grafanaLink = this.grafanaExternalLink; // Alias for backwards compatibility
    this.grafanaIframe = page.getByTestId('grafana-iframe');

    // Error state
    this.errorBanner = page.getByTestId('ai-performance-error');

    // Loading/Error States
    this.loadingState = page.getByTestId('ai-performance-loading');
    this.errorState = page.locator('[data-testid="ai-performance-page"] .text-red-500');
  }

  /**
   * Navigate to the AI Performance page
   */
  async goto(): Promise<void> {
    await this.page.goto('/ai');
  }

  /**
   * Wait for the AI Performance page to fully load
   */
  async waitForPageLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Wait for data to load (iframe visible)
   */
  async waitForDataLoad(): Promise<void> {
    await expect(this.grafanaIframe).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Click refresh button
   */
  async refresh(): Promise<void> {
    await this.refreshButton.click();
  }

  /**
   * Check if Grafana external link is visible (replaces old banner check)
   */
  async hasGrafanaBanner(): Promise<boolean> {
    // The "banner" is now the external link in the header
    return this.grafanaExternalLink.isVisible().catch(() => false);
  }

  /**
   * Get Grafana link URL
   */
  async getGrafanaLinkUrl(): Promise<string | null> {
    return this.grafanaExternalLink.getAttribute('href');
  }

  /**
   * Check if Grafana iframe is visible
   */
  async hasGrafanaIframe(): Promise<boolean> {
    return this.grafanaIframe.isVisible().catch(() => false);
  }

  /**
   * Get Grafana iframe src URL
   */
  async getGrafanaIframeSrc(): Promise<string | null> {
    return this.grafanaIframe.getAttribute('src');
  }

  /**
   * Check if loading state is shown
   */
  async isLoading(): Promise<boolean> {
    return this.loadingState.isVisible().catch(() => false);
  }

  /**
   * Check if error state is shown
   */
  async hasError(): Promise<boolean> {
    return this.errorBanner.isVisible().catch(() => false);
  }

  /**
   * Navigate to AI Performance from sidebar
   */
  async navigateFromSidebar(): Promise<void> {
    const navLink = this.page.locator('aside a[href="/ai"]');
    await navLink.click();
    await this.waitForPageLoad();
  }
}
