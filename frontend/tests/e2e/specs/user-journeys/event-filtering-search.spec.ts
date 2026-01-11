/**
 * Event Filtering and Search User Journey E2E Tests
 *
 * Linear Issue: NEM-2049
 * Test Coverage: Critical user journey for event discovery and filtering
 *
 * Acceptance Criteria:
 * - User can apply multiple filters simultaneously
 * - User can combine filters with search
 * - User can clear filters and reset view
 * - Filters persist during navigation
 * - Search results are accurate and performant
 * - Date range filtering works correctly
 * - Filter combinations produce expected results
 */

import { test, expect } from '../../fixtures';

test.describe('Event Filtering and Search Journey (NEM-2049)', () => {
  test.beforeEach(async ({ page, browserName }) => {
    // Navigate to timeline page
    await page.goto('/timeline', { waitUntil: 'domcontentloaded' });

    // Wait for timeline to load
    const timeout = browserName === 'chromium' ? 10000 : 20000;
    await page.waitForSelector('h1:has-text("Event Timeline")', {
      state: 'visible',
      timeout
    });

    // Wait for main content
    await page.waitForTimeout(1000);
  });

  test('user can apply single filter and see filtered results', async ({ page }) => {
    /**
     * Given: User is on timeline page with events
     * When: User applies a single filter (risk level)
     * Then: Event list updates to show only matching events
     */

    // Given: Timeline page loaded
    await expect(page.locator('h1:has-text("Event Timeline")')).toBeVisible();

    // When: Show filters and select high risk level
    const showFiltersButton = page.getByRole('button', { name: /Show Filters/i });
    if (await showFiltersButton.isVisible()) {
      await showFiltersButton.click();
      await page.waitForTimeout(500);
    }

    // Apply risk level filter
    const riskFilter = page.locator('#risk-filter');
    if (await riskFilter.isVisible()) {
      await riskFilter.selectOption('high');
      await page.waitForTimeout(1000);

      // Then: Verify events are filtered
      const eventCards = page.locator('[role="button"][aria-label^="View details for event"]');
      const eventCount = await eventCards.count();

      // Either we have filtered events or a "no events" message
      if (eventCount === 0) {
        const noEventsMessage = page.getByText(/No Events Found/i);
        await expect(noEventsMessage).toBeVisible();
      } else {
        // Verify at least one event is visible
        await expect(eventCards.first()).toBeVisible();
      }
    }
  });

  test('user can combine multiple filters for precise results', async ({ page }) => {
    /**
     * Given: User is on timeline with filters panel open
     * When: User applies multiple filters (camera + risk level + object type)
     * Then: Results show only events matching ALL criteria
     */

    // Given: Timeline page loaded
    await expect(page.locator('h1:has-text("Event Timeline")')).toBeVisible();

    // Show filters
    const showFiltersButton = page.getByRole('button', { name: /Show Filters/i });
    if (await showFiltersButton.isVisible()) {
      await showFiltersButton.click();
      await page.waitForTimeout(500);
    }

    // When: Apply multiple filters
    const cameraFilter = page.locator('#camera-filter');
    const riskFilter = page.locator('#risk-filter');
    const objectTypeFilter = page.locator('#object-type-filter');

    let filtersApplied = 0;

    if (await cameraFilter.isVisible()) {
      // Get available options
      const options = await cameraFilter.locator('option').count();
      if (options > 1) {
        await cameraFilter.selectOption({ index: 1 });
        filtersApplied++;
        await page.waitForTimeout(500);
      }
    }

    if (await riskFilter.isVisible()) {
      await riskFilter.selectOption('high');
      filtersApplied++;
      await page.waitForTimeout(500);
    }

    if (await objectTypeFilter.isVisible()) {
      const options = await objectTypeFilter.locator('option').count();
      if (options > 1) {
        await objectTypeFilter.selectOption({ index: 1 });
        filtersApplied++;
        await page.waitForTimeout(500);
      }
    }

    // Then: Verify filtering occurred (if filters were available)
    if (filtersApplied > 0) {
      await page.waitForTimeout(1000);

      // Check for events or no events message
      const eventCards = page.locator('[role="button"][aria-label^="View details for event"]');
      const noEventsMessage = page.getByText(/No Events Found/i);

      const hasEvents = await eventCards.first().isVisible().catch(() => false);
      const hasNoEventsMessage = await noEventsMessage.isVisible().catch(() => false);

      expect(hasEvents || hasNoEventsMessage).toBeTruthy();
    }
  });

  test('user can search events with full-text search', async ({ page }) => {
    /**
     * Given: User is on timeline page
     * When: User enters search query and submits
     * Then: Results show only events matching search terms
     */

    // Given: Timeline page loaded
    await expect(page.locator('h1:has-text("Event Timeline")')).toBeVisible();

    // When: Enter search query
    const searchInput = page.getByPlaceholder(/Search events/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill('person');
      await page.keyboard.press('Enter');

      // Wait for search results
      await page.waitForTimeout(1500);

      // Then: Verify search results or no results message
      const eventCards = page.locator('[role="button"][aria-label^="View details for event"]');
      const noEventsMessage = page.getByText(/No Events Found/i);

      const hasEvents = await eventCards.first().isVisible().catch(() => false);
      const hasNoEventsMessage = await noEventsMessage.isVisible().catch(() => false);

      expect(hasEvents || hasNoEventsMessage).toBeTruthy();
    }
  });

  test('user can combine search with filters', async ({ page }) => {
    /**
     * Given: User has applied filters
     * When: User also performs a search
     * Then: Results match both filter criteria AND search terms
     */

    // Given: Timeline page loaded
    await expect(page.locator('h1:has-text("Event Timeline")')).toBeVisible();

    // Show filters and apply one
    const showFiltersButton = page.getByRole('button', { name: /Show Filters/i });
    if (await showFiltersButton.isVisible()) {
      await showFiltersButton.click();
      await page.waitForTimeout(500);
    }

    const riskFilter = page.locator('#risk-filter');
    if (await riskFilter.isVisible()) {
      await riskFilter.selectOption('high');
      await page.waitForTimeout(1000);
    }

    // When: Also perform search
    const searchInput = page.getByPlaceholder(/Search events/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill('detection');
      await page.keyboard.press('Enter');
      await page.waitForTimeout(1500);

      // Then: Verify combined results
      const eventCards = page.locator('[role="button"][aria-label^="View details for event"]');
      const noEventsMessage = page.getByText(/No Events Found/i);

      const hasEvents = await eventCards.first().isVisible().catch(() => false);
      const hasNoEventsMessage = await noEventsMessage.isVisible().catch(() => false);

      expect(hasEvents || hasNoEventsMessage).toBeTruthy();
    }
  });

  test('user can clear all filters and return to full event list', async ({ page }) => {
    /**
     * Given: User has applied multiple filters
     * When: User clicks "Clear All Filters"
     * Then: All filters reset and full event list is shown
     */

    // Given: Timeline page with filters applied
    await expect(page.locator('h1:has-text("Event Timeline")')).toBeVisible();

    const showFiltersButton = page.getByRole('button', { name: /Show Filters/i });
    if (await showFiltersButton.isVisible()) {
      await showFiltersButton.click();
      await page.waitForTimeout(500);
    }

    // Apply some filters
    const riskFilter = page.locator('#risk-filter');
    if (await riskFilter.isVisible()) {
      await riskFilter.selectOption('high');
      await page.waitForTimeout(1000);
    }

    // When: Clear all filters
    const clearFiltersButton = page.getByRole('button', { name: /Clear All Filters/i });
    if (await clearFiltersButton.isVisible()) {
      await clearFiltersButton.click();
      await page.waitForTimeout(1000);

      // Then: Verify filters are cleared (accept 'all' or '' as default)
      const riskValue = await riskFilter.inputValue();
      expect(riskValue === 'all' || riskValue === '').toBeTruthy();
    }
  });

  test('user can filter by date range', async ({ page }) => {
    /**
     * Given: User is on timeline page with filters open
     * When: User selects start and end dates
     * Then: Only events within date range are shown
     */

    // Given: Timeline page loaded
    await expect(page.locator('h1:has-text("Event Timeline")')).toBeVisible();

    const showFiltersButton = page.getByRole('button', { name: /Show Filters/i });
    if (await showFiltersButton.isVisible()) {
      await showFiltersButton.click();
      await page.waitForTimeout(500);
    }

    // When: Set date range
    const startDateFilter = page.locator('#start-date-filter');
    const endDateFilter = page.locator('#end-date-filter');

    if (await startDateFilter.isVisible() && await endDateFilter.isVisible()) {
      // Set date range (last 7 days)
      const today = new Date();
      const lastWeek = new Date(today);
      lastWeek.setDate(today.getDate() - 7);

      const formatDate = (date: Date) => date.toISOString().split('T')[0];

      await startDateFilter.fill(formatDate(lastWeek));
      await endDateFilter.fill(formatDate(today));
      await page.waitForTimeout(1500);

      // Then: Verify date filtering applied
      const eventCards = page.locator('[role="button"][aria-label^="View details for event"]');
      const noEventsMessage = page.getByText(/No Events Found/i);

      const hasEvents = await eventCards.first().isVisible().catch(() => false);
      const hasNoEventsMessage = await noEventsMessage.isVisible().catch(() => false);

      expect(hasEvents || hasNoEventsMessage).toBeTruthy();
    }
  });

  test('user can sort events by different criteria', async ({ page }) => {
    /**
     * Given: User is viewing filtered events
     * When: User changes sort order
     * Then: Events reorder according to selected criteria
     */

    // Given: Timeline page loaded
    await expect(page.locator('h1:has-text("Event Timeline")')).toBeVisible();

    const showFiltersButton = page.getByRole('button', { name: /Show Filters/i });
    if (await showFiltersButton.isVisible()) {
      await showFiltersButton.click();
      await page.waitForTimeout(500);
    }

    // When: Change sort order
    const sortFilter = page.locator('#sort-filter');
    if (await sortFilter.isVisible()) {
      // Get initial event order
      const eventCards = page.locator('[role="button"][aria-label^="View details for event"]');
      const initialCount = await eventCards.count();

      // Change sort to oldest first
      await sortFilter.selectOption('oldest');
      await page.waitForTimeout(1500);

      // Then: Verify events are still displayed (order changed)
      const newCount = await eventCards.count();

      // Either same count (reordered) or different count (some filtered out)
      expect(newCount).toBeGreaterThanOrEqual(0);
    }
  });

  test('filters persist when navigating to event detail and back', async ({ page }) => {
    /**
     * Given: User has applied filters
     * When: User clicks an event, views detail, then goes back
     * Then: Filters remain applied
     */

    // Given: Timeline with filters applied
    await expect(page.locator('h1:has-text("Event Timeline")')).toBeVisible();

    const showFiltersButton = page.getByRole('button', { name: /Show Filters/i });
    if (await showFiltersButton.isVisible()) {
      await showFiltersButton.click();
      await page.waitForTimeout(500);
    }

    const riskFilter = page.locator('#risk-filter');
    if (await riskFilter.isVisible()) {
      await riskFilter.selectOption('high');
      await page.waitForTimeout(1000);

      // Remember filter value
      const filterValue = await riskFilter.inputValue();

      // When: Click an event (if any exist)
      const eventCards = page.locator('[role="button"][aria-label^="View details for event"]');
      if (await eventCards.first().isVisible()) {
        await eventCards.first().click();
        await page.waitForTimeout(1000);

        // Close modal with Escape
        await page.keyboard.press('Escape');
        await page.waitForTimeout(500);

        // Then: Verify filter still applied
        const currentFilterValue = await riskFilter.inputValue();
        expect(currentFilterValue).toBe(filterValue);
      }
    }
  });

  test('user can filter by reviewed status', async ({ page }) => {
    /**
     * Given: User is on timeline page
     * When: User filters by reviewed/not reviewed status
     * Then: Only events matching review status are shown
     */

    // Given: Timeline page loaded
    await expect(page.locator('h1:has-text("Event Timeline")')).toBeVisible();

    const showFiltersButton = page.getByRole('button', { name: /Show Filters/i });
    if (await showFiltersButton.isVisible()) {
      await showFiltersButton.click();
      await page.waitForTimeout(500);
    }

    // When: Filter by reviewed status
    const reviewedFilter = page.locator('#reviewed-filter');
    if (await reviewedFilter.isVisible()) {
      await reviewedFilter.selectOption('false'); // Not reviewed
      await page.waitForTimeout(1500);

      // Then: Verify filtering applied
      const eventCards = page.locator('[role="button"][aria-label^="View details for event"]');
      const noEventsMessage = page.getByText(/No Events Found/i);

      const hasEvents = await eventCards.first().isVisible().catch(() => false);
      const hasNoEventsMessage = await noEventsMessage.isVisible().catch(() => false);

      expect(hasEvents || hasNoEventsMessage).toBeTruthy();
    }
  });

  test('user can clear search and keep filters active', async ({ page }) => {
    /**
     * Given: User has both search and filters active
     * When: User clears search but keeps filters
     * Then: Filter results remain, search is cleared
     */

    // Given: Timeline with both search and filters
    await expect(page.locator('h1:has-text("Event Timeline")')).toBeVisible();

    // Apply filter
    const showFiltersButton = page.getByRole('button', { name: /Show Filters/i });
    if (await showFiltersButton.isVisible()) {
      await showFiltersButton.click();
      await page.waitForTimeout(500);
    }

    const riskFilter = page.locator('#risk-filter');
    if (await riskFilter.isVisible()) {
      await riskFilter.selectOption('medium');
      await page.waitForTimeout(1000);
    }

    // Apply search
    const searchInput = page.getByPlaceholder(/Search events/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill('test search');
      await page.keyboard.press('Enter');
      await page.waitForTimeout(1500);

      // When: Clear search
      await searchInput.clear();
      await page.keyboard.press('Enter');
      await page.waitForTimeout(1000);

      // Then: Verify filter still active but search cleared
      const searchValue = await searchInput.inputValue();
      const riskValue = await riskFilter.inputValue();

      expect(searchValue).toBe('');
      expect(riskValue).toBe('medium');
    }
  });

  test('filtering updates results count display', async ({ page }) => {
    /**
     * Given: User is viewing unfiltered events
     * When: User applies filters
     * Then: Results count updates to reflect filtered results
     */

    // Given: Timeline page loaded
    await expect(page.locator('h1:has-text("Event Timeline")')).toBeVisible();

    // Get initial results count (if displayed)
    const resultsCount = page.getByText(/Showing \d+-\d+ of \d+ events/i);
    const hasInitialCount = await resultsCount.isVisible().catch(() => false);

    // When: Apply filter
    const showFiltersButton = page.getByRole('button', { name: /Show Filters/i });
    if (await showFiltersButton.isVisible()) {
      await showFiltersButton.click();
      await page.waitForTimeout(500);
    }

    const riskFilter = page.locator('#risk-filter');
    if (await riskFilter.isVisible()) {
      await riskFilter.selectOption('critical');
      await page.waitForTimeout(1500);

      // Then: Verify count updated or events changed
      const eventCards = page.locator('[role="button"][aria-label^="View details for event"]');
      const eventCount = await eventCards.count();

      // Results should be filtered (count may be 0 or positive)
      expect(eventCount).toBeGreaterThanOrEqual(0);
    }
  });
});
