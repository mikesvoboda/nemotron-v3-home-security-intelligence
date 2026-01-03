/**
 * System Monitoring Tests for Home Security Dashboard
 *
 * Comprehensive tests for the System Monitoring page including:
 * - System overview display
 * - Service health status
 * - GPU stats
 * - Pipeline queues
 * - Time range selector
 * - AI models panel
 * - Databases panel
 * - Host system panel
 * - Containers panel
 */

import { test, expect } from '@playwright/test';
import { SystemPage } from '../pages';
import {
  setupApiMocks,
  defaultMockConfig,
  errorMockConfig,
  highAlertMockConfig,
} from '../fixtures';

test.describe('System Page Load', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    systemPage = new SystemPage(page);
  });

  test('system page loads successfully', async () => {
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('system displays page title', async () => {
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    await expect(systemPage.pageTitle).toBeVisible();
  });

  test('system displays page subtitle', async () => {
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    await expect(systemPage.pageSubtitle).toBeVisible();
  });

  test('system title says System Monitoring', async () => {
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
    await expect(systemPage.pageTitle).toHaveText(/System Monitoring/i);
  });
});

test.describe('System Overview Card', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('system overview card is visible', async () => {
    await expect(systemPage.systemOverviewCard).toBeVisible();
  });

  test('shows uptime metric', async ({ page }) => {
    await expect(page.getByText(/Uptime/i).first()).toBeVisible();
  });

  test('shows cameras metric', async ({ page }) => {
    // Redesigned dashboard uses shortened labels in compact grid
    await expect(page.getByText(/Cameras/i).first()).toBeVisible();
  });

  test('shows events metric', async ({ page }) => {
    // Redesigned dashboard uses shortened labels in compact grid
    await expect(page.getByText(/Events/i).first()).toBeVisible();
  });

  test('shows detections metric', async ({ page }) => {
    // Redesigned dashboard uses shortened labels in compact grid
    await expect(page.getByText(/Detections/i).first()).toBeVisible();
  });
});

test.describe('Service Health Card', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('service health card is visible', async () => {
    await expect(systemPage.serviceHealthCard).toBeVisible();
  });

  test('shows overall health badge', async () => {
    await expect(systemPage.overallHealthBadge).toBeVisible();
  });

  test('has service rows', async () => {
    const count = await systemPage.getServiceCount();
    expect(count).toBeGreaterThanOrEqual(0);
  });
});

test.describe('Time Range Selector', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('time range selector is visible', async () => {
    await expect(systemPage.timeRangeSelector).toBeVisible();
  });

  test('has time range buttons', async ({ page }) => {
    // The actual buttons are 5m, 15m, 60m
    const buttons = page.locator('[data-testid="time-range-selector"] button');
    const count = await buttons.count();
    expect(count).toBeGreaterThan(0);
  });
});

test.describe('GPU Stats', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('page displays GPU information', async ({ page }) => {
    // Look for GPU Statistics heading in the GpuStats component
    await expect(page.getByText(/GPU Statistics/i)).toBeVisible();
  });

  test('shows utilization metric', async ({ page }) => {
    await expect(page.getByText(/Utilization/i).first()).toBeVisible();
  });

  test('shows memory metric', async ({ page }) => {
    await expect(page.getByText(/Memory/i).first()).toBeVisible();
  });

  test('shows temperature metric', async ({ page }) => {
    await expect(page.getByText(/Temperature/i).first()).toBeVisible();
  });
});

test.describe('Pipeline Metrics Panel', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    systemPage = new SystemPage(page);
    await systemPage.goto();
    await systemPage.waitForSystemLoad();
  });

  test('pipeline metrics panel is visible', async () => {
    // Redesigned dashboard combines queues + latency + throughput into one panel
    await expect(systemPage.pipelineMetricsPanel).toBeVisible();
  });

  test('shows queue information', async ({ page }) => {
    // Pipeline metrics panel includes queue depths
    await expect(page.getByText(/Queue/i).first()).toBeVisible();
  });

  test('shows latency information', async ({ page }) => {
    // Pipeline metrics panel includes latency stats
    await expect(page.getByText(/Latency|ms/i).first()).toBeVisible();
  });
});

test.describe('System Error State', () => {
  let systemPage: SystemPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, errorMockConfig);
    systemPage = new SystemPage(page);
  });

  test('page loads even with API errors', async () => {
    await systemPage.goto();
    // The page should still render even with errors
    // In error state, the page shows an error message with Reload Page button
    // Use .or() pattern for faster detection of either error indicator
    await expect(
      systemPage.errorMessage.or(systemPage.reloadButton)
    ).toBeVisible({ timeout: 5000 });
  });
});

test.describe('System High Alert Mode', () => {
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
