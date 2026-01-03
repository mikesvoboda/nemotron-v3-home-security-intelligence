/**
 * DashboardPage - Page Object for the main Dashboard
 *
 * Provides selectors and interactions for:
 * - Risk Gauge
 * - Camera Grid
 * - Activity Feed
 * - Stats Row
 *
 * Note: GPU Statistics are displayed on the System page, not the main Dashboard.
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class DashboardPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;

  // Stats Row
  readonly statsRow: Locator;
  readonly activeCamerasStat: Locator;
  readonly eventsTodayStat: Locator;
  readonly riskScoreStat: Locator;
  readonly systemStatusStat: Locator;

  // Risk Gauge Section
  readonly riskGaugeSection: Locator;
  readonly riskGaugeHeading: Locator;
  readonly riskGauge: Locator;

  // Camera Grid Section
  readonly cameraGridSection: Locator;
  readonly cameraGridHeading: Locator;
  readonly cameraCards: Locator;

  // Activity Feed Section
  readonly activityFeedSection: Locator;
  readonly activityFeedHeading: Locator;
  readonly activityItems: Locator;
  readonly noActivityMessage: Locator;

  // Error State
  readonly errorContainer: Locator;
  readonly errorHeading: Locator;
  readonly reloadButton: Locator;

  // Loading State
  readonly loadingSkeleton: Locator;

  // Disconnected Indicator
  readonly disconnectedIndicator: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /Security Dashboard/i });
    this.pageSubtitle = page.getByText(/Real-time AI-powered home security monitoring/i);

    // Stats Row - look for the stats cards container
    this.statsRow = page
      .locator('[class*="grid"]')
      .filter({ has: page.getByText(/Active Cameras/i) });
    this.activeCamerasStat = page.getByText(/Active Cameras/i);
    this.eventsTodayStat = page.getByText(/Events Today/i);
    this.riskScoreStat = page.getByText(/Current Risk/i);
    this.systemStatusStat = page.getByText(/System Status/i);

    // Risk Gauge Section
    this.riskGaugeSection = page
      .locator('div')
      .filter({ has: page.getByRole('heading', { name: /Current Risk Level/i }) })
      .first();
    this.riskGaugeHeading = page.getByRole('heading', { name: /Current Risk Level/i });
    this.riskGauge = page.locator('[class*="RiskGauge"], [data-testid="risk-gauge"]').first();

    // Camera Grid Section
    this.cameraGridSection = page
      .locator('div')
      .filter({ has: page.getByRole('heading', { name: /Camera Status/i }) });
    this.cameraGridHeading = page.getByRole('heading', { name: /Camera Status/i });
    this.cameraCards = page.locator('[class*="CameraCard"], [data-testid^="camera-"]');

    // Activity Feed Section
    this.activityFeedSection = page
      .locator('div')
      .filter({ has: page.getByRole('heading', { name: /Live Activity/i }) });
    this.activityFeedHeading = page.getByRole('heading', { name: /Live Activity/i }).first();
    this.activityItems = page.locator('[class*="ActivityItem"], [data-testid^="activity-"]');
    this.noActivityMessage = page.getByText(/No activity/i);

    // Error State
    this.errorContainer = page
      .locator('div')
      .filter({ has: page.getByRole('heading', { name: /Error Loading Dashboard/i }) });
    this.errorHeading = page.getByRole('heading', { name: /Error Loading Dashboard/i });
    this.reloadButton = page.getByRole('button', { name: /Reload Page/i });

    // Loading State
    this.loadingSkeleton = page.locator('.animate-pulse').first();

    // Disconnected Indicator
    this.disconnectedIndicator = page.getByText(/Disconnected/i);
  }

  /**
   * Navigate to the Dashboard page
   */
  async goto(): Promise<void> {
    await this.page.goto('/');
  }

  /**
   * Wait for the dashboard to fully load (including data)
   */
  async waitForDashboardLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
    // Wait for either dashboard content OR error state to appear
    await Promise.race([
      this.riskGauge.waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
      this.errorHeading.waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
    ]).catch(() => {
      // One should appear, but continue anyway if neither does
    });
  }

  /**
   * Check if dashboard is in loading state
   */
  async isLoading(): Promise<boolean> {
    return this.loadingSkeleton.isVisible().catch(() => false);
  }

  /**
   * Check if dashboard shows error state
   */
  async isInErrorState(): Promise<boolean> {
    return this.errorHeading.isVisible().catch(() => false);
  }

  /**
   * Click reload button in error state
   */
  async clickReload(): Promise<void> {
    await this.reloadButton.click();
  }

  /**
   * Verify all main dashboard sections are visible
   * Note: Activity Feed is on the Timeline page, not the Dashboard
   */
  async expectAllSectionsVisible(): Promise<void> {
    await expect(this.pageTitle).toBeVisible();
    await expect(this.riskGaugeHeading).toBeVisible();
    await expect(this.cameraGridHeading).toBeVisible();
    // Note: activityFeedHeading is NOT on Dashboard - it's on Timeline page
  }

  /**
   * Get the number of visible camera cards
   */
  async getCameraCount(): Promise<number> {
    // Count camera-related elements in the camera grid section
    const cameraSection = this.page.locator('div').filter({ has: this.cameraGridHeading });
    const cards = cameraSection.locator('img, [class*="camera"]');
    return cards.count();
  }

  /**
   * Get the number of activity items
   */
  async getActivityItemCount(): Promise<number> {
    return this.activityItems.count();
  }

  /**
   * Check if no activity message is displayed
   */
  async hasNoActivityMessage(): Promise<boolean> {
    return this.noActivityMessage.isVisible().catch(() => false);
  }

  /**
   * Check if disconnected indicator is shown
   */
  async expectDisconnected(): Promise<void> {
    await expect(this.disconnectedIndicator).toBeVisible({ timeout: 10000 });
  }

  /**
   * Click on a camera card by name
   */
  async clickCamera(cameraName: string): Promise<void> {
    await this.page.getByText(cameraName).click();
  }

  /**
   * Click on an activity item
   */
  async clickActivityItem(index: number = 0): Promise<void> {
    await this.activityItems.nth(index).click();
  }

  /**
   * Check if specific camera is shown
   */
  async hasCameraByName(name: string): Promise<boolean> {
    // Look for the camera name in any text element
    const element = this.page.getByText(name, { exact: false });
    return element
      .first()
      .isVisible()
      .catch(() => false);
  }

  /**
   * Get risk score value displayed
   */
  async getRiskScoreText(): Promise<string | null> {
    const riskElement = this.page.locator('[class*="risk"], [data-testid*="risk"]').first();
    return riskElement.textContent();
  }

  /**
   * Check if GPU Statistics section is visible on the dashboard
   * Note: GPU stats are shown in the GPU Statistics card on the dashboard
   */
  async expectGpuStatsVisible(): Promise<void> {
    // Look for the GPU Statistics heading or section
    const gpuSection = this.page.getByText(/GPU Statistics/i);
    await expect(gpuSection).toBeVisible({ timeout: 5000 });
  }

  /**
   * Verify header is visible with navigation elements
   */
  async expectHeaderVisible(): Promise<void> {
    // Check for the header's brand/logo element
    const header = this.page.getByRole('banner');
    await expect(header).toBeVisible({ timeout: 5000 });
  }
}
