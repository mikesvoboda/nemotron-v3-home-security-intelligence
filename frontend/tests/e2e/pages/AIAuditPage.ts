/**
 * AIAuditPage - Page Object for the AI Audit Dashboard
 *
 * Provides selectors and interactions for:
 * - Quality score metrics
 * - Recommendations panel
 * - Period selector
 *
 * Note: Model contribution chart and leaderboard are now on the AI Performance page
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class AIAuditPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;

  // Controls
  readonly periodSelector: Locator;
  readonly refreshButton: Locator;

  // Quality Score Metrics
  readonly qualityScoreTrends: Locator;
  readonly qualityScoreCard: Locator;
  readonly consistencyRateCard: Locator;
  readonly enrichmentUtilizationCard: Locator;
  readonly evaluationCoverageCard: Locator;

  // Recommendations Panel
  readonly recommendationsPanel: Locator;
  readonly recommendationsAccordion: Locator;

  // Loading/Error States
  readonly loadingState: Locator;
  readonly errorState: Locator;
  readonly errorBanner: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /AI Audit Dashboard/i });
    this.pageSubtitle = page.getByText(/quality metrics/i);

    // Controls
    this.periodSelector = page.getByTestId('period-selector');
    this.refreshButton = page.getByTestId('refresh-button');

    // Quality Score Metrics
    this.qualityScoreTrends = page.getByTestId('quality-score-trends');
    this.qualityScoreCard = page.getByTestId('quality-score-card');
    this.consistencyRateCard = page.getByTestId('consistency-rate-card');
    this.enrichmentUtilizationCard = page.getByTestId('enrichment-utilization-card');
    this.evaluationCoverageCard = page.getByTestId('evaluation-coverage-card');

    // Recommendations Panel
    this.recommendationsPanel = page.getByTestId('recommendations-panel');
    this.recommendationsAccordion = page.getByTestId('recommendations-accordion');

    // Loading/Error States
    this.loadingState = page.getByTestId('ai-audit-loading');
    this.errorState = page.getByTestId('ai-audit-error');
    this.errorBanner = page.getByTestId('error-banner');
  }

  /**
   * Navigate to the AI Audit page
   */
  async goto(): Promise<void> {
    await this.page.goto('/ai-audit');
  }

  /**
   * Wait for the AI Audit page to fully load
   */
  async waitForPageLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Wait for data to load (quality metrics visible)
   */
  async waitForDataLoad(): Promise<void> {
    await expect(this.qualityScoreTrends).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Click refresh button
   */
  async refresh(): Promise<void> {
    await this.refreshButton.click();
  }

  /**
   * Select time period
   */
  async selectPeriod(period: '1' | '7' | '14' | '30' | '90'): Promise<void> {
    await this.periodSelector.click();
    await this.page.getByRole('option', { name: new RegExp(period) }).click();
  }

  /**
   * Check if recommendations are displayed
   */
  async hasRecommendations(): Promise<boolean> {
    return this.recommendationsAccordion.isVisible().catch(() => false);
  }

  /**
   * Expand a recommendation category
   */
  async expandRecommendationCategory(category: string): Promise<void> {
    const categoryAccordion = this.page.getByTestId(`recommendation-category-${category}`);
    await categoryAccordion.click();
  }

  /**
   * Check if error state is shown
   */
  async hasError(): Promise<boolean> {
    return this.errorState.isVisible().catch(() => false);
  }

  /**
   * Check if loading state is shown
   */
  async isLoading(): Promise<boolean> {
    return this.loadingState.isVisible().catch(() => false);
  }

  /**
   * Navigate to AI Audit from sidebar
   */
  async navigateFromSidebar(): Promise<void> {
    const navLink = this.page.locator('aside a[href="/ai-audit"]');
    await navLink.click();
    await this.waitForPageLoad();
  }
}
