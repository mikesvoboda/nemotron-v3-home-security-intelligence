/**
 * Visual Regression Tests - Entities Page
 *
 * These tests capture screenshots and compare against baseline images
 * to detect unintended visual changes in the Entities page.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { EntitiesPage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig } from '../fixtures';

// Mock entities data for visual tests
const mockEntities = [
  {
    id: 'entity-1',
    entity_type: 'person' as const,
    first_seen: new Date(Date.now() - 86400000).toISOString(),
    last_seen: new Date().toISOString(),
    appearance_count: 15,
    cameras_seen: ['front_door', 'backyard'],
    thumbnail_url: '/api/entities/entity-1/thumbnail',
  },
  {
    id: 'entity-2',
    entity_type: 'vehicle' as const,
    first_seen: new Date(Date.now() - 172800000).toISOString(),
    last_seen: new Date(Date.now() - 3600000).toISOString(),
    appearance_count: 8,
    cameras_seen: ['driveway'],
    thumbnail_url: '/api/entities/entity-2/thumbnail',
  },
  {
    id: 'entity-3',
    entity_type: 'person' as const,
    first_seen: new Date(Date.now() - 43200000).toISOString(),
    last_seen: new Date(Date.now() - 1800000).toISOString(),
    appearance_count: 3,
    cameras_seen: ['front_door'],
    thumbnail_url: '/api/entities/entity-3/thumbnail',
  },
];

test.describe('Entities Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, {
      ...defaultMockConfig,
      entities: mockEntities,
    });
  });

  test('entities full page matches snapshot', async ({ page }) => {
    const entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('entities-full-page.png', {
      fullPage: true,
      mask: [
        page.locator('[data-testid="timestamp"]'),
        page.locator('time'),
        page.locator('[data-testid="relative-time"]'),
        // Mask entity thumbnails as they may vary
        page.locator('img[alt*="entity" i], img[alt*="thumbnail" i]'),
      ],
    });
  });

  test('entities filter buttons match snapshot', async ({ page }) => {
    const entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();

    await page.waitForLoadState('networkidle');

    // Filter buttons area
    const filterArea = page.locator('button').filter({ hasText: 'All' }).locator('..').first();
    if (await filterArea.isVisible()) {
      await expect(filterArea).toHaveScreenshot('entities-filter-buttons.png');
    }
  });

  test('entities grid matches snapshot', async ({ page }) => {
    const entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();

    await page.waitForLoadState('networkidle');

    // Entity grid screenshot
    const entityGrid = entitiesPage.entityGrid;
    if (await entityGrid.isVisible()) {
      await expect(entityGrid).toHaveScreenshot('entities-grid.png', {
        mask: [page.locator('time'), page.locator('img[alt*="entity" i], img[alt*="thumbnail" i]')],
      });
    }
  });

  test('entities card matches snapshot', async ({ page }) => {
    const entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();

    await page.waitForLoadState('networkidle');

    // First entity card
    const entityCard = entitiesPage.entityCards.first();
    if (await entityCard.isVisible()) {
      await expect(entityCard).toHaveScreenshot('entities-card.png', {
        mask: [page.locator('time'), page.locator('img')],
      });
    }
  });
});

test.describe('Entities Visual States', () => {
  test('entities empty state matches snapshot', async ({ page }) => {
    await setupApiMocks(page, {
      ...emptyMockConfig,
      entities: [],
    });
    const entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('entities-empty-state.png', {
      fullPage: true,
    });
  });

  test('entities filtered by persons matches snapshot', async ({ page }) => {
    await setupApiMocks(page, {
      ...defaultMockConfig,
      entities: mockEntities,
    });
    const entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();

    // Filter by persons
    await entitiesPage.filterByType('person');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('entities-filtered-persons.png', {
      fullPage: true,
      mask: [page.locator('time'), page.locator('img')],
    });
  });

  test('entities filtered by vehicles matches snapshot', async ({ page }) => {
    await setupApiMocks(page, {
      ...defaultMockConfig,
      entities: mockEntities,
    });
    const entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();

    // Filter by vehicles
    await entitiesPage.filterByType('vehicle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('entities-filtered-vehicles.png', {
      fullPage: true,
      mask: [page.locator('time'), page.locator('img')],
    });
  });
});
