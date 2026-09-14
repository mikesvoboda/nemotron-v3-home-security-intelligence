/**
 * AlertRulesPage - Page Object for the Alert Rules Settings tab
 *
 * Provides selectors and interactions for:
 * - Viewing alert rules list
 * - Creating new alert rules
 * - Editing existing alert rules
 * - Deleting alert rules with confirmation
 * - Toggling rule enabled/disabled state
 * - Testing rules against sample events
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class AlertRulesPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;

  // Tab Navigation
  readonly rulesTab: Locator;

  // Rules Header
  readonly alertRulesHeader: Locator;
  readonly alertRulesDescription: Locator;
  readonly addRuleButton: Locator;

  // Rules Table
  readonly rulesTable: Locator;
  readonly rulesTableBody: Locator;
  readonly ruleRows: Locator;
  readonly emptyState: Locator;
  readonly emptyStateAddButton: Locator;

  // Rule Row Elements (accessed via nth or filter)
  readonly ruleNameCells: Locator;
  readonly ruleSeverityBadges: Locator;
  readonly ruleScheduleCells: Locator;
  readonly ruleChannelsCells: Locator;
  readonly ruleToggleSwitches: Locator;

  // Rule Actions (in each row)
  readonly testButtons: Locator;
  readonly editButtons: Locator;
  readonly deleteButtons: Locator;

  // Add/Edit Rule Modal
  readonly ruleModal: Locator;
  readonly modalTitle: Locator;
  readonly modalCloseButton: Locator;

  // Form Fields - Basic Info
  readonly nameInput: Locator;
  readonly descriptionInput: Locator;
  readonly enabledSwitch: Locator;
  readonly severitySelect: Locator;

  // Form Fields - Conditions
  readonly riskThresholdInput: Locator;
  readonly minConfidenceInput: Locator;
  readonly objectTypeButtons: Locator;
  readonly cameraButtons: Locator;

  // Form Fields - Schedule
  readonly scheduleToggle: Locator;
  readonly scheduleDayButtons: Locator;
  readonly startTimeInput: Locator;
  readonly endTimeInput: Locator;
  readonly timezoneSelect: Locator;

  // Form Fields - Notifications
  readonly channelButtons: Locator;
  readonly cooldownInput: Locator;

  // Form Actions
  readonly cancelButton: Locator;
  readonly submitButton: Locator;

  // Form Validation
  readonly nameError: Locator;
  readonly riskThresholdError: Locator;
  readonly minConfidenceError: Locator;
  readonly scheduleError: Locator;
  readonly cooldownError: Locator;

  // Delete Confirmation Modal
  readonly deleteModal: Locator;
  readonly deleteModalTitle: Locator;
  readonly deleteModalMessage: Locator;
  readonly deleteModalCancelButton: Locator;
  readonly deleteModalConfirmButton: Locator;

  // Test Rule Modal
  readonly testModal: Locator;
  readonly testModalTitle: Locator;
  readonly testModalCloseButton: Locator;
  readonly testLoading: Locator;
  readonly eventsTested: Locator;
  readonly eventsMatched: Locator;
  readonly matchRate: Locator;
  readonly testResults: Locator;
  readonly noEventsMessage: Locator;

  // Loading/Error States
  readonly loadingSpinner: Locator;
  readonly loadingText: Locator;
  readonly errorMessage: Locator;
  readonly tryAgainButton: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /Settings/i }).first();
    this.pageSubtitle = page.getByText(/Configure your security monitoring system/i);

    // Tab Navigation - Headless UI renders tabs as buttons within a tablist
    this.rulesTab = page
      .getByRole('tab', { name: /RULES/i })
      .or(page.locator('[role="tablist"] button').filter({ hasText: 'RULES' }));

    // Rules Header - use exact match for h2 heading "Alert Rules"
    this.alertRulesHeader = page.getByRole('heading', { name: 'Alert Rules', exact: true, level: 2 });
    this.alertRulesDescription = page.getByText(
      /Configure custom alert rules for security events/i
    );
    this.addRuleButton = page.getByRole('button', { name: /Add Rule/i }).first();

    // Rules Table
    this.rulesTable = page.locator('table');
    this.rulesTableBody = page.locator('table tbody');
    this.ruleRows = page.locator('table tbody tr');
    // Empty state is an h3 heading with specific text
    this.emptyState = page.getByRole('heading', { name: /No alert rules configured/i, level: 3 });
    // The empty state Add Rule button is the second one (first is in header)
    this.emptyStateAddButton = page.getByRole('button', { name: /Add Rule/i }).nth(1);

    // Rule Row Elements
    this.ruleNameCells = page.locator('table tbody tr td:nth-child(2)');
    this.ruleSeverityBadges = page.locator('table tbody tr td:nth-child(3) span');
    this.ruleScheduleCells = page.locator('table tbody tr td:nth-child(4)');
    this.ruleChannelsCells = page.locator('table tbody tr td:nth-child(5)');
    this.ruleToggleSwitches = page.locator('table tbody tr button[role="switch"]');

    // Rule Actions
    this.testButtons = page.locator('button[aria-label^="Test"]');
    this.editButtons = page.locator('button[aria-label^="Edit"]');
    this.deleteButtons = page.locator('button[aria-label^="Delete"]');

    // Add/Edit Rule Modal - Use specific heading names to identify
    // "Add Alert Rule" or "Edit Alert Rule" - distinct from the page heading "Alert Rules"
    this.ruleModal = page.getByRole('dialog', { name: /(Add|Edit) Alert Rule/i });
    this.modalTitle = page.getByRole('heading', { name: /(Add|Edit) Alert Rule/i });
    this.modalCloseButton = this.ruleModal.getByRole('button', { name: /Close modal/i });

    // Form Fields - Basic Info
    this.nameInput = page.locator('#name');
    this.descriptionInput = page.locator('#description');
    this.enabledSwitch = this.ruleModal.locator('button[role="switch"]').first();
    this.severitySelect = page.locator('#severity');

    // Form Fields - Conditions
    this.riskThresholdInput = page.locator('#risk_threshold');
    this.minConfidenceInput = page.locator('#min_confidence');
    this.objectTypeButtons = this.ruleModal.locator('button').filter({
      hasText: /person|vehicle|animal|package|face/i,
    });
    this.cameraButtons = this.ruleModal.locator(
      'button[class*="rounded-full"]:not(:has-text("Mon|Tue|Wed|Thu|Fri|Sat|Sun|person|vehicle|animal|package|face|email|webhook|pushover"))'
    );

    // Form Fields - Schedule
    this.scheduleToggle = this.ruleModal.locator('button[role="switch"]').nth(1);
    this.scheduleDayButtons = this.ruleModal
      .locator('button')
      .filter({ hasText: /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)$/ });
    this.startTimeInput = page.locator('#start_time');
    this.endTimeInput = page.locator('#end_time');
    this.timezoneSelect = page.locator('#timezone');

    // Form Fields - Notifications
    this.channelButtons = this.ruleModal.locator('button').filter({
      hasText: /^(email|webhook|pushover)$/i,
    });
    this.cooldownInput = page.locator('#cooldown');

    // Form Actions - use dialog-scoped locators
    // The dialog's submit button is inside the dialog (aria-labelledby identifies it)
    this.cancelButton = page.getByLabel(/Alert Rule/i).getByRole('button', { name: /Cancel/i });
    this.submitButton = page.getByLabel(/Alert Rule/i).getByRole('button', { name: /Add Rule|Update Rule/i });

    // Form Validation - use text patterns within the modal form
    // Note: "Name is required" aligns with backend min_length=1 constraint
    this.nameError = this.ruleModal.getByText(/Name is required/i);
    this.riskThresholdError = this.ruleModal.getByText(
      /Risk threshold must be between 0 and 100/i
    );
    this.minConfidenceError = this.ruleModal.getByText(/Confidence must be between 0 and 1/i);
    this.scheduleError = this.ruleModal.getByText(
      /Start and end times are required when schedule is enabled/i
    );
    this.cooldownError = this.ruleModal.getByText(/Cooldown cannot be negative/i);

    // Delete Confirmation Modal - use the title text to identify
    this.deleteModal = page.getByRole('dialog', { name: /Delete Alert Rule/i });
    this.deleteModalTitle = page.getByRole('heading', { name: /Delete Alert Rule/i });
    this.deleteModalMessage = page.getByText(/Are you sure you want to delete/i);
    this.deleteModalCancelButton = page.getByRole('button', { name: /^Cancel$/i });
    this.deleteModalConfirmButton = page.getByRole('button', {
      name: /Delete Rule|Deleting/i,
    });

    // Test Rule Modal - use the title text to identify
    this.testModal = page.getByRole('dialog', { name: /Test Rule:/i });
    this.testModalTitle = page.getByRole('heading', { name: /Test Rule:/i });
    this.testModalCloseButton = page.getByRole('button', { name: /^Close$/i });
    this.testLoading = this.testModal.getByText(/Testing rule against recent events/i);
    this.eventsTested = this.testModal.locator('p').filter({ hasText: /Events Tested/i });
    this.eventsMatched = this.testModal.locator('p').filter({ hasText: /Matched/i });
    this.matchRate = this.testModal.locator('p').filter({ hasText: /Match Rate/i });
    this.testResults = this.testModal.locator('[class*="max-h-60"] > div');
    this.noEventsMessage = this.testModal.getByText(/No recent events to test against/i);

    // Loading/Error States
    this.loadingSpinner = page.locator('.animate-spin');
    this.loadingText = page.getByText(/Loading alert rules/i);
    // h3 element with text, use getByText since role may not resolve for styled h3
    this.errorMessage = page.getByText(/Error loading alert rules/i);
    this.tryAgainButton = page.getByText(/Try again/i);
  }

  /**
   * Navigate to the Alert Rules settings tab
   */
  async goto(): Promise<void> {
    await this.page.goto('/settings');
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
    await this.rulesTab.click();
    await this.waitForAlertRulesLoad();
  }

  /**
   * Wait for the alert rules tab to fully load
   * Note: Error state does NOT show the alertRulesHeader, so we wait for any of the three states
   */
  async waitForAlertRulesLoad(): Promise<void> {
    // Wait for either rules table (with header), empty state (with header), or error state (no header)
    await Promise.race([
      // Normal state with rules: header + table
      (async () => {
        await this.alertRulesHeader.waitFor({ state: 'visible', timeout: this.pageLoadTimeout });
        await this.rulesTable.waitFor({ state: 'visible', timeout: this.pageLoadTimeout });
      })(),
      // Empty state: header + empty message
      (async () => {
        await this.alertRulesHeader.waitFor({ state: 'visible', timeout: this.pageLoadTimeout });
        await this.emptyState.waitFor({ state: 'visible', timeout: this.pageLoadTimeout });
      })(),
      // Error state: no header, just error message (component returns early on error)
      this.errorMessage.waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
    ]).catch(() => {
      // One should appear, but continue anyway
    });
  }

  /**
   * Click the Add Rule button to open the modal
   */
  async openAddRuleModal(): Promise<void> {
    // Ensure button is visible and enabled before clicking
    await expect(this.addRuleButton).toBeVisible({ timeout: this.pageLoadTimeout });
    await expect(this.addRuleButton).toBeEnabled({ timeout: this.pageLoadTimeout });

    // Click button first, then wait for modal to appear
    // Sequential execution avoids race condition where wait starts before click completes
    // Modal has 300ms animation, plus rendering time in CI can be slow (especially webkit)
    await this.addRuleButton.click();
    await this.modalTitle.waitFor({ state: 'visible', timeout: 20000 });
  }

  /**
   * Click the empty state Add Rule button
   */
  async openAddRuleModalFromEmptyState(): Promise<void> {
    // Ensure button is visible and enabled before clicking
    await expect(this.emptyStateAddButton).toBeVisible({ timeout: this.pageLoadTimeout });
    await expect(this.emptyStateAddButton).toBeEnabled({ timeout: this.pageLoadTimeout });

    // Click button first, then wait for modal to appear
    // Sequential execution avoids race condition where wait starts before click completes
    // Modal has 300ms animation, plus rendering time in CI can be slow (especially webkit)
    await this.emptyStateAddButton.click();
    await this.modalTitle.waitFor({ state: 'visible', timeout: 20000 });
  }

  /**
   * Close the rule modal
   */
  async closeRuleModal(): Promise<void> {
    await this.modalCloseButton.click();
    await expect(this.modalTitle).not.toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Cancel the rule modal
   */
  async cancelRuleModal(): Promise<void> {
    await this.cancelButton.click();
    await expect(this.modalTitle).not.toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Fill out the rule form with provided data
   */
  async fillRuleForm(data: {
    name?: string;
    description?: string;
    enabled?: boolean;
    severity?: 'low' | 'medium' | 'high' | 'critical';
    riskThreshold?: number;
    minConfidence?: number;
    objectTypes?: string[];
    scheduleEnabled?: boolean;
    scheduleDays?: string[];
    startTime?: string;
    endTime?: string;
    timezone?: string;
    channels?: string[];
    cooldown?: number;
  }): Promise<void> {
    if (data.name !== undefined) {
      await this.nameInput.fill(data.name);
    }
    if (data.description !== undefined) {
      await this.descriptionInput.fill(data.description);
    }
    if (data.severity !== undefined) {
      await this.severitySelect.selectOption(data.severity);
    }
    if (data.riskThreshold !== undefined) {
      await this.riskThresholdInput.fill(String(data.riskThreshold));
    }
    if (data.minConfidence !== undefined) {
      await this.minConfidenceInput.fill(String(data.minConfidence));
    }
    if (data.objectTypes !== undefined) {
      for (const type of data.objectTypes) {
        await this.ruleModal.locator('button').filter({ hasText: new RegExp(`^${type}$`, 'i') }).click();
      }
    }
    if (data.scheduleEnabled !== undefined && data.scheduleEnabled) {
      await this.scheduleToggle.click();
    }
    if (data.scheduleDays !== undefined) {
      for (const day of data.scheduleDays) {
        await this.scheduleDayButtons.filter({ hasText: day }).click();
      }
    }
    if (data.startTime !== undefined) {
      await this.startTimeInput.fill(data.startTime);
    }
    if (data.endTime !== undefined) {
      await this.endTimeInput.fill(data.endTime);
    }
    if (data.timezone !== undefined) {
      await this.timezoneSelect.selectOption(data.timezone);
    }
    if (data.channels !== undefined) {
      for (const channel of data.channels) {
        await this.channelButtons.filter({ hasText: new RegExp(`^${channel}$`, 'i') }).click();
      }
    }
    if (data.cooldown !== undefined) {
      await this.cooldownInput.fill(String(data.cooldown));
    }
  }

  /**
   * Submit the rule form
   */
  async submitRuleForm(): Promise<void> {
    await this.submitButton.click();
  }

  /**
   * Get the count of rules in the table
   */
  async getRuleCount(): Promise<number> {
    return this.ruleRows.count();
  }

  /**
   * Check if empty state is displayed
   */
  async hasEmptyState(): Promise<boolean> {
    return this.emptyState.isVisible().catch(() => false);
  }

  /**
   * Check if error state is displayed
   */
  async hasError(): Promise<boolean> {
    return this.errorMessage.isVisible().catch(() => false);
  }

  /**
   * Click edit button for a rule by index
   */
  async editRule(index: number = 0): Promise<void> {
    const editButton = this.editButtons.nth(index);
    await expect(editButton).toBeVisible({ timeout: this.pageLoadTimeout });
    await expect(editButton).toBeEnabled({ timeout: this.pageLoadTimeout });

    // Click button first, then wait for modal to appear
    // Sequential execution avoids race condition where wait starts before click completes
    // Modal has 300ms animation, plus rendering time in CI can be slow (especially webkit)
    await editButton.click();
    await this.modalTitle.waitFor({ state: 'visible', timeout: 20000 });
  }

  /**
   * Click delete button for a rule by index
   */
  async deleteRule(index: number = 0): Promise<void> {
    await this.deleteButtons.nth(index).click();
    await expect(this.deleteModalTitle).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Confirm deletion in the delete modal
   */
  async confirmDelete(): Promise<void> {
    await this.deleteModalConfirmButton.click();
    await expect(this.deleteModalTitle).not.toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Cancel deletion in the delete modal
   */
  async cancelDelete(): Promise<void> {
    await this.deleteModalCancelButton.click();
    await expect(this.deleteModalTitle).not.toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Click test button for a rule by index
   */
  async testRule(index: number = 0): Promise<void> {
    const testButton = this.testButtons.nth(index);
    await expect(testButton).toBeVisible({ timeout: this.pageLoadTimeout });
    await expect(testButton).toBeEnabled({ timeout: this.pageLoadTimeout });

    // Click button first, then wait for modal to appear
    // Sequential execution avoids race condition where wait starts before click completes
    // Modal has 300ms animation, plus rendering time in CI can be slow (especially webkit)
    await testButton.click();
    await this.testModalTitle.waitFor({ state: 'visible', timeout: 20000 });
  }

  /**
   * Close the test modal
   */
  async closeTestModal(): Promise<void> {
    await this.testModalCloseButton.click();
    await expect(this.testModalTitle).not.toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Wait for test results to load
   */
  async waitForTestResults(): Promise<void> {
    // Wait for loading to disappear
    await this.testLoading.waitFor({ state: 'hidden', timeout: this.pageLoadTimeout }).catch(() => {});
    // Wait for results or "no events" message
    await Promise.race([
      this.eventsTested.first().waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
      this.noEventsMessage.waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
    ]).catch(() => {});
  }

  /**
   * Toggle a rule's enabled state by index
   */
  async toggleRuleEnabled(index: number = 0): Promise<void> {
    await this.ruleToggleSwitches.nth(index).click();
  }

  /**
   * Get the name of a rule by index
   */
  async getRuleName(index: number = 0): Promise<string | null> {
    return this.ruleNameCells.nth(index).locator('span.font-medium').textContent();
  }

  /**
   * Get the severity of a rule by index
   */
  async getRuleSeverity(index: number = 0): Promise<string | null> {
    return this.ruleSeverityBadges.nth(index).textContent();
  }

  /**
   * Check if a rule is enabled by index
   */
  async isRuleEnabled(index: number = 0): Promise<boolean> {
    const toggle = this.ruleToggleSwitches.nth(index);
    const ariaChecked = await toggle.getAttribute('aria-checked');
    return ariaChecked === 'true';
  }

  /**
   * Find a rule row by name
   */
  getRuleRowByName(name: string): Locator {
    return this.ruleRows.filter({ hasText: name });
  }

  /**
   * Edit a rule by name
   */
  async editRuleByName(name: string): Promise<void> {
    const row = this.getRuleRowByName(name);
    const editButton = row.locator('button[aria-label^="Edit"]');
    await expect(editButton).toBeVisible({ timeout: this.pageLoadTimeout });
    await expect(editButton).toBeEnabled({ timeout: this.pageLoadTimeout });

    // Click button first, then wait for modal to appear
    // Sequential execution avoids race condition where wait starts before click completes
    // Modal has 300ms animation, plus rendering time in CI can be slow (especially webkit)
    await editButton.click();
    await this.modalTitle.waitFor({ state: 'visible', timeout: 20000 });
  }

  /**
   * Delete a rule by name
   */
  async deleteRuleByName(name: string): Promise<void> {
    const row = this.getRuleRowByName(name);
    await row.locator('button[aria-label^="Delete"]').click();
    await expect(this.deleteModalTitle).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Test a rule by name
   */
  async testRuleByName(name: string): Promise<void> {
    const row = this.getRuleRowByName(name);
    const testButton = row.locator('button[aria-label^="Test"]');
    await expect(testButton).toBeVisible({ timeout: this.pageLoadTimeout });
    await expect(testButton).toBeEnabled({ timeout: this.pageLoadTimeout });

    // Click button first, then wait for modal to appear
    // Sequential execution avoids race condition where wait starts before click completes
    // Modal has 300ms animation, plus rendering time in CI can be slow (especially webkit)
    await testButton.click();
    await this.testModalTitle.waitFor({ state: 'visible', timeout: 20000 });
  }

  /**
   * Toggle a rule's enabled state by name
   */
  async toggleRuleEnabledByName(name: string): Promise<void> {
    const row = this.getRuleRowByName(name);
    await row.locator('button[role="switch"]').click();
  }
}
