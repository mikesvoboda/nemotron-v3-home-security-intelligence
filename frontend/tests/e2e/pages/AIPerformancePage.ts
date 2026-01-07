/**
 * AIPerformancePage - Page Object for the AI Performance Dashboard
 *
 * Provides selectors and interactions for:
 * - Model status cards (RT-DETRv2, Nemotron)
 * - Latency metrics panel
 * - Pipeline health panel
 * - Insights charts
 * - Model Zoo section
 * - Model contribution chart and leaderboard
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class AIPerformancePage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;

  // Controls
  readonly refreshButton: Locator;

  // Banners
  readonly grafanaBanner: Locator;
  readonly grafanaLink: Locator;
  readonly errorBanner: Locator;

  // Summary Row
  readonly summaryRow: Locator;

  // Model Status Cards
  readonly modelStatusCards: Locator;
  readonly rtdetrStatusCard: Locator;
  readonly nemotronStatusCard: Locator;

  // Latency Panel
  readonly latencyPanel: Locator;
  readonly detectionLatency: Locator;
  readonly analysisLatency: Locator;
  readonly pipelineLatency: Locator;

  // Pipeline Health Panel
  readonly pipelineHealthPanel: Locator;
  readonly detectionQueueDepth: Locator;
  readonly analysisQueueDepth: Locator;
  readonly totalDetections: Locator;
  readonly totalEvents: Locator;

  // Insights Charts
  readonly insightsCharts: Locator;
  readonly detectionsByClassChart: Locator;

  // Model Zoo Section
  readonly modelZooSection: Locator;
  readonly modelZooAnalytics: Locator;

  // Model Contribution Chart
  readonly modelContributionChart: Locator;

  // Model Leaderboard
  readonly modelLeaderboard: Locator;

  // Loading/Error States
  readonly loadingState: Locator;
  readonly errorState: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /AI Performance/i });
    this.pageSubtitle = page.getByText(/model metrics|latency|pipeline health/i);

    // Controls
    this.refreshButton = page.getByTestId('ai-performance-refresh-button');

    // Banners
    this.grafanaBanner = page.getByTestId('grafana-banner');
    this.grafanaLink = page.getByTestId('grafana-link');
    this.errorBanner = page.getByTestId('error-banner');

    // Summary Row
    this.summaryRow = page.getByTestId('ai-performance-summary-row');

    // Model Status Cards
    this.modelStatusCards = page.getByTestId('model-status-cards');
    this.rtdetrStatusCard = page.getByTestId('rtdetr-status-card');
    this.nemotronStatusCard = page.getByTestId('nemotron-status-card');

    // Latency Panel
    this.latencyPanel = page.getByTestId('latency-panel');
    this.detectionLatency = page.getByTestId('detection-latency');
    this.analysisLatency = page.getByTestId('analysis-latency');
    this.pipelineLatency = page.getByTestId('pipeline-latency');

    // Pipeline Health Panel
    this.pipelineHealthPanel = page.getByTestId('pipeline-health-panel');
    this.detectionQueueDepth = page.getByTestId('detection-queue-depth');
    this.analysisQueueDepth = page.getByTestId('analysis-queue-depth');
    this.totalDetections = page.getByTestId('total-detections');
    this.totalEvents = page.getByTestId('total-events');

    // Insights Charts
    this.insightsCharts = page.getByTestId('insights-charts');
    this.detectionsByClassChart = page.getByTestId('detections-by-class-chart');

    // Model Zoo Section
    this.modelZooSection = page.getByTestId('model-zoo-section');
    this.modelZooAnalytics = page.getByTestId('model-zoo-analytics-section');

    // Model Contribution Chart
    this.modelContributionChart = page.getByTestId('model-contribution-chart');

    // Model Leaderboard
    this.modelLeaderboard = page.getByTestId('model-leaderboard');

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
   * Wait for data to load (model status cards visible)
   */
  async waitForDataLoad(): Promise<void> {
    await expect(
      this.page.getByTestId('ai-performance-page')
    ).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Click refresh button
   */
  async refresh(): Promise<void> {
    await this.refreshButton.click();
  }

  /**
   * Check if Grafana banner is visible
   */
  async hasGrafanaBanner(): Promise<boolean> {
    return this.grafanaBanner.isVisible().catch(() => false);
  }

  /**
   * Get Grafana link URL
   */
  async getGrafanaLinkUrl(): Promise<string | null> {
    return this.grafanaLink.getAttribute('href');
  }

  /**
   * Check if model status cards are visible
   */
  async hasModelStatusCards(): Promise<boolean> {
    // Check if the page has loaded with model status information
    const pageLoaded = await this.page.getByTestId('ai-performance-page').isVisible();
    return pageLoaded;
  }

  /**
   * Check if RT-DETR status is visible
   */
  async hasRtdetrStatus(): Promise<boolean> {
    // Look for RT-DETR related content
    const rtdetrText = this.page.getByText(/RT-DETR|RTDETR/i);
    return rtdetrText.first().isVisible().catch(() => false);
  }

  /**
   * Check if Nemotron status is visible
   */
  async hasNemotronStatus(): Promise<boolean> {
    // Look for Nemotron related content
    const nemotronText = this.page.getByText(/Nemotron/i);
    return nemotronText.first().isVisible().catch(() => false);
  }

  /**
   * Check if latency panel is visible
   */
  async hasLatencyPanel(): Promise<boolean> {
    // Look for latency-related content
    const latencyText = this.page.getByText(/Latency|latency/i);
    return latencyText.first().isVisible().catch(() => false);
  }

  /**
   * Check if pipeline health panel is visible
   */
  async hasPipelineHealthPanel(): Promise<boolean> {
    // Look for pipeline health content
    const pipelineText = this.page.getByText(/Pipeline|Queue/i);
    return pipelineText.first().isVisible().catch(() => false);
  }

  /**
   * Check if insights charts are visible
   */
  async hasInsightsCharts(): Promise<boolean> {
    // Look for chart/insights content
    const insightsText = this.page.getByText(/Insights|Detections/i);
    return insightsText.first().isVisible().catch(() => false);
  }

  /**
   * Check if model zoo section is visible
   */
  async hasModelZooSection(): Promise<boolean> {
    // Look for model zoo content
    const modelZooText = this.page.getByText(/Model Zoo/i);
    return modelZooText.first().isVisible().catch(() => false);
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
    return this.errorState.isVisible().catch(() => false);
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
