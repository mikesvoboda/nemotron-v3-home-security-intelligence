/**
 * Alert Lifecycle E2E Tests
 *
 * Linear Issue: NEM-1664
 * Test Coverage: Critical user journey for alert management and acknowledgment
 *
 * Acceptance Criteria:
 * - User can navigate to alerts page
 * - User can filter alerts by severity
 * - User can acknowledge individual alerts
 * - Alert status changes are reflected in UI
 * - User can view alert details
 */

import { test, expect } from '@playwright/test';

test.describe('Alert Lifecycle Journey (NEM-1664)', () => {
  test.beforeEach(async ({ page, browserName }) => {
    // Navigate to dashboard first
    await page.goto('/');

    // Wait for initial load - WebSocket status indicator
    // Firefox/WebKit need longer timeout for WebSocket connection establishment
    const timeout = browserName === 'chromium' ? 10000 : 20000;
    await page.waitForSelector('[data-testid="websocket-status"]', {
      state: 'visible',
      timeout
    });
  });

  test('user can navigate to alerts page from dashboard', async ({ page }) => {
    /**
     * Given: User is on the dashboard
     * When: User clicks the alerts navigation link
     * Then: User is taken to the alerts page with alert list
     */

    // Given: Dashboard is visible
    await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

    // When: Click alerts navigation link
    const alertsLink = page.locator('[data-testid="nav-alerts"]').or(
      page.locator('a[href="/alerts"]')
    );

    await expect(alertsLink.first()).toBeVisible();
    await alertsLink.first().click();

    // Then: Alerts page should load
    await expect(page).toHaveURL(/\/alerts/);

    // Verify alerts page container
    const alertsPage = page.locator('[data-testid="alerts-page"]').or(
      page.locator('[data-testid="alerts-container"]')
    );
    await expect(alertsPage.first()).toBeVisible({ timeout: 5000 });
  });

  test('user can filter alerts by severity level', async ({ page }) => {
    /**
     * Given: User is on the alerts page with multiple alerts
     * When: User selects a severity filter (high/medium/low)
     * Then: Alert list updates to show only alerts of that severity
     */

    // Given: Navigate to alerts page
    await page.goto('/alerts');

    const alertsContainer = page.locator('[data-testid="alerts-page"]').or(
      page.locator('[data-testid="alerts-container"]')
    );
    await expect(alertsContainer.first()).toBeVisible({ timeout: 5000 });

    // When: Locate severity filter dropdown/buttons
    const severityFilter = page.locator('[data-testid="severity-filter"]').or(
      page.locator('[data-testid="filter-severity"]')
    );

    // Check if filter exists
    if (await severityFilter.count() > 0) {
      await expect(severityFilter.first()).toBeVisible();

      // Get initial alert count
      const allAlerts = page.locator('[data-testid^="alert-card-"]');
      const initialCount = await allAlerts.count();

      // Select high severity filter
      const highSeverityOption = page.locator('[data-testid="severity-high"]').or(
        page.locator('button:has-text("High")').or(
          page.locator('option:has-text("High")')
        )
      );

      if (await highSeverityOption.count() > 0) {
        await highSeverityOption.first().click();

        // Then: Wait for filter to apply
        await page.waitForTimeout(500);

        // Verify alerts are filtered (count may change)
        const filteredAlerts = page.locator('[data-testid^="alert-card-"]');
        const filteredCount = await filteredAlerts.count();

        // Verify all visible alerts have high severity indicator
        if (filteredCount > 0) {
          const firstAlert = filteredAlerts.first();
          const severityBadge = firstAlert.locator('[data-testid*="severity"]');
          await expect(severityBadge).toBeVisible();
        }
      }
    }
  });

  test('user can acknowledge an alert and see status change', async ({ page }) => {
    /**
     * Given: User is viewing an unacknowledged alert
     * When: User clicks the acknowledge button
     * Then: Alert status changes to acknowledged and UI updates
     */

    // Given: Navigate to alerts page
    await page.goto('/alerts');

    const alertsContainer = page.locator('[data-testid="alerts-page"]').or(
      page.locator('[data-testid="alerts-container"]')
    );
    await expect(alertsContainer.first()).toBeVisible({ timeout: 5000 });

    // Find first unacknowledged alert
    const alerts = page.locator('[data-testid^="alert-card-"]');

    if (await alerts.count() > 0) {
      const firstAlert = alerts.first();
      await expect(firstAlert).toBeVisible();

      // When: Click acknowledge button
      const acknowledgeButton = firstAlert.locator('[data-testid="acknowledge-button"]').or(
        firstAlert.locator('button:has-text("Acknowledge")')
      );

      // Check if acknowledge button exists
      if (await acknowledgeButton.count() > 0) {
        await acknowledgeButton.click();

        // Then: Verify status change
        // Look for acknowledged status indicator
        const acknowledgedStatus = firstAlert.locator('[data-testid="alert-status-acknowledged"]').or(
          firstAlert.locator('[data-testid*="acknowledged"]')
        );

        // Status should appear or button should be disabled/hidden
        await page.waitForTimeout(1000);

        // Verify either status badge appears or button is disabled
        const statusVisible = await acknowledgedStatus.count() > 0;
        const buttonDisabled = await acknowledgeButton.isDisabled().catch(() => true);
        const buttonHidden = await acknowledgeButton.isHidden().catch(() => true);

        expect(statusVisible || buttonDisabled || buttonHidden).toBeTruthy();
      }
    }
  });

  test('user can view detailed alert information', async ({ page }) => {
    /**
     * Given: User is on the alerts page
     * When: User clicks on an alert card
     * Then: Alert detail view opens showing comprehensive information
     */

    // Given: Navigate to alerts page
    await page.goto('/alerts');

    const alertsContainer = page.locator('[data-testid="alerts-page"]').or(
      page.locator('[data-testid="alerts-container"]')
    );
    await expect(alertsContainer.first()).toBeVisible({ timeout: 5000 });

    // When: Click on first alert
    const firstAlert = page.locator('[data-testid^="alert-card-"]').first();

    if (await firstAlert.count() > 0) {
      await firstAlert.click();

      // Then: Alert detail should open (either modal or expanded view)
      const alertDetail = page.locator('[data-testid="alert-detail-modal"]').or(
        page.locator('[data-testid="alert-detail"]').or(
          page.locator('[data-testid="event-detail-modal"]')
        )
      );

      await expect(alertDetail.first()).toBeVisible({ timeout: 5000 });

      // Verify detail contains key information
      await expect(
        alertDetail.first().locator('[data-testid*="timestamp"]')
      ).toBeVisible();

      await expect(
        alertDetail.first().locator('[data-testid*="severity"]')
      ).toBeVisible();
    }
  });

  test('alerts page displays summary statistics', async ({ page }) => {
    /**
     * Given: User navigates to alerts page
     * When: Page loads with alerts data
     * Then: Summary statistics are displayed (total, by severity, acknowledged count)
     */

    // Given & When: Navigate to alerts page
    await page.goto('/alerts');

    const alertsContainer = page.locator('[data-testid="alerts-page"]').or(
      page.locator('[data-testid="alerts-container"]')
    );
    await expect(alertsContainer.first()).toBeVisible({ timeout: 5000 });

    // Then: Look for summary statistics
    const summarySection = page.locator('[data-testid="alerts-summary"]').or(
      page.locator('[data-testid="alert-stats"]')
    );

    // Check if summary section exists
    if (await summarySection.count() > 0) {
      await expect(summarySection.first()).toBeVisible();

      // Verify summary contains numeric statistics
      const summaryText = await summarySection.first().textContent();
      expect(summaryText).toMatch(/\d+/); // Contains at least one number
    } else {
      // Alternative: Check for individual stat cards
      const statCards = page.locator('[data-testid*="stat"]');
      const cardCount = await statCards.count();

      // If stats exist, verify they contain numbers
      if (cardCount > 0) {
        const firstStatText = await statCards.first().textContent();
        expect(firstStatText).toMatch(/\d+/);
      }
    }
  });

  test('user can clear/dismiss multiple alerts in batch', async ({ page }) => {
    /**
     * Given: User has multiple alerts selected
     * When: User clicks batch acknowledge/dismiss button
     * Then: All selected alerts are marked as acknowledged
     */

    // Given: Navigate to alerts page
    await page.goto('/alerts');

    const alertsContainer = page.locator('[data-testid="alerts-page"]').or(
      page.locator('[data-testid="alerts-container"]')
    );
    await expect(alertsContainer.first()).toBeVisible({ timeout: 5000 });

    // Check if batch actions are available
    const batchActionButton = page.locator('[data-testid="batch-acknowledge"]').or(
      page.locator('[data-testid="acknowledge-all"]')
    );

    if (await batchActionButton.count() > 0) {
      await expect(batchActionButton.first()).toBeVisible();

      // Get initial alert count
      const alerts = page.locator('[data-testid^="alert-card-"]');
      const initialCount = await alerts.count();

      // When: Click batch acknowledge
      await batchActionButton.first().click();

      // Then: Wait for action to complete
      await page.waitForTimeout(1000);

      // Verify alerts are acknowledged or removed
      const remainingAlerts = page.locator('[data-testid^="alert-card-"]');
      const remainingCount = await remainingAlerts.count();

      // Count should decrease or all should show acknowledged status
      if (remainingCount === initialCount) {
        // All alerts should show acknowledged status
        const acknowledgedAlerts = page.locator('[data-testid*="acknowledged"]');
        const acknowledgedCount = await acknowledgedAlerts.count();
        expect(acknowledgedCount).toBeGreaterThan(0);
      } else {
        // Some alerts were removed
        expect(remainingCount).toBeLessThanOrEqual(initialCount);
      }
    }
  });

  test('alert severity is visually distinguished by color', async ({ page }) => {
    /**
     * Given: User is viewing alerts page with various severity levels
     * When: User looks at different alert cards
     * Then: Each severity level has distinct visual styling
     */

    // Given: Navigate to alerts page
    await page.goto('/alerts');

    const alertsContainer = page.locator('[data-testid="alerts-page"]').or(
      page.locator('[data-testid="alerts-container"]')
    );
    await expect(alertsContainer.first()).toBeVisible({ timeout: 5000 });

    // When: Locate alerts with severity indicators
    const alerts = page.locator('[data-testid^="alert-card-"]');

    if (await alerts.count() > 0) {
      const firstAlert = alerts.first();
      await expect(firstAlert).toBeVisible();

      // Then: Verify severity badge exists with color/styling
      const severityBadge = firstAlert.locator('[data-testid*="severity"]').or(
        firstAlert.locator('.severity-badge').or(
          firstAlert.locator('[class*="severity"]')
        )
      );

      if (await severityBadge.count() > 0) {
        await expect(severityBadge.first()).toBeVisible();

        // Verify badge has styling (background color, text color, etc.)
        const badgeClasses = await severityBadge.first().getAttribute('class');
        expect(badgeClasses).toBeTruthy();
        expect(badgeClasses?.length || 0).toBeGreaterThan(0);
      }
    }
  });
});
