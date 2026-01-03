/**
 * TimelinePage - Page Object for the Event Timeline
 *
 * Provides selectors and interactions for:
 * - Event list/cards
 * - Filtering (camera, risk level, date range, etc.)
 * - Search functionality
 * - Pagination
 * - Bulk actions
 * - Export functionality
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class TimelinePage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;

  // Search Section
  readonly fullTextSearchInput: Locator;
  readonly searchButton: Locator;
  readonly backToBrowseButton: Locator;

  // Filter Section
  readonly showFiltersButton: Locator;
  readonly hideFiltersButton: Locator;
  readonly filterActiveIndicator: Locator;
  readonly summarySearchInput: Locator;
  readonly clearSearchButton: Locator;

  // Filter Dropdowns
  readonly cameraFilter: Locator;
  readonly riskLevelFilter: Locator;
  readonly reviewedStatusFilter: Locator;
  readonly objectTypeFilter: Locator;
  readonly confidenceFilter: Locator;
  readonly sortByFilter: Locator;
  readonly startDateFilter: Locator;
  readonly endDateFilter: Locator;
  readonly clearFiltersButton: Locator;

  // Export Section
  readonly quickExportButton: Locator;
  readonly advancedExportButton: Locator;
  readonly exportPanel: Locator;

  // Results Section
  readonly resultsCount: Locator;
  readonly riskBadges: Locator;
  readonly eventCards: Locator;
  readonly noEventsMessage: Locator;

  // Bulk Actions
  readonly selectAllButton: Locator;
  readonly selectedCount: Locator;
  readonly markReviewedButton: Locator;
  readonly markNotReviewedButton: Locator;

  // Pagination
  readonly previousPageButton: Locator;
  readonly nextPageButton: Locator;
  readonly pageInfo: Locator;

  // Event Detail Modal
  readonly eventDetailModal: Locator;
  readonly modalCloseButton: Locator;

  // Loading/Error States
  readonly loadingSpinner: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /Event Timeline/i });
    this.pageSubtitle = page.getByText(/View and filter all security events/i);

    // Search Section
    this.fullTextSearchInput = page.getByPlaceholder(/Search events/i);
    this.searchButton = page.getByRole('button', { name: /Search/i });
    this.backToBrowseButton = page.getByText(/Back to browse/i);

    // Filter Section
    this.showFiltersButton = page.getByRole('button', { name: /Show Filters/i });
    this.hideFiltersButton = page.getByRole('button', { name: /Hide Filters/i });
    this.filterActiveIndicator = page.getByText(/Active/i);
    this.summarySearchInput = page.getByPlaceholder(/Search summaries/i);
    this.clearSearchButton = page.locator('button[aria-label="Clear search"]');

    // Filter Dropdowns
    this.cameraFilter = page.locator('#camera-filter');
    this.riskLevelFilter = page.locator('#risk-filter');
    this.reviewedStatusFilter = page.locator('#reviewed-filter');
    this.objectTypeFilter = page.locator('#object-type-filter');
    this.confidenceFilter = page.locator('#confidence-filter');
    this.sortByFilter = page.locator('#sort-filter');
    this.startDateFilter = page.locator('#start-date-filter');
    this.endDateFilter = page.locator('#end-date-filter');
    this.clearFiltersButton = page.getByRole('button', { name: /Clear All Filters/i });

    // Export Section
    this.quickExportButton = page.getByRole('button', { name: /Quick Export/i });
    this.advancedExportButton = page.getByRole('button', { name: /Advanced Export/i });
    this.exportPanel = page.locator('[class*="ExportPanel"]');

    // Results Section
    this.resultsCount = page.getByText(/Showing \d+-\d+ of \d+ events/i);
    this.riskBadges = page.locator('[class*="RiskBadge"]');
    // EventCard components are rendered as clickable divs with role="button" and aria-label starting with "View details"
    // They are inside the events grid (grid layout with gap-6)
    this.eventCards = page.locator('[role="button"][aria-label^="View details for event"]');
    this.noEventsMessage = page.getByText(/No Events Found/i);

    // Bulk Actions
    this.selectAllButton = page.getByRole('button', { name: /Select all/i });
    this.selectedCount = page.getByText(/\d+ selected/i);
    this.markReviewedButton = page.getByRole('button', { name: /Mark as Reviewed/i });
    this.markNotReviewedButton = page.getByRole('button', { name: /Mark Not Reviewed/i });

    // Pagination
    this.previousPageButton = page.getByRole('button', { name: /Previous/i });
    this.nextPageButton = page.getByRole('button', { name: /Next/i });
    this.pageInfo = page.getByText(/Page \d+ of \d+/i);

    // Event Detail Modal
    this.eventDetailModal = page.locator('[role="dialog"]');
    this.modalCloseButton = page.locator('[role="dialog"] button[aria-label*="close" i], [role="dialog"] button:has-text("Close")');

    // Loading/Error States
    this.loadingSpinner = page.locator('.animate-spin');
    this.errorMessage = page.getByText(/Error Loading Events/i);
  }

  /**
   * Navigate to the Timeline page
   */
  async goto(): Promise<void> {
    await this.page.goto('/timeline');
  }

  /**
   * Wait for the timeline to fully load (including data)
   */
  async waitForTimelineLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
    // Wait for either events to load OR no events message OR error state
    // This ensures we don't proceed until actual content is rendered
    await Promise.race([
      this.eventCards.first().waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
      this.noEventsMessage.waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
      this.errorMessage.waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
    ]).catch(() => {
      // One of them should appear, but if none do within timeout, continue anyway
    });
  }

  /**
   * Show the filters panel
   */
  async showFilters(): Promise<void> {
    const isHidden = await this.showFiltersButton.isVisible();
    if (isHidden) {
      await this.showFiltersButton.click();
    }
  }

  /**
   * Hide the filters panel
   */
  async hideFilters(): Promise<void> {
    const isShown = await this.hideFiltersButton.isVisible();
    if (isShown) {
      await this.hideFiltersButton.click();
    }
  }

  /**
   * Filter by camera
   */
  async filterByCamera(cameraId: string): Promise<void> {
    await this.showFilters();
    await this.cameraFilter.selectOption(cameraId);
  }

  /**
   * Filter by risk level
   */
  async filterByRiskLevel(level: 'low' | 'medium' | 'high' | 'critical'): Promise<void> {
    await this.showFilters();
    await this.riskLevelFilter.selectOption(level);
  }

  /**
   * Filter by reviewed status
   */
  async filterByReviewedStatus(reviewed: boolean): Promise<void> {
    await this.showFilters();
    await this.reviewedStatusFilter.selectOption(reviewed ? 'true' : 'false');
  }

  /**
   * Set date range filter
   */
  async filterByDateRange(startDate: string, endDate: string): Promise<void> {
    await this.showFilters();
    await this.startDateFilter.fill(startDate);
    await this.endDateFilter.fill(endDate);
  }

  /**
   * Sort events
   */
  async sortBy(option: 'newest' | 'oldest' | 'risk_high' | 'risk_low'): Promise<void> {
    await this.showFilters();
    await this.sortByFilter.selectOption(option);
  }

  /**
   * Clear all filters
   */
  async clearAllFilters(): Promise<void> {
    await this.showFilters();
    await this.clearFiltersButton.click();
  }

  /**
   * Search events by summary
   */
  async searchSummary(query: string): Promise<void> {
    await this.summarySearchInput.fill(query);
  }

  /**
   * Full-text search
   */
  async fullTextSearch(query: string): Promise<void> {
    await this.fullTextSearchInput.fill(query);
    await this.page.keyboard.press('Enter');
  }

  /**
   * Get count of displayed events
   */
  async getEventCount(): Promise<number> {
    return this.eventCards.count();
  }

  /**
   * Click on an event card
   */
  async clickEvent(index: number = 0): Promise<void> {
    await this.eventCards.nth(index).click();
  }

  /**
   * Select an event for bulk action
   */
  async selectEvent(index: number): Promise<void> {
    const checkbox = this.eventCards.nth(index).locator('button[aria-label*="Select"]');
    await checkbox.click();
  }

  /**
   * Select all events
   */
  async selectAllEvents(): Promise<void> {
    await this.selectAllButton.click();
  }

  /**
   * Mark selected events as reviewed
   */
  async markSelectedAsReviewed(): Promise<void> {
    await this.markReviewedButton.click();
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
   * Quick export events
   */
  async quickExport(): Promise<void> {
    await this.quickExportButton.click();
  }

  /**
   * Check if event detail modal is open
   */
  async isModalOpen(): Promise<boolean> {
    return this.eventDetailModal.isVisible();
  }

  /**
   * Close event detail modal
   */
  async closeModal(): Promise<void> {
    // Try clicking outside the modal or pressing Escape
    await this.page.keyboard.press('Escape');
  }

  /**
   * Check if no events message is shown
   */
  async hasNoEventsMessage(): Promise<boolean> {
    return this.noEventsMessage.isVisible().catch(() => false);
  }

  /**
   * Check if filters are active
   */
  async hasActiveFilters(): Promise<boolean> {
    return this.filterActiveIndicator.isVisible().catch(() => false);
  }
}
