/**
 * AlertRulesPage - Page Object for Alert Rules management
 *
 * Provides selectors and interactions for:
 * - Alert rules list display
 * - Alert rule CRUD operations
 * - Rule enable/disable toggle
 * - Rule testing
 */

import type { Locator, Page } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class AlertRulesPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;

  // Alert rules list
  readonly rulesList: Locator;
  readonly ruleItems: Locator;
  readonly emptyState: Locator;
  readonly addRuleButton: Locator;

  // Rule item elements
  readonly ruleEditButton: Locator;
  readonly ruleDeleteButton: Locator;
  readonly ruleToggle: Locator;
  readonly ruleTestButton: Locator;
  readonly ruleSeverityBadge: Locator;

  // Rule form dialog
  readonly ruleFormDialog: Locator;
  readonly ruleNameInput: Locator;
  readonly ruleSeveritySelect: Locator;
  readonly ruleConditionInput: Locator;
  readonly ruleCameraSelect: Locator;
  readonly ruleObjectTypeSelect: Locator;
  readonly ruleScheduleSection: Locator;
  readonly ruleSaveButton: Locator;
  readonly ruleCancelButton: Locator;

  // Delete confirmation
  readonly deleteConfirmDialog: Locator;
  readonly deleteConfirmButton: Locator;
  readonly deleteCancelButton: Locator;

  // Test result
  readonly testResultDialog: Locator;
  readonly testResultMessage: Locator;
  readonly testResultClose: Locator;

  // Messages
  readonly successMessage: Locator;
  readonly errorMessage: Locator;
  readonly loadingSpinner: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /Alert Rules/i });

    // Alert rules list
    this.rulesList = page.locator('[data-testid="alert-rules-list"]');
    this.ruleItems = page.locator('[data-testid^="alert-rule-"]');
    this.emptyState = page.getByText(/No alert rules|No rules defined/i);
    this.addRuleButton = page.getByRole('button', { name: /Add Rule|Create Rule|New Rule/i });

    // Rule item elements
    this.ruleEditButton = page.locator('[data-testid="rule-edit"]');
    this.ruleDeleteButton = page.locator('[data-testid="rule-delete"]');
    this.ruleToggle = page.locator('[data-testid="rule-toggle"]');
    this.ruleTestButton = page.locator('[data-testid="rule-test"]');
    this.ruleSeverityBadge = page.locator('[data-testid="rule-severity"]');

    // Rule form dialog
    this.ruleFormDialog = page.locator('[role="dialog"]');
    this.ruleNameInput = page.getByLabel(/Rule Name|Name/i);
    this.ruleSeveritySelect = page.getByLabel(/Severity/i);
    this.ruleConditionInput = page.getByLabel(/Condition/i);
    this.ruleCameraSelect = page.getByLabel(/Camera/i);
    this.ruleObjectTypeSelect = page.getByLabel(/Object Type|Detection Type/i);
    this.ruleScheduleSection = page.locator('[data-testid="rule-schedule"]');
    this.ruleSaveButton = page.getByRole('button', { name: /Save|Create/i });
    this.ruleCancelButton = page.getByRole('button', { name: /Cancel/i });

    // Delete confirmation
    this.deleteConfirmDialog = page.locator('[role="alertdialog"]');
    this.deleteConfirmButton = page.getByRole('button', { name: /Delete|Confirm/i });
    this.deleteCancelButton = page.getByRole('button', { name: /Cancel/i });

    // Test result
    this.testResultDialog = page.locator('[data-testid="test-result-dialog"]');
    this.testResultMessage = page.locator('[data-testid="test-result-message"]');
    this.testResultClose = page.getByRole('button', { name: /Close|OK/i });

    // Messages
    this.successMessage = page.getByText(/saved|created|deleted|updated|success/i);
    this.errorMessage = page.getByText(/error|failed/i);
    this.loadingSpinner = page.locator('[data-testid="loading"]');
  }

  /**
   * Navigate to alert rules settings
   */
  async goto(): Promise<void> {
    await this.page.goto('/settings');
    // Wait for settings page to load
    await this.page.waitForLoadState('networkidle');
    // Click on Notifications tab where alert rules typically live
    const notificationsTab = this.page.getByRole('tab', { name: /NOTIFICATIONS/i });
    if (await notificationsTab.isVisible().catch(() => false)) {
      await notificationsTab.click();
    }
  }

  /**
   * Wait for alert rules to load
   */
  async waitForRulesLoad(): Promise<void> {
    await expect(this.rulesList.or(this.emptyState)).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Get count of alert rules in the list
   */
  async getRuleCount(): Promise<number> {
    return this.ruleItems.count();
  }

  /**
   * Check if rules list is empty
   */
  async isEmpty(): Promise<boolean> {
    return this.emptyState.isVisible().catch(() => false);
  }

  /**
   * Click add rule button
   */
  async clickAddRule(): Promise<void> {
    await this.addRuleButton.click();
    await expect(this.ruleFormDialog).toBeVisible();
  }

  /**
   * Click edit button on a rule by index
   */
  async clickEditRule(index: number): Promise<void> {
    await this.ruleItems.nth(index).locator('button').filter({ hasText: /edit/i }).click();
  }

  /**
   * Click delete button on a rule by index
   */
  async clickDeleteRule(index: number): Promise<void> {
    await this.ruleItems.nth(index).locator('button').filter({ hasText: /delete/i }).click();
  }

  /**
   * Toggle a rule enable/disable by index
   */
  async toggleRule(index: number): Promise<void> {
    await this.ruleItems.nth(index).locator('[role="switch"]').click();
  }

  /**
   * Click test button on a rule by index
   */
  async clickTestRule(index: number): Promise<void> {
    await this.ruleItems.nth(index).locator('button').filter({ hasText: /test/i }).click();
  }

  /**
   * Fill in rule form
   */
  async fillRuleForm(data: {
    name?: string;
    severity?: string;
    objectTypes?: string[];
  }): Promise<void> {
    if (data.name) {
      await this.ruleNameInput.fill(data.name);
    }
    if (data.severity) {
      await this.ruleSeveritySelect.selectOption(data.severity);
    }
  }

  /**
   * Save rule form
   */
  async saveRule(): Promise<void> {
    await this.ruleSaveButton.click();
  }

  /**
   * Cancel rule form
   */
  async cancelRule(): Promise<void> {
    await this.ruleCancelButton.click();
  }

  /**
   * Confirm deletion in dialog
   */
  async confirmDelete(): Promise<void> {
    await this.deleteConfirmButton.click();
  }

  /**
   * Cancel deletion in dialog
   */
  async cancelDelete(): Promise<void> {
    await this.deleteCancelButton.click();
  }

  /**
   * Check if success message is displayed
   */
  async hasSuccessMessage(): Promise<boolean> {
    return this.successMessage.isVisible().catch(() => false);
  }

  /**
   * Check if error message is displayed
   */
  async hasErrorMessage(): Promise<boolean> {
    return this.errorMessage.isVisible().catch(() => false);
  }

  /**
   * Get rule name by index
   */
  async getRuleName(index: number): Promise<string | null> {
    return this.ruleItems.nth(index).locator('[data-testid="rule-name"]').textContent();
  }

  /**
   * Get rule severity by index
   */
  async getRuleSeverity(index: number): Promise<string | null> {
    return this.ruleItems.nth(index).locator('[data-testid="rule-severity"]').textContent();
  }

  /**
   * Check if rule is enabled by index
   */
  async isRuleEnabled(index: number): Promise<boolean> {
    const toggle = this.ruleItems.nth(index).locator('[role="switch"]');
    const checked = await toggle.getAttribute('aria-checked');
    return checked === 'true';
  }
}
