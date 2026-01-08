/**
 * Performance Fixtures for E2E Tests (NEM-1484)
 *
 * Provides utilities for collecting Core Web Vitals and enforcing
 * performance budgets in E2E tests.
 *
 * Core Web Vitals measured:
 * - LCP (Largest Contentful Paint): Should be < 2.5s for good UX
 * - FCP (First Contentful Paint): Should be < 1.8s for good UX
 * - CLS (Cumulative Layout Shift): Should be < 0.1 for good UX
 * - TTFB (Time to First Byte): Should be < 800ms for good UX
 *
 * @see https://web.dev/vitals/
 */

import type { Page } from '@playwright/test';

/**
 * Core Web Vitals metrics collected from the browser
 */
export interface WebVitalsMetrics {
  /** Largest Contentful Paint in milliseconds */
  lcp: number;
  /** First Contentful Paint in milliseconds */
  fcp: number;
  /** Cumulative Layout Shift (unitless) */
  cls: number;
  /** Time to First Byte in milliseconds */
  ttfb: number;
}

/**
 * Extended performance metrics including navigation timing
 */
export interface PerformanceMetrics extends WebVitalsMetrics {
  /** DOM Content Loaded time in milliseconds */
  domContentLoaded: number;
  /** Full page load time in milliseconds */
  loadComplete: number;
  /** DNS lookup time in milliseconds */
  dnsLookup: number;
  /** TCP connection time in milliseconds */
  tcpConnect: number;
  /** Total resource count */
  resourceCount: number;
  /** Total transferred bytes */
  transferSize: number;
}

/**
 * Performance budget thresholds based on Google's Core Web Vitals guidelines
 *
 * Good: Metrics at or below these values indicate good performance
 * Needs Improvement: Above good but below poor
 * Poor: Above these values indicates poor performance
 */
export const PERFORMANCE_BUDGETS = {
  // Core Web Vitals (Good thresholds)
  LCP_GOOD: 2500, // 2.5 seconds
  LCP_POOR: 4000, // 4 seconds
  FCP_GOOD: 1800, // 1.8 seconds
  FCP_POOR: 3000, // 3 seconds
  CLS_GOOD: 0.1,
  CLS_POOR: 0.25,
  TTFB_GOOD: 800, // 800ms
  TTFB_POOR: 1800, // 1.8 seconds

  // Navigation timing budgets
  DOM_CONTENT_LOADED: 3000, // 3 seconds
  FULL_LOAD: 5000, // 5 seconds

  // Resource budgets
  MAX_RESOURCE_COUNT: 100,
  MAX_TRANSFER_SIZE_KB: 2000, // 2MB
} as const;

/**
 * Collects Core Web Vitals metrics from the browser using PerformanceObserver API
 *
 * Note: Some metrics (LCP, CLS) require interaction or may not be available
 * until certain page events occur. This function waits for metrics to stabilize.
 *
 * @param page - Playwright Page object
 * @param timeout - Maximum time to wait for metrics (default: 5000ms)
 * @returns Promise resolving to WebVitalsMetrics
 *
 * @example
 * ```typescript
 * const metrics = await collectWebVitals(page);
 * expect(metrics.lcp).toBeLessThan(PERFORMANCE_BUDGETS.LCP_GOOD);
 * ```
 */
export async function collectWebVitals(page: Page, timeout: number = 5000): Promise<WebVitalsMetrics> {
  // Inject Web Vitals collection script and wait for metrics
  const metrics = await page.evaluate(
    async (timeoutMs) => {
      return new Promise<WebVitalsMetrics>((resolve) => {
        const results: Partial<WebVitalsMetrics> = {
          lcp: 0,
          fcp: 0,
          cls: 0,
          ttfb: 0,
        };

        // Collect TTFB from Navigation Timing API
        const navEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
        if (navEntry) {
          results.ttfb = navEntry.responseStart - navEntry.requestStart;
        }

        // Collect FCP from Paint Timing API
        const paintEntries = performance.getEntriesByType('paint');
        const fcpEntry = paintEntries.find((entry) => entry.name === 'first-contentful-paint');
        if (fcpEntry) {
          results.fcp = fcpEntry.startTime;
        }

        // Collect LCP using PerformanceObserver
        let lcpValue = 0;
        const lcpObserver = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          // LCP is the largest contentful paint observed so far
          const lastEntry = entries[entries.length - 1];
          lcpValue = lastEntry.startTime;
        });

        try {
          lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });
        } catch {
          // LCP not supported in this browser
        }

        // Collect CLS using PerformanceObserver
        let clsValue = 0;
        const clsObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            // Only count shifts without recent user input
            if (!(entry as PerformanceEntry & { hadRecentInput?: boolean }).hadRecentInput) {
              clsValue += (entry as PerformanceEntry & { value?: number }).value || 0;
            }
          }
        });

        try {
          clsObserver.observe({ type: 'layout-shift', buffered: true });
        } catch {
          // CLS not supported in this browser
        }

        // Wait for metrics to stabilize, then resolve
        setTimeout(() => {
          lcpObserver.disconnect();
          clsObserver.disconnect();

          results.lcp = lcpValue;
          results.cls = clsValue;

          resolve(results as WebVitalsMetrics);
        }, Math.min(timeoutMs, 3000));
      });
    },
    [timeout]
  );

  return metrics;
}

/**
 * Collects extended performance metrics including navigation timing and resource data
 *
 * @param page - Playwright Page object
 * @returns Promise resolving to PerformanceMetrics
 *
 * @example
 * ```typescript
 * const metrics = await collectPerformanceMetrics(page);
 * expect(metrics.loadComplete).toBeLessThan(PERFORMANCE_BUDGETS.FULL_LOAD);
 * expect(metrics.transferSize).toBeLessThan(PERFORMANCE_BUDGETS.MAX_TRANSFER_SIZE_KB * 1024);
 * ```
 */
export async function collectPerformanceMetrics(page: Page): Promise<PerformanceMetrics> {
  // First collect Web Vitals
  const webVitals = await collectWebVitals(page);

  // Then collect extended metrics
  const extendedMetrics = await page.evaluate(() => {
    const navEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    const resourceEntries = performance.getEntriesByType('resource') as PerformanceResourceTiming[];

    let totalTransferSize = 0;
    for (const entry of resourceEntries) {
      totalTransferSize += entry.transferSize || 0;
    }

    return {
      domContentLoaded: navEntry ? navEntry.domContentLoadedEventEnd - navEntry.startTime : 0,
      loadComplete: navEntry ? navEntry.loadEventEnd - navEntry.startTime : 0,
      dnsLookup: navEntry ? navEntry.domainLookupEnd - navEntry.domainLookupStart : 0,
      tcpConnect: navEntry ? navEntry.connectEnd - navEntry.connectStart : 0,
      resourceCount: resourceEntries.length,
      transferSize: totalTransferSize,
    };
  });

  return {
    ...webVitals,
    ...extendedMetrics,
  };
}

/**
 * Measures page load time from navigation start to load complete
 *
 * @param page - Playwright Page object
 * @param url - URL to navigate to
 * @returns Promise resolving to load time in milliseconds
 *
 * @example
 * ```typescript
 * const loadTime = await measurePageLoadTime(page, '/');
 * expect(loadTime).toBeLessThan(3000);
 * ```
 */
export async function measurePageLoadTime(page: Page, url: string): Promise<number> {
  const start = Date.now();
  await page.goto(url, { waitUntil: 'load' });
  return Date.now() - start;
}

/**
 * Measures time to interactive - when the page becomes reliably interactive
 *
 * This is approximated by waiting for the main thread to be idle
 * (no long tasks blocking for > 50ms)
 *
 * @param page - Playwright Page object
 * @param url - URL to navigate to
 * @returns Promise resolving to TTI in milliseconds
 */
export async function measureTimeToInteractive(page: Page, url: string): Promise<number> {
  const start = Date.now();
  await page.goto(url, { waitUntil: 'networkidle' });

  // Wait for any pending animations or microtasks
  await page.evaluate(() => {
    return new Promise<void>((resolve) => {
      requestIdleCallback(() => resolve(), { timeout: 1000 });
    });
  });

  return Date.now() - start;
}

/**
 * Asserts that all Core Web Vitals are within "good" thresholds
 *
 * @param metrics - WebVitalsMetrics to validate
 * @throws Error if any metric exceeds the good threshold
 *
 * @example
 * ```typescript
 * const metrics = await collectWebVitals(page);
 * assertGoodWebVitals(metrics); // Throws if any metric is poor
 * ```
 */
export function assertGoodWebVitals(metrics: WebVitalsMetrics): void {
  const issues: string[] = [];

  if (metrics.lcp > PERFORMANCE_BUDGETS.LCP_GOOD) {
    issues.push(`LCP ${metrics.lcp}ms exceeds ${PERFORMANCE_BUDGETS.LCP_GOOD}ms threshold`);
  }
  if (metrics.fcp > PERFORMANCE_BUDGETS.FCP_GOOD) {
    issues.push(`FCP ${metrics.fcp}ms exceeds ${PERFORMANCE_BUDGETS.FCP_GOOD}ms threshold`);
  }
  if (metrics.cls > PERFORMANCE_BUDGETS.CLS_GOOD) {
    issues.push(`CLS ${metrics.cls.toFixed(3)} exceeds ${PERFORMANCE_BUDGETS.CLS_GOOD} threshold`);
  }
  if (metrics.ttfb > PERFORMANCE_BUDGETS.TTFB_GOOD) {
    issues.push(`TTFB ${metrics.ttfb}ms exceeds ${PERFORMANCE_BUDGETS.TTFB_GOOD}ms threshold`);
  }

  if (issues.length > 0) {
    throw new Error(`Web Vitals budget exceeded:\n${issues.join('\n')}`);
  }
}

/**
 * Formats performance metrics for logging/reporting
 *
 * @param metrics - PerformanceMetrics or WebVitalsMetrics to format
 * @returns Formatted string representation
 */
export function formatMetrics(metrics: Partial<PerformanceMetrics>): string {
  const lines: string[] = ['Performance Metrics:'];

  if (metrics.lcp !== undefined) {
    const lcpStatus = metrics.lcp <= PERFORMANCE_BUDGETS.LCP_GOOD ? 'GOOD' : 'POOR';
    lines.push(`  LCP: ${metrics.lcp.toFixed(0)}ms [${lcpStatus}]`);
  }
  if (metrics.fcp !== undefined) {
    const fcpStatus = metrics.fcp <= PERFORMANCE_BUDGETS.FCP_GOOD ? 'GOOD' : 'POOR';
    lines.push(`  FCP: ${metrics.fcp.toFixed(0)}ms [${fcpStatus}]`);
  }
  if (metrics.cls !== undefined) {
    const clsStatus = metrics.cls <= PERFORMANCE_BUDGETS.CLS_GOOD ? 'GOOD' : 'POOR';
    lines.push(`  CLS: ${metrics.cls.toFixed(3)} [${clsStatus}]`);
  }
  if (metrics.ttfb !== undefined) {
    const ttfbStatus = metrics.ttfb <= PERFORMANCE_BUDGETS.TTFB_GOOD ? 'GOOD' : 'POOR';
    lines.push(`  TTFB: ${metrics.ttfb.toFixed(0)}ms [${ttfbStatus}]`);
  }
  if (metrics.domContentLoaded !== undefined) {
    lines.push(`  DOM Content Loaded: ${metrics.domContentLoaded.toFixed(0)}ms`);
  }
  if (metrics.loadComplete !== undefined) {
    lines.push(`  Load Complete: ${metrics.loadComplete.toFixed(0)}ms`);
  }
  if (metrics.resourceCount !== undefined) {
    lines.push(`  Resource Count: ${metrics.resourceCount}`);
  }
  if (metrics.transferSize !== undefined) {
    lines.push(`  Transfer Size: ${(metrics.transferSize / 1024).toFixed(1)}KB`);
  }

  return lines.join('\n');
}

/**
 * Creates a performance budget test helper that can be used across multiple pages
 *
 * @param budgets - Custom budget overrides
 * @returns Object with test helper methods
 *
 * @example
 * ```typescript
 * const perfHelper = createPerformanceHelper({
 *   LCP_GOOD: 2000, // Stricter LCP budget
 * });
 *
 * test('page meets performance budget', async ({ page }) => {
 *   await page.goto('/');
 *   await perfHelper.assertPagePerformance(page);
 * });
 * ```
 */
export function createPerformanceHelper(budgets: Partial<typeof PERFORMANCE_BUDGETS> = {}) {
  const effectiveBudgets = { ...PERFORMANCE_BUDGETS, ...budgets };

  return {
    budgets: effectiveBudgets,

    async collectMetrics(page: Page): Promise<PerformanceMetrics> {
      return collectPerformanceMetrics(page);
    },

    async assertPagePerformance(page: Page): Promise<PerformanceMetrics> {
      const metrics = await collectPerformanceMetrics(page);

      if (metrics.lcp > effectiveBudgets.LCP_GOOD) {
        throw new Error(`LCP ${metrics.lcp}ms exceeds budget of ${effectiveBudgets.LCP_GOOD}ms`);
      }
      if (metrics.fcp > effectiveBudgets.FCP_GOOD) {
        throw new Error(`FCP ${metrics.fcp}ms exceeds budget of ${effectiveBudgets.FCP_GOOD}ms`);
      }
      if (metrics.cls > effectiveBudgets.CLS_GOOD) {
        throw new Error(`CLS ${metrics.cls} exceeds budget of ${effectiveBudgets.CLS_GOOD}`);
      }

      return metrics;
    },

    formatMetrics,
  };
}
