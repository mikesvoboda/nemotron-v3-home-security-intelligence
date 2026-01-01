/**
 * AlertsPage - Page Object for the Alerts page
 *
 * Provides selectors and interactions for:
 * - High/critical risk event display
 * - Risk level filtering
 * - Alert cards
 * - Pagination
 * - Refresh functionality
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class AlertsPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;
  readonly alertIcon: Locator;

  // Filter Section
  readonly riskFilter: Locator;
  readonly refreshButton: Locator;

  // Results Section
  readonly alertsCount: Locator;
  readonly alertCards: Locator;
  readonly riskBadges: Locator;
  readonly criticalCount: Locator;
  readonly highCount: Locator;

  // Empty State
  readonly noAlertsMessage: Locator;
  readonly noAlertsIcon: Locator;

  // Pagination
  readonly previousPageButton: Locator;
  readonly nextPageButton: Locator;
  readonly pageInfo: Locator;

  // Loading/Error States
  readonly loadingSpinner: Locator;
  readonly loadingText: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /Alerts/i }).first();
    this.pageSubtitle = page.getByText(/High and critical risk events/i);
    this.alertIcon = page.locator('svg.lucide-alert-triangle').first();

    // Filter Section
    this.riskFilter = page.locator('#risk-filter');
    this.refreshButton = page.getByRole('button', { name: /Refresh/i });

    // Results Section
    this.alertsCount = page.getByText(/\d+ alerts? found/i);
    this.alertCards = page.locator('[class*="EventCard"]');
    this.riskBadges = page.locator('[class*="RiskBadge"]');
    this.criticalCount = page.locator('span.text-red-400');
    this.highCount = page.locator('span.text-orange-400');

    // Empty State
    this.noAlertsMessage = page.getByText(/No Alerts at This Time/i);
    this.noAlertsIcon = page.locator('svg.lucide-bell');

    // Pagination
    this.previousPageButton = page.getByRole('button', { name: /Previous/i });
    this.nextPageButton = page.getByRole('button', { name: /Next/i });
    this.pageInfo = page.getByText(/Page \d+ of \d+/i);

    // Loading/Error States
    this.loadingSpinner = page.locator('.animate-spin');
    this.loadingText = page.getByText(/Loading alerts/i);
    this.errorMessage = page.getByText(/Error Loading Alerts/i);
  }

  /**
   * Navigate to the Alerts page
   */
  async goto(): Promise<void> {
    await this.page.goto('/alerts');
  }

  /**
   * Wait for the alerts page to fully load (including data)
   */
  async waitForAlertsLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
    // Wait for loading spinner/text to disappear (data loaded)
    await this.loadingText.waitFor({ state: 'hidden', timeout: this.pageLoadTimeout }).catch(() => {
      // Loading text might not appear if data loads quickly, that's fine
    });
  }

  /**
   * Filter by severity level
   */
  async filterBySeverity(level: 'all' | 'critical' | 'high'): Promise<void> {
    await this.riskFilter.selectOption(level);
  }

  /**
   * Refresh the alerts list
   */
  async refresh(): Promise<void> {
    await this.refreshButton.click();
  }

  /**
   * Get count of displayed alerts
   */
  async getAlertCount(): Promise<number> {
    return this.alertCards.count();
  }

  /**
   * Click on an alert card
   */
  async clickAlert(index: number = 0): Promise<void> {
    await this.alertCards.nth(index).click();
  }

  /**
   * Check if no alerts message is shown
   */
  async hasNoAlertsMessage(): Promise<boolean> {
    return this.noAlertsMessage.isVisible().catch(() => false);
  }

  /**
   * Check if loading state is shown
   */
  async isLoading(): Promise<boolean> {
    return this.loadingText.isVisible().catch(() => false);
  }

  /**
   * Check if error state is shown.
   * Waits for either the error message or the loading to complete before checking.
   */
  async hasError(): Promise<boolean> {
    // Wait for the page to finish loading (either error or content appears)
    // The error should appear after API retries complete
    try {
      await this.errorMessage.waitFor({ state: 'visible', timeout: this.pageLoadTimeout });
      return true;
    } catch {
      // Error message didn't appear within timeout
      return false;
    }
  }

  /**
   * Go to next page
   */
  async goToNextPage(): Promise<void> {
    await this.nextPageButton.click();
  }

  /**
   * Go to previous page
   */
  async goToPreviousPage(): Promise<void> {
    await this.previousPageButton.click();
  }

  /**
   * Get the total alert count from the page text
   */
  async getTotalAlertCount(): Promise<number | null> {
    const text = await this.alertsCount.textContent();
    if (!text) return null;
    const match = text.match(/(\d+) alerts?/);
    return match ? parseInt(match[1], 10) : null;
  }
}
