/**
 * LogsPage - Page Object for the System Logs page
 *
 * Provides selectors and interactions for:
 * - Log stats cards
 * - Log filtering
 * - Logs table
 * - Log detail modal
 * - Pagination
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class LogsPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;

  // Stats Cards
  readonly statsSection: Locator;
  readonly debugCount: Locator;
  readonly infoCount: Locator;
  readonly warningCount: Locator;
  readonly errorCount: Locator;
  readonly totalCount: Locator;

  // Filters
  readonly filtersSection: Locator;
  readonly levelFilter: Locator;
  readonly componentFilter: Locator;
  readonly cameraFilter: Locator;
  readonly startDateFilter: Locator;
  readonly endDateFilter: Locator;
  readonly searchInput: Locator;
  readonly clearFiltersButton: Locator;

  // Logs Table
  readonly logsTable: Locator;
  readonly tableRows: Locator;
  readonly tableHeaders: Locator;
  readonly emptyState: Locator;

  // Log Detail Modal
  readonly detailModal: Locator;
  readonly modalTitle: Locator;
  readonly modalCloseButton: Locator;
  readonly logMessage: Locator;
  readonly logDetails: Locator;

  // Pagination
  readonly previousPageButton: Locator;
  readonly nextPageButton: Locator;
  readonly pageInfo: Locator;

  // Loading/Error States
  readonly loadingSpinner: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /System Logs/i });
    this.pageSubtitle = page.getByText(/View and filter all system logs/i);

    // Stats Cards
    this.statsSection = page.locator('[class*="LogStatsCards"]');
    this.debugCount = page.getByText(/Debug/i).locator('..').locator('[class*="count"], span');
    this.infoCount = page.getByText(/Info/i).locator('..').locator('[class*="count"], span');
    this.warningCount = page.getByText(/Warning/i).locator('..').locator('[class*="count"], span');
    this.errorCount = page.getByText(/Error/i).locator('..').locator('[class*="count"], span');
    this.totalCount = page.getByText(/Total/i).locator('..').locator('[class*="count"], span');

    // Filters - use id selectors that match the actual form elements (filters hidden by default)
    this.filtersSection = page.locator('[class*="LogFilters"]');
    this.levelFilter = page.locator('#level-filter');
    this.componentFilter = page.locator('#component-filter');
    this.cameraFilter = page.locator('#camera-filter');
    this.startDateFilter = page.locator('#start-date-filter');
    this.endDateFilter = page.locator('#end-date-filter');
    this.searchInput = page.getByPlaceholder(/Search log messages/i);
    this.clearFiltersButton = page.getByRole('button', { name: /Clear All Filters/i });

    // Logs Table
    this.logsTable = page.locator('[class*="LogsTable"], table');
    this.tableRows = page.locator('tbody tr');
    this.tableHeaders = page.locator('thead th');
    this.emptyState = page.getByText(/No logs found/i);

    // Log Detail Modal
    this.detailModal = page.locator('[role="dialog"]');
    this.modalTitle = page.locator('[role="dialog"] h2, [role="dialog"] [class*="title"]');
    this.modalCloseButton = page.locator('[role="dialog"] button[aria-label*="close" i]');
    this.logMessage = page.locator('[role="dialog"] [class*="message"]');
    this.logDetails = page.locator('[role="dialog"] [class*="details"], [role="dialog"] pre');

    // Pagination
    this.previousPageButton = page.getByRole('button', { name: /Previous/i });
    this.nextPageButton = page.getByRole('button', { name: /Next/i });
    this.pageInfo = page.getByText(/Page \d+ of \d+/i);

    // Loading/Error States
    this.loadingSpinner = page.locator('.animate-spin');
    this.errorMessage = page.getByText(/Failed to load logs/i);
  }

  /**
   * Navigate to the Logs page
   */
  async goto(): Promise<void> {
    await this.page.goto('/logs');
  }

  /**
   * Wait for the logs page to fully load
   */
  async waitForLogsLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Show the filters panel
   */
  async showFilters(): Promise<void> {
    const showBtn = this.page.getByRole('button', { name: /Show Filters/i });
    if (await showBtn.isVisible()) {
      await showBtn.click();
    }
  }

  /**
   * Filter by log level
   */
  async filterByLevel(level: 'debug' | 'info' | 'warning' | 'error'): Promise<void> {
    await this.showFilters();
    await this.levelFilter.selectOption(level.toUpperCase());
  }

  /**
   * Filter by component
   */
  async filterByComponent(component: string): Promise<void> {
    await this.componentFilter.selectOption(component);
  }

  /**
   * Search logs
   */
  async searchLogs(query: string): Promise<void> {
    await this.searchInput.fill(query);
  }

  /**
   * Set date range filter
   */
  async filterByDateRange(startDate: string, endDate: string): Promise<void> {
    await this.startDateFilter.fill(startDate);
    await this.endDateFilter.fill(endDate);
  }

  /**
   * Clear all filters
   */
  async clearFilters(): Promise<void> {
    await this.clearFiltersButton.click();
  }

  /**
   * Get count of displayed log rows
   */
  async getLogRowCount(): Promise<number> {
    return this.tableRows.count();
  }

  /**
   * Click on a log row to open detail modal
   */
  async clickLogRow(index: number = 0): Promise<void> {
    await this.tableRows.nth(index).click();
  }

  /**
   * Check if detail modal is open
   */
  async isModalOpen(): Promise<boolean> {
    return this.detailModal.isVisible();
  }

  /**
   * Close detail modal
   */
  async closeModal(): Promise<void> {
    await this.page.keyboard.press('Escape');
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
   * Check if empty state is shown
   * Waits up to 10s for the empty state to appear (WebKit is slower)
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
   * Check if error state is shown
   */
  async hasError(): Promise<boolean> {
    return this.errorMessage.isVisible().catch(() => false);
  }
}
