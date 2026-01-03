/**
 * ZonesPage - Page Object for Zone management
 *
 * Provides selectors and interactions for zone management UI:
 * - Zone list display
 * - Zone creation/editing forms
 * - Zone polygon drawing on canvas
 * - Zone visibility toggles
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class ZonesPage extends BasePage {
  // Page elements
  readonly pageTitle: Locator;
  readonly zonesSection: Locator;

  // Camera selector for zones
  readonly cameraSelector: Locator;
  readonly selectedCameraName: Locator;

  // Zone list
  readonly zonesList: Locator;
  readonly zoneCards: Locator;
  readonly emptyZonesMessage: Locator;

  // Zone creation
  readonly addZoneButton: Locator;
  readonly zoneFormModal: Locator;
  readonly zoneNameInput: Locator;
  readonly zoneTypeSelect: Locator;
  readonly zoneColorPicker: Locator;
  readonly zonePriorityInput: Locator;
  readonly zoneEnabledToggle: Locator;
  readonly saveZoneButton: Locator;
  readonly cancelZoneButton: Locator;

  // Zone drawing canvas
  readonly zoneCanvas: Locator;
  readonly drawPolygonButton: Locator;
  readonly drawRectangleButton: Locator;
  readonly clearDrawingButton: Locator;

  // Zone actions
  readonly editZoneButton: Locator;
  readonly deleteZoneButton: Locator;
  readonly toggleZoneButton: Locator;

  // Confirmation modal
  readonly deleteConfirmModal: Locator;
  readonly confirmDeleteButton: Locator;
  readonly cancelDeleteButton: Locator;

  // Error/success messages
  readonly errorMessage: Locator;
  readonly successMessage: Locator;

  // Zone overlap warning
  readonly overlapWarning: Locator;

  constructor(page: Page) {
    super(page);

    // Page elements
    this.pageTitle = page.getByRole('heading', { name: /Zones/i }).first();
    this.zonesSection = page.locator('[data-testid="zones-section"]');

    // Camera selector
    this.cameraSelector = page.locator('[data-testid="camera-selector"]');
    this.selectedCameraName = page.locator('[data-testid="selected-camera-name"]');

    // Zone list
    this.zonesList = page.locator('[data-testid="zones-list"]');
    this.zoneCards = page.locator('[data-testid^="zone-card-"]');
    this.emptyZonesMessage = page.getByText(/No zones defined/i);

    // Zone creation
    this.addZoneButton = page.getByRole('button', { name: /Add Zone/i });
    this.zoneFormModal = page.locator('[data-testid="zone-form-modal"]');
    this.zoneNameInput = page.getByLabel(/Zone Name/i);
    this.zoneTypeSelect = page.getByLabel(/Zone Type/i);
    this.zoneColorPicker = page.locator('[data-testid="zone-color-picker"]');
    this.zonePriorityInput = page.getByLabel(/Priority/i);
    this.zoneEnabledToggle = page.getByLabel(/Enabled/i);
    this.saveZoneButton = page.getByRole('button', { name: /Save Zone/i });
    this.cancelZoneButton = page.getByRole('button', { name: /Cancel/i });

    // Zone drawing canvas
    this.zoneCanvas = page.locator('[data-testid="zone-canvas"]');
    this.drawPolygonButton = page.getByRole('button', { name: /Draw Polygon/i });
    this.drawRectangleButton = page.getByRole('button', { name: /Draw Rectangle/i });
    this.clearDrawingButton = page.getByRole('button', { name: /Clear/i });

    // Zone actions
    this.editZoneButton = page.getByRole('button', { name: /Edit/i });
    this.deleteZoneButton = page.getByRole('button', { name: /Delete/i });
    this.toggleZoneButton = page.locator('[data-testid="zone-toggle"]');

    // Confirmation modal
    this.deleteConfirmModal = page.locator('[data-testid="delete-confirm-modal"]');
    this.confirmDeleteButton = page.getByRole('button', { name: /Confirm Delete/i });
    this.cancelDeleteButton = page.getByRole('button', { name: /Cancel/i }).last();

    // Messages
    this.errorMessage = page.locator('[data-testid="zone-error"]');
    this.successMessage = page.locator('[data-testid="zone-success"]');

    // Overlap warning
    this.overlapWarning = page.getByText(/overlaps with/i);
  }

  /**
   * Navigate to zones management page (via settings or dedicated route)
   */
  async goto(): Promise<void> {
    await this.page.goto('/settings');
  }

  /**
   * Navigate to zones tab if in settings page
   */
  async goToZonesTab(): Promise<void> {
    const zonesTab = this.page.locator('button').filter({ hasText: /ZONES/i });
    await zonesTab.click();
  }

  /**
   * Wait for zones to load
   */
  async waitForZonesLoad(): Promise<void> {
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Select a camera to manage zones for
   */
  async selectCamera(cameraName: string): Promise<void> {
    await this.cameraSelector.click();
    await this.page.getByRole('option', { name: cameraName }).click();
  }

  /**
   * Get all zone card names
   */
  async getZoneNames(): Promise<string[]> {
    const cards = await this.zoneCards.all();
    const names: string[] = [];
    for (const card of cards) {
      const name = await card.locator('[data-testid="zone-name"]').textContent();
      if (name) names.push(name);
    }
    return names;
  }

  /**
   * Get zone count
   */
  async getZoneCount(): Promise<number> {
    return this.zoneCards.count();
  }

  /**
   * Click add zone button to open form
   */
  async clickAddZone(): Promise<void> {
    await this.addZoneButton.click();
  }

  /**
   * Fill zone creation form
   */
  async fillZoneForm(data: {
    name: string;
    zoneType?: string;
    color?: string;
    priority?: number;
    enabled?: boolean;
  }): Promise<void> {
    await this.zoneNameInput.fill(data.name);

    if (data.zoneType) {
      await this.zoneTypeSelect.selectOption(data.zoneType);
    }

    if (data.priority !== undefined) {
      await this.zonePriorityInput.fill(String(data.priority));
    }

    if (data.enabled !== undefined && !data.enabled) {
      // Toggle off if enabled is false
      await this.zoneEnabledToggle.click();
    }
  }

  /**
   * Save zone form
   */
  async saveZone(): Promise<void> {
    await this.saveZoneButton.click();
  }

  /**
   * Cancel zone form
   */
  async cancelZoneForm(): Promise<void> {
    await this.cancelZoneButton.click();
  }

  /**
   * Click on a zone card to select it
   */
  async selectZone(zoneName: string): Promise<void> {
    await this.page.locator('[data-testid^="zone-card-"]').filter({ hasText: zoneName }).click();
  }

  /**
   * Click edit on a specific zone
   */
  async clickEditZone(zoneName: string): Promise<void> {
    const card = this.page.locator('[data-testid^="zone-card-"]').filter({ hasText: zoneName });
    await card.getByRole('button', { name: /Edit/i }).click();
  }

  /**
   * Click delete on a specific zone
   */
  async clickDeleteZone(zoneName: string): Promise<void> {
    const card = this.page.locator('[data-testid^="zone-card-"]').filter({ hasText: zoneName });
    await card.getByRole('button', { name: /Delete/i }).click();
  }

  /**
   * Confirm zone deletion
   */
  async confirmDelete(): Promise<void> {
    await this.confirmDeleteButton.click();
  }

  /**
   * Cancel zone deletion
   */
  async cancelDelete(): Promise<void> {
    await this.cancelDeleteButton.click();
  }

  /**
   * Toggle zone enabled/disabled
   */
  async toggleZone(zoneName: string): Promise<void> {
    const card = this.page.locator('[data-testid^="zone-card-"]').filter({ hasText: zoneName });
    await card.locator('[data-testid="zone-toggle"]').click();
  }

  /**
   * Check if a zone is enabled
   */
  async isZoneEnabled(zoneName: string): Promise<boolean> {
    const card = this.page.locator('[data-testid^="zone-card-"]').filter({ hasText: zoneName });
    const toggle = card.locator('[data-testid="zone-toggle"]');
    const checked = await toggle.getAttribute('aria-checked');
    return checked === 'true';
  }

  /**
   * Draw a rectangle on the canvas
   * @param startX - Starting X coordinate (normalized 0-1)
   * @param startY - Starting Y coordinate (normalized 0-1)
   * @param endX - Ending X coordinate (normalized 0-1)
   * @param endY - Ending Y coordinate (normalized 0-1)
   */
  async drawRectangle(startX: number, startY: number, endX: number, endY: number): Promise<void> {
    await this.drawRectangleButton.click();

    const canvas = this.zoneCanvas;
    const box = await canvas.boundingBox();

    if (box) {
      const x1 = box.x + box.width * startX;
      const y1 = box.y + box.height * startY;
      const x2 = box.x + box.width * endX;
      const y2 = box.y + box.height * endY;

      await this.page.mouse.click(x1, y1);
      await this.page.mouse.click(x2, y2);
    }
  }

  /**
   * Draw a polygon on the canvas
   * @param points - Array of [x, y] coordinates (normalized 0-1)
   */
  async drawPolygon(points: [number, number][]): Promise<void> {
    await this.drawPolygonButton.click();

    const canvas = this.zoneCanvas;
    const box = await canvas.boundingBox();

    if (box) {
      for (const [x, y] of points) {
        const absX = box.x + box.width * x;
        const absY = box.y + box.height * y;
        await this.page.mouse.click(absX, absY);
      }
      // Double-click to finish polygon
      const [lastX, lastY] = points[points.length - 1];
      const absLastX = box.x + box.width * lastX;
      const absLastY = box.y + box.height * lastY;
      await this.page.mouse.dblclick(absLastX, absLastY);
    }
  }

  /**
   * Clear the current drawing
   */
  async clearDrawing(): Promise<void> {
    await this.clearDrawingButton.click();
  }

  /**
   * Check if success message is shown
   */
  async hasSuccessMessage(): Promise<boolean> {
    return this.successMessage.isVisible().catch(() => false);
  }

  /**
   * Check if error message is shown
   */
  async hasErrorMessage(): Promise<boolean> {
    return this.errorMessage.isVisible().catch(() => false);
  }

  /**
   * Check if overlap warning is shown
   */
  async hasOverlapWarning(): Promise<boolean> {
    return this.overlapWarning.isVisible().catch(() => false);
  }

  /**
   * Get zone by name locator
   */
  getZoneCard(zoneName: string): Locator {
    return this.page.locator('[data-testid^="zone-card-"]').filter({ hasText: zoneName });
  }

  /**
   * Check if a specific zone exists
   */
  async hasZone(zoneName: string): Promise<boolean> {
    const card = this.getZoneCard(zoneName);
    return card.isVisible().catch(() => false);
  }
}
