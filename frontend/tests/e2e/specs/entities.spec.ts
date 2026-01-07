/**
 * Entities Tests for Home Security Dashboard
 *
 * Tests for the Entities page - tracking people and vehicles.
 */

import { test, expect } from '@playwright/test';
import { EntitiesPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

test.describe('Entities Page Load', () => {
  let entitiesPage: EntitiesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    entitiesPage = new EntitiesPage(page);
  });

  test('entities page loads successfully', async () => {
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();
  });

  test('entities displays page title', async () => {
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();
    await expect(entitiesPage.pageTitle).toBeVisible();
  });

  test('entities displays page subtitle', async () => {
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();
    await expect(entitiesPage.pageSubtitle).toBeVisible();
  });

  test('entities title says Entities', async () => {
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();
    await expect(entitiesPage.pageTitle).toHaveText(/Entities/i);
  });
});

test.describe('Entities Filters', () => {
  let entitiesPage: EntitiesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();
  });

  test('shows entity type filter buttons', async () => {
    await expect(entitiesPage.allFilterButton).toBeVisible();
    await expect(entitiesPage.personFilterButton).toBeVisible();
    await expect(entitiesPage.vehicleFilterButton).toBeVisible();
  });

  test('all filter is active by default', async () => {
    await expect(entitiesPage.allFilterButton).toHaveAttribute('aria-pressed', 'true');
  });

  test('can switch to person filter', async () => {
    await entitiesPage.personFilterButton.click();
    await expect(entitiesPage.personFilterButton).toHaveAttribute('aria-pressed', 'true');
  });

  test('can switch to vehicle filter', async () => {
    await entitiesPage.vehicleFilterButton.click();
    await expect(entitiesPage.vehicleFilterButton).toHaveAttribute('aria-pressed', 'true');
  });
});

test.describe('Entities Empty State', () => {
  let entitiesPage: EntitiesPage;

  test.beforeEach(async ({ page }) => {
    // Mock with empty entities response
    await setupApiMocks(page, {
      ...defaultMockConfig,
      entities: [],
    });
    entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();
  });

  test('shows empty state message', async () => {
    await expect(entitiesPage.emptyStateMessage).toBeVisible();
  });

  test('empty state mentions no entities', async () => {
    await expect(entitiesPage.emptyStateHeading).toHaveText(/No Entities (Found|Tracked Yet)/i);
  });
});

test.describe('Entities Layout', () => {
  let entitiesPage: EntitiesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();
  });

  test('header is visible', async () => {
    await entitiesPage.expectHeaderVisible();
  });

  test('sidebar is visible', async () => {
    await entitiesPage.expectSidebarVisible();
  });

  test('full layout is preserved', async () => {
    await entitiesPage.expectLayoutLoaded();
  });

  test('refresh button is visible', async () => {
    await expect(entitiesPage.refreshButton).toBeVisible();
  });
});
