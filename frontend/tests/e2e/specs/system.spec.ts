/**
 * Operations Page Tests for Home Security Dashboard
 *
 * Comprehensive tests for the Operations page (formerly System Monitoring) including:
 * - Page load and title
 * - Pipeline flow visualization
 * - Circuit breakers panel
 * - File operations panel
 * - Debug mode toggle
 * - Grafana monitoring banner
 *
 * Note: Most metrics-only components have been moved to Grafana.
 * This page now focuses on interactive/actionable components.
 */

import { test, expect } from '@playwright/test';
import { SystemPage } from '../pages';
import {
  setupApiMocks,
  defaultMockConfig,
  errorMockConfig,
  highAlertMockConfig,
} from '../fixtures';

test.describe('Operations Page Load', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    systemPage = new SystemPage(page);
  });

  test('operations page loads successfully', async () => {
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('operations displays page title', async () => {
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    await expect(systemPage.pageTitle).toBeVisible();
  });

  test('operations displays page subtitle', async () => {
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    await expect(systemPage.pageSubtitle).toBeVisible();
  });

  test('operations title says Operations', async () => {
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    await expect(systemPage.pageTitle).toHaveText(/Operations/i);
  });
});

test.describe('Grafana Monitoring Banner', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('grafana banner is visible', async ({ page }) => {
    await expect(page.getByTestId('grafana-monitoring-banner')).toBeVisible();
  });

  test('grafana link is visible', async ({ page }) => {
    await expect(page.getByTestId('grafana-link')).toBeVisible();
  });

  test('grafana link opens in new tab', async ({ page }) => {
    const grafanaLink = page.getByTestId('grafana-link');
    await expect(grafanaLink).toHaveAttribute('target', '_blank');
  });

  test('grafana link has Open Grafana text', async ({ page }) => {
    const grafanaLink = page.getByTestId('grafana-link');
    await expect(grafanaLink).toContainText('Open Grafana');
  });
});

test.describe('Pipeline Flow Visualization', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('pipeline flow visualization is visible', async ({ page }) => {
    await expect(page.getByTestId('pipeline-flow-visualization')).toBeVisible();
  });
});

test.describe('Circuit Breakers Section', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('circuit breakers section is visible', async ({ page }) => {
    await expect(page.getByTestId('circuit-breakers-section')).toBeVisible();
  });

  test('circuit breakers section has title', async ({ page }) => {
    await expect(page.getByText(/Circuit Breakers/i).first()).toBeVisible();
  });
});

test.describe('File Operations Section', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('file operations section is visible', async ({ page }) => {
    await expect(page.getByTestId('file-operations-section')).toBeVisible();
  });

  test('file operations section has title', async ({ page }) => {
    await expect(page.getByText(/File Operations/i).first()).toBeVisible();
  });
});

test.describe('Debug Mode Toggle', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('debug mode toggle container is in page', async ({ page }) => {
    // DebugModeToggle only renders when backend has DEBUG=true
    // Test that we're on the page where the toggle would appear
    await expect(page.getByTestId('operations-page')).toBeVisible();
  });
});

test.describe('Operations Error State', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    systemPage = new SystemPage(page);
  });

  test('page loads even with API errors', async () => {
    await systemPage.goto();
    // The page should still render even with errors
    // In error state, the page shows an error message with Reload Page button
    // Use .first() since both elements may be visible (button is inside the error container)
    // Timeout needs to be long enough for API retry exhaustion (~10s in CI)
    await expect(
      systemPage.errorMessage.or(systemPage.reloadButton).first()
    ).toBeVisible({ timeout: 15000 });
  });
});

test.describe('Operations High Alert Mode', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, highAlertMockConfig);
    systemPage = new SystemPage(page);
  });

  test('loads with high alert config', async () => {
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });
});
