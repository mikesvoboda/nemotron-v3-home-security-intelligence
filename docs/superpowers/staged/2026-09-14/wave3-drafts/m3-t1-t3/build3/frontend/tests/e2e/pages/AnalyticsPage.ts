/**
 * AnalyticsPage - Page Object for the Analytics Dashboard
 *
 * Provides selectors and interactions for the Grafana-based Analytics page:
 * - Page heading and title
 * - Grafana iframe embedding
 * - Refresh and external link controls
 * - Loading and error states
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class AnalyticsPage extends BasePage {
  // Page container
  readonly pageContainer: Locator;

  // Page heading
  readonly pageTitle: Locator;

  // Controls
  readonly refreshButton: Locator;
  readonly externalLink: Locator;

  // Grafana iframe
  readonly grafanaIframe: Locator;

  // Loading/Error States
  readonly loadingState: Locator;
  readonly errorBanner: Locator;

  constructor(page: Page) {
    super(page);

    // Page container
    this.pageContainer = page.getByTestId('analytics-page');

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /Analytics/i });

    // Controls
    this.refreshButton = page.getByTestId('analytics-refresh-button');
    this.externalLink = page.getByTestId('grafana-external-link');

    // Grafana iframe
    this.grafanaIframe = page.getByTestId('grafana-iframe');

    // Loading/Error States
    this.loadingState = page.getByTestId('analytics-loading');
    this.errorBanner = page.getByTestId('analytics-error');
  }

  /**
   * Navigate to the Analytics page
   */
  async goto(): Promise<void> {
    await this.page.goto('/analytics');
  }

  /**
   * Wait for the Analytics page to fully load
   */
  async waitForPageLoad(): Promise<void> {
    // Wait for either the page container or loading state
    await expect(
      this.pageContainer.or(this.loadingState)
    ).toBeVisible({ timeout: this.pageLoadTimeout });

    // If loading, wait for actual page
    if (await this.loadingState.isVisible().catch(() => false)) {
      await expect(this.pageContainer).toBeVisible({ timeout: this.pageLoadTimeout });
    }
  }

  /**
   * Wait for Grafana iframe to be present
   */
  async waitForGrafanaIframe(): Promise<void> {
    await expect(this.grafanaIframe).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Click refresh button to reload the Grafana dashboard
   */
  async refresh(): Promise<void> {
    await this.refreshButton.click();
  }

  /**
   * Check if loading state is visible
   */
  async isLoading(): Promise<boolean> {
    return this.loadingState.isVisible().catch(() => false);
  }

  /**
   * Check if error banner is shown
   */
  async hasError(): Promise<boolean> {
    return this.errorBanner.isVisible().catch(() => false);
  }

  /**
   * Check if Grafana iframe is displayed
   */
  async hasGrafanaIframe(): Promise<boolean> {
    return this.grafanaIframe.isVisible().catch(() => false);
  }

  /**
   * Get the Grafana iframe src URL
   */
  async getGrafanaUrl(): Promise<string | null> {
    return this.grafanaIframe.getAttribute('src');
  }

  /**
   * Check if refresh button is enabled
   */
  async isRefreshEnabled(): Promise<boolean> {
    return this.refreshButton.isEnabled().catch(() => false);
  }

  /**
   * Navigate to Analytics from sidebar
   */
  async navigateFromSidebar(): Promise<void> {
    const navLink = this.page.locator('aside a[href="/analytics"]');
    await navLink.click();
    await this.waitForPageLoad();
  }
}
