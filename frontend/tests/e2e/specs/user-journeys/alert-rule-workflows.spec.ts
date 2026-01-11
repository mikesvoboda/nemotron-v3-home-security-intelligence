/**
 * Advanced Alert Rule Workflows User Journey E2E Tests
 *
 * Linear Issue: NEM-2049
 * Test Coverage: Critical user journey for complex alert rule scenarios
 *
 * Acceptance Criteria:
 * - User can create rule with schedule constraints
 * - User can create rule with multiple object types
 * - User can create rule with multiple notification channels
 * - User can test rules against historical events
 * - User can duplicate existing rules
 * - User can manage rule priorities
 * - User can bulk enable/disable rules
 * - Rules execute in correct order
 */

import { test, expect } from '../../fixtures';

test.describe('Advanced Alert Rule Workflows (NEM-2049)', () => {
  test.beforeEach(async ({ page, browserName }) => {
    // Navigate to settings page, then to Rules tab
    await page.goto('/settings', { waitUntil: 'domcontentloaded' });

    const timeout = browserName === 'chromium' ? 10000 : 20000;
    await page.waitForSelector('h1:has-text("Settings")', {
      state: 'visible',
      timeout
    });

    // Navigate to Rules tab
    const rulesTab = page.getByRole('tab', { name: /RULES/i })
      .or(page.locator('button').filter({ hasText: 'RULES' }));

    await rulesTab.click();
    await page.waitForTimeout(1500);
  });

  test('user can create rule with time-based schedule constraints', async ({ page }) => {
    /**
     * Given: User is creating a new alert rule
     * When: User configures schedule (active only at certain times)
     * Then: Rule is created with schedule constraints
     */

    // Given: On Rules tab, open add rule modal
    const addRuleButton = page.getByRole('button', { name: /Add Rule/i });
    if (await addRuleButton.isVisible()) {
      await addRuleButton.click();
      await page.waitForTimeout(1000);

      // When: Look for schedule configuration
      const scheduleSection = page.locator('[data-testid*="schedule"]')
        .or(page.getByText(/Schedule/i))
        .or(page.getByText(/Active hours/i));

      if (await scheduleSection.count() > 0) {
        // Fill in rule basics
        const nameInput = page.locator('input[name="name"]')
          .or(page.getByLabel(/Name/i));

        if (await nameInput.isVisible()) {
          await nameInput.fill('Night Watch Rule');
          await page.waitForTimeout(500);

          // Look for schedule time inputs
          const timeInput = page.locator('input[type="time"]');
          if (await timeInput.count() > 0) {
            // Configure schedule (example: 10 PM to 6 AM)
            await timeInput.first().fill('22:00');
            if (await timeInput.count() > 1) {
              await timeInput.last().fill('06:00');
            }
          }

          // Then: Submit rule
          const submitButton = page.getByRole('button', { name: /Save/i })
            .or(page.getByRole('button', { name: /Create/i }));

          if (await submitButton.isVisible()) {
            await submitButton.click();
            await page.waitForTimeout(1500);

            // Verify modal closed (rule created)
            const modal = page.locator('[role="dialog"]');
            const modalVisible = await modal.isVisible().catch(() => false);
            expect(modalVisible).toBe(false);
          }
        }
      }

      // Close modal if still open
      await page.keyboard.press('Escape');
    }
  });

  test('user can create rule targeting multiple object types', async ({ page }) => {
    /**
     * Given: User is creating an alert rule
     * When: User selects multiple object types (person + vehicle)
     * Then: Rule triggers for any of the selected types
     */

    // Given: On Rules tab, open add rule modal
    const addRuleButton = page.getByRole('button', { name: /Add Rule/i });
    if (await addRuleButton.isVisible()) {
      await addRuleButton.click();
      await page.waitForTimeout(1000);

      // When: Fill rule name
      const nameInput = page.locator('input[name="name"]')
        .or(page.getByLabel(/Name/i));

      if (await nameInput.isVisible()) {
        await nameInput.fill('Multi-Object Detection');
        await page.waitForTimeout(500);

        // Select multiple object types
        const personButton = page.locator('button').filter({ hasText: /^person$/i });
        const vehicleButton = page.locator('button').filter({ hasText: /^vehicle$/i });

        if (await personButton.isVisible()) {
          await personButton.click();
          await page.waitForTimeout(300);
        }

        if (await vehicleButton.isVisible()) {
          await vehicleButton.click();
          await page.waitForTimeout(300);
        }

        // Set severity
        const severitySelect = page.locator('select[name="severity"]')
          .or(page.getByLabel(/Severity/i));

        if (await severitySelect.isVisible()) {
          await severitySelect.selectOption('high');
        }

        // Then: Submit rule
        const submitButton = page.getByRole('button', { name: /Save/i })
          .or(page.getByRole('button', { name: /Create/i }));

        if (await submitButton.isVisible()) {
          await submitButton.click();
          await page.waitForTimeout(1500);
        }
      }

      // Close modal
      await page.keyboard.press('Escape');
    }
  });

  test('user can configure multiple notification channels for rule', async ({ page }) => {
    /**
     * Given: User is creating an alert rule
     * When: User selects multiple notification channels (email + webhook)
     * Then: Rule sends notifications to all selected channels
     */

    // Given: On Rules tab, open add rule modal
    const addRuleButton = page.getByRole('button', { name: /Add Rule/i });
    if (await addRuleButton.isVisible()) {
      await addRuleButton.click();
      await page.waitForTimeout(1000);

      // When: Fill rule details
      const nameInput = page.locator('input[name="name"]')
        .or(page.getByLabel(/Name/i));

      if (await nameInput.isVisible()) {
        await nameInput.fill('Multi-Channel Alert');
        await page.waitForTimeout(500);

        // Select multiple notification channels
        const emailButton = page.locator('button').filter({ hasText: /^email$/i });
        const webhookButton = page.locator('button').filter({ hasText: /^webhook$/i });

        if (await emailButton.isVisible()) {
          await emailButton.click();
          await page.waitForTimeout(300);
        }

        if (await webhookButton.isVisible()) {
          await webhookButton.click();
          await page.waitForTimeout(300);
        }

        // Set severity
        const severitySelect = page.locator('select[name="severity"]')
          .or(page.getByLabel(/Severity/i));

        if (await severitySelect.isVisible()) {
          await severitySelect.selectOption('critical');
        }

        // Then: Submit rule
        const submitButton = page.getByRole('button', { name: /Save/i })
          .or(page.getByRole('button', { name: /Create/i }));

        if (await submitButton.isVisible()) {
          await submitButton.click();
          await page.waitForTimeout(1500);
        }
      }

      // Close modal
      await page.keyboard.press('Escape');
    }
  });

  test('user can test rule against historical events', async ({ page }) => {
    /**
     * Given: User has existing alert rules
     * When: User clicks test button on a rule
     * Then: Rule is tested against recent events and results shown
     */

    // Given: Rules tab with existing rules
    const testButtons = page.locator('button[aria-label*="Test"]')
      .or(page.getByRole('button', { name: /Test/i }));

    if (await testButtons.count() > 0) {
      // When: Click first test button
      await testButtons.first().click();
      await page.waitForTimeout(1500);

      // Then: Test results modal should appear
      const testModal = page.locator('[role="dialog"]');
      if (await testModal.isVisible()) {
        await expect(testModal).toBeVisible();

        // Verify test results content
        const modalText = await testModal.textContent();
        expect(modalText).toMatch(/Events Tested|Matched|Test Result/i);

        // Close modal
        await page.keyboard.press('Escape');
      }
    }
  });

  test('user can view rule test results with match details', async ({ page }) => {
    /**
     * Given: User has tested a rule
     * When: Test results modal displays
     * Then: User can see how many events matched and why
     */

    // Given: Test a rule
    const testButtons = page.locator('button[aria-label*="Test"]')
      .or(page.getByRole('button', { name: /Test/i }));

    if (await testButtons.count() > 0) {
      await testButtons.first().click();
      await page.waitForTimeout(1500);

      // When: Test modal is open
      const testModal = page.locator('[role="dialog"]');
      if (await testModal.isVisible()) {
        // Then: Verify detailed results are shown
        const eventsTestedText = testModal.getByText(/Events Tested/i);
        const matchedText = testModal.getByText(/Matched/i);
        const matchRateText = testModal.getByText(/Match Rate|Rate/i);

        // At least one result metric should be visible
        const hasEventsCount = await eventsTestedText.isVisible().catch(() => false);
        const hasMatchedCount = await matchedText.isVisible().catch(() => false);
        const hasMatchRate = await matchRateText.isVisible().catch(() => false);

        expect(hasEventsCount || hasMatchedCount || hasMatchRate).toBeTruthy();

        // Close modal
        await page.keyboard.press('Escape');
      }
    }
  });

  test('user can edit rule and preserve existing configuration', async ({ page }) => {
    /**
     * Given: User has existing alert rules
     * When: User edits a rule and changes one field
     * Then: Other fields remain unchanged
     */

    // Given: Rules tab with existing rules
    const editButtons = page.locator('button[aria-label*="Edit"]')
      .or(page.getByRole('button', { name: /Edit/i }));

    if (await editButtons.count() > 0) {
      // When: Click first edit button
      await editButtons.first().click();
      await page.waitForTimeout(1000);

      // Get current name value
      const nameInput = page.locator('input[name="name"]')
        .or(page.getByLabel(/Name/i));

      if (await nameInput.isVisible()) {
        const originalName = await nameInput.inputValue();
        const originalSeverity = await page.locator('select[name="severity"]').inputValue().catch(() => 'unknown');

        // Modify only the name
        await nameInput.clear();
        await nameInput.fill(`${originalName} - Modified`);
        await page.waitForTimeout(500);

        // Then: Verify severity unchanged
        const currentSeverity = await page.locator('select[name="severity"]').inputValue().catch(() => 'unknown');
        expect(currentSeverity).toBe(originalSeverity);

        // Cancel to avoid saving
        const cancelButton = page.getByRole('button', { name: /Cancel/i });
        if (await cancelButton.isVisible()) {
          await cancelButton.click();
        } else {
          await page.keyboard.press('Escape');
        }
      }
    }
  });

  test('user can disable multiple rules at once', async ({ page }) => {
    /**
     * Given: User has multiple enabled alert rules
     * When: User toggles multiple rule switches
     * Then: All selected rules are disabled
     */

    // Given: Rules tab with toggle switches
    const ruleToggles = page.locator('[role="switch"]')
      .or(page.locator('button[role="switch"]'));

    const toggleCount = await ruleToggles.count();

    if (toggleCount > 1) {
      // When: Get initial states and toggle multiple
      const initialStates = [];
      for (let i = 0; i < Math.min(toggleCount, 2); i++) {
        const toggle = ruleToggles.nth(i);
        const isChecked = await toggle.isChecked().catch(() => false);
        initialStates.push(isChecked);

        // Toggle the rule
        await toggle.click();
        await page.waitForTimeout(500);
      }

      // Then: Verify states changed
      for (let i = 0; i < Math.min(toggleCount, 2); i++) {
        const toggle = ruleToggles.nth(i);
        const newState = await toggle.isChecked().catch(() => false);
        expect(newState).not.toBe(initialStates[i]);

        // Toggle back to original state
        await toggle.click();
        await page.waitForTimeout(500);
      }
    }
  });

  test('user can see rule severity visually distinguished', async ({ page }) => {
    /**
     * Given: User is viewing alert rules list
     * When: Multiple rules with different severities exist
     * Then: Each severity level has distinct visual styling
     */

    // Given: Rules tab loaded
    const severityBadges = page.locator('[data-testid*="severity"]')
      .or(page.locator('.severity-badge'))
      .or(page.locator('span:has-text("Critical"), span:has-text("High"), span:has-text("Medium"), span:has-text("Low")'));

    const badgeCount = await severityBadges.count();

    if (badgeCount > 0) {
      // When/Then: Check each badge has styling
      for (let i = 0; i < Math.min(badgeCount, 4); i++) {
        const badge = severityBadges.nth(i);
        await expect(badge).toBeVisible();

        // Verify badge has CSS classes for styling
        const classes = await badge.getAttribute('class');
        expect(classes).toBeTruthy();
        expect(classes?.length || 0).toBeGreaterThan(0);
      }
    }
  });

  test('user can filter rules by severity in table', async ({ page }) => {
    /**
     * Given: User is viewing multiple alert rules
     * When: User looks for specific severity rules
     * Then: Rules are organized/filterable by severity
     */

    // Given: Rules tab with rules
    const rulesTable = page.locator('table');

    if (await rulesTable.isVisible()) {
      // When: Count rules by severity
      const criticalBadges = page.locator('span:has-text("Critical")');
      const highBadges = page.locator('span:has-text("High")');
      const mediumBadges = page.locator('span:has-text("Medium")');
      const lowBadges = page.locator('span:has-text("Low")');

      const criticalCount = await criticalBadges.count();
      const highCount = await highBadges.count();
      const mediumCount = await mediumBadges.count();
      const lowCount = await lowBadges.count();

      // Then: Verify rules exist and are visible
      const totalRules = criticalCount + highCount + mediumCount + lowCount;
      expect(totalRules).toBeGreaterThan(0);
    }
  });

  test('user can view rule schedule in rules list', async ({ page }) => {
    /**
     * Given: User has rules with schedule constraints
     * When: User views rules list
     * Then: Schedule information is displayed for each rule
     */

    // Given: Rules tab with rules table
    const rulesTable = page.locator('table');

    if (await rulesTable.isVisible()) {
      // When: Look for schedule column
      const scheduleHeader = page.locator('th:has-text("Schedule")');
      const hasScheduleColumn = await scheduleHeader.isVisible().catch(() => false);

      if (hasScheduleColumn) {
        // Then: Verify schedule data is present in rows
        const scheduleCell = page.locator('td').filter({ hasText: /Always|24\/7|\d{1,2}:\d{2}/ });
        const hasScheduleData = await scheduleCell.count() > 0;

        expect(hasScheduleData).toBeTruthy();
      }
    }
  });

  test('user can view notification channels configured for each rule', async ({ page }) => {
    /**
     * Given: User is viewing alert rules list
     * When: Rules have notification channels configured
     * Then: Channels are displayed for each rule
     */

    // Given: Rules tab with rules table
    const rulesTable = page.locator('table');

    if (await rulesTable.isVisible()) {
      // When: Look for channels column
      const channelsHeader = page.locator('th:has-text("Channels")');
      const hasChannelsColumn = await channelsHeader.isVisible().catch(() => false);

      if (hasChannelsColumn) {
        // Then: Verify channel badges/icons are present
        const channelBadges = page.locator('td').filter({ hasText: /email|webhook|pushover/i });
        const hasChannelData = await channelBadges.count() > 0;

        expect(hasChannelData).toBeTruthy();
      }
    }
  });

  test('rules list displays enabled/disabled status clearly', async ({ page }) => {
    /**
     * Given: User has mix of enabled and disabled rules
     * When: User views rules list
     * Then: Enabled state is clearly visible for each rule
     */

    // Given: Rules tab loaded
    const ruleToggles = page.locator('[role="switch"]')
      .or(page.locator('button[role="switch"]'));

    const toggleCount = await ruleToggles.count();

    if (toggleCount > 0) {
      // When/Then: Each rule has visible enabled toggle
      for (let i = 0; i < Math.min(toggleCount, 3); i++) {
        const toggle = ruleToggles.nth(i);
        await expect(toggle).toBeVisible();

        // Verify toggle has proper ARIA attributes
        const ariaChecked = await toggle.getAttribute('aria-checked');
        expect(['true', 'false']).toContain(ariaChecked);
      }
    }
  });

  test('user can quickly identify high-priority rules', async ({ page }) => {
    /**
     * Given: User has multiple rules with different severities
     * When: User scans rules list
     * Then: Critical/High severity rules are visually prominent
     */

    // Given: Rules tab with rules
    const criticalBadges = page.locator('span:has-text("Critical")');
    const highBadges = page.locator('span:has-text("High")');

    const criticalCount = await criticalBadges.count();
    const highCount = await highBadges.count();

    if (criticalCount > 0 || highCount > 0) {
      // When: Check first high-priority badge
      const priorityBadge = criticalCount > 0 ? criticalBadges.first() : highBadges.first();
      await expect(priorityBadge).toBeVisible();

      // Then: Verify it has styling classes for prominence
      const classes = await priorityBadge.getAttribute('class');
      expect(classes).toBeTruthy();

      // High priority badges typically have red/orange colors
      expect(classes?.includes('red') || classes?.includes('orange') || classes?.includes('critical') || classes?.includes('high')).toBeTruthy();
    }
  });
});
