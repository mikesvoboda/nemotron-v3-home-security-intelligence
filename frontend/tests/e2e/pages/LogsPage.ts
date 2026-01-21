/**
 * LogsPage - Page Object for the Grafana-embedded System Logs page
 *
 * Provides selectors and interactions for:
 * - Page header and title
 * - External Grafana links
 * - Refresh functionality
 * - Grafana iframe
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class LogsPage extends BasePage {
  // Page container
  readonly pageContainer: Locator;

  // Page heading
  readonly pageTitle: Locator;

  // Header buttons
  readonly openGrafanaButton: Locator;
  readonly exploreButton: Locator;
  readonly refreshButton: Locator;

  // Grafana iframe
  readonly grafanaIframe: Locator;

  // Loading state
  readonly loadingState: Locator;

  // Error state
  readonly errorState: Locator;

  constructor(page: Page) {
    super(page);

    // Page container
    this.pageContainer = page.locator('[data-testid="logs-page"]');

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /System Logs/i });

    // Header buttons
    this.openGrafanaButton = page.getByRole('link', { name: /Open Grafana/i });
    this.exploreButton = page.getByRole('link', { name: /Explore.*LogQL/i });
    this.refreshButton = page.getByRole('button', { name: /Refresh/i });

    // Grafana iframe
    this.grafanaIframe = page.locator('iframe[data-testid="grafana-logs-iframe"]');

    // Loading state
    this.loadingState = page.locator('[data-testid="logs-loading"]');

    // Error state
    this.errorState = page.locator('[data-testid="logs-error"]');
  }

  /**
   * Navigate to the Logs page
   */
  async goto(): Promise<void> {
    await this.page.goto('/logs');
  }

  /**
   * Wait for the logs page to fully load
   */
  async waitForLogsLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Check if the Grafana iframe is visible
   */
  async isGrafanaIframeVisible(): Promise<boolean> {
    return this.grafanaIframe.isVisible();
  }

  /**
   * Refresh the Grafana iframe
   */
  async refresh(): Promise<void> {
    await this.refreshButton.click();
  }

  /**
   * Check if the Open Grafana link has the correct href
   */
  async getOpenGrafanaHref(): Promise<string | null> {
    return this.openGrafanaButton.getAttribute('href');
  }

  /**
   * Check if the Explore link has the correct href
   */
  async getExploreHref(): Promise<string | null> {
    return this.exploreButton.getAttribute('href');
  }

  /**
   * Check if loading state is shown
   */
  async isLoading(): Promise<boolean> {
    return this.loadingState.isVisible();
  }

  /**
   * Check if error state is shown
   */
  async hasError(): Promise<boolean> {
    return this.errorState.isVisible();
  }
}
