/**
 * ZonesPage - Page Object for Zone management
 *
 * Provides selectors and interactions for:
 * - Zone list display
 * - Zone CRUD operations
 * - Zone visibility toggle
 */

import type { Locator, Page } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class ZonesPage extends BasePage {
  // Zone list
  readonly zoneList: Locator;
  readonly zoneItems: Locator;
  readonly emptyState: Locator;
  readonly addZoneButton: Locator;

  // Zone item elements
  readonly zoneEditButton: Locator;
  readonly zoneDeleteButton: Locator;
  readonly zoneVisibilityToggle: Locator;
  readonly zoneTypeBadge: Locator;

  // Zone form/editor
  readonly zoneNameInput: Locator;
  readonly zoneTypeSelect: Locator;
  readonly zoneSaveButton: Locator;
  readonly zoneCancelButton: Locator;

  // Delete confirmation
  readonly deleteConfirmDialog: Locator;
  readonly deleteConfirmButton: Locator;
  readonly deleteCancelButton: Locator;

  // Messages
  readonly successMessage: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Zone list
    this.zoneList = page.locator('[data-testid="zone-list"]');
    this.zoneItems = page.locator('[data-testid^="zone-item-"]');
    this.emptyState = page.getByText(/No zones defined/i);
    this.addZoneButton = page.getByRole('button', { name: /Add Zone|Create Zone/i });

    // Zone item elements
    this.zoneEditButton = page.locator('[data-testid="zone-edit"]');
    this.zoneDeleteButton = page.locator('[data-testid="zone-delete"]');
    this.zoneVisibilityToggle = page.locator('[data-testid="zone-visibility-toggle"]');
    this.zoneTypeBadge = page.locator('[data-testid="zone-type-badge"]');

    // Zone form/editor
    this.zoneNameInput = page.getByLabel(/Zone Name|Name/i);
    this.zoneTypeSelect = page.getByLabel(/Zone Type|Type/i);
    this.zoneSaveButton = page.getByRole('button', { name: /Save/i });
    this.zoneCancelButton = page.getByRole('button', { name: /Cancel/i });

    // Delete confirmation
    this.deleteConfirmDialog = page.locator('[role="dialog"]');
    this.deleteConfirmButton = page.getByRole('button', { name: /Delete|Confirm/i });
    this.deleteCancelButton = page.getByRole('button', { name: /Cancel/i });

    // Messages
    this.successMessage = page.getByText(/saved|created|deleted|updated/i);
    this.errorMessage = page.getByText(/error|failed/i);
  }

  /**
   * Navigate to zones settings
   */
  async goto(): Promise<void> {
    await this.page.goto('/settings');
    // Click on Zones tab if it exists, otherwise zones may be in cameras settings
    const zonesTab = this.page.getByRole('tab', { name: /Zones/i });
    if (await zonesTab.isVisible().catch(() => false)) {
      await zonesTab.click();
    }
  }

  /**
   * Wait for zone list to load
   */
  async waitForZonesLoad(): Promise<void> {
    // Wait for either zone list or empty state
    await expect(this.zoneList.or(this.emptyState)).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Get count of zones in the list
   */
  async getZoneCount(): Promise<number> {
    return this.zoneItems.count();
  }

  /**
   * Check if zones list is empty
   */
  async isEmpty(): Promise<boolean> {
    return this.emptyState.isVisible().catch(() => false);
  }

  /**
   * Click edit button on a zone by index
   */
  async clickEditZone(index: number): Promise<void> {
    await this.zoneItems.nth(index).locator('[data-testid="zone-edit"]').click();
  }

  /**
   * Click delete button on a zone by index
   */
  async clickDeleteZone(index: number): Promise<void> {
    await this.zoneItems.nth(index).locator('[data-testid="zone-delete"]').click();
  }

  /**
   * Toggle visibility of a zone by index
   */
  async toggleZoneVisibility(index: number): Promise<void> {
    await this.zoneItems.nth(index).locator('button').filter({ hasText: '' }).first().click();
  }

  /**
   * Confirm deletion in dialog
   */
  async confirmDelete(): Promise<void> {
    await this.deleteConfirmButton.click();
  }

  /**
   * Cancel deletion in dialog
   */
  async cancelDelete(): Promise<void> {
    await this.deleteCancelButton.click();
  }

  /**
   * Check if success message is displayed
   */
  async hasSuccessMessage(): Promise<boolean> {
    return this.successMessage.isVisible().catch(() => false);
  }

  /**
   * Check if error message is displayed
   */
  async hasErrorMessage(): Promise<boolean> {
    return this.errorMessage.isVisible().catch(() => false);
  }

  /**
   * Get zone name by index
   */
  async getZoneName(index: number): Promise<string | null> {
    return this.zoneItems.nth(index).locator('[data-testid="zone-name"]').textContent();
  }

  /**
   * Get zone type badge text by index
   */
  async getZoneType(index: number): Promise<string | null> {
    return this.zoneItems.nth(index).locator('[data-testid="zone-type-badge"]').textContent();
  }
}
