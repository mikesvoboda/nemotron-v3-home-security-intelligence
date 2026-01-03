/**
 * ZonesPage - Page Object for Zone Management
 *
 * Provides selectors and interactions for:
 * - Opening zone editor from camera settings
 * - Drawing zones (rectangle and polygon)
 * - Editing zone properties
 * - Deleting zones with confirmation
 * - Toggling zone visibility
 */

import type { Page, Locator } from '@playwright/test';
import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class ZonesPage extends BasePage {
  // Zone Editor Modal
  readonly zoneEditorModal: Locator;
  readonly zoneEditorTitle: Locator;
  readonly zoneEditorCloseButton: Locator;

  // Drawing Toolbar
  readonly drawRectangleButton: Locator;
  readonly drawPolygonButton: Locator;
  readonly drawingModeIndicator: Locator;
  readonly cancelDrawingButton: Locator;

  // Zone Canvas
  readonly zoneCanvas: Locator;
  readonly zoneCanvasImage: Locator;

  // Zone List
  readonly zoneListHeader: Locator;
  readonly zoneListItems: Locator;
  readonly noZonesMessage: Locator;

  // Zone Form
  readonly zoneFormTitle: Locator;
  readonly zoneNameInput: Locator;
  readonly zoneTypeSelect: Locator;
  readonly zonePrioritySlider: Locator;
  readonly zoneEnabledToggle: Locator;
  readonly zoneFormSubmitButton: Locator;
  readonly zoneFormCancelButton: Locator;
  readonly zoneColorButtons: Locator;

  // Delete Confirmation
  readonly deleteConfirmation: Locator;
  readonly deleteConfirmButton: Locator;
  readonly deleteCancelButton: Locator;

  // Error Display
  readonly errorMessage: Locator;

  constructor(page: Page) {
    super(page);

    // Zone Editor Modal - use heading as primary indicator since dialog may have transitions
    this.zoneEditorTitle = page.getByRole('heading', { name: /Zone Configuration/i });
    this.zoneEditorModal = page.locator('[role="dialog"]').filter({ has: this.zoneEditorTitle });
    this.zoneEditorCloseButton = this.zoneEditorModal.locator('button').filter({ has: page.locator('svg.lucide-x') }).first();

    // Drawing Toolbar
    this.drawRectangleButton = page.getByRole('button', { name: /Rectangle/i });
    this.drawPolygonButton = page.getByRole('button', { name: /Polygon/i });
    // The UI shows "Drawing rectangle..." or "Drawing polygon..." in a badge
    this.drawingModeIndicator = page.getByText(/Drawing (rectangle|polygon)\.\.\./i);
    this.cancelDrawingButton = page.getByRole('button', { name: /Cancel/i }).filter({ hasNotText: 'Delete' });

    // Zone Canvas - label changes when in drawing mode
    this.zoneCanvas = page.getByLabel('Camera zones view')
      .or(page.getByLabel('Zone drawing canvas - click and drag to draw'));
    this.zoneCanvasImage = page.locator('img[alt="Camera snapshot"]');

    // Zone List
    this.zoneListHeader = page.getByRole('heading', { name: /Zones \(/i });
    this.zoneListItems = page.locator('[role="button"][aria-pressed]');
    this.noZonesMessage = page.getByText(/No zones defined/i);

    // Zone Form
    this.zoneFormTitle = page.getByRole('heading', { name: /New Zone|Edit Zone/i });
    this.zoneNameInput = page.getByLabel(/Zone Name/i);
    this.zoneTypeSelect = page.getByLabel(/Zone Type/i);
    this.zonePrioritySlider = page.getByLabel(/Priority/i);
    this.zoneEnabledToggle = page.getByRole('switch', { name: /Enabled/i });
    this.zoneFormSubmitButton = page.getByRole('button', { name: /Create Zone|Update Zone/i });
    this.zoneFormCancelButton = page.getByRole('button', { name: /^Cancel$/i });
    this.zoneColorButtons = page.locator('button[style*="background-color"]');

    // Delete Confirmation
    this.deleteConfirmation = page.getByText(/Delete zone.*This action cannot be undone/i);
    this.deleteConfirmButton = page.getByRole('button', { name: /^Delete$/i });
    this.deleteCancelButton = page.locator('button').filter({ hasText: /^Cancel$/ });

    // Error Display
    this.errorMessage = page.locator('.text-red-400, .text-red-500').filter({ hasText: /Failed|Error/i });
  }

  /**
   * Navigate to Settings page and open Cameras tab
   */
  async gotoSettings(): Promise<void> {
    await this.page.goto('/settings');
    await expect(this.page.getByRole('heading', { name: /Settings/i })).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Open zone editor for a specific camera
   */
  async openZoneEditor(cameraName: string): Promise<void> {
    // Find the camera row and click the zones button
    const cameraRow = this.page.locator('tr').filter({ hasText: cameraName });

    // Click the "Configure zones" button
    const zonesButton = cameraRow.getByRole('button', { name: new RegExp(`Configure zones for ${cameraName}`, 'i') });
    await zonesButton.click();

    // Wait for the dialog title to be visible (more reliable than dialog itself during transitions)
    await expect(this.zoneEditorTitle).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Wait for zone editor to be fully loaded
   */
  async waitForZoneEditorLoad(): Promise<void> {
    await expect(this.zoneEditorTitle).toBeVisible({ timeout: this.pageLoadTimeout });
    // Wait for zones list header to be visible (always shown even if empty)
    await expect(this.zoneListHeader).toBeVisible({ timeout: this.pageLoadTimeout });
  }

  /**
   * Close zone editor modal
   */
  async closeZoneEditor(): Promise<void> {
    await this.zoneEditorCloseButton.click();
    await expect(this.zoneEditorModal).not.toBeVisible();
  }

  /**
   * Start drawing a rectangle zone
   */
  async startDrawingRectangle(): Promise<void> {
    await this.drawRectangleButton.click();
    await expect(this.drawingModeIndicator).toBeVisible();
  }

  /**
   * Start drawing a polygon zone
   */
  async startDrawingPolygon(): Promise<void> {
    await this.drawPolygonButton.click();
    await expect(this.drawingModeIndicator).toBeVisible();
  }

  /**
   * Cancel drawing mode
   */
  async cancelDrawing(): Promise<void> {
    // Find the cancel button in the drawing mode indicator area
    const cancelInDrawingMode = this.page.locator('.bg-primary\\/10').getByText(/Cancel/i);
    await cancelInDrawingMode.click();
    await expect(this.drawingModeIndicator).not.toBeVisible();
  }

  /**
   * Draw a rectangle zone on the canvas
   * Coordinates are percentages (0-100) of the canvas dimensions
   */
  async drawRectangle(
    startX: number,
    startY: number,
    endX: number,
    endY: number
  ): Promise<void> {
    const canvas = this.zoneCanvas;
    const box = await canvas.boundingBox();
    if (!box) throw new Error('Canvas not found');

    const pixelStartX = box.x + (box.width * startX) / 100;
    const pixelStartY = box.y + (box.height * startY) / 100;
    const pixelEndX = box.x + (box.width * endX) / 100;
    const pixelEndY = box.y + (box.height * endY) / 100;

    await this.page.mouse.move(pixelStartX, pixelStartY);
    await this.page.mouse.down();
    await this.page.mouse.move(pixelEndX, pixelEndY);
    await this.page.mouse.up();
  }

  /**
   * Draw a polygon zone on the canvas by clicking points
   * Points are arrays of [x, y] percentages (0-100)
   */
  async drawPolygon(points: [number, number][]): Promise<void> {
    if (points.length < 3) throw new Error('Polygon needs at least 3 points');

    const canvas = this.zoneCanvas;
    const box = await canvas.boundingBox();
    if (!box) throw new Error('Canvas not found');

    // Click each point
    for (const [x, y] of points) {
      const pixelX = box.x + (box.width * x) / 100;
      const pixelY = box.y + (box.height * y) / 100;
      await this.page.mouse.click(pixelX, pixelY);
      // Small delay between clicks
      await this.page.waitForTimeout(100);
    }

    // Double-click to complete the polygon
    const lastPoint = points[points.length - 1];
    const lastX = box.x + (box.width * lastPoint[0]) / 100;
    const lastY = box.y + (box.height * lastPoint[1]) / 100;
    await this.page.mouse.dblclick(lastX, lastY);
  }

  /**
   * Fill zone form with data
   */
  async fillZoneForm(data: {
    name: string;
    type?: string;
    priority?: number;
    enabled?: boolean;
  }): Promise<void> {
    await this.zoneNameInput.fill(data.name);

    if (data.type) {
      await this.zoneTypeSelect.selectOption(data.type);
    }

    if (data.priority !== undefined) {
      await this.zonePrioritySlider.fill(String(data.priority));
    }

    if (data.enabled !== undefined) {
      const currentState = await this.zoneEnabledToggle.getAttribute('aria-checked');
      const isCurrentlyEnabled = currentState === 'true';
      if (isCurrentlyEnabled !== data.enabled) {
        await this.zoneEnabledToggle.click();
      }
    }
  }

  /**
   * Submit zone form
   */
  async submitZoneForm(): Promise<void> {
    await this.zoneFormSubmitButton.click();
  }

  /**
   * Cancel zone form
   */
  async cancelZoneForm(): Promise<void> {
    await this.zoneFormCancelButton.click();
  }

  /**
   * Get zone count from header
   */
  async getZoneCount(): Promise<number> {
    const headerText = await this.zoneListHeader.textContent();
    if (!headerText) return 0;
    const match = headerText.match(/Zones \((\d+)\)/);
    return match ? parseInt(match[1], 10) : 0;
  }

  /**
   * Select a zone from the list by name
   */
  async selectZone(zoneName: string): Promise<void> {
    const zoneItem = this.page.locator('[role="button"]').filter({ hasText: zoneName });
    await zoneItem.click();
  }

  /**
   * Click edit button for a zone
   */
  async clickEditZone(zoneName: string): Promise<void> {
    const zoneItem = this.page.locator('[role="button"]').filter({ hasText: zoneName });
    const editButton = zoneItem.locator('button[title="Edit zone"]');
    await editButton.click();
  }

  /**
   * Click delete button for a zone
   */
  async clickDeleteZone(zoneName: string): Promise<void> {
    const zoneItem = this.page.locator('[role="button"]').filter({ hasText: zoneName });
    const deleteButton = zoneItem.locator('button[title="Delete zone"]');
    await deleteButton.click();
  }

  /**
   * Toggle zone enabled state
   */
  async toggleZoneEnabled(zoneName: string): Promise<void> {
    const zoneItem = this.page.locator('[role="button"]').filter({ hasText: zoneName });
    const toggleButton = zoneItem.locator('button[title*="zone"]').filter({ has: this.page.locator('svg.lucide-eye, svg.lucide-eye-off') });
    await toggleButton.click();
  }

  /**
   * Confirm zone deletion
   */
  async confirmDelete(): Promise<void> {
    await expect(this.deleteConfirmation).toBeVisible();
    await this.deleteConfirmButton.click();
  }

  /**
   * Cancel zone deletion
   */
  async cancelDelete(): Promise<void> {
    await expect(this.deleteConfirmation).toBeVisible();
    // Find the cancel button in the delete confirmation area
    const cancelButton = this.page.locator('.bg-red-500\\/5').getByRole('button', { name: /Cancel/i });
    await cancelButton.click();
  }

  /**
   * Check if a zone exists in the list
   */
  async hasZone(zoneName: string): Promise<boolean> {
    const zoneItem = this.page.locator('[role="button"]').filter({ hasText: zoneName });
    return zoneItem.isVisible().catch(() => false);
  }

  /**
   * Check if zone is enabled (has Eye icon, not EyeOff)
   */
  async isZoneEnabled(zoneName: string): Promise<boolean> {
    const zoneItem = this.page.locator('[role="button"]').filter({ hasText: zoneName });
    const eyeIcon = zoneItem.locator('svg.lucide-eye');
    return eyeIcon.isVisible().catch(() => false);
  }

  /**
   * Check if zone has disabled badge
   */
  async hasDisabledBadge(zoneName: string): Promise<boolean> {
    const zoneItem = this.page.locator('[role="button"]').filter({ hasText: zoneName });
    const disabledBadge = zoneItem.getByText('Disabled');
    return disabledBadge.isVisible().catch(() => false);
  }

  /**
   * Select a color in the form
   */
  async selectColor(colorHex: string): Promise<void> {
    const colorButton = this.page.locator(`button[style*="background-color: ${colorHex}"]`)
      .or(this.page.locator(`button[style*="background-color:${colorHex}"]`));
    await colorButton.click();
  }

  /**
   * Get zone type badge text
   */
  async getZoneType(zoneName: string): Promise<string | null> {
    const zoneItem = this.page.locator('[role="button"]').filter({ hasText: zoneName });
    const typeBadge = zoneItem.locator('.rounded.px-1\\.5.py-0\\.5.text-xs').first();
    return typeBadge.textContent();
  }

  /**
   * Press Escape key to cancel drawing
   */
  async pressEscapeToCancel(): Promise<void> {
    await this.page.keyboard.press('Escape');
  }
}
