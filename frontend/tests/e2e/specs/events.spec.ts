/**
 * Events/Timeline Tests for Home Security Dashboard
 *
 * Comprehensive tests for the Event Timeline page including:
 * - Event listing and display
 * - Filtering functionality
 * - Search functionality
 * - Pagination
 * - Bulk actions
 * - Export functionality
 */

import { test, expect } from '@playwright/test';
import { TimelinePage } from '../pages';
import {
  setupApiMocks,
  defaultMockConfig,
  emptyMockConfig,
  errorMockConfig,
  highAlertMockConfig,
} from '../fixtures';

test.describe('Event Timeline Page Load', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
  });

  test('timeline page loads successfully', async () => {
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('timeline displays page title', async () => {
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    await expect(timelinePage.pageTitle).toBeVisible();
  });

  test('timeline displays page subtitle', async () => {
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    await expect(timelinePage.pageSubtitle).toBeVisible();
  });

  test('timeline has full-text search input', async () => {
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    await expect(timelinePage.fullTextSearchInput).toBeVisible();
  });
});

test.describe('Event Timeline Filters', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('show filters button is visible', async () => {
    await expect(timelinePage.showFiltersButton).toBeVisible();
  });

  test('can expand filters panel', async () => {
    await timelinePage.showFilters();
    await expect(timelinePage.cameraFilter).toBeVisible();
  });

  test('camera filter dropdown is available', async () => {
    await timelinePage.showFilters();
    await expect(timelinePage.cameraFilter).toBeVisible();
  });

  test('risk level filter dropdown is available', async () => {
    await timelinePage.showFilters();
    await expect(timelinePage.riskLevelFilter).toBeVisible();
  });

  test('reviewed status filter dropdown is available', async () => {
    await timelinePage.showFilters();
    await expect(timelinePage.reviewedStatusFilter).toBeVisible();
  });

  test('object type filter dropdown is available', async () => {
    await timelinePage.showFilters();
    await expect(timelinePage.objectTypeFilter).toBeVisible();
  });

  test('sort by filter dropdown is available', async () => {
    await timelinePage.showFilters();
    await expect(timelinePage.sortByFilter).toBeVisible();
  });

  test('start date filter is available', async () => {
    await timelinePage.showFilters();
    await expect(timelinePage.startDateFilter).toBeVisible();
  });

  test('end date filter is available', async () => {
    await timelinePage.showFilters();
    await expect(timelinePage.endDateFilter).toBeVisible();
  });

  test('clear filters button is available', async () => {
    await timelinePage.showFilters();
    await expect(timelinePage.clearFiltersButton).toBeVisible();
  });
});

test.describe('Event Timeline Search', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('summary search input is visible', async () => {
    await timelinePage.showFilters();
    await expect(timelinePage.summarySearchInput).toBeVisible();
  });

  test('can type in summary search', async () => {
    await timelinePage.showFilters();
    await timelinePage.searchSummary('person');
    await expect(timelinePage.summarySearchInput).toHaveValue('person');
  });

  test('full-text search input accepts query', async () => {
    await timelinePage.fullTextSearchInput.fill('suspicious');
    await expect(timelinePage.fullTextSearchInput).toHaveValue('suspicious');
  });
});

test.describe('Event Timeline Export', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('quick export button is visible', async () => {
    await expect(timelinePage.quickExportButton).toBeVisible();
  });

  test('advanced export button is visible', async () => {
    await expect(timelinePage.advancedExportButton).toBeVisible();
  });
});

test.describe('Event Timeline Pagination', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('previous page button exists', async () => {
    await expect(timelinePage.previousPageButton).toBeVisible();
  });

  test('next page button exists', async () => {
    await expect(timelinePage.nextPageButton).toBeVisible();
  });
});

test.describe('Event Timeline Bulk Actions', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
  });

  test('select all button is visible', async () => {
    await expect(timelinePage.selectAllButton).toBeVisible();
  });
});

test.describe('Event Timeline Empty State', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    timelinePage = new TimelinePage(page);
  });

  test('shows no events message when no events', async () => {
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    const hasNoEvents = await timelinePage.hasNoEventsMessage();
    expect(hasNoEvents).toBe(true);
  });
});

test.describe('Event Timeline Error State', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    timelinePage = new TimelinePage(page);
  });

  test('shows error message when API fails', async () => {
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    await expect(timelinePage.errorMessage).toBeVisible({ timeout: 8000 });
  });
});
