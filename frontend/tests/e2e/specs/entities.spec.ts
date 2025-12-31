/**
 * Entities Tests for Home Security Dashboard
 *
 * Tests for the Entities page (Coming Soon placeholder).
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

test.describe('Entities Coming Soon', () => {
  let entitiesPage: EntitiesPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    entitiesPage = new EntitiesPage(page);
    await entitiesPage.goto();
    await entitiesPage.waitForEntitiesLoad();
  });

  test('shows coming soon message', async () => {
    const hasComingSoon = await entitiesPage.hasComingSoonMessage();
    expect(hasComingSoon).toBe(true);
  });

  test('coming soon heading says Coming Soon', async () => {
    await expect(entitiesPage.comingSoonHeading).toHaveText(/Coming Soon/i);
  });

  test('shows feature description', async () => {
    await expect(entitiesPage.comingSoonDescription).toBeVisible();
  });

  test('lists planned features', async () => {
    const featureCount = await entitiesPage.getFeatureCount();
    expect(featureCount).toBeGreaterThan(0);
  });

  test('shows check back message', async () => {
    await expect(entitiesPage.checkBackMessage).toBeVisible();
  });

  test('feature list mentions tracking', async () => {
    const featureText = await entitiesPage.getFeatureText(0);
    expect(featureText).toMatch(/track/i);
  });

  test('feature list mentions movement patterns', async () => {
    const featureText = await entitiesPage.getFeatureText(1);
    expect(featureText).toMatch(/movement|pattern/i);
  });

  test('feature list mentions classification', async () => {
    const featureText = await entitiesPage.getFeatureText(2);
    expect(featureText).toMatch(/classif|known/i);
  });

  test('feature list mentions search', async () => {
    const featureText = await entitiesPage.getFeatureText(3);
    expect(featureText).toMatch(/search|filter/i);
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
});
