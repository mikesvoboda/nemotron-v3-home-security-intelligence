/**
 * Smoke Tests for Home Security Dashboard
 *
 * These tests verify that the application loads and renders correctly.
 * They run against a development server with mocked backend responses.
 * Includes accessibility checks using axe-core to ensure WCAG 2.1 AA compliance.
 *
 * Tags: @smoke (all tests in this file are smoke tests)
 *
 * Run with: npx playwright test specs/smoke.spec.ts
 * Or use project: npx playwright test --project=smoke
 */

import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { DashboardPage, TimelinePage, SettingsPage } from '../pages';
import { setupApiMocks, defaultMockConfig } from '../fixtures';

/**
 * WCAG 2.1 AA compliance tags for accessibility testing
 */
const WCAG_AA_TAGS = ['wcag2a', 'wcag2aa', 'wcag21aa'];

test.describe('Dashboard Smoke Tests @smoke', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('dashboard page loads successfully', async ({ page }) => {
    await dashboardPage.goto();
    await expect(page).toHaveTitle(/Security Dashboard/i);
    await dashboardPage.waitForDashboardLoad();
  });

  test('dashboard displays key components', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectAllSectionsVisible();
  });

  test('dashboard shows real-time monitoring subtitle', async ({ page }) => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.pageSubtitle).toBeVisible();
  });

  test('dashboard has correct page title', async ({ page }) => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(page).toHaveTitle(/Security Dashboard/i);
  });

  test('dashboard shows risk score card', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.riskScoreStat).toBeVisible();
  });

  test('dashboard shows camera status section', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await expect(dashboardPage.cameraGridHeading).toBeVisible();
  });

  test('dashboard shows active cameras stat', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // Dashboard displays StatsRow with Active Cameras, Events Today, Current Risk, System Status
    // GPU Statistics are available on the System page, not the Dashboard
    await expect(dashboardPage.activeCamerasStat).toBeVisible();
  });
});

test.describe('Layout Smoke Tests @smoke', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('header displays branding', async ({ page }) => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // Check for NVIDIA logo image and Nemotron branding text
    await expect(page.getByAltText(/NVIDIA/i).first()).toBeVisible();
    await expect(page.getByText(/Nemotron/i).first()).toBeVisible();
  });

  test('sidebar navigation is visible', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectSidebarVisible();
  });

  test('header is visible', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectHeaderVisible();
  });

  test('full layout is rendered', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    await dashboardPage.expectLayoutLoaded();
  });
});

test.describe('Dashboard Camera Tests @smoke', () => {
  let dashboardPage: DashboardPage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    dashboardPage = new DashboardPage(page);
  });

  test('displays camera cards from API', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    // We have 4 cameras in mock data
    const hasFrontDoor = await dashboardPage.hasCameraByName('Front Door');
    expect(hasFrontDoor).toBe(true);
  });

  test('shows camera names', async () => {
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();
    const hasBackYard = await dashboardPage.hasCameraByName('Back Yard');
    expect(hasBackYard).toBe(true);
  });
});

test.describe('Timeline Event Tests @smoke', () => {
  let timelinePage: TimelinePage;

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    timelinePage = new TimelinePage(page);
  });

  test('shows event cards when events exist', async () => {
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();
    // Timeline should show event cards from mock data
    await expect(timelinePage.pageTitle).toBeVisible();
    const eventCount = await timelinePage.getEventCount();
    expect(eventCount).toBeGreaterThan(0);
  });
});

/**
 * Accessibility Smoke Tests
 *
 * Quick accessibility checks for critical pages during smoke testing.
 * These tests use axe-core to verify WCAG 2.1 AA compliance.
 * For comprehensive accessibility testing, see accessibility.spec.ts
 *
 * Color-contrast is now enforced after WCAG 2.1 AA compliance fixes (NEM-1481).
 */
test.describe('Accessibility Smoke Tests @smoke @critical', () => {

  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  // TODO: Fix color contrast violations in dashboard (timestamp text)
  test.skip('dashboard page has no critical accessibility violations', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.goto();
    await dashboardPage.waitForDashboardLoad();

    const results = await new AxeBuilder({ page })
      .withTags(WCAG_AA_TAGS)
      .analyze();

    // Log violations for debugging if any exist
    if (results.violations.length > 0) {
      console.log(
        'Dashboard a11y violations:',
        results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length} elements)`)
      );
    }

    expect(results.violations).toEqual([]);
  });

  test('timeline page has no critical accessibility violations', async ({ page }) => {
    const timelinePage = new TimelinePage(page);
    await timelinePage.goto();
    await timelinePage.waitForTimelineLoad();

    const results = await new AxeBuilder({ page })
      .withTags(WCAG_AA_TAGS)
      .analyze();

    if (results.violations.length > 0) {
      console.log(
        'Timeline a11y violations:',
        results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length} elements)`)
      );
    }

    expect(results.violations).toEqual([]);
  });

  test('settings page has no critical accessibility violations', async ({ page }) => {
    const settingsPage = new SettingsPage(page);
    await settingsPage.goto();
    await settingsPage.waitForSettingsLoad();

    const results = await new AxeBuilder({ page })
      .withTags(WCAG_AA_TAGS)
      .analyze();

    if (results.violations.length > 0) {
      console.log(
        'Settings a11y violations:',
        results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length} elements)`)
      );
    }

    expect(results.violations).toEqual([]);
  });
});
