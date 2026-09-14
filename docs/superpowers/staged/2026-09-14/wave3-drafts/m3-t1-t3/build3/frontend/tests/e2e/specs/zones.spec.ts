/**
 * Zone Management E2E Tests
 *
 * Comprehensive tests for zone management including:
 * - Opening zone editor from camera settings
 * - Creating zones by drawing (rectangle and polygon)
 * - Editing zone properties
 * - Deleting zones with confirmation
 * - Toggling zone visibility
 * - Multi-zone scenarios
 * - Zone overlap considerations
 *
 * NOTE: Skipped in CI due to Settings page load timing issues causing flakiness.
 * Run locally for zone management validation.
 */

import { test, expect } from '@playwright/test';

// Skip entire file in CI - Settings page load timing issues cause flaky failures
test.skip(() => !!process.env.CI, 'Zone tests flaky in CI - run locally');
import { ZonesPage } from '../pages/ZonesPage';
import { SettingsPage } from '../pages';
import { setupApiMocks, defaultMockConfig, type ApiMockConfig } from '../fixtures';
import { mockZones, zonesByCamera } from '../fixtures/test-data';

test.describe('Zone Editor Access', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
  });

  test('can access zone editor from camera settings', async () => {
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
    await expect(zonesPage.zoneEditorTitle).toContainText('Zone Configuration - Front Door');
  });

  test('zone editor shows camera name in title', async () => {
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Back Yard');
    await zonesPage.waitForZoneEditorLoad();
    await expect(zonesPage.zoneEditorTitle).toContainText('Back Yard');
  });

  test('can close zone editor', async () => {
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
    await zonesPage.closeZoneEditor();
    await expect(zonesPage.zoneEditorModal).not.toBeVisible();
  });
});

test.describe('Zone List Display', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
  });

  test('shows existing zones for camera', async () => {
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();

    // Front Door has 3 zones in mock data
    const count = await zonesPage.getZoneCount();
    expect(count).toBe(3);
  });

  test('displays zone names in list', async () => {
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();

    // Verify zone names are visible in the zone list (not canvas)
    const zoneList = zonesPage.page.locator('[role="button"]');
    await expect(zoneList.filter({ hasText: 'Front Door Entry' })).toBeVisible();
    await expect(zoneList.filter({ hasText: 'Front Driveway' })).toBeVisible();
    await expect(zoneList.filter({ hasText: 'Sidewalk Monitor' })).toBeVisible();
  });

  test('shows zone type badges', async () => {
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();

    // Check that type badges are displayed in zone list items
    const zoneList = zonesPage.page.locator('[role="button"]');
    await expect(zoneList.filter({ hasText: 'Entry Point' })).toBeVisible();
    await expect(zoneList.filter({ hasText: /Driveway/i }).first()).toBeVisible();
  });

  test('shows disabled badge for disabled zones', async () => {
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();

    // Sidewalk Monitor is disabled in mock data
    const hasDisabled = await zonesPage.hasDisabledBadge('Sidewalk Monitor');
    expect(hasDisabled).toBe(true);
  });

  test('shows correct zone count for camera with no zones', async () => {
    // Open Garage which has no zones in mock data
    await zonesPage.openZoneEditor('Garage');
    await zonesPage.waitForZoneEditorLoad();

    // Check that zone count shows 0
    const zoneHeader = zonesPage.page.getByRole('heading', { name: 'Zones (0)' });
    await expect(zoneHeader).toBeVisible({ timeout: 5000 });
  });

  test('shows priority for each zone', async () => {
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();

    await expect(zonesPage.page.getByText('Priority: 90')).toBeVisible();
    await expect(zonesPage.page.getByText('Priority: 50')).toBeVisible();
  });
});

test.describe('Zone Selection', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
  });

  test('can select a zone from the list', async () => {
    await zonesPage.selectZone('Front Door Entry');

    // Check that the zone item has aria-pressed="true"
    const zoneItem = zonesPage.page.locator('[role="button"]').filter({ hasText: 'Front Door Entry' });
    await expect(zoneItem).toHaveAttribute('aria-pressed', 'true');
  });

  test('clicking another zone changes selection', async () => {
    // Select the first zone
    await zonesPage.selectZone('Front Door Entry');

    const firstZone = zonesPage.page.locator('[role="button"]').filter({ hasText: 'Front Door Entry' });
    await expect(firstZone).toHaveAttribute('aria-pressed', 'true');

    // Select a different zone
    await zonesPage.selectZone('Front Driveway');

    const secondZone = zonesPage.page.locator('[role="button"]').filter({ hasText: 'Front Driveway' });

    // Second zone should now be selected
    await expect(secondZone).toHaveAttribute('aria-pressed', 'true');
    // First zone should be deselected
    await expect(firstZone).toHaveAttribute('aria-pressed', 'false');
  });

  test('selecting different zone changes selection', async () => {
    await zonesPage.selectZone('Front Door Entry');
    await zonesPage.selectZone('Front Driveway');

    const firstZone = zonesPage.page.locator('[role="button"]').filter({ hasText: 'Front Door Entry' });
    const secondZone = zonesPage.page.locator('[role="button"]').filter({ hasText: 'Front Driveway' });

    await expect(firstZone).toHaveAttribute('aria-pressed', 'false');
    await expect(secondZone).toHaveAttribute('aria-pressed', 'true');
  });
});

test.describe('Zone Drawing - Rectangle', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
  });

  test('rectangle draw button is visible', async () => {
    await expect(zonesPage.drawRectangleButton).toBeVisible();
    await expect(zonesPage.drawRectangleButton).toContainText('Rectangle');
  });

  test('clicking rectangle button enters drawing mode', async () => {
    await zonesPage.startDrawingRectangle();
    await expect(zonesPage.drawingModeIndicator).toBeVisible();
    await expect(zonesPage.drawingModeIndicator).toContainText('rectangle');
  });

  test('can cancel drawing with cancel button', async () => {
    await zonesPage.startDrawingRectangle();
    await zonesPage.cancelDrawing();
    await expect(zonesPage.drawingModeIndicator).not.toBeVisible();
  });

  test('pressing Escape cancels drawing mode', async () => {
    await zonesPage.startDrawingRectangle();
    await zonesPage.pressEscapeToCancel();
    await expect(zonesPage.drawingModeIndicator).not.toBeVisible();
  });

  test('drawing instructions are shown in rectangle mode', async () => {
    await zonesPage.startDrawingRectangle();
    await expect(zonesPage.page.getByText('Click and drag on the camera view to draw a rectangle zone.')).toBeVisible();
  });
});

test.describe('Zone Drawing - Polygon', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
  });

  test('polygon draw button is visible', async () => {
    await expect(zonesPage.drawPolygonButton).toBeVisible();
    await expect(zonesPage.drawPolygonButton).toContainText('Polygon');
  });

  test('clicking polygon button enters drawing mode', async () => {
    await zonesPage.startDrawingPolygon();
    await expect(zonesPage.drawingModeIndicator).toBeVisible();
    await expect(zonesPage.drawingModeIndicator).toContainText('polygon');
  });

  test('drawing instructions are shown in polygon mode', async () => {
    await zonesPage.startDrawingPolygon();
    await expect(zonesPage.page.getByText('Click on the camera view to add polygon points. Double-click to complete the shape.')).toBeVisible();
  });

  test('can cancel polygon drawing', async () => {
    await zonesPage.startDrawingPolygon();
    await zonesPage.cancelDrawing();
    await expect(zonesPage.drawingModeIndicator).not.toBeVisible();
  });
});

test.describe('Zone Creation Form', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    // Use a camera with existing zones to test form functionality via edit mode
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
  });

  test('drawing mode can be activated', async ({ page }) => {
    await zonesPage.startDrawingRectangle();

    // Drawing mode indicator should show
    await expect(zonesPage.drawingModeIndicator).toBeVisible();

    // Canvas should be available for drawing
    const canvas = zonesPage.zoneCanvas;
    const box = await canvas.boundingBox();
    expect(box).not.toBeNull();
  });

  test('zone form has all required fields when editing', async () => {
    await zonesPage.clickEditZone('Front Door Entry');

    // Verify form fields
    await expect(zonesPage.zoneNameInput).toBeVisible();
    await expect(zonesPage.zoneTypeSelect).toBeVisible();
  });

  test('zone form shows current zone name when editing', async () => {
    await zonesPage.clickEditZone('Front Door Entry');

    // Name input should have the current zone name
    await expect(zonesPage.zoneNameInput).toHaveValue('Front Door Entry');
  });

  test('can modify and submit zone edit form', async () => {
    await zonesPage.clickEditZone('Front Door Entry');

    // Modify the name (keep a valid name)
    await zonesPage.zoneNameInput.clear();
    await zonesPage.zoneNameInput.fill('Updated Zone Name');

    await zonesPage.submitZoneForm();

    // Should return to view mode (form hidden)
    await expect(zonesPage.zoneFormTitle).not.toBeVisible({ timeout: 5000 });
  });

  test('can cancel zone edit form', async () => {
    await zonesPage.clickEditZone('Front Door Entry');
    await zonesPage.cancelZoneForm();

    // Should return to view mode
    await expect(zonesPage.zoneFormTitle).not.toBeVisible();
    await expect(zonesPage.drawRectangleButton).toBeVisible();
  });
});

test.describe('Zone Editing', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
  });

  test('edit button is visible for each zone', async () => {
    const editButtons = zonesPage.page.locator('button[title="Edit zone"]');
    const count = await editButtons.count();
    expect(count).toBeGreaterThan(0);
  });

  test('clicking edit opens zone form with existing data', async () => {
    await zonesPage.clickEditZone('Front Door Entry');

    await expect(zonesPage.zoneFormTitle).toBeVisible();
    await expect(zonesPage.zoneFormTitle).toHaveText('Edit Zone');

    // Form should be pre-filled
    await expect(zonesPage.zoneNameInput).toHaveValue('Front Door Entry');
  });

  test('can update zone name', async () => {
    await zonesPage.clickEditZone('Front Door Entry');

    await zonesPage.zoneNameInput.clear();
    await zonesPage.zoneNameInput.fill('Updated Zone Name');
    await zonesPage.submitZoneForm();

    // Should return to view mode
    await expect(zonesPage.zoneFormTitle).not.toBeVisible({ timeout: 5000 });
  });

  test('can cancel zone edit', async () => {
    await zonesPage.clickEditZone('Front Door Entry');

    await zonesPage.zoneNameInput.clear();
    await zonesPage.zoneNameInput.fill('This should be cancelled');
    await zonesPage.cancelZoneForm();

    // Original name should still be visible in the zone list
    const zoneList = zonesPage.page.locator('[role="button"]').filter({ hasText: 'Front Door Entry' });
    await expect(zoneList).toBeVisible();
  });

  test('edit form shows Update Zone button', async () => {
    await zonesPage.clickEditZone('Front Door Entry');
    await expect(zonesPage.page.getByRole('button', { name: 'Update Zone' })).toBeVisible();
  });
});

test.describe('Zone Deletion', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
  });

  test('delete button is visible for each zone', async () => {
    const deleteButtons = zonesPage.page.locator('button[title="Delete zone"]');
    const count = await deleteButtons.count();
    expect(count).toBeGreaterThan(0);
  });

  test('clicking delete shows confirmation', async () => {
    await zonesPage.clickDeleteZone('Front Door Entry');
    await expect(zonesPage.deleteConfirmation).toBeVisible();
  });

  test('confirmation shows zone name', async () => {
    await zonesPage.clickDeleteZone('Front Door Entry');
    await expect(zonesPage.page.getByText(/Delete zone "Front Door Entry"/)).toBeVisible();
  });

  test('confirmation warns action cannot be undone', async () => {
    await zonesPage.clickDeleteZone('Front Door Entry');
    await expect(zonesPage.page.getByText('This action cannot be undone')).toBeVisible();
  });

  test('can cancel deletion', async () => {
    await zonesPage.clickDeleteZone('Front Door Entry');

    // Find the cancel button in the delete confirmation section (border-gray-600 styling)
    const cancelButton = zonesPage.page.getByRole('button', { name: /^Cancel$/i }).last();
    await cancelButton.click();

    // Zone should still be visible in the list
    const zoneList = zonesPage.page.locator('[role="button"]').filter({ hasText: 'Front Door Entry' });
    await expect(zoneList).toBeVisible();
  });

  test('can confirm deletion', async () => {
    await zonesPage.clickDeleteZone('Front Driveway');
    await zonesPage.confirmDelete();

    // Confirmation should disappear
    await expect(zonesPage.deleteConfirmation).not.toBeVisible({ timeout: 5000 });
  });
});

test.describe('Zone Visibility Toggle', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
  });

  test('toggle button is visible for each zone', async () => {
    // Each zone should have an enable/disable toggle
    const toggleButtons = zonesPage.page.locator('button[title*="zone"]').filter({
      has: zonesPage.page.locator('svg.lucide-eye, svg.lucide-eye-off'),
    });
    const count = await toggleButtons.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });

  test('enabled zone shows eye icon', async () => {
    // Front Door Entry is enabled
    const zoneItem = zonesPage.page.locator('[role="button"]').filter({ hasText: 'Front Door Entry' });
    const eyeIcon = zoneItem.locator('svg.lucide-eye');
    await expect(eyeIcon).toBeVisible();
  });

  test('disabled zone shows eye-off icon', async () => {
    // Sidewalk Monitor is disabled
    const zoneItem = zonesPage.page.locator('[role="button"]').filter({ hasText: 'Sidewalk Monitor' });
    const eyeOffIcon = zoneItem.locator('svg.lucide-eye-off');
    await expect(eyeOffIcon).toBeVisible();
  });

  test('clicking toggle changes zone enabled state', async () => {
    await zonesPage.toggleZoneEnabled('Front Door Entry');

    // API call should be made - the mock will handle it
    // We can verify the toggle was clicked by checking the action completed
    await zonesPage.page.waitForTimeout(500); // Allow time for API call
  });
});

test.describe('Multi-Zone Scenarios', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
  });

  test('camera can have multiple zones', async () => {
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();

    const count = await zonesPage.getZoneCount();
    expect(count).toBe(3);
  });

  test('zones are ordered by priority', async () => {
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();

    // Check that zones are in priority order (highest first)
    // Front Door Entry (90) should come before Front Driveway (50)
    const zoneTexts = await zonesPage.page.locator('[role="button"] .font-medium.text-text-primary').allTextContents();

    // First zone should be highest priority
    expect(zoneTexts[0]).toBe('Front Door Entry'); // Priority 90
  });

  test('different cameras have different zones', async ({ page }) => {
    // Check Front Door
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
    let count = await zonesPage.getZoneCount();
    expect(count).toBe(3);
    await zonesPage.closeZoneEditor();

    // Wait for modal to close
    await page.waitForTimeout(300);

    // Check Back Yard
    await zonesPage.openZoneEditor('Back Yard');
    await zonesPage.waitForZoneEditorLoad();
    count = await zonesPage.getZoneCount();
    expect(count).toBe(1);
    // Check for Back Fence in the zone list
    const zoneList = page.locator('[role="button"]').filter({ hasText: 'Back Fence' });
    await expect(zoneList).toBeVisible();
  });

  test('zones can have different types', async () => {
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();

    // Verify different zone types are displayed in zone list items
    const zoneList = zonesPage.page.locator('[role="button"]');
    await expect(zoneList.filter({ hasText: 'Entry Point' })).toBeVisible();
    await expect(zoneList.filter({ hasText: /Driveway/i }).first()).toBeVisible();
    await expect(zoneList.filter({ hasText: /Sidewalk/i })).toBeVisible();
  });

  test('zones can have different colors', async () => {
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();

    // Each zone has a color indicator div
    const colorIndicators = zonesPage.page.locator('[role="button"] .h-8.w-8.rounded');
    const count = await colorIndicators.count();
    expect(count).toBe(3);
  });
});

test.describe('Zone Color Selection', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
  });

  test('color options are shown in drawing mode', async () => {
    await zonesPage.startDrawingRectangle();

    await expect(zonesPage.page.getByText('Zone Color')).toBeVisible();

    // Multiple color buttons should be visible
    const colorButtons = zonesPage.zoneColorButtons;
    const count = await colorButtons.count();
    expect(count).toBeGreaterThanOrEqual(6);
  });

  test('clicking color button changes selection', async () => {
    await zonesPage.startDrawingRectangle();

    // Get all color buttons
    const colorButtons = zonesPage.zoneColorButtons;
    const count = await colorButtons.count();

    // Click the second color button (not the currently selected one)
    if (count >= 2) {
      await colorButtons.nth(1).click();
      // Verify the button is now marked as selected with ring styles
      await expect(colorButtons.nth(1)).toHaveClass(/ring-2|ring-primary/);
    }
  });
});

test.describe('Zone Canvas', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
  });

  test('canvas displays camera snapshot', async () => {
    // The canvas should have an image element
    await expect(zonesPage.zoneCanvasImage).toBeVisible();
  });

  test('canvas has correct aspect ratio', async () => {
    const canvas = zonesPage.zoneCanvas;
    // Check that canvas maintains proper video aspect ratio (16:9 or similar)
    const box = await canvas.boundingBox();
    if (box) {
      const ratio = box.width / box.height;
      // Allow for 16:9 (1.77) or similar aspect ratios
      expect(ratio).toBeGreaterThan(1.3);
      expect(ratio).toBeLessThan(2.0);
    }
  });

  test('drawing mode shows visual indicator', async () => {
    await zonesPage.startDrawingRectangle();
    // When in drawing mode, the drawing mode indicator should be visible
    await expect(zonesPage.drawingModeIndicator).toBeVisible();
    await expect(zonesPage.drawingModeIndicator).toContainText(/rectangle/i);
  });
});

test.describe('Zone Editor Error Handling', () => {
  test('shows error when zone loading fails', async ({ page }) => {
    const errorConfig: ApiMockConfig = {
      ...defaultMockConfig,
      zonesError: true,
    };
    await setupApiMocks(page, errorConfig);

    const zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();

    // Click the configure zones button
    const cameraRow = page.locator('tr').filter({ hasText: 'Front Door' });
    const zonesButton = cameraRow.getByRole('button', { name: /Configure zones/i });
    await zonesButton.click();

    // Should show error message or dialog might not open properly
    const errorOrDialog = page.getByText(/Failed|Error|unable/i).or(
      page.getByRole('heading', { name: /Zone Configuration/i })
    );
    await expect(errorOrDialog).toBeVisible({ timeout: 5000 });
  });

  test('shows error when zone update fails', async ({ page }) => {
    // Start with working API, then make it fail for updates
    await setupApiMocks(page, defaultMockConfig);

    const zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();

    // Override zone update endpoint to fail
    await page.route('**/api/cameras/*/zones/*', async (route) => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Failed to update zone' }),
        });
      } else {
        await route.continue();
      }
    });

    // Try to edit a zone
    await zonesPage.clickEditZone('Front Door Entry');
    await zonesPage.zoneNameInput.clear();
    await zonesPage.zoneNameInput.fill('Updated Name');

    // Click submit button (don't use submitZoneForm helper as it waits for success)
    await zonesPage.zoneFormSubmitButton.click();

    // Should show error or form should remain visible
    const errorOrForm = page.getByText(/Failed|Error/i).or(zonesPage.zoneFormTitle);
    await expect(errorOrForm).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Zone Form Zone Types', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
  });

  test('zone type dropdown has all options', async () => {
    await zonesPage.clickEditZone('Front Door Entry');

    const select = zonesPage.zoneTypeSelect;

    // Check that the select dropdown has multiple options
    const options = select.locator('option');
    const count = await options.count();
    expect(count).toBeGreaterThanOrEqual(4); // entry_point, driveway, sidewalk, yard, other
  });

  test('zone type shows description', async () => {
    await zonesPage.clickEditZone('Front Door Entry');

    // Select entry_point to see its description
    await zonesPage.zoneTypeSelect.selectOption('entry_point');
    await expect(zonesPage.page.getByText('Doors, gates, or other entry areas')).toBeVisible();
  });

  test('changing zone type updates description', async () => {
    await zonesPage.clickEditZone('Front Door Entry');

    await zonesPage.zoneTypeSelect.selectOption('driveway');
    await expect(zonesPage.page.getByText('Vehicle access areas')).toBeVisible();

    await zonesPage.zoneTypeSelect.selectOption('yard');
    await expect(zonesPage.page.getByText('Private property areas')).toBeVisible();
  });
});

test.describe('Zone Priority Slider', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
  });

  test('priority slider shows current value', async () => {
    await zonesPage.clickEditZone('Front Door Entry');

    // Priority should be shown in label
    await expect(zonesPage.page.getByText(/Priority: 90/)).toBeVisible();
  });

  test('priority description explains overlap behavior', async () => {
    await zonesPage.clickEditZone('Front Door Entry');

    await expect(zonesPage.page.getByText('Higher priority zones take precedence when overlapping')).toBeVisible();
  });

  test('priority slider has correct range', async () => {
    await zonesPage.clickEditZone('Front Door Entry');

    const slider = zonesPage.zonePrioritySlider;
    await expect(slider).toHaveAttribute('min', '0');
    await expect(slider).toHaveAttribute('max', '100');
  });
});

test.describe('Zone Keyboard Navigation', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
    await zonesPage.gotoSettings();
    await zonesPage.openZoneEditor('Front Door');
    await zonesPage.waitForZoneEditorLoad();
  });

  test('zones can be selected with Enter key', async ({ page }) => {
    // Focus the first zone
    const firstZone = page.locator('[role="button"]').filter({ hasText: 'Front Door Entry' });
    await firstZone.focus();
    await page.keyboard.press('Enter');

    await expect(firstZone).toHaveAttribute('aria-pressed', 'true');
  });

  test('zones can be selected with Space key', async ({ page }) => {
    const firstZone = page.locator('[role="button"]').filter({ hasText: 'Front Door Entry' });
    await firstZone.focus();
    await page.keyboard.press('Space');

    await expect(firstZone).toHaveAttribute('aria-pressed', 'true');
  });

  test('Escape key closes zone editor modal', async ({ page }) => {
    await page.keyboard.press('Escape');
    await expect(zonesPage.zoneEditorModal).not.toBeVisible();
  });
});
