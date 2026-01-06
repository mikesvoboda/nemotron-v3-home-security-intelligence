/**
 * SettingsPage - Page Object for the Settings page
 *
 * Provides selectors and interactions for:
 * - Tab navigation (Cameras, Processing, Notifications)
 * - Settings forms within each tab
 *
 * Note: AI Models tab was moved to /ai page
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class SettingsPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;

  // Tab Navigation (5 tabs: Cameras, Analytics, Rules, Processing, Notifications)
  readonly tabList: Locator;
  readonly camerasTab: Locator;
  readonly analyticsTab: Locator;
  readonly rulesTab: Locator;
  readonly processingTab: Locator;
  readonly notificationsTab: Locator;

  // Tab Panels
  readonly tabPanel: Locator;

  // Cameras Tab Content
  readonly camerasList: Locator;
  readonly addCameraButton: Locator;
  readonly cameraCards: Locator;

  // Processing Tab Content
  readonly batchWindowInput: Locator;
  readonly idleTimeoutInput: Locator;
  readonly retentionDaysInput: Locator;
  readonly saveProcessingButton: Locator;

  // AI Models Tab Content
  readonly rtdetrStatus: Locator;
  readonly nemotronStatus: Locator;
  readonly modelInfo: Locator;

  // Notifications Tab Content
  readonly emailNotifications: Locator;
  readonly webhookUrl: Locator;
  readonly saveNotificationsButton: Locator;

  // General
  readonly saveButton: Locator;
  readonly successMessage: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /Settings/i }).first();
    this.pageSubtitle = page.getByText(/Configure your security monitoring system/i);

    // Tab Navigation - Headless UI renders tabs as buttons
    // Order: Cameras, Analytics, Rules, Processing, Notifications
    // Note: AI Models tab was moved to /ai page
    this.tabList = page.locator('[role="tablist"]');
    this.camerasTab = page.getByRole('tab', { name: /CAMERAS/i }).or(page.locator('button').filter({ hasText: 'CAMERAS' }));
    this.analyticsTab = page.getByRole('tab', { name: /ANALYTICS/i }).or(page.locator('button').filter({ hasText: 'ANALYTICS' }));
    this.rulesTab = page.getByRole('tab', { name: /RULES/i }).or(page.locator('button').filter({ hasText: 'RULES' }));
    this.processingTab = page.getByRole('tab', { name: /PROCESSING/i }).or(page.locator('button').filter({ hasText: 'PROCESSING' }));
    this.notificationsTab = page.getByRole('tab', { name: /NOTIFICATIONS/i }).or(page.locator('button').filter({ hasText: 'NOTIFICATIONS' }));

    // Tab Panels
    this.tabPanel = page.locator('[role="tabpanel"]');

    // Cameras Tab Content
    this.camerasList = page.locator('[data-testid="cameras-list"]');
    this.addCameraButton = page.getByRole('button', { name: /Add Camera/i });
    this.cameraCards = page.locator('[data-testid^="camera-config-"]');

    // Processing Tab Content
    this.batchWindowInput = page.getByLabel(/Batch Window/i);
    this.idleTimeoutInput = page.getByLabel(/Idle Timeout/i);
    this.retentionDaysInput = page.getByLabel(/Retention Days/i);
    this.saveProcessingButton = page.getByRole('button', { name: /Save Processing/i });

    // AI Models Tab Content
    this.rtdetrStatus = page.getByText(/RT-DETR/i);
    this.nemotronStatus = page.getByText(/Nemotron/i);
    this.modelInfo = page.locator('[data-testid="model-info"]');

    // Notifications Tab Content
    this.emailNotifications = page.getByLabel(/Email Notifications/i);
    this.webhookUrl = page.getByLabel(/Webhook URL/i);
    this.saveNotificationsButton = page.getByRole('button', { name: /Save Notifications/i });

    // General
    this.saveButton = page.getByRole('button', { name: /Save/i });
    this.successMessage = page.getByText(/saved successfully/i);
    this.errorMessage = page.getByText(/Failed to save/i);
  }

  /**
   * Navigate to the Settings page
   */
  async goto(): Promise<void> {
    await this.page.goto('/settings');
  }

  /**
   * Wait for the settings page to fully load
   */
  async waitForSettingsLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Go to Cameras tab
   */
  async goToCamerasTab(): Promise<void> {
    await this.camerasTab.click();
    await expect(this.camerasTab).toHaveAttribute('data-selected', 'true');
  }

  /**
   * Go to Processing tab
   */
  async goToProcessingTab(): Promise<void> {
    await this.processingTab.click();
    await expect(this.processingTab).toHaveAttribute('data-selected', 'true');
  }

  /**
   * Go to Notifications tab
   */
  async goToNotificationsTab(): Promise<void> {
    await this.notificationsTab.click();
    await expect(this.notificationsTab).toHaveAttribute('data-selected', 'true');
  }

  /**
   * Go to Analytics tab
   */
  async goToAnalyticsTab(): Promise<void> {
    await this.analyticsTab.click();
    await expect(this.analyticsTab).toHaveAttribute('data-selected', 'true');
  }

  /**
   * Go to Rules tab
   */
  async goToRulesTab(): Promise<void> {
    await this.rulesTab.click();
    await expect(this.rulesTab).toHaveAttribute('data-selected', 'true');
  }

  /**
   * Check if a tab is selected
   */
  async isTabSelected(tab: 'cameras' | 'analytics' | 'rules' | 'processing' | 'notifications'): Promise<boolean> {
    const tabs: Record<string, Locator> = {
      cameras: this.camerasTab,
      analytics: this.analyticsTab,
      rules: this.rulesTab,
      processing: this.processingTab,
      notifications: this.notificationsTab,
    };
    const attr = await tabs[tab].getAttribute('data-selected');
    return attr === 'true';
  }

  /**
   * Get the text content of the active tab panel
   */
  async getTabPanelContent(): Promise<string | null> {
    return this.tabPanel.textContent();
  }

  /**
   * Check if success message is shown
   */
  async hasSuccessMessage(): Promise<boolean> {
    return this.successMessage.isVisible().catch(() => false);
  }

  /**
   * Check if error message is shown
   */
  async hasErrorMessage(): Promise<boolean> {
    return this.errorMessage.isVisible().catch(() => false);
  }

  /**
   * Get number of camera config cards
   */
  async getCameraCount(): Promise<number> {
    return this.cameraCards.count();
  }

  /**
   * Use keyboard to navigate tabs
   */
  async navigateTabsWithKeyboard(direction: 'left' | 'right'): Promise<void> {
    const key = direction === 'right' ? 'ArrowRight' : 'ArrowLeft';
    await this.tabList.press(key);
  }
}
