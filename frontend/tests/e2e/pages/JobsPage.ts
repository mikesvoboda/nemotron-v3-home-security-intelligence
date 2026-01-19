/**
 * JobsPage - Page Object for the Jobs page
 *
 * Provides selectors and interactions for:
 * - Jobs list display
 * - Job filtering (status, type, search)
 * - Job detail panel
 * - Job operations (retry, cancel, view logs)
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class JobsPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;

  // Header actions
  readonly refreshButton: Locator;
  readonly statsButton: Locator;

  // Search and filters
  readonly searchInput: Locator;
  readonly statusFilter: Locator;
  readonly typeFilter: Locator;
  readonly clearFiltersButton: Locator;

  // Jobs list
  readonly jobsList: Locator;
  readonly jobsListItems: Locator;
  readonly emptyState: Locator;
  readonly noMatchState: Locator;

  // Job detail panel
  readonly jobDetailPanel: Locator;
  readonly jobDetailPlaceholder: Locator;

  // Loading/Error States
  readonly loadingSpinner: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /^Jobs$/i });
    this.pageSubtitle = page.getByText(/Monitor background jobs and their progress/i);

    // Header actions
    this.refreshButton = page.getByRole('button', { name: /Refresh/i });
    this.statsButton = page.getByRole('button', { name: /Stats/i });

    // Search and filters
    this.searchInput = page.getByPlaceholder(/Search jobs/i);
    this.statusFilter = page.locator('#jobs-status-filter');
    this.typeFilter = page.locator('#jobs-type-filter');
    this.clearFiltersButton = page.getByRole('button', { name: /Clear all/i });

    // Jobs list
    this.jobsList = page.locator('[data-testid="jobs-list"]');
    this.jobsListItems = page.locator('[data-testid^="job-item-"]');
    this.emptyState = page.getByText(/No jobs have been created yet/i);
    this.noMatchState = page.getByText(/No jobs match your search/i);

    // Job detail panel
    this.jobDetailPanel = page.locator('[data-testid="job-detail-panel"]');
    this.jobDetailPlaceholder = page.getByText(/Select a job to view details/i);

    // Loading/Error States
    this.loadingSpinner = page.locator('.animate-spin');
    this.errorMessage = page.getByText(/Error Loading Jobs/i);
  }

  /**
   * Navigate to the Jobs page
   */
  async goto(): Promise<void> {
    await this.page.goto('/jobs');
  }

  /**
   * Wait for the jobs page to fully load (including data loading)
   */
  async waitForJobsLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
    // Wait for loading spinner to disappear (if visible)
    await this.loadingSpinner.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
    // Wait for filters to be enabled (not loading)
    await expect(this.searchInput).toBeEnabled({ timeout: 10000 });
  }

  /**
   * Get count of displayed job items
   */
  async getJobCount(): Promise<number> {
    return this.jobsListItems.count();
  }

  /**
   * Search jobs by query
   */
  async searchJobs(query: string): Promise<void> {
    await this.searchInput.fill(query);
    // Wait for debounce
    await this.page.waitForTimeout(500);
  }

  /**
   * Filter by job status
   */
  async filterByStatus(status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'): Promise<void> {
    await this.statusFilter.selectOption(status);
  }

  /**
   * Filter by job type
   */
  async filterByType(type: string): Promise<void> {
    await this.typeFilter.selectOption(type);
  }

  /**
   * Clear all filters
   */
  async clearFilters(): Promise<void> {
    await this.clearFiltersButton.click();
  }

  /**
   * Click on a job in the list
   */
  async clickJob(index: number = 0): Promise<void> {
    await this.jobsListItems.nth(index).click();
  }

  /**
   * Click on a specific job by ID
   */
  async clickJobById(jobId: string): Promise<void> {
    await this.page.locator(`[data-testid="job-item-${jobId}"]`).click();
  }

  /**
   * Refresh the jobs list
   */
  async refresh(): Promise<void> {
    await this.refreshButton.click();
  }

  /**
   * Check if empty state is shown
   */
  async hasEmptyState(): Promise<boolean> {
    try {
      await this.emptyState.waitFor({ state: 'visible', timeout: 10000 });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Check if no match state is shown
   */
  async hasNoMatchState(): Promise<boolean> {
    try {
      await this.noMatchState.waitFor({ state: 'visible', timeout: 5000 });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Check if error state is shown
   */
  async hasError(): Promise<boolean> {
    return this.errorMessage.isVisible().catch(() => false);
  }

  /**
   * Check if job detail panel is visible
   */
  async isDetailPanelVisible(): Promise<boolean> {
    return this.jobDetailPanel.isVisible().catch(() => false);
  }

  /**
   * Check if detail panel shows placeholder
   */
  async isDetailPlaceholderVisible(): Promise<boolean> {
    return this.jobDetailPlaceholder.isVisible().catch(() => false);
  }
}
