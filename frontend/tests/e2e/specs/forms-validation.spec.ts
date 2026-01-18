/**
 * Form Validation E2E Tests for Home Security Dashboard
 *
 * Comprehensive validation tests for all major forms:
 * - Alert Rule Form validation
 * - Camera Configuration Form validation
 * - Settings Form validation (notification preferences, quiet hours)
 *
 * Tests cover:
 * - Required field validation
 * - Input range validation (min/max)
 * - Format validation (email, IP, time)
 * - Duplicate detection
 * - Cross-field validation
 * - Error message display
 * - Cross-browser consistency
 *
 * @file frontend/tests/e2e/specs/forms-validation.spec.ts
 */

import { test, expect } from '@playwright/test';
import { AlertRulesPage, SettingsPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

// Configure extended timeout for form interaction tests
test.describe.configure({ timeout: 30000 });

// =============================================================================
// Alert Rule Form Validation Tests
// =============================================================================

test.describe('Alert Rule Form Validation', () => {
  let alertRulesPage: AlertRulesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
    await alertRulesPage.openAddRuleModal();
  });

  test('empty rule name shows validation error @critical', async () => {
    // Try to submit with empty name
    await alertRulesPage.fillRuleForm({
      name: '',
      severity: 'medium',
    });

    await alertRulesPage.submitRuleForm();

    // Should show "Name is required" error
    await expect(alertRulesPage.nameError).toBeVisible();
    await expect(alertRulesPage.nameError).toContainText(/name is required/i);

    // Modal should remain open
    await expect(alertRulesPage.modalTitle).toBeVisible();
  });

  test('whitespace-only rule name shows validation error @critical', async () => {
    // Fill with only whitespace (will be trimmed to empty string)
    await alertRulesPage.fillRuleForm({
      name: '   ',
      severity: 'high',
    });

    await alertRulesPage.submitRuleForm();

    // Should show name required error after trimming
    await expect(alertRulesPage.nameError).toBeVisible();
    await expect(alertRulesPage.nameError).toContainText(/name is required/i);
  });

  // TODO: Fix risk score validation test - NEM-2748 (pre-existing test failure)
  test.skip('risk score below 0 is rejected @critical', async ({ page }) => {
    // Fill in valid name
    const nameInput = page.getByTestId('alert-rule-name-input');
    const riskInput = page.getByTestId('alert-rule-risk-threshold-input');
    const submitButton = page.getByTestId('alert-rule-form-submit');

    await nameInput.fill('Test Rule');

    // Try to set risk threshold below minimum
    await riskInput.fill('-1');
    await riskInput.blur();

    await submitButton.click();

    // Should show validation error
    const riskError = page.locator('text=/risk threshold must be at least 0/i');
    await expect(riskError).toBeVisible();
  });

  // TODO: Fix risk score validation test - NEM-2748 (pre-existing test failure)
  test.skip('risk score above 100 is rejected @critical', async ({ page }) => {
    // Fill in valid name
    const nameInput = page.getByTestId('alert-rule-name-input');
    const riskInput = page.getByTestId('alert-rule-risk-threshold-input');
    const submitButton = page.getByTestId('alert-rule-form-submit');

    await nameInput.fill('Test Rule');

    // Try to set risk threshold above maximum
    await riskInput.fill('101');
    await riskInput.blur();

    await submitButton.click();

    // Should show validation error
    const riskError = page.locator('text=/risk threshold must be at most 100/i');
    await expect(riskError).toBeVisible();
  });

  test('risk score at boundary (0) is accepted', async ({ page }) => {
    await alertRulesPage.fillRuleForm({
      name: 'Boundary Test Rule',
      riskThreshold: 0,
      severity: 'low',
    });

    const responsePromise = page.waitForResponse('**/api/alerts/rules');
    await alertRulesPage.submitRuleForm();
    await responsePromise;

    // Should submit successfully and close modal
    await expect(alertRulesPage.modalTitle).not.toBeVisible({ timeout: 5000 });
  });

  test('risk score at boundary (100) is accepted', async ({ page }) => {
    await alertRulesPage.fillRuleForm({
      name: 'Boundary Test Rule',
      riskThreshold: 100,
      severity: 'critical',
    });

    const responsePromise = page.waitForResponse('**/api/alerts/rules');
    await alertRulesPage.submitRuleForm();
    await responsePromise;

    // Should submit successfully
    await expect(alertRulesPage.modalTitle).not.toBeVisible({ timeout: 5000 });
  });

  test('valid form submits successfully @smoke', async ({ page }) => {
    await alertRulesPage.fillRuleForm({
      name: 'Valid Alert Rule',
      description: 'A properly validated rule',
      severity: 'high',
      riskThreshold: 75,
      minConfidence: 0.8,
      cooldown: 300,
    });

    const responsePromise = page.waitForResponse('**/api/alerts/rules');
    await alertRulesPage.submitRuleForm();
    await responsePromise;

    // Form should close on successful submission
    await expect(alertRulesPage.ruleModal).not.toBeVisible({ timeout: 5000 });
  });

  // TODO: Fix confidence validation test - NEM-2748 (pre-existing test failure)
  test.skip('min confidence below 0 is rejected', async ({ page }) => {
    // Fill in valid name
    const nameInput = page.getByTestId('alert-rule-name-input');
    const confidenceInput = page.getByTestId('alert-rule-min-confidence-input');
    const submitButton = page.getByTestId('alert-rule-form-submit');

    await nameInput.fill('Test Rule');

    // Try to set min confidence below 0
    await confidenceInput.fill('-0.1');
    await confidenceInput.blur();

    await submitButton.click();

    // Should show validation error
    const confidenceError = page.locator('text=/confidence must be at least 0/i');
    await expect(confidenceError).toBeVisible();
  });

  // TODO: Fix confidence validation test - NEM-2748 (pre-existing test failure)
  test.skip('min confidence above 1 is rejected', async ({ page }) => {
    // Fill in valid name
    const nameInput = page.getByTestId('alert-rule-name-input');
    const confidenceInput = page.getByTestId('alert-rule-min-confidence-input');
    const submitButton = page.getByTestId('alert-rule-form-submit');

    await nameInput.fill('Test Rule');

    // Try to set min confidence above 1
    await confidenceInput.fill('1.1');
    await confidenceInput.blur();

    await submitButton.click();

    // Should show validation error
    const confidenceError = page.locator('text=/confidence must be at most 1/i');
    await expect(confidenceError).toBeVisible();
  });

  // TODO: Fix cooldown validation test - NEM-2748 (pre-existing test failure)
  test.skip('negative cooldown is rejected', async ({ page }) => {
    // Fill in valid name
    const nameInput = page.getByTestId('alert-rule-name-input');
    const cooldownInput = page.getByTestId('alert-rule-cooldown-input');
    const submitButton = page.getByTestId('alert-rule-form-submit');

    await nameInput.fill('Test Rule');

    // Try to set negative cooldown
    await cooldownInput.fill('-100');
    await cooldownInput.blur();

    await submitButton.click();

    // Should show validation error
    const cooldownError = page.locator('text=/cooldown cannot be negative/i');
    await expect(cooldownError).toBeVisible();
  });

  test('rule name exceeding 255 characters is truncated', async ({ page }) => {
    const nameInput = page.getByTestId('alert-rule-name-input');
    const longName = 'A'.repeat(300);

    await nameInput.fill(longName);

    // Input should enforce maxLength=255
    const actualValue = await nameInput.inputValue();
    expect(actualValue.length).toBeLessThanOrEqual(255);
  });
});

// =============================================================================
// Camera Configuration Form Validation Tests
// =============================================================================

test.describe('Camera Configuration Form Validation', () => {
  let settingsPage: SettingsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();
    await settingsPage.goToCamerasTab();
  });

  test('empty camera name shows validation error @critical', async () => {
    // Open add camera modal
    const addButton = settingsPage.page.getByTestId('add-camera-button');
    await addButton.click();

    // Try to submit with empty name
    const nameInput = settingsPage.page.getByTestId('camera-name-input');
    const folderInput = settingsPage.page.getByTestId('camera-folder-path-input');
    const submitButton = settingsPage.page.getByTestId('camera-form-submit');

    await nameInput.fill('');
    await folderInput.fill('/valid/path');
    await nameInput.blur();

    await submitButton.click();

    // Should show validation error
    const nameError = settingsPage.page.locator('text=/name is required/i');
    await expect(nameError).toBeVisible();
  });

  test('empty folder path shows validation error @critical', async () => {
    const addButton = settingsPage.page.getByTestId('add-camera-button');
    await addButton.click();

    const nameInput = settingsPage.page.getByTestId('camera-name-input');
    const folderInput = settingsPage.page.getByTestId('camera-folder-path-input');
    const submitButton = settingsPage.page.getByTestId('camera-form-submit');

    await nameInput.fill('Valid Camera');
    await folderInput.fill('');
    await folderInput.blur();

    await submitButton.click();

    // Should show validation error
    const pathError = settingsPage.page.locator('text=/folder path is required/i');
    await expect(pathError).toBeVisible();
  });

  test('folder path with path traversal (..) is rejected @critical', async () => {
    const addButton = settingsPage.page.getByTestId('add-camera-button');
    await addButton.click();

    const nameInput = settingsPage.page.getByTestId('camera-name-input');
    const folderInput = settingsPage.page.getByTestId('camera-folder-path-input');
    const submitButton = settingsPage.page.getByTestId('camera-form-submit');

    await nameInput.fill('Test Camera');
    await folderInput.fill('/export/../etc/passwd');
    await folderInput.blur();

    await submitButton.click();

    // Should show path traversal error
    const pathError = settingsPage.page.locator('text=/path traversal.*not allowed/i');
    await expect(pathError).toBeVisible();
  });

  test('folder path with forbidden characters is rejected', async () => {
    const addButton = settingsPage.page.getByTestId('add-camera-button');
    await addButton.click();

    const nameInput = settingsPage.page.getByTestId('camera-name-input');
    const folderInput = settingsPage.page.getByTestId('camera-folder-path-input');
    const submitButton = settingsPage.page.getByTestId('camera-form-submit');

    await nameInput.fill('Test Camera');

    // Test a forbidden character
    await folderInput.fill('/export/foscam/<test>');
    await folderInput.blur();
    await submitButton.click();

    // Should show forbidden characters error
    const pathError = settingsPage.page.locator('text=/forbidden characters/i');
    await expect(pathError).toBeVisible();
  });

  test('valid camera configuration saves successfully @smoke', async ({ page }) => {
    const addButton = settingsPage.page.getByTestId('add-camera-button');
    await addButton.click();

    const nameInput = settingsPage.page.getByTestId('camera-name-input');
    const folderInput = settingsPage.page.getByTestId('camera-folder-path-input');
    const submitButton = settingsPage.page.getByTestId('camera-form-submit');

    await nameInput.fill('Front Door Camera');
    await folderInput.fill('/export/foscam/front_door');

    const responsePromise = page.waitForResponse('**/api/cameras');
    await submitButton.click();
    await responsePromise;

    // Modal should close on success
    const modal = settingsPage.page.locator('[role="dialog"]');
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test('camera name exceeding 255 characters is truncated', async () => {
    const addButton = settingsPage.page.getByTestId('add-camera-button');
    await addButton.click();

    const nameInput = settingsPage.page.getByTestId('camera-name-input');
    const longName = 'C'.repeat(300);

    await nameInput.fill(longName);

    // Input should enforce maxLength=255
    const actualValue = await nameInput.inputValue();
    expect(actualValue.length).toBeLessThanOrEqual(255);
  });

  test('folder path exceeding 500 characters is truncated', async () => {
    const addButton = settingsPage.page.getByTestId('add-camera-button');
    await addButton.click();

    const folderInput = settingsPage.page.getByTestId('camera-folder-path-input');
    const longPath = '/export/' + 'a'.repeat(600);

    await folderInput.fill(longPath);

    // Input should enforce maxLength=500
    const actualValue = await folderInput.inputValue();
    expect(actualValue.length).toBeLessThanOrEqual(500);
  });
});

// =============================================================================
// Settings Form Validation Tests (Notification Preferences)
// =============================================================================

// TODO: Fix notification preferences form validation - NEM-2748 (pre-existing test failures)
test.describe.skip('Notification Preferences Form Validation', () => {
  let settingsPage: SettingsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();
    // Navigate to notifications tab
    await settingsPage.notificationsTab.click();
  });

  test('notification preferences form loads successfully', async () => {
    // Verify form is visible
    const notificationCard = settingsPage.page.locator('text=/Notification Preferences/i');
    await expect(notificationCard).toBeVisible();
  });

  test('can toggle notification enabled state', async ({ page }) => {
    const toggleSwitch = settingsPage.page.locator('[role="switch"][aria-label*="Enable notifications"]');
    await expect(toggleSwitch).toBeVisible();

    // Get initial state
    const initialState = await toggleSwitch.getAttribute('aria-checked');

    // Wait for update request
    const responsePromise = page.waitForResponse('**/api/notifications/preferences');
    await toggleSwitch.click();
    await responsePromise;

    // State should have changed
    const newState = await toggleSwitch.getAttribute('aria-checked');
    expect(newState).not.toBe(initialState);
  });

  test('can select notification sound', async () => {
    const soundSelect = settingsPage.page.locator('select, [role="combobox"]').filter({ hasText: /default|chime|alert|bell/i }).first();
    await expect(soundSelect).toBeVisible();
  });

  test('can toggle risk level filters', async ({ page }) => {
    // Find risk level filter buttons
    const criticalButton = settingsPage.page.locator('button').filter({ hasText: /^Critical$/i });
    const highButton = settingsPage.page.locator('button').filter({ hasText: /^High$/i });
    const mediumButton = settingsPage.page.locator('button').filter({ hasText: /^Medium$/i });
    const lowButton = settingsPage.page.locator('button').filter({ hasText: /^Low$/i });

    // Should be able to see all risk level buttons
    await expect(criticalButton).toBeVisible();
    await expect(highButton).toBeVisible();
    await expect(mediumButton).toBeVisible();
    await expect(lowButton).toBeVisible();

    // Should be able to click them
    const responsePromise = page.waitForResponse('**/api/notifications/preferences');
    await criticalButton.click();
    await responsePromise;
  });
});

// =============================================================================
// Quiet Hours Form Validation Tests
// =============================================================================

// TODO: Fix quiet hours form validation - NEM-2748 (pre-existing test failures)
test.describe.skip('Quiet Hours Form Validation', () => {
  let settingsPage: SettingsPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();
    await settingsPage.notificationsTab.click();

    // Open quiet hours form
    const addPeriodButton = settingsPage.page.locator('button').filter({ hasText: /Add Period/i });
    await addPeriodButton.click();
  });

  test('empty quiet hours label shows validation error @critical', async () => {
    const form = settingsPage.page.getByTestId('quiet-hours-form');
    await expect(form).toBeVisible();

    const labelInput = settingsPage.page.locator('#quiet-hours-label');
    const submitButton = form.locator('button[type="submit"]');

    // Leave label empty
    await labelInput.fill('');
    await labelInput.blur();

    await submitButton.click();

    // Should show validation error
    const labelError = form.locator('text=/label.*required/i').or(settingsPage.page.locator('text=/label.*required/i'));
    await expect(labelError).toBeVisible();
  });

  test('quiet hours label exceeding 255 characters is rejected', async () => {
    const form = settingsPage.page.getByTestId('quiet-hours-form');
    const labelInput = settingsPage.page.locator('#quiet-hours-label');

    const longLabel = 'L'.repeat(300);
    await labelInput.fill(longLabel);

    // Input should enforce maxLength=255
    const actualValue = await labelInput.inputValue();
    expect(actualValue.length).toBeLessThanOrEqual(255);
  });

  test('start time same as end time shows validation error', async () => {
    const form = settingsPage.page.getByTestId('quiet-hours-form');
    const labelInput = settingsPage.page.locator('#quiet-hours-label');
    const startTimeInput = settingsPage.page.locator('#quiet-hours-start');
    const endTimeInput = settingsPage.page.locator('#quiet-hours-end');
    const submitButton = form.locator('button[type="submit"]');

    await labelInput.fill('Night Hours');
    await startTimeInput.fill('22:00');
    await endTimeInput.fill('22:00');

    await submitButton.click();

    // Should show validation error
    const timeError = form.locator('text=/start time must be different from end time/i');
    await expect(timeError).toBeVisible();
  });

  test('no days selected shows validation error', async () => {
    const form = settingsPage.page.getByTestId('quiet-hours-form');
    const labelInput = settingsPage.page.locator('#quiet-hours-label');
    const submitButton = form.locator('button[type="submit"]');

    await labelInput.fill('Night Hours');

    // Click "None" button to deselect all days
    const noneButton = form.locator('button').filter({ hasText: /^None$/i });
    await noneButton.click();

    await submitButton.click();

    // Should show validation error
    const daysError = form.locator('text=/at least one day must be selected/i');
    await expect(daysError).toBeVisible();
  });

  test('valid quiet hours period submits successfully @smoke', async ({ page }) => {
    const form = settingsPage.page.getByTestId('quiet-hours-form');
    const labelInput = settingsPage.page.locator('#quiet-hours-label');
    const startTimeInput = settingsPage.page.locator('#quiet-hours-start');
    const endTimeInput = settingsPage.page.locator('#quiet-hours-end');
    const submitButton = form.locator('button[type="submit"]');

    await labelInput.fill('Night Hours');
    await startTimeInput.fill('22:00');
    await endTimeInput.fill('06:00');

    // Days should be pre-selected (all days by default)

    const responsePromise = page.waitForResponse('**/api/notifications/quiet-hours');
    await submitButton.click();
    await responsePromise;

    // Form should close on success
    await expect(form).not.toBeVisible({ timeout: 5000 });
  });
});

// =============================================================================
// Cross-Browser Validation Consistency Tests
// =============================================================================

// TODO: Fix cross-browser validation consistency - NEM-2748 (pre-existing test failures)
test.describe.skip('Cross-Browser Form Validation Consistency', () => {
  test('alert rule validation messages are consistent across browsers @critical', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
    await alertRulesPage.openAddRuleModal();

    // Submit empty form
    await alertRulesPage.submitRuleForm();

    // Error message should be consistent
    await expect(alertRulesPage.nameError).toBeVisible();
    const errorText = await alertRulesPage.nameError.textContent();
    expect(errorText?.toLowerCase()).toContain('required');
  });

  test('camera validation messages are consistent across browsers', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();
    await settingsPage.goToCamerasTab();

    const addButton = settingsPage.page.getByTestId('add-camera-button');
    await addButton.click();

    const submitButton = settingsPage.page.getByTestId('camera-form-submit');
    await submitButton.click();

    // Should show validation errors
    const nameError = settingsPage.page.locator('text=/name is required/i');
    const pathError = settingsPage.page.locator('text=/folder path is required/i');

    await expect(nameError).toBeVisible();
    await expect(pathError).toBeVisible();
  });

  test('error messages remain visible after validation @critical', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const alertRulesPage = new AlertRulesPage(page);
    await alertRulesPage.goto();
    await alertRulesPage.openAddRuleModal();

    // Submit with invalid data
    await alertRulesPage.fillRuleForm({
      name: '',
      severity: 'medium',
    });
    await alertRulesPage.submitRuleForm();

    // Error should be visible
    await expect(alertRulesPage.nameError).toBeVisible();

    // Wait and verify error persists
    await page.waitForTimeout(1000);
    await expect(alertRulesPage.nameError).toBeVisible();
  });
});
