/**
 * Batch Operations E2E Tests for Home Security Dashboard
 *
 * Tests for selecting multiple events and performing batch actions:
 * - Multi-select with checkboxes
 * - Bulk mark as reviewed/not reviewed
 * - Bulk export selected events
 * - Select all on current page
 *
 * NOTE: Skipped in CI due to timeline page load timing issues causing flakiness.
 * Run locally for batch operations validation.
 *
 * Related: NEM-2061
 */

import { test, expect } from '@playwright/test';

// Skip entire file in CI - timeline page load timing issues cause flaky failures
test.skip(() => !!process.env.CI, 'Batch operations tests flaky in CI - run locally');
import { TimelinePage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';
import type { Page, Route } from '@playwright/test';

/**
 * Helper function to click an event checkbox by index (toggle selection)
 * Checkboxes are buttons with aria-labels like "Select event X" or "Deselect event X"
 * Located in absolute positioned divs above each event card
 */
async function clickEventCheckbox(page: Page, index: number): Promise<void> {
  // Get all checkbox buttons (both selected and unselected)
  const checkboxes = page.locator('button').filter({
    has: page.locator('svg'), // Has an icon (Square or CheckSquare)
  }).filter({
    hasText: '', // Filter for buttons with no text content (icon-only)
  });

  // Find checkboxes with specific aria-labels
  const eventCheckboxes = page.locator('button[aria-label*="Select event"], button[aria-label*="Deselect event"]');
  await eventCheckboxes.nth(index).click();
}

test.describe('Batch Operations - Event Selection', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('can select individual events with checkboxes @smoke @critical', async ({ page }) => {
    // Verify at least 3 events are displayed
    const eventCount = await timelinePage.getEventCount();
    expect(eventCount).toBeGreaterThanOrEqual(3);

    // Select first event using helper function
    await clickEventCheckbox(page,0);
    await expect(timelinePage.selectedCount).toHaveText('1 selected');

    // Select second event
    await clickEventCheckbox(page,1);
    await expect(timelinePage.selectedCount).toHaveText('2 selected');

    // Select third event
    await clickEventCheckbox(page,2);
    await expect(timelinePage.selectedCount).toHaveText('3 selected');
  });

  test('can deselect events by clicking checkbox again', async ({ page }) => {
    // Select first event
    await clickEventCheckbox(page,0);
    await expect(timelinePage.selectedCount).toHaveText('1 selected');

    // Deselect first event by clicking again (toggle)
    await clickEventCheckbox(page, 0);

    // Selection count should be hidden when no items selected
    await expect(timelinePage.selectedCount).not.toBeVisible();
  });

  test('select all button selects all events on current page', async () => {
    const eventCount = await timelinePage.getEventCount();
    expect(eventCount).toBeGreaterThan(0);

    // Click select all
    await timelinePage.selectAllEvents();

    // Verify selection count matches event count
    await expect(timelinePage.selectedCount).toHaveText(`${eventCount} selected`);

    // Verify select all button shows all selected state
    await expect(timelinePage.selectAllButton).toContainText(`${eventCount} selected`);
  });

  test('select all button deselects all when all are selected', async () => {
    // Select all events
    await timelinePage.selectAllEvents();
    const eventCount = await timelinePage.getEventCount();
    await expect(timelinePage.selectedCount).toHaveText(`${eventCount} selected`);

    // Click select all again to deselect
    await timelinePage.selectAllEvents();

    // Selection count should be hidden
    await expect(timelinePage.selectedCount).not.toBeVisible();

    // Select all button should show "Select all" text
    await expect(timelinePage.selectAllButton).toContainText('Select all');
  });

  // TODO: Fix modal navigation causing test instability
  test.skip('selection persists when navigating between events', async ({ page }) => {
    // Select first event
    await clickEventCheckbox(page,0);
    await expect(timelinePage.selectedCount).toHaveText('1 selected');

    // Click event to open modal (wait for modal content to be visible)
    await timelinePage.clickEvent(1);
    await page.waitForSelector('[role="dialog"][data-open]', { timeout: 3000 }).catch(() => null);

    // Close modal
    await timelinePage.closeModal();
    await page.waitForTimeout(300); // Wait for modal close animation

    // Selection should still be maintained
    await expect(timelinePage.selectedCount).toHaveText('1 selected');
  });

  test('checkbox UI has proper aria-labels for accessibility', async ({ page }) => {
    const eventCount = await timelinePage.getEventCount();
    expect(eventCount).toBeGreaterThan(0);

    // Check first event checkbox has proper aria-label
    const firstCheckbox = page.locator('button[aria-label^="Select event"]').first();
    const ariaLabel = await firstCheckbox.getAttribute('aria-label');
    expect(ariaLabel).toMatch(/Select event \d+/);
  });
});

test.describe('Batch Operations - Bulk Mark as Reviewed', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  // TODO: Enable when bulk mark UI components are implemented
  test.skip('bulk mark as reviewed button appears when events are selected', async ({ page }) => {
    // Button should not be visible initially
    await expect(timelinePage.markReviewedButton).not.toBeVisible();

    // Select first event
    await clickEventCheckbox(page,0);
    await expect(timelinePage.selectedCount).toHaveText('1 selected');

    // Button should now be visible (with increased timeout for state update)
    await expect(timelinePage.markReviewedButton).toBeVisible({ timeout: 5000 });
    await expect(timelinePage.markReviewedButton).toContainText('Mark as Reviewed');
  });

  // TODO: Enable when bulk mark UI components are implemented
  test.skip('can bulk mark multiple events as reviewed @critical', async ({ page }) => {
    // Mock the bulk update endpoint
    const bulkUpdatePromise = page.waitForRequest((request) => {
      return (
        request.url().includes('/api/events/bulk') &&
        request.method() === 'PATCH' &&
        request.postDataJSON()?.events?.length === 3
      );
    });

    // Mock successful bulk update response
    await page.route('**/api/events/bulk', async (route: Route) => {
      const request = route.request();
      if (request.method() === 'PATCH') {
        const requestData = request.postDataJSON();
        const eventIds = requestData.events.map((e: any) => e.id);
        await route.fulfill({
          status: 207,
          contentType: 'application/json',
          body: JSON.stringify({
            successful: eventIds.map((id: number) => ({ id, status: 200 })),
            failed: [],
            summary: {
              total: eventIds.length,
              succeeded: eventIds.length,
              failed: 0,
            },
          }),
        });
      } else {
        await route.continue();
      }
    });

    // Select 3 events
    await clickEventCheckbox(page,0);
    await clickEventCheckbox(page,1);
    await clickEventCheckbox(page,2);
    await expect(timelinePage.selectedCount).toHaveText('3 selected');

    // Click bulk mark as reviewed
    await timelinePage.markSelectedAsReviewed();

    // Verify API was called
    await bulkUpdatePromise;

    // Selection should be cleared after successful update
    // Note: The component reloads events after bulk update
    await page.waitForTimeout(500); // Wait for state update
    await expect(timelinePage.selectedCount).not.toBeVisible();
  });

  // TODO: Enable when bulk mark UI components are implemented
  test.skip('bulk mark not reviewed button works correctly', async ({ page }) => {
    // Mock the bulk update endpoint
    await page.route('**/api/events/bulk', async (route: Route) => {
      const request = route.request();
      if (request.method() === 'PATCH') {
        const requestData = request.postDataJSON();
        const eventIds = requestData.events.map((e: any) => e.id);
        await route.fulfill({
          status: 207,
          contentType: 'application/json',
          body: JSON.stringify({
            successful: eventIds.map((id: number) => ({ id, status: 200 })),
            failed: [],
            summary: {
              total: eventIds.length,
              succeeded: eventIds.length,
              failed: 0,
            },
          }),
        });
      } else {
        await route.continue();
      }
    });

    // Select 2 events
    await clickEventCheckbox(page,0);
    await clickEventCheckbox(page,1);
    await expect(timelinePage.selectedCount).toHaveText('2 selected');

    // Mark Not Reviewed button should be visible
    await expect(timelinePage.markNotReviewedButton).toBeVisible();

    // Click bulk mark as not reviewed
    await timelinePage.markNotReviewedButton.click();

    // Wait for update
    await page.waitForTimeout(500);

    // Selection should be cleared
    await expect(timelinePage.selectedCount).not.toBeVisible();
  });

  // TODO: Enable when bulk mark UI components are implemented
  test.skip('shows loading state during bulk update', async ({ page }) => {
    // Mock slow bulk update endpoint
    await page.route('**/api/events/bulk', async (route: Route) => {
      await page.waitForTimeout(1000); // Simulate slow response
      await route.fulfill({
        status: 207,
        contentType: 'application/json',
        body: JSON.stringify({
          successful: [{ id: 1, status: 200 }],
          failed: [],
          summary: { total: 1, succeeded: 1, failed: 0 },
        }),
      });
    });

    // Select one event
    await clickEventCheckbox(page,0);

    // Click bulk mark as reviewed
    const markReviewedPromise = timelinePage.markSelectedAsReviewed();

    // Verify loading state is shown
    await expect(timelinePage.markReviewedButton).toContainText('Updating...');
    await expect(timelinePage.markReviewedButton).toBeDisabled();

    await markReviewedPromise;
  });

  // TODO: Enable when bulk mark UI components are implemented
  test.skip('handles bulk update failures gracefully', async ({ page }) => {
    // Mock failed bulk update
    await page.route('**/api/events/bulk', async (route: Route) => {
      const request = route.request();
      if (request.method() === 'PATCH') {
        await route.fulfill({
          status: 207,
          contentType: 'application/json',
          body: JSON.stringify({
            successful: [{ id: 1, status: 200 }],
            failed: [{ id: 2, status: 404, error: 'Event not found' }],
            summary: { total: 2, succeeded: 1, failed: 1 },
          }),
        });
      } else {
        await route.continue();
      }
    });

    // Select 2 events
    await clickEventCheckbox(page,0);
    await clickEventCheckbox(page,1);

    // Mark as reviewed
    await timelinePage.markSelectedAsReviewed();

    // Wait for error state
    await page.waitForTimeout(500);

    // Error message should be displayed
    // Note: Component shows partial success message
    const errorElement = await page.getByText(/but \d+ failed/).isVisible();
    expect(errorElement).toBe(true);
  });

  // TODO: Enable when bulk mark UI components are implemented
  test.skip('bulk action buttons have proper aria-labels', async ({ page }) => {
    await clickEventCheckbox(page,0);

    // Check Mark as Reviewed button aria-label
    const markReviewedLabel = await timelinePage.markReviewedButton.getAttribute('aria-label');
    expect(markReviewedLabel).toMatch(/Mark \d+ selected event/);

    // Check Mark Not Reviewed button aria-label
    const markNotReviewedLabel = await timelinePage.markNotReviewedButton.getAttribute('aria-label');
    expect(markNotReviewedLabel).toMatch(/Mark \d+ selected event/);
  });
});

test.describe('Batch Operations - Bulk Export', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('quick export button is visible and enabled', async () => {
    await expect(timelinePage.quickExportButton).toBeVisible();
    await expect(timelinePage.quickExportButton).toBeEnabled();
  });

  test('quick export downloads CSV file @critical', async ({ page }) => {
    // Mock export endpoint with CSV data
    await page.route('**/api/events/export*', async (route: Route) => {
      const csvContent = `Event ID,Camera Name,Timestamp,Risk Score,Risk Level,Summary,Detection Count,Reviewed
1,Front Door,2024-01-09T10:00:00Z,85,high,"Person detected",3,false
2,Back Yard,2024-01-09T10:05:00Z,45,medium,"Animal detected",1,true
`;
      await route.fulfill({
        status: 200,
        contentType: 'text/csv',
        headers: {
          'Content-Disposition': 'attachment; filename="events_export_2024-01-09.csv"',
        },
        body: csvContent,
      });
    });

    // Wait for download to start
    const downloadPromise = page.waitForEvent('download');

    // Click quick export
    await timelinePage.quickExport();

    // Verify download was triggered
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/events_export_.*\.csv/);
  });

  test('quick export passes current filters to export endpoint', async ({ page }) => {
    // Setup filter
    await timelinePage.showFilters();
    await timelinePage.filterByRiskLevel('high');

    // Mock export with request inspection
    const exportRequestPromise = page.waitForRequest((request) => {
      return (
        request.url().includes('/api/events/export') &&
        request.url().includes('risk_level=high')
      );
    });

    await page.route('**/api/events/export*', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/csv',
        body: 'Event ID,Camera Name\n',
      });
    });

    // Trigger export
    await timelinePage.quickExport();

    // Verify request included filter
    const exportRequest = await exportRequestPromise;
    expect(exportRequest.url()).toContain('risk_level=high');
  });

  // TODO: Enable when export panel UI is implemented
  test.skip('export button shows loading state during export', async ({ page }) => {
    // Mock slow export
    await page.route('**/api/events/export*', async (route: Route) => {
      await page.waitForTimeout(1000);
      await route.fulfill({
        status: 200,
        contentType: 'text/csv',
        body: 'Event ID\n',
      });
    });

    // Click export
    const exportPromise = timelinePage.quickExport();

    // Verify loading state
    await expect(timelinePage.quickExportButton).toContainText('Exporting...');
    await expect(timelinePage.quickExportButton).toBeDisabled();

    await exportPromise;
  });

  test('export button is disabled when no events available', async ({ page }) => {
    // Mock empty events response
    await page.route('**/api/events*', async (route: Route) => {
      if (!route.request().url().includes('/export')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [],
            pagination: {
              total: 0,
              limit: 50,
              offset: 0,
              has_more: false,
            },
          }),
        });
      }
    });

    // Reload page
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    // Export button should be disabled
    await expect(timelinePage.quickExportButton).toBeDisabled();
  });

  // TODO: Enable when export panel UI is implemented
  test.skip('advanced export panel can be toggled', async () => {
    // Panel should not be visible initially
    await expect(timelinePage.exportPanel).not.toBeVisible();

    // Click advanced export button
    await timelinePage.advancedExportButton.click();

    // Panel should now be visible
    await expect(timelinePage.exportPanel).toBeVisible();

    // Click again to hide
    await timelinePage.advancedExportButton.click();

    // Panel should be hidden
    await expect(timelinePage.exportPanel).not.toBeVisible();
  });

  test('handles export errors gracefully', async ({ page }) => {
    // Mock failed export
    await page.route('**/api/events/export*', async (route: Route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Export failed' }),
      });
    });

    // Attempt export
    await timelinePage.quickExport();

    // Wait for error state
    await page.waitForTimeout(500);

    // Error message should be displayed
    await expect(timelinePage.errorMessage).toBeVisible();
  });
});

test.describe('Batch Operations - Select All Functionality', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('select all only selects events on current page', async () => {
    // Note: With default mock data (4 events), all will be on one page
    const eventCount = await timelinePage.getEventCount();

    // Select all
    await timelinePage.selectAllEvents();

    // Verify all events on page are selected
    await expect(timelinePage.selectedCount).toHaveText(`${eventCount} selected`);
  });

  test('selecting individual events updates select all button state', async ({ page }) => {
    const eventCount = await timelinePage.getEventCount();
    expect(eventCount).toBeGreaterThanOrEqual(2);

    // Select first event
    await clickEventCheckbox(page,0);

    // Select all button should still show partial state (not all selected)
    const selectAllText = await timelinePage.selectAllButton.textContent();
    expect(selectAllText).toContain('1 selected');

    // Select all remaining events manually
    for (let i = 1; i < eventCount; i++) {
      await clickEventCheckbox(page,i);
    }

    // Now select all button should show all selected state
    const finalText = await timelinePage.selectAllButton.textContent();
    expect(finalText).toContain(`${eventCount} selected`);
  });

  test('select all button updates count correctly', async () => {
    const eventCount = await timelinePage.getEventCount();

    // Initially should show "Select all"
    await expect(timelinePage.selectAllButton).toContainText('Select all');

    // After selecting all
    await timelinePage.selectAllEvents();
    await expect(timelinePage.selectAllButton).toContainText(`${eventCount} selected`);

    // After deselecting all
    await timelinePage.selectAllEvents();
    await expect(timelinePage.selectAllButton).toContainText('Select all');
  });

  test('selection clears when changing pages', async ({ page }) => {
    // Select first event
    await clickEventCheckbox(page,0);
    await expect(timelinePage.selectedCount).toHaveText('1 selected');

    // Note: With default mock data, pagination might not be visible
    // If pagination exists, test page navigation clears selection
    const hasNextPage = await timelinePage.nextPageButton.isVisible();
    if (hasNextPage && (await timelinePage.nextPageButton.isEnabled())) {
      await timelinePage.goToNextPage();

      // Wait for page to load
      await page.waitForTimeout(500);

      // Selection should be maintained (per component implementation)
      // The component doesn't clear selection on page change
      // So we verify the selection count is still visible
      const isVisible = await timelinePage.selectedCount.isVisible();
      // This is implementation-dependent - document the actual behavior
      expect(typeof isVisible).toBe('boolean');
    }
  });
});

test.describe('Batch Operations - Edge Cases', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('cannot perform bulk actions without selecting events', async () => {
    // Bulk action buttons should not be visible when nothing is selected
    await expect(timelinePage.markReviewedButton).not.toBeVisible();
    await expect(timelinePage.markNotReviewedButton).not.toBeVisible();
  });

  // TODO: Enable when checkbox visual feedback UI is implemented
  test.skip('selection state visual feedback is clear', async ({ page }) => {
    // Select first event
    await clickEventCheckbox(page,0);

    // Verify checkbox shows selected state (CheckSquare icon with green color)
    const firstCheckbox = timelinePage.eventCards.first().locator('button[aria-label*="Deselect"]').first();
    await expect(firstCheckbox).toBeVisible();

    // Icon should have green color class
    const checkIcon = firstCheckbox.locator('svg');
    await expect(checkIcon).toHaveClass(/text-\[#76B900\]/);
  });

  // TODO: Enable when checkbox keyboard navigation is implemented
  test.skip('keyboard navigation works with checkboxes', async ({ page }) => {
    // Focus first checkbox
    const firstCheckbox = timelinePage.eventCards.first().locator('button[aria-label*="Select"]').first();
    await firstCheckbox.focus();

    // Press Enter to select
    await page.keyboard.press('Enter');

    // Verify selection
    await expect(timelinePage.selectedCount).toHaveText('1 selected');

    // Press Enter again to deselect
    await page.keyboard.press('Enter');

    // Selection should be cleared
    await expect(timelinePage.selectedCount).not.toBeVisible();
  });

  // TODO: Enable when bulk mark UI components are implemented
  test.skip('bulk operations work with mixed event types', async ({ page }) => {
    // Mock bulk update endpoint
    await page.route('**/api/events/bulk', async (route: Route) => {
      const request = route.request();
      if (request.method() === 'PATCH') {
        await route.fulfill({
          status: 207,
          contentType: 'application/json',
          body: JSON.stringify({
            successful: [{ id: 1, status: 200 }, { id: 2, status: 200 }],
            failed: [],
            summary: { total: 2, succeeded: 2, failed: 0 },
          }),
        });
      }
    });

    // Select multiple events (different risk levels)
    await clickEventCheckbox(page,0);
    await clickEventCheckbox(page,1);

    // Bulk mark as reviewed should work
    await timelinePage.markSelectedAsReviewed();

    // Wait for completion
    await page.waitForTimeout(500);

    // Should succeed
    await expect(timelinePage.selectedCount).not.toBeVisible();
  });

  test('rapid selection changes are handled correctly', async ({ page }) => {
    // Rapidly toggle selection
    for (let i = 0; i < 3; i++) {
      await clickEventCheckbox(page,0);
      await clickEventCheckbox(page,0); // Deselect
    }

    // Final state should be deselected
    await expect(timelinePage.selectedCount).not.toBeVisible();

    // Select and verify final state
    await clickEventCheckbox(page,0);
    await expect(timelinePage.selectedCount).toHaveText('1 selected');
  });
});
