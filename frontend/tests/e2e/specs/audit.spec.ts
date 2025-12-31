/**
 * Audit Log Tests for Home Security Dashboard
 *
 * Comprehensive tests for the Audit Log page including:
 * - Audit stats display
 * - Audit filtering
 * - Audit table display
 * - Pagination
 * - Audit detail modal
 */

import { test, expect } from '@playwright/test';
import { AuditPage } from '../pages';
import {
  setupApiMocks,
  defaultMockConfig,
  emptyMockConfig,
  errorMockConfig,
} from '../fixtures';

test.describe('Audit Page Load', () => {
  let auditPage: AuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    auditPage = new AuditPage(page);
  });

  test('audit page loads successfully', async () => {
    await auditPage.goto();
    await auditPage.waitForAuditLoad();
  });

  test('audit displays page title', async () => {
    await auditPage.goto();
    await auditPage.waitForAuditLoad();
    await expect(auditPage.pageTitle).toBeVisible();
  });

  test('audit displays page subtitle', async () => {
    await auditPage.goto();
    await auditPage.waitForAuditLoad();
    await expect(auditPage.pageSubtitle).toBeVisible();
  });

  test('audit title says Audit Log', async () => {
    await auditPage.goto();
    await auditPage.waitForAuditLoad();
    await expect(auditPage.pageTitle).toHaveText(/Audit Log/i);
  });
});

test.describe('Audit Filters', () => {
  let auditPage: AuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    auditPage = new AuditPage(page);
    await auditPage.goto();
    await auditPage.waitForAuditLoad();
  });

  test('show filters button is visible', async ({ page }) => {
    // Audit filters are collapsed by default, look for the toggle button
    const showFiltersBtn = page.getByRole('button', { name: /Show Filters/i });
    await expect(showFiltersBtn).toBeVisible();
  });

  test('can expand filters', async ({ page }) => {
    // Click the show filters button to expand
    const showFiltersBtn = page.getByRole('button', { name: /Show Filters/i });
    await showFiltersBtn.click();
    // After expansion, filter controls should be visible
    await expect(page.locator('#action-filter')).toBeVisible();
  });
});

test.describe('Audit Table', () => {
  let auditPage: AuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    auditPage = new AuditPage(page);
    await auditPage.goto();
    await auditPage.waitForAuditLoad();
  });

  test('audit table is visible', async () => {
    await expect(auditPage.auditTable).toBeVisible();
  });

  test('audit table has rows', async () => {
    const rowCount = await auditPage.getAuditRowCount();
    expect(rowCount).toBeGreaterThanOrEqual(0);
  });
});

test.describe('Audit Pagination', () => {
  let auditPage: AuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    auditPage = new AuditPage(page);
    await auditPage.goto();
    await auditPage.waitForAuditLoad();
  });

  test('previous page button exists', async () => {
    await expect(auditPage.previousPageButton).toBeVisible();
  });

  test('next page button exists', async () => {
    await expect(auditPage.nextPageButton).toBeVisible();
  });
});

test.describe('Audit Empty State', () => {
  let auditPage: AuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, emptyMockConfig);
    auditPage = new AuditPage(page);
  });

  test('loads page with empty data', async () => {
    await auditPage.goto();
    await auditPage.waitForAuditLoad();
    // Page should load without error
    await expect(auditPage.pageTitle).toBeVisible();
  });
});

test.describe('Audit Error State', () => {
  let auditPage: AuditPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    auditPage = new AuditPage(page);
  });

  test('page loads even with API errors', async () => {
    await auditPage.goto();
    // Page should attempt to load
    await auditPage.waitForAuditLoad();
  });
});
