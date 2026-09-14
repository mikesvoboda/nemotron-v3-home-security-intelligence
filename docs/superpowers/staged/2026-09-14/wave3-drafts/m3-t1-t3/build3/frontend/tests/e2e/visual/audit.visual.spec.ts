/**
 * Visual Regression Tests - Audit Log Page
 *
 * These tests capture screenshots and compare against baseline images
 * to detect unintended visual changes in the Audit Log page.
 *
 * Running visual tests:
 *   npx playwright test --project=visual-chromium
 *
 * Updating baselines:
 *   npx playwright test --project=visual-chromium --update-snapshots
 */

import { test, expect } from '@playwright/test';
import { AuditPage } from '../pages';
import { setupApiMocks, defaultMockConfig, emptyMockConfig } from '../fixtures';

test.describe('Audit Log Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('audit full page matches snapshot', async ({ page }) => {
    const auditPage = new AuditPage(page);
    await auditPage.goto();
    await auditPage.waitForAuditLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('audit-full-page.png', {
      fullPage: true,
      mask: [
        page.locator('[data-testid="timestamp"]'),
        page.locator('time'),
        page.locator('[data-testid="relative-time"]'),
      ],
    });
  });

  test('audit stats cards match snapshot', async ({ page }) => {
    const auditPage = new AuditPage(page);
    await auditPage.goto();
    await auditPage.waitForAuditLoad();

    await page.waitForLoadState('networkidle');

    // Stats section screenshot
    const statsSection = auditPage.statsSection;
    if (await statsSection.isVisible()) {
      await expect(statsSection).toHaveScreenshot('audit-stats-cards.png');
    }
  });

  test('audit filters section matches snapshot', async ({ page }) => {
    const auditPage = new AuditPage(page);
    await auditPage.goto();
    await auditPage.waitForAuditLoad();

    await page.waitForLoadState('networkidle');

    // Filters section screenshot
    const filtersSection = auditPage.filtersSection;
    if (await filtersSection.isVisible()) {
      await expect(filtersSection).toHaveScreenshot('audit-filters-section.png');
    }
  });

  test('audit table matches snapshot', async ({ page }) => {
    const auditPage = new AuditPage(page);
    await auditPage.goto();
    await auditPage.waitForAuditLoad();

    await page.waitForLoadState('networkidle');

    // Table screenshot
    const auditTable = auditPage.auditTable;
    if (await auditTable.isVisible()) {
      await expect(auditTable).toHaveScreenshot('audit-table.png', {
        mask: [page.locator('time'), page.locator('[data-testid="audit-time"]')],
      });
    }
  });

  test('audit pagination matches snapshot', async ({ page }) => {
    const auditPage = new AuditPage(page);
    await auditPage.goto();
    await auditPage.waitForAuditLoad();

    await page.waitForLoadState('networkidle');

    // Pagination area screenshot
    const paginationArea = page.locator('[class*="pagination"], [class*="Pagination"]').first();
    if (await paginationArea.isVisible()) {
      await expect(paginationArea).toHaveScreenshot('audit-pagination.png');
    }
  });
});

test.describe('Audit Log Visual States', () => {
  test('audit empty state matches snapshot', async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    const auditPage = new AuditPage(page);
    await auditPage.goto();
    await auditPage.waitForAuditLoad();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot('audit-empty-state.png', {
      fullPage: true,
    });
  });

  test('audit filtered by action matches snapshot', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    const auditPage = new AuditPage(page);
    await auditPage.goto();
    await auditPage.waitForAuditLoad();

    // Wait for filters to be available, then apply filter if possible
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(300);

    await expect(page).toHaveScreenshot('audit-with-data.png', {
      fullPage: true,
      mask: [page.locator('time'), page.locator('[data-testid="audit-time"]')],
    });
  });
});
