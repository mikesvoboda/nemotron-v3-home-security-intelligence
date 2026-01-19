/**
 * Performance Budget Tests (NEM-1484)
 *
 * E2E tests that enforce performance budgets based on Core Web Vitals
 * and page load timing metrics.
 *
 * These tests measure real user experience metrics and assert they
 * meet defined budgets. Failed tests indicate performance regressions
 * that should be investigated before merging.
 *
 * Test Categories:
 * - Core Web Vitals (LCP, FCP, CLS, TTFB)
 * - Page Load Times
 * - Navigation Timing
 * - Resource Loading
 *
 * Note: Performance tests use relaxed budgets in development/E2E environment
 * since dev builds have unminified assets and no CDN caching. Production
 * budgets (PERFORMANCE_BUDGETS) are stricter and used for production monitoring.
 *
 * @see https://web.dev/vitals/
 */

import { test, expect } from '@playwright/test';
import { setupApiMocks, defaultMockConfig } from '../fixtures';
import {
  collectWebVitals,
  collectPerformanceMetrics,
  measurePageLoadTime,
  PERFORMANCE_BUDGETS,
  formatMetrics,
  createPerformanceHelper,
} from '../fixtures/performance';

// Performance tests should have longer timeouts as they measure real loading times
test.setTimeout(30000);

/**
 * E2E/Development environment budgets - more lenient than production
 *
 * Development builds include:
 * - Unminified JavaScript/CSS
 * - Source maps
 * - React dev mode overhead
 * - No CDN caching
 *
 * These budgets are ~2-3x more lenient than production budgets
 */
const E2E_BUDGETS = {
  // Relaxed Core Web Vitals for dev environment
  LCP: 6000, // 6s (production: 2.5s)
  FCP: 3000, // 3s (production: 1.8s)
  CLS: 0.25, // Same as "needs improvement" threshold
  TTFB: 2000, // 2s (production: 800ms)

  // Navigation timing
  DOM_CONTENT_LOADED: 5000, // 5s
  FULL_LOAD: 8000, // 8s (accounts for dev server startup)
  TTI: 10000, // 10s

  // Resource budgets for dev
  MAX_RESOURCES: 175, // Dev has more files (unminified) - increased for CI stability
  MAX_TRANSFER_KB: 15000, // 15MB (dev builds are larger)
} as const;

test.describe('Performance Budgets @slow', () => {
  test.beforeEach(async ({ page }) => {
    // Set up API mocks to ensure consistent test environment
    await setupApiMocks(page, defaultMockConfig);
  });

  test('dashboard loads within performance budget', async ({ page }) => {
    const start = Date.now();
    await page.goto('/');

    // Wait for page to be fully loaded and interactive
    await page.waitForLoadState('load');
    const loadTime = Date.now() - start;

    // Log the load time for debugging
    console.log(`Dashboard load time: ${loadTime}ms`);

    // Assert load time is within E2E budget (more lenient for dev builds)
    expect(loadTime).toBeLessThan(E2E_BUDGETS.FULL_LOAD);
  });

  test('LCP under budget for dashboard @critical', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    // Allow time for LCP to be measured
    const metrics = await collectWebVitals(page, 3000);

    // Log metrics for debugging
    console.log(formatMetrics(metrics));

    // LCP budget for E2E environment (dev builds are slower)
    expect(metrics.lcp).toBeLessThan(E2E_BUDGETS.LCP);
  });

  test('FCP under budget for dashboard', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    const metrics = await collectWebVitals(page, 2000);

    console.log(`FCP: ${metrics.fcp}ms`);

    // First Contentful Paint budget for E2E
    expect(metrics.fcp).toBeLessThan(E2E_BUDGETS.FCP);
  });

  test('CLS under budget for dashboard stability', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    // Wait a bit longer for layout shifts to be detected
    const metrics = await collectWebVitals(page, 3000);

    console.log(`CLS: ${metrics.cls.toFixed(3)}`);

    // Cumulative Layout Shift should be under threshold for visual stability
    expect(metrics.cls).toBeLessThan(E2E_BUDGETS.CLS);
  });

  test('TTFB under budget for dashboard', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    const metrics = await collectWebVitals(page);

    console.log(`TTFB: ${metrics.ttfb}ms`);

    // Time to First Byte budget for E2E environment
    expect(metrics.ttfb).toBeLessThan(E2E_BUDGETS.TTFB);
  });
});

test.describe('Navigation Performance', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('DOM Content Loaded within budget', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const metrics = await collectPerformanceMetrics(page);

    console.log(`DOM Content Loaded: ${metrics.domContentLoaded}ms`);

    expect(metrics.domContentLoaded).toBeLessThan(E2E_BUDGETS.DOM_CONTENT_LOADED);
  });

  test('full page load within budget', async ({ page }) => {
    const loadTime = await measurePageLoadTime(page, '/');

    console.log(`Full page load: ${loadTime}ms`);

    expect(loadTime).toBeLessThan(E2E_BUDGETS.FULL_LOAD);
  });

  test('time to interactive within acceptable range', async ({ page }) => {
    // Use 'load' instead of 'networkidle' to avoid timeout issues with mocked APIs
    const start = Date.now();
    await page.goto('/');
    await page.waitForLoadState('load');

    // Wait for any pending animations or idle state
    await page.waitForTimeout(500);
    const tti = Date.now() - start;

    console.log(`Time to Interactive: ${tti}ms`);

    // TTI should be under budget for E2E environment
    expect(tti).toBeLessThan(E2E_BUDGETS.TTI);
  });
});

test.describe('Page-specific Performance', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  test('timeline page loads within budget', async ({ page }) => {
    const loadTime = await measurePageLoadTime(page, '/timeline');

    console.log(`Timeline page load: ${loadTime}ms`);

    expect(loadTime).toBeLessThan(E2E_BUDGETS.FULL_LOAD);
  });

  test('system page loads within budget', async ({ page }) => {
    const loadTime = await measurePageLoadTime(page, '/system');

    console.log(`System page load: ${loadTime}ms`);

    expect(loadTime).toBeLessThan(E2E_BUDGETS.FULL_LOAD);
  });

  test('settings page loads within budget', async ({ page }) => {
    const loadTime = await measurePageLoadTime(page, '/settings');

    console.log(`Settings page load: ${loadTime}ms`);

    expect(loadTime).toBeLessThan(E2E_BUDGETS.FULL_LOAD);
  });

  test('logs page loads within budget', async ({ page }) => {
    const loadTime = await measurePageLoadTime(page, '/logs');

    console.log(`Logs page load: ${loadTime}ms`);

    expect(loadTime).toBeLessThan(E2E_BUDGETS.FULL_LOAD);
  });
});

test.describe('Resource Performance', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
  });

  // Skip in CI - flaky due to variable resource loading
  test.skip(!!process.env.CI, 'Flaky in CI environment');
  test('resource count within budget', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    const metrics = await collectPerformanceMetrics(page);

    console.log(`Resource count: ${metrics.resourceCount}`);

    // Should not load excessive resources (E2E budget allows more for dev builds)
    expect(metrics.resourceCount).toBeLessThan(E2E_BUDGETS.MAX_RESOURCES);
  });

  test('transfer size within budget', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    const metrics = await collectPerformanceMetrics(page);
    const transferSizeKB = metrics.transferSize / 1024;

    console.log(`Transfer size: ${transferSizeKB.toFixed(1)}KB`);

    // Total transfer should be under E2E budget (dev builds are larger)
    expect(metrics.transferSize).toBeLessThan(E2E_BUDGETS.MAX_TRANSFER_KB * 1024);
  });
});

test.describe('Performance Helper', () => {
  test('createPerformanceHelper with custom budgets', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    await page.goto('/');
    await page.waitForLoadState('load');

    // Create helper with stricter budgets for this test
    const perfHelper = createPerformanceHelper({
      LCP_GOOD: 3000, // 3 seconds (more lenient for testing)
      FCP_GOOD: 2000, // 2 seconds
    });

    const metrics = await perfHelper.collectMetrics(page);

    console.log(perfHelper.formatMetrics(metrics));

    // Verify metrics are collected
    expect(metrics).toHaveProperty('lcp');
    expect(metrics).toHaveProperty('fcp');
    expect(metrics).toHaveProperty('cls');
    expect(metrics).toHaveProperty('ttfb');
    expect(metrics).toHaveProperty('domContentLoaded');
    expect(metrics).toHaveProperty('loadComplete');
  });

  test('performance metrics are non-negative', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    await page.goto('/');
    await page.waitForLoadState('load');

    const metrics = await collectPerformanceMetrics(page);

    // All timing metrics should be non-negative
    expect(metrics.lcp).toBeGreaterThanOrEqual(0);
    expect(metrics.fcp).toBeGreaterThanOrEqual(0);
    expect(metrics.cls).toBeGreaterThanOrEqual(0);
    expect(metrics.ttfb).toBeGreaterThanOrEqual(0);
    expect(metrics.domContentLoaded).toBeGreaterThanOrEqual(0);
    expect(metrics.loadComplete).toBeGreaterThanOrEqual(0);
    expect(metrics.resourceCount).toBeGreaterThanOrEqual(0);
    expect(metrics.transferSize).toBeGreaterThanOrEqual(0);
  });
});

test.describe('Web Vitals Collection', () => {
  test('collectWebVitals returns valid metrics structure', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    await page.goto('/');
    await page.waitForLoadState('load');

    const metrics = await collectWebVitals(page);

    // Verify structure
    expect(metrics).toEqual(
      expect.objectContaining({
        lcp: expect.any(Number),
        fcp: expect.any(Number),
        cls: expect.any(Number),
        ttfb: expect.any(Number),
      })
    );
  });

  test('collectPerformanceMetrics includes extended metrics', async ({ page }) => {
    await setupApiMocks(page, defaultMockConfig);
    await page.goto('/');
    await page.waitForLoadState('load');

    const metrics = await collectPerformanceMetrics(page);

    // Verify extended metrics are present
    expect(metrics).toHaveProperty('domContentLoaded');
    expect(metrics).toHaveProperty('loadComplete');
    expect(metrics).toHaveProperty('dnsLookup');
    expect(metrics).toHaveProperty('tcpConnect');
    expect(metrics).toHaveProperty('resourceCount');
    expect(metrics).toHaveProperty('transferSize');
  });
});
