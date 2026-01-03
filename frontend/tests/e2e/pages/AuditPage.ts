/**
 * AuditPage - Page Object for the Audit Log page
 *
 * Provides selectors and interactions for:
 * - Audit stats cards
 * - Audit filtering
 * - Audit table
 * - Audit detail modal
 * - Pagination
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class AuditPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;

  // Stats Cards
  readonly statsSection: Locator;
  readonly totalActionsCard: Locator;
  readonly successRateCard: Locator;
  readonly recentActorsCard: Locator;

  // Filters
  readonly filtersSection: Locator;
  readonly actionFilter: Locator;
  readonly resourceTypeFilter: Locator;
  readonly actorFilter: Locator;
  readonly statusFilter: Locator;
  readonly startDateFilter: Locator;
  readonly endDateFilter: Locator;
  readonly clearFiltersButton: Locator;

  // Audit Table
  readonly auditTable: Locator;
  readonly tableRows: Locator;
  readonly tableHeaders: Locator;
  readonly emptyState: Locator;

  // Audit Detail Modal
  readonly detailModal: Locator;
  readonly modalTitle: Locator;
  readonly modalCloseButton: Locator;
  readonly auditAction: Locator;
  readonly auditDetails: Locator;

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
    this.pageTitle = page.getByRole('heading', { name: /Audit Log/i });
    this.pageSubtitle = page.getByText(/Review security-sensitive operations/i);

    // Stats Cards
    this.statsSection = page.locator('[class*="AuditStatsCards"]');
    this.totalActionsCard = page.getByText(/Total Actions/i).locator('..');
    this.successRateCard = page.getByText(/Success Rate/i).locator('..');
    this.recentActorsCard = page.getByText(/Recent Actors/i).locator('..');

    // Filters - use select locators that match actual form structure
    this.filtersSection = page.locator('[class*="AuditFilters"]');
    this.actionFilter = page.locator('select').filter({ has: page.locator('option:text-is("All Actions")') }).first();
    this.resourceTypeFilter = page.locator('select').filter({ has: page.locator('option:text-is("All Resources")') }).first();
    this.actorFilter = page.locator('select').filter({ has: page.locator('option:text-is("All Actors")') }).first();
    this.statusFilter = page.locator('select').filter({ has: page.locator('option:text-is("All Statuses")') }).first();
    this.startDateFilter = page.locator('input[type="date"]').first();
    this.endDateFilter = page.locator('input[type="date"]').last();
    this.clearFiltersButton = page.getByRole('button', { name: /Clear/i });

    // Audit Table - look for either the table element or empty/error states
    // Note: The table may show loading state, empty state, or data state
    this.auditTable = page.locator('table').first();
    this.tableRows = page.locator('tbody tr');
    this.tableHeaders = page.locator('thead th');
    this.emptyState = page.getByText(/No audit logs found/i);

    // Audit Detail Modal
    this.detailModal = page.locator('[role="dialog"]');
    this.modalTitle = page.locator('[role="dialog"] h2');
    this.modalCloseButton = page.locator('[role="dialog"] button[aria-label*="close" i]');
    this.auditAction = page.locator('[role="dialog"] [class*="action"]');
    this.auditDetails = page.locator('[role="dialog"] [class*="details"], [role="dialog"] pre');

    // Pagination
    this.previousPageButton = page.getByRole('button', { name: /Previous/i });
    this.nextPageButton = page.getByRole('button', { name: /Next/i });
    this.pageInfo = page.getByText(/Page \d+ of \d+/i);

    // Loading/Error States
    this.loadingSpinner = page.locator('.animate-spin');
    this.errorMessage = page.getByText(/Failed to load audit logs/i);
  }

  /**
   * Navigate to the Audit page
   */
  async goto(): Promise<void> {
    await this.page.goto('/audit');
  }

  /**
   * Wait for the audit page to fully load
   */
  async waitForAuditLoad(): Promise<void> {
    await expect(this.pageTitle).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Filter by action type
   */
  async filterByAction(action: string): Promise<void> {
    await this.actionFilter.selectOption(action);
  }

  /**
   * Filter by resource type
   */
  async filterByResourceType(resourceType: string): Promise<void> {
    await this.resourceTypeFilter.selectOption(resourceType);
  }

  /**
   * Filter by actor
   */
  async filterByActor(actor: string): Promise<void> {
    await this.actorFilter.selectOption(actor);
  }

  /**
   * Filter by status
   */
  async filterByStatus(status: 'success' | 'failed'): Promise<void> {
    await this.statusFilter.selectOption(status);
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
   * Get count of displayed audit rows
   */
  async getAuditRowCount(): Promise<number> {
    return this.tableRows.count();
  }

  /**
   * Click on an audit row to open detail modal
   */
  async clickAuditRow(index: number = 0): Promise<void> {
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
   */
  async hasEmptyState(): Promise<boolean> {
    return this.emptyState.isVisible().catch(() => false);
  }

  /**
   * Check if error state is shown
   */
  async hasError(): Promise<boolean> {
    return this.errorMessage.isVisible().catch(() => false);
  }
}
