/**
 * TrashPage - Page Object for the Trash/Deleted Events Page
 *
 * Provides selectors and interactions for:
 * - Viewing soft-deleted events
 * - Restoring events
 * - Permanently deleting events (with confirmation)
 * - Search and filter functionality
 * - Empty state handling
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class TrashPage extends BasePage {
  // Page heading
  readonly pageTitle: Locator;
  readonly pageSubtitle: Locator;

  // Info notice
  readonly autoCleanupNotice: Locator;

  // Event count
  readonly eventsCount: Locator;

  // Deleted event cards
  readonly deletedEventCards: Locator;

  // Empty state
  readonly emptyStateIcon: Locator;
  readonly emptyStateTitle: Locator;
  readonly emptyStateDescription: Locator;

  // Error states
  readonly errorMessage: Locator;
  readonly tryAgainButton: Locator;
  readonly mutationErrorMessage: Locator;

  // Loading state
  readonly loadingSpinner: Locator;

  constructor(page: Page) {
    super(page);

    // Page heading
    this.pageTitle = page.getByRole('heading', { name: /^Trash$/i });
    this.pageSubtitle = page.getByText(/Review and manage deleted events/i);

    // Info notice
    this.autoCleanupNotice = page.getByText(/Events in trash are automatically deleted after 30 days/i);

    // Event count
    this.eventsCount = page.getByText(/\d+ events? in trash/i);

    // Deleted event cards (using data-testid from DeletedEventCard component)
    this.deletedEventCards = page.locator('[data-testid^="deleted-event-card-"]');

    // Empty state
    this.emptyStateIcon = page.locator('svg').filter({ has: page.locator('title', { hasText: /trash/i }) });
    this.emptyStateTitle = page.getByText(/Trash is empty/i);
    this.emptyStateDescription = page.getByText(/Deleted events will appear here/i);

    // Error states
    this.errorMessage = page.getByText(/Failed to load deleted events/i);
    this.tryAgainButton = page.getByRole('button', { name: /Try Again/i });
    this.mutationErrorMessage = page.getByText(/Action failed/i);

    // Loading state
    this.loadingSpinner = page.locator('.animate-spin');
  }

  /**
   * Navigate to the Trash page
   */
  async goto(): Promise<void> {
    await this.page.goto('/trash');
  }

  /**
   * Wait for the trash page to fully load (including data)
   */
  async waitForTrashLoad(): Promise<void> {
    // Wait for page to be in network idle state first
    await this.page.waitForLoadState('networkidle').catch(() => {
      // Continue if network idle times out
    });

    // Increased timeout for CI environments where rendering may be slower
    await expect(this.pageTitle).toBeVisible({ timeout: 15000 });

    // Wait for either deleted events to load OR empty state OR error state
    await Promise.race([
      this.deletedEventCards.first().waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
      this.emptyStateTitle.waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
      this.errorMessage.waitFor({ state: 'visible', timeout: this.pageLoadTimeout }),
    ]).catch(() => {
      // One of them should appear, but if none do within timeout, continue anyway
    });
  }

  /**
   * Get count of deleted events
   */
  async getDeletedEventCount(): Promise<number> {
    return this.deletedEventCards.count();
  }

  /**
   * Check if empty state is shown
   */
  async hasEmptyState(): Promise<boolean> {
    return this.emptyStateTitle.isVisible().catch(() => false);
  }

  /**
   * Check if error message is shown
   */
  async hasErrorMessage(): Promise<boolean> {
    return this.errorMessage.isVisible().catch(() => false);
  }

  /**
   * Get a specific deleted event card by index
   */
  getDeletedEventCard(index: number = 0): Locator {
    return this.deletedEventCards.nth(index);
  }

  /**
   * Get the restore button for a specific deleted event
   */
  getRestoreButton(index: number = 0): Locator {
    return this.getDeletedEventCard(index).getByRole('button', { name: /Restore/i });
  }

  /**
   * Get the delete forever button for a specific deleted event
   */
  getDeleteForeverButton(index: number = 0): Locator {
    return this.getDeletedEventCard(index).getByRole('button', { name: /Delete Forever/i });
  }

  /**
   * Get the confirmation dialog for permanent delete
   */
  getConfirmDialog(): Locator {
    return this.page.locator('[role="dialog"][aria-modal="true"]');
  }

  /**
   * Get the cancel button in the confirmation dialog
   */
  getConfirmDialogCancelButton(): Locator {
    return this.getConfirmDialog().getByRole('button', { name: /Cancel/i });
  }

  /**
   * Get the confirm delete button in the confirmation dialog
   */
  getConfirmDialogDeleteButton(): Locator {
    return this.getConfirmDialog().getByRole('button', { name: /Delete Forever/i });
  }

  /**
   * Restore a deleted event by index
   */
  async restoreEvent(index: number = 0): Promise<void> {
    await this.getRestoreButton(index).click();
  }

  /**
   * Click delete forever button (opens confirmation dialog)
   */
  async clickDeleteForever(index: number = 0): Promise<void> {
    await this.getDeleteForeverButton(index).click();
  }

  /**
   * Confirm permanent deletion in the dialog
   */
  async confirmPermanentDelete(): Promise<void> {
    await this.getConfirmDialogDeleteButton().click();
  }

  /**
   * Cancel permanent deletion in the dialog
   */
  async cancelPermanentDelete(): Promise<void> {
    await this.getConfirmDialogCancelButton().click();
  }

  /**
   * Permanently delete an event (click delete forever + confirm)
   */
  async permanentlyDeleteEvent(index: number = 0): Promise<void> {
    await this.clickDeleteForever(index);
    await expect(this.getConfirmDialog()).toBeVisible();
    await this.confirmPermanentDelete();
  }

  /**
   * Check if confirmation dialog is visible
   */
  async isConfirmDialogVisible(): Promise<boolean> {
    return this.getConfirmDialog().isVisible().catch(() => false);
  }

  /**
   * Check if auto-cleanup notice is visible
   */
  async hasAutoCleanupNotice(): Promise<boolean> {
    return this.autoCleanupNotice.isVisible().catch(() => false);
  }

  /**
   * Click the Try Again button (on error state)
   */
  async clickTryAgain(): Promise<void> {
    await this.tryAgainButton.click();
  }

  /**
   * Get the deleted timestamp text for a specific event
   */
  async getDeletedTimestamp(index: number = 0): Promise<string> {
    const card = this.getDeletedEventCard(index);
    // Match "Deleted X ago" or "Deleted Just now"
    const timestampLocator = card.getByText(/Deleted (?:.+)/i);
    return timestampLocator.innerText();
  }

  /**
   * Get the camera name for a specific deleted event
   */
  async getCameraName(index: number = 0): Promise<string> {
    const card = this.getDeletedEventCard(index);
    // Camera name is in an h3 element
    const cameraLocator = card.locator('h3').first();
    return cameraLocator.innerText();
  }

  /**
   * Check if a restore operation is in progress (button shows loading state)
   */
  async isRestoreInProgress(index: number = 0): Promise<boolean> {
    const restoreButton = this.getRestoreButton(index);
    // Check if button is disabled or has loading spinner
    const isDisabled = await restoreButton.isDisabled().catch(() => false);
    const hasSpinner = await restoreButton.locator('.animate-spin').isVisible().catch(() => false);
    return isDisabled || hasSpinner;
  }

  /**
   * Check if a delete operation is in progress
   */
  async isDeleteInProgress(index: number = 0): Promise<boolean> {
    const deleteButton = this.getConfirmDialogDeleteButton();
    const isDisabled = await deleteButton.isDisabled().catch(() => false);
    const hasSpinner = await deleteButton.locator('.animate-spin').isVisible().catch(() => false);
    return isDisabled || hasSpinner;
  }
}
