/**
 * AlertRulesPage - Page Object for the Alert Rules management page
 *
 * Provides selectors and interactions for:
 * - Alert rule listing and filtering
 * - CRUD operations for alert rules
 * - Rule form fields and validation
 * - Enable/disable toggle
 * - Rule testing functionality
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class AlertRulesPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;

  // Rule List
  readonly rulesList: Locator;
  readonly ruleCards: Locator;
  readonly emptyRulesMessage: Locator;

  // Filters
  readonly enabledFilter: Locator;
  readonly severityFilter: Locator;
  readonly searchInput: Locator;

  // Actions
  readonly createRuleButton: Locator;
  readonly refreshButton: Locator;

  // Pagination
  readonly previousPageButton: Locator;
  readonly nextPageButton: Locator;
  readonly pageInfo: Locator;

  // Rule Form Modal
  readonly ruleModal: Locator;
  readonly modalTitle: Locator;
  readonly closeModalButton: Locator;

  // Rule Form Fields
  readonly nameInput: Locator;
  readonly descriptionInput: Locator;
  readonly enabledToggle: Locator;
  readonly severitySelect: Locator;
  readonly riskThresholdInput: Locator;
  readonly objectTypesSelect: Locator;
  readonly cameraIdsSelect: Locator;
  readonly minConfidenceInput: Locator;
  readonly cooldownSecondsInput: Locator;
  readonly dedupKeyTemplateInput: Locator;
  readonly channelsSelect: Locator;

  // Schedule Fields
  readonly scheduleSection: Locator;
  readonly startTimeInput: Locator;
  readonly endTimeInput: Locator;
  readonly timezoneSelect: Locator;
  readonly dayCheckboxes: Locator;

  // Form Actions
  readonly saveButton: Locator;
  readonly cancelButton: Locator;
  readonly deleteButton: Locator;
  readonly testRuleButton: Locator;

  // Validation Messages
  readonly validationErrors: Locator;
  readonly nameRequiredError: Locator;
  readonly formSuccessMessage: Locator;
  readonly formErrorMessage: Locator;

  // Delete Confirmation Modal
  readonly deleteConfirmModal: Locator;
  readonly confirmDeleteButton: Locator;
  readonly cancelDeleteButton: Locator;

  // Test Rule Section
  readonly testResultsSection: Locator;
  readonly testResultsCount: Locator;
  readonly testResultsMatchRate: Locator;
  readonly testResultsEvents: Locator;

  // Loading/Error States
  readonly loadingSpinner: Locator;
  readonly loadingText: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /Alert Rules/i }).first();
    this.pageSubtitle = page.getByText(/Manage alert rules/i);

    // Rule List
    this.rulesList = page.locator('[data-testid="rules-list"]');
    this.ruleCards = page.locator('[data-testid^="rule-card-"]');
    this.emptyRulesMessage = page.getByText(/No alert rules/i);

    // Filters
    this.enabledFilter = page.locator('#enabled-filter');
    this.severityFilter = page.locator('#severity-filter');
    this.searchInput = page.getByPlaceholder(/Search rules/i);

    // Actions
    this.createRuleButton = page.getByRole('button', { name: /Create Rule|Add Rule|New Rule/i });
    this.refreshButton = page.getByRole('button', { name: /Refresh/i });

    // Pagination
    this.previousPageButton = page.getByRole('button', { name: /Previous/i });
    this.nextPageButton = page.getByRole('button', { name: /Next/i });
    this.pageInfo = page.getByText(/Page \d+ of \d+/i);

    // Rule Form Modal
    this.ruleModal = page.locator('[data-testid="rule-modal"], [role="dialog"]');
    this.modalTitle = this.ruleModal.getByRole('heading').first();
    this.closeModalButton = this.ruleModal.getByRole('button', { name: /Close|X/i });

    // Rule Form Fields
    this.nameInput = page.getByLabel(/Name/i);
    this.descriptionInput = page.getByLabel(/Description/i);
    this.enabledToggle = page.getByRole('switch', { name: /Enabled/i }).or(
      page.locator('[data-testid="enabled-toggle"]')
    );
    this.severitySelect = page.getByLabel(/Severity/i);
    this.riskThresholdInput = page.getByLabel(/Risk Threshold/i);
    this.objectTypesSelect = page.getByLabel(/Object Types/i);
    this.cameraIdsSelect = page.getByLabel(/Cameras/i);
    this.minConfidenceInput = page.getByLabel(/Minimum Confidence/i);
    this.cooldownSecondsInput = page.getByLabel(/Cooldown/i);
    this.dedupKeyTemplateInput = page.getByLabel(/Dedup Key/i);
    this.channelsSelect = page.getByLabel(/Notification Channels/i);

    // Schedule Fields
    this.scheduleSection = page.locator('[data-testid="schedule-section"]');
    this.startTimeInput = page.getByLabel(/Start Time/i);
    this.endTimeInput = page.getByLabel(/End Time/i);
    this.timezoneSelect = page.getByLabel(/Timezone/i);
    this.dayCheckboxes = page.locator('[data-testid^="day-checkbox-"]');

    // Form Actions
    this.saveButton = page.getByRole('button', { name: /Save|Create|Update/i });
    this.cancelButton = page.getByRole('button', { name: /Cancel/i });
    this.deleteButton = page.getByRole('button', { name: /Delete/i });
    this.testRuleButton = page.getByRole('button', { name: /Test Rule/i });

    // Validation Messages
    this.validationErrors = page.locator('[data-testid="validation-error"], .text-red-500, .error-message');
    this.nameRequiredError = page.getByText(/Name is required/i);
    this.formSuccessMessage = page.getByText(/saved successfully|created successfully|Rule updated/i);
    this.formErrorMessage = page.getByText(/Failed to save|Error saving|Could not create/i);

    // Delete Confirmation Modal
    this.deleteConfirmModal = page.locator('[data-testid="delete-confirm-modal"], [role="alertdialog"]');
    this.confirmDeleteButton = page.getByRole('button', { name: /Confirm|Yes, Delete/i });
    this.cancelDeleteButton = this.deleteConfirmModal.getByRole('button', { name: /Cancel|No/i });

    // Test Rule Section
    this.testResultsSection = page.locator('[data-testid="test-results"]');
    this.testResultsCount = page.getByText(/Events tested:/i);
    this.testResultsMatchRate = page.getByText(/Match rate:/i);
    this.testResultsEvents = page.locator('[data-testid^="test-result-event-"]');

    // Loading/Error States
    this.loadingSpinner = page.locator('.animate-spin');
    this.loadingText = page.getByText(/Loading rules/i);
    this.errorMessage = page.getByText(/Error loading rules|Failed to load/i);
  }

  /**
   * Navigate to the Alert Rules page
   */
  async goto(): Promise<void> {
    await this.page.goto('/alerts/rules');
  }

  /**
   * Wait for the alert rules page to fully load (including data)
   */
  async waitForRulesLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
    // Wait for either rules list OR empty message OR error state
    await Promise.race([
      this.ruleCards.first().waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
      this.emptyRulesMessage.waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
      this.errorMessage.waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
    ]).catch(() => {
      // One should appear, but continue anyway if neither does
    });
  }

  /**
   * Filter rules by enabled status
   */
  async filterByEnabled(value: 'all' | 'enabled' | 'disabled'): Promise<void> {
    await this.enabledFilter.selectOption(value);
  }

  /**
   * Filter rules by severity
   */
  async filterBySeverity(severity: 'all' | 'low' | 'medium' | 'high' | 'critical'): Promise<void> {
    await this.severityFilter.selectOption(severity);
  }

  /**
   * Search for rules by name
   */
  async searchRules(query: string): Promise<void> {
    await this.searchInput.fill(query);
  }

  /**
   * Get count of displayed rules
   */
  async getRuleCount(): Promise<number> {
    return this.ruleCards.count();
  }

  /**
   * Click on a rule card to edit it
   */
  async clickRule(index: number = 0): Promise<void> {
    await this.ruleCards.nth(index).click();
  }

  /**
   * Click on a rule by name
   */
  async clickRuleByName(name: string): Promise<void> {
    await this.page.locator('[data-testid^="rule-card-"]', { hasText: name }).click();
  }

  /**
   * Open the create rule modal
   */
  async openCreateRuleModal(): Promise<void> {
    await this.createRuleButton.click();
    await expect(this.ruleModal).toBeVisible();
  }

  /**
   * Close the rule modal
   */
  async closeRuleModal(): Promise<void> {
    await this.closeModalButton.click();
    await expect(this.ruleModal).not.toBeVisible();
  }

  /**
   * Fill the rule form with provided data
   */
  async fillRuleForm(data: {
    name?: string;
    description?: string;
    enabled?: boolean;
    severity?: 'low' | 'medium' | 'high' | 'critical';
    riskThreshold?: number;
    objectTypes?: string[];
    minConfidence?: number;
    cooldownSeconds?: number;
  }): Promise<void> {
    if (data.name !== undefined) {
      await this.nameInput.fill(data.name);
    }
    if (data.description !== undefined) {
      await this.descriptionInput.fill(data.description);
    }
    if (data.enabled !== undefined) {
      const isChecked = await this.enabledToggle.isChecked();
      if (isChecked !== data.enabled) {
        await this.enabledToggle.click();
      }
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
    if (data.cooldownSeconds !== undefined) {
      await this.cooldownSecondsInput.fill(String(data.cooldownSeconds));
    }
  }

  /**
   * Save the rule form
   */
  async saveRule(): Promise<void> {
    await this.saveButton.click();
  }

  /**
   * Cancel rule editing
   */
  async cancelRuleEdit(): Promise<void> {
    await this.cancelButton.click();
  }

  /**
   * Delete the current rule (opens confirmation)
   */
  async deleteRule(): Promise<void> {
    await this.deleteButton.click();
    await expect(this.deleteConfirmModal).toBeVisible();
  }

  /**
   * Confirm rule deletion
   */
  async confirmDelete(): Promise<void> {
    await this.confirmDeleteButton.click();
    await expect(this.deleteConfirmModal).not.toBeVisible();
  }

  /**
   * Cancel rule deletion
   */
  async cancelDelete(): Promise<void> {
    await this.cancelDeleteButton.click();
    await expect(this.deleteConfirmModal).not.toBeVisible();
  }

  /**
   * Toggle rule enabled status from the list (not modal)
   */
  async toggleRuleEnabled(index: number = 0): Promise<void> {
    const ruleCard = this.ruleCards.nth(index);
    const toggle = ruleCard.getByRole('switch').or(ruleCard.locator('[data-testid="enabled-toggle"]'));
    await toggle.click();
  }

  /**
   * Test a rule against historical events
   */
  async testRule(): Promise<void> {
    await this.testRuleButton.click();
    await expect(this.testResultsSection).toBeVisible();
  }

  /**
   * Check if no rules message is shown
   */
  async hasNoRulesMessage(): Promise<boolean> {
    return this.emptyRulesMessage.isVisible().catch(() => false);
  }

  /**
   * Check if loading state is shown
   */
  async isLoading(): Promise<boolean> {
    return this.loadingText.isVisible().catch(() => false);
  }

  /**
   * Check if error state is shown
   */
  async hasError(): Promise<boolean> {
    try {
      await this.errorMessage.waitFor({ state: 'visible', timeout: this.pageLoadTimeout });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Check if validation errors are visible
   */
  async hasValidationErrors(): Promise<boolean> {
    return this.validationErrors.first().isVisible().catch(() => false);
  }

  /**
   * Check if success message is shown
   */
  async hasSuccessMessage(): Promise<boolean> {
    return this.formSuccessMessage.isVisible().catch(() => false);
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
   * Get the name of a rule card
   */
  async getRuleName(index: number = 0): Promise<string | null> {
    const nameElement = this.ruleCards.nth(index).locator('[data-testid="rule-name"], h3, h4').first();
    return nameElement.textContent();
  }

  /**
   * Check if a rule is enabled (by looking at the badge/toggle state)
   */
  async isRuleEnabled(index: number = 0): Promise<boolean> {
    const ruleCard = this.ruleCards.nth(index);
    const enabledBadge = ruleCard.getByText(/Enabled/i);
    const disabledBadge = ruleCard.getByText(/Disabled/i);
    const isEnabledBadgeVisible = await enabledBadge.isVisible().catch(() => false);
    const isDisabledBadgeVisible = await disabledBadge.isVisible().catch(() => false);

    if (isEnabledBadgeVisible) return true;
    if (isDisabledBadgeVisible) return false;

    // Fallback to toggle state
    const toggle = ruleCard.getByRole('switch');
    return toggle.isChecked().catch(() => false);
  }

  /**
   * Refresh the rules list
   */
  async refresh(): Promise<void> {
    await this.refreshButton.click();
  }
}
