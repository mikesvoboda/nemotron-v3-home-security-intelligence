/**
 * Entity Trust Classification E2E Tests
 *
 * Tests for the entity trust classification feature.
 * These tests verify UI interactions for marking entities as trusted, suspicious, or unknown,
 * and ensure that trust status changes are reflected in the UI and alert behavior.
 */

import { test, expect } from '@playwright/test';
import { EntitiesPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';
import { mockEntitiesWithTrust, mockDetectionWithBbox } from '../fixtures/test-data';

// TODO: Re-enable after fixing entity card rendering in E2E mocks
// Entity cards don't render despite correct mock setup - needs investigation
test.describe.skip('Entity Trust Classification', () => {
  let entitiesPage: EntitiesPage;

  test.beforeEach(async ({ page }) => {
    // Setup API mocks with entities that have trust status
    await setupApiMocks(page, {
      ...defaultMockConfig,
      entities: mockEntitiesWithTrust,
    });

    entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();
  });

  test.describe('Entity Detail Modal', () => {
    test('entity card click opens detail modal', async ({ page }) => {
      // Click on the first entity card
      await entitiesPage.clickEntityCard(0);

      // Verify modal is visible
      await expect(page.getByRole('dialog')).toBeVisible();
      await expect(page.getByText(/Entity Details/i)).toBeVisible();
    });

    test('modal displays entity information', async ({ page }) => {
      // Click on the first entity card
      await entitiesPage.clickEntityCard(0);

      // Verify entity details are displayed
      const modal = page.getByRole('dialog');
      await expect(modal).toBeVisible();

      // Check for key entity information
      await expect(modal.getByText(/person/i)).toBeVisible();
      await expect(modal.getByText(/First Seen/i)).toBeVisible();
      await expect(modal.getByText(/Last Seen/i)).toBeVisible();
      await expect(modal.getByText(/Appearances/i)).toBeVisible();
    });

    test('modal displays trust status buttons', async ({ page }) => {
      await entitiesPage.clickEntityCard(0);

      const modal = page.getByRole('dialog');
      await expect(modal).toBeVisible();

      // Verify trust action buttons are present
      await expect(modal.getByRole('button', { name: /Mark.*Trusted/i })).toBeVisible();
      await expect(modal.getByRole('button', { name: /Mark.*Suspicious/i })).toBeVisible();
    });

    test('modal can be closed with escape key', async ({ page }) => {
      await entitiesPage.clickEntityCard(0);

      const modal = page.getByRole('dialog');
      await expect(modal).toBeVisible();

      // Press escape to close
      await page.keyboard.press('Escape');
      await expect(modal).not.toBeVisible();
    });

    test('modal can be closed with close button', async ({ page }) => {
      await entitiesPage.clickEntityCard(0);

      const modal = page.getByRole('dialog');
      await expect(modal).toBeVisible();

      // Click close button
      await page.getByRole('button', { name: /Close/i }).click();
      await expect(modal).not.toBeVisible();
    });
  });

  test.describe('Bounding Box Display', () => {
    test('bounding box is displayed on detection image', async ({ page }) => {
      // Setup mock for detection endpoint with bbox data
      await page.route('**/api/detections/**', (route) => {
        void route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockDetectionWithBbox),
        });
      });

      await entitiesPage.clickEntityCard(0);

      // Verify bounding box is rendered
      const bbox = page.locator('[data-testid="bounding-box"]');
      await expect(bbox).toBeVisible();
    });

    test('bounding box has correct dimensions', async ({ page }) => {
      await page.route('**/api/detections/**', (route) => {
        void route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockDetectionWithBbox),
        });
      });

      await entitiesPage.clickEntityCard(0);

      const bbox = page.locator('[data-testid="bounding-box"]');
      await expect(bbox).toBeVisible();

      // Verify bbox has style attributes (position and size)
      const boxStyles = await bbox.getAttribute('style');
      expect(boxStyles).toBeTruthy();
      expect(boxStyles).toContain('position');
    });
  });

  test.describe('Trust Status Updates', () => {
    test('mark entity as trusted', async ({ page }) => {
      // Setup route to intercept trust API call
      const trustUpdatePromise = page.waitForResponse(
        (resp) => resp.url().includes('/trust') && resp.status() === 200
      );

      // Open entity modal
      await entitiesPage.clickEntityCard(0);

      // Click trust button
      await page.getByRole('button', { name: /Mark.*Trusted/i }).click();

      // Verify API call was made
      await trustUpdatePromise;

      // Verify success toast message
      await expect(page.getByText(/marked as trusted/i)).toBeVisible();

      // Close modal
      await page.keyboard.press('Escape');

      // Verify entity card shows trusted badge
      await expect(page.locator('[data-testid="trust-badge-trusted"]').first()).toBeVisible();
    });

    test('mark entity as suspicious', async ({ page }) => {
      const trustUpdatePromise = page.waitForResponse(
        (resp) => resp.url().includes('/trust') && resp.status() === 200
      );

      await entitiesPage.clickEntityCard(0);

      // Click suspicious button
      await page.getByRole('button', { name: /Mark.*Suspicious/i }).click();

      await trustUpdatePromise;

      // Verify success message
      await expect(page.getByText(/marked as suspicious/i)).toBeVisible();

      // Close and verify badge
      await page.keyboard.press('Escape');
      await expect(page.locator('[data-testid="trust-badge-suspicious"]').first()).toBeVisible();
    });

    test('reset trust status to unknown', async ({ page }) => {
      // First mark as trusted
      await entitiesPage.clickEntityCard(0);
      await page.getByRole('button', { name: /Mark.*Trusted/i }).click();
      await page.waitForTimeout(500);

      // Then reset to unknown
      await page.getByRole('button', { name: /Reset/i }).click();

      // Verify success message
      await expect(page.getByText(/status reset/i)).toBeVisible();

      // Close and verify no badge is shown
      await page.keyboard.press('Escape');
      const trustedBadge = page.locator('[data-testid="trust-badge-trusted"]').first();
      await expect(trustedBadge).not.toBeVisible();
    });

    test('trust status change updates entity list immediately', async ({ page }) => {
      // Open modal and change trust status
      await entitiesPage.clickEntityCard(0);
      await page.getByRole('button', { name: /Mark.*Trusted/i }).click();

      // Wait for success message
      await expect(page.getByText(/marked as trusted/i)).toBeVisible();

      // Close modal
      await page.keyboard.press('Escape');

      // Verify the entity card in the list reflects the change
      const firstCard = page.locator('[data-testid="entity-card"]').first();
      await expect(firstCard.locator('[data-testid="trust-badge-trusted"]')).toBeVisible();
    });
  });

  test.describe('Trust Filter', () => {
    test('can filter entities by trust status', async ({ page }) => {
      // Look for trust status filter dropdown
      const trustFilter = page.locator('select#trust-filter');
      await expect(trustFilter).toBeVisible();

      // Select trusted entities only
      await trustFilter.selectOption('trusted');

      // Verify only trusted entities are shown
      const entityCards = page.locator('[data-testid="entity-card"]');
      const count = await entityCards.count();

      // Each visible entity should have a trusted badge
      for (let i = 0; i < count; i++) {
        await expect(
          entityCards.nth(i).locator('[data-testid="trust-badge-trusted"]')
        ).toBeVisible();
      }
    });

    test('filter shows correct counts', async ({ page }) => {
      const trustFilter = page.locator('select#trust-filter');

      // Check that filter has options with counts
      await expect(trustFilter.locator('option[value="all"]')).toContainText(/All/i);
      await expect(trustFilter.locator('option[value="trusted"]')).toContainText(/Trusted/i);
      await expect(trustFilter.locator('option[value="suspicious"]')).toContainText(/Suspicious/i);
      await expect(trustFilter.locator('option[value="unknown"]')).toContainText(/Unknown/i);
    });

    test('can clear trust filter', async ({ page }) => {
      const trustFilter = page.locator('select#trust-filter');

      // Apply filter
      await trustFilter.selectOption('trusted');
      await page.waitForTimeout(300);

      const filteredCount = await page.locator('[data-testid="entity-card"]').count();

      // Reset to all
      await trustFilter.selectOption('all');
      await page.waitForTimeout(300);

      const allCount = await page.locator('[data-testid="entity-card"]').count();

      // Should show more entities after clearing filter
      expect(allCount).toBeGreaterThan(filteredCount);
    });
  });

  test.describe('Alert Behavior with Trust', () => {
    test('trusted entity indicator is visible in entity card', async ({ page }) => {
      // Find an entity marked as trusted
      const trustedCard = page
        .locator('[data-testid="entity-card"]')
        .filter({ has: page.locator('[data-testid="trust-badge-trusted"]') })
        .first();

      await expect(trustedCard).toBeVisible();

      // Verify badge styling indicates trusted status
      const badge = trustedCard.locator('[data-testid="trust-badge-trusted"]');
      await expect(badge).toHaveClass(/trusted/i);
    });

    test('suspicious entity indicator uses warning styling', async ({ page }) => {
      // Find an entity marked as suspicious
      const suspiciousCard = page
        .locator('[data-testid="entity-card"]')
        .filter({ has: page.locator('[data-testid="trust-badge-suspicious"]') })
        .first();

      if ((await suspiciousCard.count()) > 0) {
        await expect(suspiciousCard).toBeVisible();

        const badge = suspiciousCard.locator('[data-testid="trust-badge-suspicious"]');
        await expect(badge).toHaveClass(/suspicious|warning/i);
      }
    });

    test('entity detail shows trust status prominently', async ({ page }) => {
      await entitiesPage.clickEntityCard(0);

      const modal = page.getByRole('dialog');
      await expect(modal).toBeVisible();

      // Check for trust status indicator in modal
      const trustIndicator = modal.locator('[data-testid="entity-trust-status"]');
      await expect(trustIndicator).toBeVisible();
    });
  });

  test.describe('Error Handling', () => {
    test('handles API error gracefully when updating trust', async ({ page }) => {
      // Mock API error
      await page.route('**/api/entities/*/trust', (route) => {
        void route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal server error' }),
        });
      });

      await entitiesPage.clickEntityCard(0);
      await page.getByRole('button', { name: /Mark.*Trusted/i }).click();

      // Verify error message is shown
      await expect(page.getByText(/failed to update|error/i)).toBeVisible();
    });

    test('handles network error when updating trust', async ({ page }) => {
      // Mock network failure
      await page.route('**/api/entities/*/trust', (route) => {
        void route.abort('failed');
      });

      await entitiesPage.clickEntityCard(0);
      await page.getByRole('button', { name: /Mark.*Trusted/i }).click();

      // Verify error message is shown
      await expect(page.getByText(/failed to update|network error/i)).toBeVisible();
    });

    test('handles not found error gracefully', async ({ page }) => {
      await page.route('**/api/entities/*/trust', (route) => {
        void route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Entity not found' }),
        });
      });

      await entitiesPage.clickEntityCard(0);
      await page.getByRole('button', { name: /Mark.*Trusted/i }).click();

      await expect(page.getByText(/not found|entity.*not found/i)).toBeVisible();
    });

    test('shows validation error for invalid trust status', async ({ page }) => {
      await page.route('**/api/entities/*/trust', (route) => {
        void route.fulfill({
          status: 422,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Invalid trust status' }),
        });
      });

      await entitiesPage.clickEntityCard(0);
      await page.getByRole('button', { name: /Mark.*Trusted/i }).click();

      await expect(page.getByText(/invalid|validation error/i)).toBeVisible();
    });
  });

  test.describe('Accessibility', () => {
    test('trust buttons have proper ARIA labels', async ({ page }) => {
      await entitiesPage.clickEntityCard(0);

      const modal = page.getByRole('dialog');

      // Check ARIA labels on trust buttons
      const trustedButton = modal.getByRole('button', { name: /Mark.*Trusted/i });
      await expect(trustedButton).toBeVisible();
      expect(await trustedButton.getAttribute('aria-label')).toBeTruthy();

      const suspiciousButton = modal.getByRole('button', { name: /Mark.*Suspicious/i });
      await expect(suspiciousButton).toBeVisible();
      expect(await suspiciousButton.getAttribute('aria-label')).toBeTruthy();
    });

    test('trust badges have descriptive text for screen readers', async ({ page }) => {
      const trustedBadge = page.locator('[data-testid="trust-badge-trusted"]').first();

      if ((await trustedBadge.count()) > 0) {
        await expect(trustedBadge).toBeVisible();

        // Check for sr-only text or aria-label
        const ariaLabel = await trustedBadge.getAttribute('aria-label');
        const hasScreenReaderText = (await trustedBadge.locator('.sr-only').count()) > 0;

        expect(ariaLabel || hasScreenReaderText).toBeTruthy();
      }
    });

    test('modal is keyboard navigable', async ({ page }) => {
      await entitiesPage.clickEntityCard(0);

      const modal = page.getByRole('dialog');
      await expect(modal).toBeVisible();

      // Tab through modal elements
      await page.keyboard.press('Tab');
      await page.keyboard.press('Tab');

      // Verify focus is within modal
      const focusedElement = page.locator(':focus');
      await expect(focusedElement).toBeVisible();

      // Verify escape closes modal
      await page.keyboard.press('Escape');
      await expect(modal).not.toBeVisible();
    });
  });

  test.describe('Bulk Operations', () => {
    test('can select multiple entities for bulk trust update', async ({ page }) => {
      // Look for checkbox on entity cards
      const firstCardCheckbox = page
        .locator('[data-testid="entity-card"]')
        .first()
        .locator('input[type="checkbox"]');
      const secondCardCheckbox = page
        .locator('[data-testid="entity-card"]')
        .nth(1)
        .locator('input[type="checkbox"]');

      if ((await firstCardCheckbox.count()) > 0) {
        await firstCardCheckbox.check();
        await secondCardCheckbox.check();

        // Verify bulk action button appears
        await expect(page.getByRole('button', { name: /Bulk.*Trust/i })).toBeVisible();
      }
    });

    test('bulk trust update affects all selected entities', async ({ page }) => {
      const firstCheckbox = page
        .locator('[data-testid="entity-card"]')
        .first()
        .locator('input[type="checkbox"]');
      const secondCheckbox = page
        .locator('[data-testid="entity-card"]')
        .nth(1)
        .locator('input[type="checkbox"]');

      if ((await firstCheckbox.count()) > 0) {
        await firstCheckbox.check();
        await secondCheckbox.check();

        // Click bulk trust button
        await page.getByRole('button', { name: /Bulk.*Trust/i }).click();

        // Select "Trusted" from dropdown
        await page.getByRole('menuitem', { name: /Mark.*Trusted/i }).click();

        // Verify success message shows count
        await expect(page.getByText(/2.*entities.*marked as trusted/i)).toBeVisible();
      }
    });
  });
});
