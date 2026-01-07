/**
 * AnalyticsPage - Page Object for the Analytics Dashboard
 *
 * Provides selectors and interactions for:
 * - Camera selector
 * - Activity heatmap display
 * - Class frequency chart
 * - Anomaly configuration panel
 * - Baseline statistics
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class AnalyticsPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;

  // Controls
  readonly cameraSelector: Locator;
  readonly refreshButton: Locator;

  // Baseline Status
  readonly totalSamplesText: Locator;
  readonly learningStatusBadge: Locator;

  // Activity Heatmap
  readonly activityHeatmap: Locator;
  readonly heatmapTitle: Locator;

  // Class Frequency Chart
  readonly classFrequencyChart: Locator;
  readonly classFrequencyTitle: Locator;

  // Anomaly Config Panel
  readonly anomalyConfigPanel: Locator;
  readonly anomalyConfigTitle: Locator;

  // Loading/Error States
  readonly loadingIndicator: Locator;
  readonly errorMessage: Locator;

  // Empty State
  readonly noCamerasState: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /Analytics/i });
    this.pageSubtitle = page.getByText(/View activity patterns and configure anomaly detection/i);

    // Controls
    this.cameraSelector = page.getByTestId('camera-selector');
    // Use .first() to handle cases where multiple refresh buttons may exist (e.g., PipelineLatencyPanel)
    this.refreshButton = page.getByRole('button', { name: /refresh/i }).first();

    // Baseline Status
    this.totalSamplesText = page.getByText(/Total samples:/i);
    this.learningStatusBadge = page
      .getByText(/Learning Complete|Still Learning/i)
      .first();

    // Activity Heatmap
    this.activityHeatmap = page.getByText('Weekly Activity Pattern').locator('..');
    this.heatmapTitle = page.getByText('Weekly Activity Pattern');

    // Class Frequency Chart
    this.classFrequencyChart = page.getByText('Class Frequency Distribution').locator('..');
    this.classFrequencyTitle = page.getByText('Class Frequency Distribution');

    // Anomaly Config Panel
    this.anomalyConfigPanel = page.getByText('Anomaly Detection').locator('..');
    this.anomalyConfigTitle = page.getByText('Anomaly Detection');

    // Loading/Error States
    this.loadingIndicator = page.locator('.animate-spin');
    this.errorMessage = page.getByText(/Failed to load|Error/i);

    // Empty State
    this.noCamerasState = page.getByText(/No Cameras Found/i);
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
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Wait for data to load (heatmap title or empty state visible)
   */
  async waitForDataLoad(): Promise<void> {
    // Wait for either heatmap title to appear or empty state
    await Promise.race([
      expect(this.heatmapTitle).toBeVisible({ timeout: this.pageLoadTimeout }),
      expect(this.noCamerasState).toBeVisible({ timeout: this.pageLoadTimeout }),
    ]);
  }

  /**
   * Click refresh button
   */
  async refresh(): Promise<void> {
    await this.refreshButton.click();
  }

  /**
   * Select a camera by its name or ID
   */
  async selectCamera(cameraNameOrId: string): Promise<void> {
    await this.cameraSelector.selectOption({ label: cameraNameOrId });
  }

  /**
   * Select camera by index
   */
  async selectCameraByIndex(index: number): Promise<void> {
    const options = await this.cameraSelector.locator('option').all();
    if (index < options.length) {
      const value = await options[index].getAttribute('value');
      if (value) {
        await this.cameraSelector.selectOption(value);
      }
    }
  }

  /**
   * Get the selected camera name
   */
  async getSelectedCamera(): Promise<string | null> {
    return this.cameraSelector.inputValue();
  }

  /**
   * Check if loading indicator is visible
   */
  async isLoading(): Promise<boolean> {
    return this.loadingIndicator.isVisible().catch(() => false);
  }

  /**
   * Check if error state is shown
   */
  async hasError(): Promise<boolean> {
    return this.errorMessage.isVisible().catch(() => false);
  }

  /**
   * Check if activity heatmap is displayed
   */
  async hasActivityHeatmap(): Promise<boolean> {
    return this.heatmapTitle.isVisible().catch(() => false);
  }

  /**
   * Check if class frequency chart is displayed
   */
  async hasClassFrequencyChart(): Promise<boolean> {
    return this.classFrequencyTitle.isVisible().catch(() => false);
  }

  /**
   * Check if anomaly config panel is displayed
   */
  async hasAnomalyConfigPanel(): Promise<boolean> {
    return this.anomalyConfigTitle.isVisible().catch(() => false);
  }

  /**
   * Check if learning is complete
   */
  async isLearningComplete(): Promise<boolean> {
    const badge = this.page.getByText('Learning Complete');
    return badge.isVisible().catch(() => false);
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
