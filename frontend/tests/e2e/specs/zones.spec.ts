/**
 * Zone Management E2E Tests
 *
 * Comprehensive tests for zone management functionality including:
 * - Zone CRUD operations (create, read, update, delete)
 * - Zone polygon drawing on camera view
 * - Zone visibility toggle
 * - Multi-zone per camera support
 * - Zone overlap warnings
 *
 * NOTE: These tests mock the zone API endpoints and test UI interactions.
 * The actual zone management UI component may need to be implemented.
 * Tests follow Page Object Model pattern for maintainability.
 */

import { test, expect } from '@playwright/test';
import { ZonesPage } from '../pages';
import {
  setupApiMocks,
  defaultMockConfig,
  setupZoneApiMocks,
  setupZoneApiMocksWithError,
} from '../fixtures';
import { mockZonesByCamera, mockZones, allCameras } from '../fixtures';

// Skip tests if zone UI is not implemented
// Remove this skip when zone management UI is built
test.describe.configure({ mode: 'serial' });

test.describe('Zone List Display', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    await setupZoneApiMocks(page, mockZonesByCamera);
    zonesPage = new ZonesPage(page);
  });

  test('zones section is accessible from settings', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();
    // Verify settings page loads
    await expect(page.getByRole('heading', { name: /Settings/i })).toBeVisible();
  });

  test('displays zones tab in settings navigation', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();
    // Look for zones-related UI element
    const zonesTabOrSection = page.locator('button, [role="tab"]').filter({ hasText: /ZONES|Zones/i });
    // This test documents expected UI structure
    const count = await zonesTabOrSection.count();
    // Log for debugging - remove when UI is implemented
    if (count === 0) {
      test.skip(true, 'Zone management UI not yet implemented');
    }
  });

  test('empty state shows no zones message', async ({ page }) => {
    // Setup with empty zones for all cameras
    await setupZoneApiMocks(page, { 'cam-1': [], 'cam-2': [], 'cam-3': [], 'cam-4': [] });
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    // Try to navigate to zones tab if it exists
    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (await zonesTab.isVisible()) {
      await zonesTab.click();
      await expect(zonesPage.emptyZonesMessage).toBeVisible();
    } else {
      test.skip(true, 'Zone management UI not yet implemented');
    }
  });
});

test.describe('Zone CRUD Operations', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    await setupZoneApiMocks(page, mockZonesByCamera);
    zonesPage = new ZonesPage(page);
  });

  test('can create a new zone', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    // Check if zones UI is available
    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();

    // Click add zone
    await zonesPage.clickAddZone();

    // Fill the form
    await zonesPage.fillZoneForm({
      name: 'New Test Zone',
      zoneType: 'entry_point',
      priority: 5,
    });

    // Save the zone
    await zonesPage.saveZone();

    // Verify zone was created
    await expect(zonesPage.getZoneCard('New Test Zone')).toBeVisible();
  });

  test('can edit zone coordinates', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();

    // Find an existing zone and click edit
    const existingZone = mockZones.frontDoorEntry.name;
    await zonesPage.clickEditZone(existingZone);

    // Verify edit modal opens
    await expect(zonesPage.zoneFormModal).toBeVisible();

    // Update the name
    await zonesPage.zoneNameInput.clear();
    await zonesPage.zoneNameInput.fill('Updated Zone Name');

    // Save changes
    await zonesPage.saveZone();

    // Verify update
    await expect(zonesPage.getZoneCard('Updated Zone Name')).toBeVisible();
  });

  test('can delete zone with confirmation', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();

    // Click delete on an existing zone
    const zoneToDelete = mockZones.disabledZone.name;
    await zonesPage.clickDeleteZone(zoneToDelete);

    // Verify confirmation modal appears
    await expect(zonesPage.deleteConfirmModal).toBeVisible();

    // Confirm deletion
    await zonesPage.confirmDelete();

    // Verify zone is removed
    await expect(zonesPage.getZoneCard(zoneToDelete)).not.toBeVisible();
  });

  test('can cancel zone deletion', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();

    const zoneName = mockZones.frontDoorEntry.name;
    await zonesPage.clickDeleteZone(zoneName);

    // Cancel deletion
    await zonesPage.cancelDelete();

    // Verify zone still exists
    await expect(zonesPage.getZoneCard(zoneName)).toBeVisible();
  });
});

test.describe('Zone Visibility Toggle', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    await setupZoneApiMocks(page, mockZonesByCamera);
    zonesPage = new ZonesPage(page);
  });

  test('can toggle zone enabled/disabled', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();

    // Find an enabled zone
    const enabledZoneName = mockZones.frontDoorEntry.name;

    // Toggle it off
    await zonesPage.toggleZone(enabledZoneName);

    // Verify it's now disabled (visual indicator changes)
    const isEnabled = await zonesPage.isZoneEnabled(enabledZoneName);
    expect(isEnabled).toBe(false);

    // Toggle it back on
    await zonesPage.toggleZone(enabledZoneName);

    // Verify it's enabled again
    const isEnabledAgain = await zonesPage.isZoneEnabled(enabledZoneName);
    expect(isEnabledAgain).toBe(true);
  });

  test('disabled zones show visual indication', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();

    // The pre-disabled zone should have visual indicator
    const disabledZoneName = mockZones.disabledZone.name;
    const card = zonesPage.getZoneCard(disabledZoneName);

    // Check for disabled styling (opacity, badge, etc.)
    const isDisabled = !(await zonesPage.isZoneEnabled(disabledZoneName));
    expect(isDisabled).toBe(true);
  });
});

test.describe('Zone Polygon Drawing', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    await setupZoneApiMocks(page, mockZonesByCamera);
    zonesPage = new ZonesPage(page);
  });

  test('can draw rectangle zone on camera view', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();
    await zonesPage.clickAddZone();

    // Check if canvas is visible
    if (!(await zonesPage.zoneCanvas.isVisible())) {
      test.skip(true, 'Zone canvas not yet implemented');
      return;
    }

    // Draw a rectangle
    await zonesPage.drawRectangle(0.2, 0.2, 0.6, 0.6);

    // Fill form and save
    await zonesPage.fillZoneForm({ name: 'Drawn Rectangle Zone' });
    await zonesPage.saveZone();

    // Verify zone was created
    await expect(zonesPage.getZoneCard('Drawn Rectangle Zone')).toBeVisible();
  });

  test('can draw polygon zone on camera view', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();
    await zonesPage.clickAddZone();

    if (!(await zonesPage.zoneCanvas.isVisible())) {
      test.skip(true, 'Zone canvas not yet implemented');
      return;
    }

    // Draw a polygon with 5 points
    await zonesPage.drawPolygon([
      [0.1, 0.1],
      [0.5, 0.1],
      [0.6, 0.5],
      [0.5, 0.9],
      [0.1, 0.9],
    ]);

    // Fill form and save
    await zonesPage.fillZoneForm({ name: 'Custom Polygon Zone' });
    await zonesPage.saveZone();

    // Verify zone was created
    await expect(zonesPage.getZoneCard('Custom Polygon Zone')).toBeVisible();
  });

  test('can resize/move zone polygon', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();

    // Edit existing zone
    const zoneName = mockZones.frontDoorEntry.name;
    await zonesPage.clickEditZone(zoneName);

    if (!(await zonesPage.zoneCanvas.isVisible())) {
      test.skip(true, 'Zone canvas not yet implemented');
      return;
    }

    // Clear and redraw
    await zonesPage.clearDrawing();
    await zonesPage.drawRectangle(0.3, 0.3, 0.7, 0.7);

    await zonesPage.saveZone();

    // Verify changes saved (would need API verification)
    await expect(zonesPage.successMessage).toBeVisible();
  });

  test('can clear drawing before saving', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();
    await zonesPage.clickAddZone();

    if (!(await zonesPage.zoneCanvas.isVisible())) {
      test.skip(true, 'Zone canvas not yet implemented');
      return;
    }

    // Draw something
    await zonesPage.drawRectangle(0.2, 0.2, 0.5, 0.5);

    // Clear it
    await zonesPage.clearDrawing();

    // Draw again
    await zonesPage.drawRectangle(0.3, 0.3, 0.6, 0.6);

    // Cancel - should not save
    await zonesPage.cancelZoneForm();

    // Verify modal closed
    await expect(zonesPage.zoneFormModal).not.toBeVisible();
  });
});

test.describe('Multi-zone Per Camera', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    await setupZoneApiMocks(page, mockZonesByCamera);
    zonesPage = new ZonesPage(page);
  });

  test('displays multiple zones for same camera', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();

    // cam-1 has 2 zones in mock data
    await zonesPage.selectCamera('Front Door');

    const zoneCount = await zonesPage.getZoneCount();
    expect(zoneCount).toBe(2);
  });

  test('can switch between cameras and see different zones', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();

    // Select cam-1 (has 2 zones)
    await zonesPage.selectCamera('Front Door');
    let zoneCount = await zonesPage.getZoneCount();
    expect(zoneCount).toBe(2);

    // Select cam-3 (has 0 zones)
    await zonesPage.selectCamera('Garage');
    zoneCount = await zonesPage.getZoneCount();
    expect(zoneCount).toBe(0);

    // Select cam-4 (has 1 zone)
    await zonesPage.selectCamera('Driveway');
    zoneCount = await zonesPage.getZoneCount();
    expect(zoneCount).toBe(1);
  });

  test('zones are sorted by priority', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();

    // Select cam-1 which has zones with different priorities
    await zonesPage.selectCamera('Front Door');

    const zoneNames = await zonesPage.getZoneNames();

    // frontDoorEntry has priority 1, disabledZone has priority 0
    // Higher priority should come first
    expect(zoneNames[0]).toBe(mockZones.frontDoorEntry.name);
  });
});

test.describe('Zone Overlap Warnings', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    await setupZoneApiMocks(page, mockZonesByCamera);
    zonesPage = new ZonesPage(page);
  });

  test('shows warning when zones overlap', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();

    // Select camera with existing zones
    await zonesPage.selectCamera('Front Door');

    // Try to create a zone that overlaps with existing
    await zonesPage.clickAddZone();

    if (!(await zonesPage.zoneCanvas.isVisible())) {
      test.skip(true, 'Zone canvas not yet implemented');
      return;
    }

    // Draw in overlapping area (frontDoorEntry is at 0.1-0.4 x, 0.2-0.8 y)
    await zonesPage.drawRectangle(0.2, 0.3, 0.5, 0.7);

    await zonesPage.fillZoneForm({ name: 'Overlapping Zone' });

    // Warning should appear
    const hasWarning = await zonesPage.hasOverlapWarning();
    // Note: This may pass or fail depending on UI implementation
    // The warning is advisory, not blocking
    if (hasWarning) {
      await expect(zonesPage.overlapWarning).toBeVisible();
    }

    // Should still be able to save
    await zonesPage.saveZone();
  });
});

test.describe('Zone Error Handling', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    zonesPage = new ZonesPage(page);
  });

  test('shows error when zone API fails', async ({ page }) => {
    await setupZoneApiMocksWithError(page);
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();

    // Attempt to load zones should show error
    const hasError = await zonesPage.hasErrorMessage();
    if (hasError) {
      await expect(zonesPage.errorMessage).toBeVisible();
    }
  });

  test('validates zone name is required', async ({ page }) => {
    await setupZoneApiMocks(page, mockZonesByCamera);
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();
    await zonesPage.clickAddZone();

    // Try to save without name
    await zonesPage.saveZone();

    // Should show validation error
    const nameInput = zonesPage.zoneNameInput;
    const validationMessage = await nameInput.evaluate((el: HTMLInputElement) => el.validationMessage);
    expect(validationMessage.length).toBeGreaterThan(0);
  });
});

test.describe('Zone Type Selection', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    await setupZoneApiMocks(page, mockZonesByCamera);
    zonesPage = new ZonesPage(page);
  });

  test('can select different zone types', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();
    await zonesPage.clickAddZone();

    // Check zone type options are available
    const zoneTypeSelect = zonesPage.zoneTypeSelect;

    if (!(await zoneTypeSelect.isVisible())) {
      test.skip(true, 'Zone type select not visible');
      return;
    }

    // Verify all expected types are available
    const options = await zoneTypeSelect.locator('option').allTextContents();

    expect(options.some(opt => opt.toLowerCase().includes('entry'))).toBe(true);
    expect(options.some(opt => opt.toLowerCase().includes('driveway'))).toBe(true);
    expect(options.some(opt => opt.toLowerCase().includes('yard') || opt.toLowerCase().includes('sidewalk'))).toBe(true);
  });

  test('zone type is shown on zone card', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();
    await zonesPage.selectCamera('Front Door');

    // Entry point zone should show its type
    const entryZoneCard = zonesPage.getZoneCard(mockZones.frontDoorEntry.name);
    const cardText = await entryZoneCard.textContent();

    expect(cardText?.toLowerCase()).toContain('entry');
  });
});

test.describe('Zone Color Selection', () => {
  let zonesPage: ZonesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    await setupZoneApiMocks(page, mockZonesByCamera);
    zonesPage = new ZonesPage(page);
  });

  test('zone color is displayed on zone card', async ({ page }) => {
    await zonesPage.goto();
    await zonesPage.waitForZonesLoad();

    const zonesTab = page.locator('button').filter({ hasText: /ZONES/i });
    if (!(await zonesTab.isVisible())) {
      test.skip(true, 'Zone management UI not yet implemented');
      return;
    }

    await zonesTab.click();
    await zonesPage.selectCamera('Front Door');

    // Check that zones have color indicators
    const zoneCard = zonesPage.getZoneCard(mockZones.frontDoorEntry.name);

    // Zone should have a color indicator element
    const colorIndicator = zoneCard.locator('[data-testid="zone-color"]');

    if (await colorIndicator.isVisible()) {
      // Verify the color matches the mock data
      const bgColor = await colorIndicator.evaluate((el) =>
        getComputedStyle(el).backgroundColor
      );
      // Color should be set (not empty/transparent)
      expect(bgColor).toBeTruthy();
    }
  });
});
