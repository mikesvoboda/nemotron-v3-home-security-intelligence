/**
 * Alert Rules E2E Tests for Home Security Dashboard
 *
 * Comprehensive tests for the Alert Rules Settings functionality including:
 * - Page load and navigation
 * - Creating new alert rules with form validation
 * - Editing existing alert rules
 * - Deleting alert rules with confirmation dialog
 * - Enabling/disabling rules via toggle
 * - Testing rules against sample events
 * - Empty and error states
 *
 * @file frontend/tests/e2e/specs/alert-rules.spec.ts
 */

import { test, expect } from '@playwright/test';
import { AlertRulesPage } from '../pages';
import {
  setupApiMocks,
  defaultMockConfig,
  emptyMockConfig,
  errorMockConfig,
  type ApiMockConfig,
} from '../fixtures';
import { mockRuleTestResults } from '../fixtures/test-data';

test.describe('Alert Rules Page Load', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
  });

  test('navigates to alert rules tab successfully', async () => {
    await alertRulesPage.goto();
    await expect(alertRulesPage.alertRulesHeader).toBeVisible();
  });

  test('displays alert rules header and description', async () => {
    await alertRulesPage.goto();
    await expect(alertRulesPage.alertRulesHeader).toHaveText(/Alert Rules/i);
    await expect(alertRulesPage.alertRulesDescription).toBeVisible();
  });

  test('displays Add Rule button', async () => {
    await alertRulesPage.goto();
    await expect(alertRulesPage.addRuleButton).toBeVisible();
  });

  test('displays rules table with mock data', async () => {
    await alertRulesPage.goto();
    await expect(alertRulesPage.rulesTable).toBeVisible();
    const count = await alertRulesPage.getRuleCount();
    expect(count).toBe(4); // 4 mock rules
  });

  test('displays rule names correctly', async () => {
    await alertRulesPage.goto();
    const firstName = await alertRulesPage.getRuleName(0);
    expect(firstName).toBeTruthy();
  });
});

test.describe('Alert Rules Empty State', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    const emptyRulesConfig: ApiMockConfig = {
      ...defaultMockConfig,
      alertRules: [],
    };
    await setupApiMocks(page, emptyRulesConfig);
    alertRulesPage = new AlertRulesPage(page);
  });

  test('displays empty state when no rules exist', async () => {
    await alertRulesPage.goto();
    const hasEmpty = await alertRulesPage.hasEmptyState();
    expect(hasEmpty).toBe(true);
  });

  test('displays Add Rule button in empty state', async () => {
    await alertRulesPage.goto();
    await expect(alertRulesPage.emptyStateAddButton).toBeVisible();
  });

  test('can open add rule modal from empty state', async () => {
    await alertRulesPage.goto();
    await alertRulesPage.openAddRuleModalFromEmptyState();
    // Use modalTitle instead of ruleModal due to Headless UI Transition visibility handling
    await expect(alertRulesPage.modalTitle).toBeVisible();
  });
});

test.describe('Alert Rules Error State', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    const errorRulesConfig: ApiMockConfig = {
      ...defaultMockConfig,
      alertRulesError: true,
    };
    await setupApiMocks(page, errorRulesConfig);
    alertRulesPage = new AlertRulesPage(page);
  });

  test('displays error state when API fails', async () => {
    await alertRulesPage.goto();
    // Wait for error message to be visible with explicit timeout
    await expect(alertRulesPage.errorMessage).toBeVisible({ timeout: 10000 });
  });

  test('displays try again button on error', async () => {
    await alertRulesPage.goto();
    await expect(alertRulesPage.tryAgainButton).toBeVisible();
  });
});

test.describe('Create Alert Rule', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
  });

  test('opens add rule modal when clicking Add Rule button', async () => {
    await alertRulesPage.openAddRuleModal();
    // Check modal title is visible - more reliable than checking dialog element
    // due to Headless UI Transition component visibility handling
    await expect(alertRulesPage.modalTitle).toBeVisible();
    await expect(alertRulesPage.modalTitle).toHaveText(/Add Alert Rule/i);
  });

  test('modal has all required form fields', async () => {
    await alertRulesPage.openAddRuleModal();
    await expect(alertRulesPage.nameInput).toBeVisible();
    await expect(alertRulesPage.descriptionInput).toBeVisible();
    await expect(alertRulesPage.severitySelect).toBeVisible();
    await expect(alertRulesPage.riskThresholdInput).toBeVisible();
    await expect(alertRulesPage.minConfidenceInput).toBeVisible();
    await expect(alertRulesPage.cooldownInput).toBeVisible();
  });

  test('can close modal with X button', async () => {
    await alertRulesPage.openAddRuleModal();
    await alertRulesPage.closeRuleModal();
    await expect(alertRulesPage.ruleModal).not.toBeVisible();
  });

  test('can close modal with Cancel button', async () => {
    await alertRulesPage.openAddRuleModal();
    await alertRulesPage.cancelRuleModal();
    await expect(alertRulesPage.ruleModal).not.toBeVisible();
  });

  test('creates a new rule with minimal data', async ({ page }) => {
    await alertRulesPage.openAddRuleModal();

    await alertRulesPage.fillRuleForm({
      name: 'Test Alert Rule',
      severity: 'high',
    });

    // Wait for request and submit
    const responsePromise = page.waitForResponse('**/api/alerts/rules');
    await alertRulesPage.submitRuleForm();
    await responsePromise;

    // Modal should close on success
    await expect(alertRulesPage.ruleModal).not.toBeVisible({ timeout: 5000 });
  });

  test('creates a rule with full configuration', async ({ page }) => {
    await alertRulesPage.openAddRuleModal();

    await alertRulesPage.fillRuleForm({
      name: 'Full Config Rule',
      description: 'A rule with all options configured',
      severity: 'critical',
      riskThreshold: 75,
      minConfidence: 0.9,
      objectTypes: ['person', 'vehicle'],
      cooldown: 600,
      channels: ['email', 'webhook'],
    });

    const responsePromise = page.waitForResponse('**/api/alerts/rules');
    await alertRulesPage.submitRuleForm();
    await responsePromise;

    await expect(alertRulesPage.ruleModal).not.toBeVisible({ timeout: 5000 });
  });

  test('shows validation error for empty name', async () => {
    await alertRulesPage.openAddRuleModal();

    // Leave name empty, just set severity
    await alertRulesPage.fillRuleForm({
      name: '',
      severity: 'medium',
    });

    await alertRulesPage.submitRuleForm();

    // Should show validation error
    await expect(alertRulesPage.nameError).toBeVisible();
  });

  test('shows validation error for single character name', async () => {
    await alertRulesPage.openAddRuleModal();

    await alertRulesPage.fillRuleForm({
      name: 'A',
      severity: 'medium',
    });

    await alertRulesPage.submitRuleForm();

    // Should show validation error (name must be at least 2 characters)
    await expect(alertRulesPage.nameError).toBeVisible();
  });
});

test.describe('Edit Alert Rule', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
  });

  test('opens edit modal when clicking edit button', async () => {
    await alertRulesPage.editRule(0);
    await expect(alertRulesPage.modalTitle).toBeVisible();
    await expect(alertRulesPage.modalTitle).toHaveText(/Edit Alert Rule/i);
  });

  test('edit modal pre-fills existing rule data', async () => {
    await alertRulesPage.editRule(0);

    // Name should be pre-filled with existing rule name
    const nameValue = await alertRulesPage.nameInput.inputValue();
    expect(nameValue).toBeTruthy();
  });

  test('can update an existing rule', async ({ page }) => {
    await alertRulesPage.editRule(0);

    // Clear and fill with new name
    await alertRulesPage.nameInput.clear();
    await alertRulesPage.fillRuleForm({
      name: 'Updated Rule Name',
    });

    // Wait for PUT request
    const responsePromise = page.waitForResponse((response) =>
      response.url().includes('/api/alerts/rules/') && response.request().method() === 'PUT'
    );
    await alertRulesPage.submitRuleForm();
    await responsePromise;

    await expect(alertRulesPage.ruleModal).not.toBeVisible({ timeout: 5000 });
  });

  test('can edit rule by name', async () => {
    await alertRulesPage.editRuleByName('Night Intruder Alert');
    // editRuleByName already waits for modal title to be visible
    await expect(alertRulesPage.modalTitle).toBeVisible();
  });
});

test.describe('Delete Alert Rule', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
  });

  test('opens delete confirmation dialog when clicking delete', async () => {
    await alertRulesPage.deleteRule(0);
    // deleteRule already waits for deleteModalTitle to be visible
    await expect(alertRulesPage.deleteModalTitle).toBeVisible();
  });

  test('delete dialog shows rule name', async () => {
    await alertRulesPage.deleteRule(0);
    await expect(alertRulesPage.deleteModalMessage).toBeVisible();
  });

  test('can cancel delete operation', async () => {
    await alertRulesPage.deleteRule(0);
    await alertRulesPage.cancelDelete();
    await expect(alertRulesPage.deleteModal).not.toBeVisible();
  });

  test('can confirm and delete rule', async ({ page }) => {
    await alertRulesPage.deleteRule(0);

    // Wait for DELETE request
    const responsePromise = page.waitForResponse((response) =>
      response.url().includes('/api/alerts/rules/') && response.request().method() === 'DELETE'
    );
    await alertRulesPage.confirmDelete();
    await responsePromise;

    // Modal should close
    await expect(alertRulesPage.deleteModal).not.toBeVisible({ timeout: 5000 });
  });

  test('can delete rule by name', async () => {
    await alertRulesPage.deleteRuleByName('Vehicle Detection');
    // deleteRuleByName already waits for delete modal title to be visible
    await expect(alertRulesPage.deleteModalTitle).toBeVisible();
  });
});

test.describe('Toggle Alert Rule Enabled State', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
  });

  test('displays toggle switches for each rule', async () => {
    const toggleCount = await alertRulesPage.ruleToggleSwitches.count();
    expect(toggleCount).toBe(4); // 4 mock rules
  });

  test('can toggle rule enabled state', async ({ page }) => {
    // Wait for PUT request when toggling
    const responsePromise = page.waitForResponse((response) =>
      response.url().includes('/api/alerts/rules/') && response.request().method() === 'PUT'
    );

    await alertRulesPage.toggleRuleEnabled(0);
    await responsePromise;
  });

  test('can toggle rule by name', async ({ page }) => {
    const responsePromise = page.waitForResponse((response) =>
      response.url().includes('/api/alerts/rules/') && response.request().method() === 'PUT'
    );

    await alertRulesPage.toggleRuleEnabledByName('Animal Alert');
    await responsePromise;
  });
});

test.describe('Test Alert Rule', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
  });

  test('opens test modal when clicking test button', async () => {
    await alertRulesPage.testRule(0);
    // testRule already waits for testModalTitle to be visible
    await expect(alertRulesPage.testModalTitle).toBeVisible();
  });

  test('test modal shows rule name in title', async () => {
    await alertRulesPage.testRule(0);
    await expect(alertRulesPage.testModalTitle).toContainText(/Test Rule:/i);
  });

  test('displays test results after loading', async () => {
    await alertRulesPage.testRule(0);
    await alertRulesPage.waitForTestResults();

    // Should show test statistics
    const modalText = await alertRulesPage.testModal.textContent();
    expect(modalText).toContain('Events Tested');
    expect(modalText).toContain('Matched');
    expect(modalText).toContain('Match Rate');
  });

  test('can close test modal', async () => {
    await alertRulesPage.testRule(0);
    await alertRulesPage.waitForTestResults();
    await alertRulesPage.closeTestModal();
    await expect(alertRulesPage.testModal).not.toBeVisible();
  });

  test('can test rule by name', async () => {
    await alertRulesPage.testRuleByName('High Risk Event');
    // testRuleByName already waits for test modal title to be visible
    await expect(alertRulesPage.testModalTitle).toBeVisible();
  });

  test('shows matched events in results', async () => {
    await alertRulesPage.testRule(0);
    await alertRulesPage.waitForTestResults();

    // With default mock data, we should see some matched events
    const resultsText = await alertRulesPage.testModal.textContent();
    expect(resultsText).toContain('5'); // events_tested from mock
    expect(resultsText).toContain('3'); // events_matched from mock
  });
});

test.describe('Test Alert Rule - No Events', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    const noEventsConfig: ApiMockConfig = {
      ...defaultMockConfig,
      ruleTestResults: mockRuleTestResults.noEvents,
    };
    await setupApiMocks(page, noEventsConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
  });

  test('shows no events message when no events to test', async () => {
    await alertRulesPage.testRule(0);
    await alertRulesPage.waitForTestResults();

    await expect(alertRulesPage.noEventsMessage).toBeVisible();
  });
});

test.describe('Test Alert Rule - No Matches', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    const noMatchesConfig: ApiMockConfig = {
      ...defaultMockConfig,
      ruleTestResults: mockRuleTestResults.noMatches,
    };
    await setupApiMocks(page, noMatchesConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
  });

  test('shows zero matched when no events match', async () => {
    await alertRulesPage.testRule(0);
    await alertRulesPage.waitForTestResults();

    const resultsText = await alertRulesPage.testModal.textContent();
    // events_matched should be 0
    expect(resultsText).toContain('0');
  });
});

test.describe('Alert Rules Form Validation', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
  });

  test('accepts valid risk threshold', async ({ page }) => {
    await alertRulesPage.openAddRuleModal();

    await alertRulesPage.fillRuleForm({
      name: 'Valid Risk Rule',
      riskThreshold: 80, // Valid: 0-100
      severity: 'high',
    });

    const responsePromise = page.waitForResponse('**/api/alerts/rules');
    await alertRulesPage.submitRuleForm();
    await responsePromise;

    await expect(alertRulesPage.modalTitle).not.toBeVisible({ timeout: 5000 });
  });

  test('accepts valid min confidence', async ({ page }) => {
    await alertRulesPage.openAddRuleModal();

    // Use fillRuleForm with minConfidence value (0.8 is valid - aligns with step=0.1)
    // Note: The input has step=0.1, so values like 0.85 won't pass browser validation
    await alertRulesPage.fillRuleForm({
      name: 'Valid Confidence Rule',
      minConfidence: 0.8,
      severity: 'medium',
    });

    const responsePromise = page.waitForResponse('**/api/alerts/rules');
    await alertRulesPage.submitRuleForm();
    await responsePromise;

    // Check modal closed (form submitted successfully)
    await expect(alertRulesPage.modalTitle).not.toBeVisible({ timeout: 5000 });
  });

  test('accepts boundary values for risk threshold', async ({ page }) => {
    await alertRulesPage.openAddRuleModal();

    await alertRulesPage.fillRuleForm({
      name: 'Boundary Risk Rule',
      riskThreshold: 0, // Valid: boundary 0
      severity: 'low',
    });

    const responsePromise = page.waitForResponse('**/api/alerts/rules');
    await alertRulesPage.submitRuleForm();
    await responsePromise;

    await expect(alertRulesPage.modalTitle).not.toBeVisible({ timeout: 5000 });
  });

  test('accepts boundary values for min confidence', async ({ page }) => {
    await alertRulesPage.openAddRuleModal();

    await alertRulesPage.fillRuleForm({
      name: 'Boundary Confidence Rule',
      minConfidence: 1, // Valid: boundary 1
      severity: 'critical',
    });

    const responsePromise = page.waitForResponse('**/api/alerts/rules');
    await alertRulesPage.submitRuleForm();
    await responsePromise;

    await expect(alertRulesPage.modalTitle).not.toBeVisible({ timeout: 5000 });
  });
});

test.describe('Alert Rules Object Type Selection', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
  });

  test('displays object type buttons', async () => {
    await alertRulesPage.openAddRuleModal();

    // Check that object type buttons are visible
    const personButton = alertRulesPage.ruleModal.locator('button').filter({ hasText: /^person$/i });
    const vehicleButton = alertRulesPage.ruleModal.locator('button').filter({ hasText: /^vehicle$/i });
    const animalButton = alertRulesPage.ruleModal.locator('button').filter({ hasText: /^animal$/i });

    await expect(personButton).toBeVisible();
    await expect(vehicleButton).toBeVisible();
    await expect(animalButton).toBeVisible();
  });

  test('can select multiple object types', async ({ page }) => {
    await alertRulesPage.openAddRuleModal();

    // Select person and vehicle
    await alertRulesPage.fillRuleForm({
      name: 'Multi Object Rule',
      objectTypes: ['person', 'vehicle'],
      severity: 'high',
    });

    const responsePromise = page.waitForResponse('**/api/alerts/rules');
    await alertRulesPage.submitRuleForm();
    const response = await responsePromise;

    // Verify the request body contains the selected object types
    const requestBody = response.request().postDataJSON();
    expect(requestBody.object_types).toContain('person');
    expect(requestBody.object_types).toContain('vehicle');
  });
});

test.describe('Alert Rules Notification Channels', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
  });

  test('displays channel buttons', async () => {
    await alertRulesPage.openAddRuleModal();

    // Check that channel buttons are visible
    const emailButton = alertRulesPage.ruleModal.locator('button').filter({ hasText: /^email$/i });
    const webhookButton = alertRulesPage.ruleModal.locator('button').filter({ hasText: /^webhook$/i });
    const pushoverButton = alertRulesPage.ruleModal.locator('button').filter({ hasText: /^pushover$/i });

    await expect(emailButton).toBeVisible();
    await expect(webhookButton).toBeVisible();
    await expect(pushoverButton).toBeVisible();
  });

  test('can select notification channels', async ({ page }) => {
    await alertRulesPage.openAddRuleModal();

    await alertRulesPage.fillRuleForm({
      name: 'Channel Test Rule',
      channels: ['email', 'pushover'],
      severity: 'critical',
    });

    const responsePromise = page.waitForResponse('**/api/alerts/rules');
    await alertRulesPage.submitRuleForm();
    const response = await responsePromise;

    // Verify the request body contains the selected channels
    const requestBody = response.request().postDataJSON();
    expect(requestBody.channels).toContain('email');
    expect(requestBody.channels).toContain('pushover');
  });
});

test.describe('Alert Rules Severity Selection', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
  });

  test('can select all severity levels', async () => {
    await alertRulesPage.openAddRuleModal();

    // Test all severity options
    for (const severity of ['low', 'medium', 'high', 'critical'] as const) {
      await alertRulesPage.severitySelect.selectOption(severity);
      await expect(alertRulesPage.severitySelect).toHaveValue(severity);
    }
  });

  test('severity is required and has default value', async () => {
    await alertRulesPage.openAddRuleModal();

    // Default severity should be 'medium'
    const defaultValue = await alertRulesPage.severitySelect.inputValue();
    expect(['low', 'medium', 'high', 'critical']).toContain(defaultValue);
  });
});

test.describe('Alert Rules Table Display', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
  });

  test('displays severity badges for each rule', async () => {
    const badgeCount = await alertRulesPage.ruleSeverityBadges.count();
    expect(badgeCount).toBe(4); // 4 mock rules
  });

  test('displays action buttons for each rule', async () => {
    const testCount = await alertRulesPage.testButtons.count();
    const editCount = await alertRulesPage.editButtons.count();
    const deleteCount = await alertRulesPage.deleteButtons.count();

    expect(testCount).toBe(4);
    expect(editCount).toBe(4);
    expect(deleteCount).toBe(4);
  });

  test('table has proper column headers', async ({ page }) => {
    const headers = page.locator('table thead th');
    const headerTexts = await headers.allTextContents();

    expect(headerTexts.join(' ')).toContain('Enabled');
    expect(headerTexts.join(' ')).toContain('Name');
    expect(headerTexts.join(' ')).toContain('Severity');
    expect(headerTexts.join(' ')).toContain('Schedule');
    expect(headerTexts.join(' ')).toContain('Channels');
    expect(headerTexts.join(' ')).toContain('Actions');
  });
});

test.describe('Alert Rules Full CRUD Workflow', () => {
  let alertRulesPage: AlertRulesPage;

  test('completes full CRUD workflow', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();

    // 1. CREATE: Add a new rule
    await alertRulesPage.openAddRuleModal();
    await alertRulesPage.fillRuleForm({
      name: 'E2E Test Rule',
      description: 'Created via E2E test',
      severity: 'high',
      riskThreshold: 70,
      channels: ['email'],
    });

    let responsePromise = page.waitForResponse('**/api/alerts/rules');
    await alertRulesPage.submitRuleForm();
    await responsePromise;
    await expect(alertRulesPage.ruleModal).not.toBeVisible({ timeout: 5000 });

    // 2. READ: Verify the rules table is displayed
    await expect(alertRulesPage.rulesTable).toBeVisible();

    // 3. UPDATE: Edit the first rule
    await alertRulesPage.editRule(0);
    await alertRulesPage.nameInput.clear();
    await alertRulesPage.fillRuleForm({
      name: 'Updated E2E Rule',
    });

    responsePromise = page.waitForResponse((response) =>
      response.url().includes('/api/alerts/rules/') && response.request().method() === 'PUT'
    );
    await alertRulesPage.submitRuleForm();
    await responsePromise;
    await expect(alertRulesPage.ruleModal).not.toBeVisible({ timeout: 5000 });

    // 4. DELETE: Delete a rule
    await alertRulesPage.deleteRule(0);
    responsePromise = page.waitForResponse((response) =>
      response.url().includes('/api/alerts/rules/') && response.request().method() === 'DELETE'
    );
    await alertRulesPage.confirmDelete();
    await responsePromise;
    await expect(alertRulesPage.deleteModal).not.toBeVisible({ timeout: 5000 });
  });
});
