/**
 * Real User Monitoring (RUM) service for Core Web Vitals tracking.
 *
 * This service collects Core Web Vitals metrics from real users using the
 * web-vitals library and sends them to the backend for storage and analysis.
 *
 * Core Web Vitals collected:
 * - LCP (Largest Contentful Paint): Loading performance
 * - FID (First Input Delay): Interactivity (legacy)
 * - INP (Interaction to Next Paint): Interactivity (new standard)
 * - CLS (Cumulative Layout Shift): Visual stability
 * - TTFB (Time to First Byte): Server response time
 * - FCP (First Contentful Paint): First content render
 *
 * NEM-1635: Implements RUM collection for production user monitoring.
 *
 * Usage:
 *   import { initRUM } from './rum';
 *
 *   // Initialize in main.tsx
 *   const rum = initRUM();
 *
 *   // Or with custom config
 *   const rum = initRUM({
 *     enabled: true,
 *     sessionId: 'user-session-123',
 *   });
 */

/**
 * Core Web Vital metric names supported by web-vitals library.
 */
export type WebVitalName = 'LCP' | 'FID' | 'INP' | 'CLS' | 'TTFB' | 'FCP';

/**
 * Rating values returned by web-vitals library.
 */
export type WebVitalRating = 'good' | 'needs-improvement' | 'poor';

/**
 * Web Vital metric structure matching web-vitals library output.
 */
export interface WebVitalMetric {
  /** Metric name (LCP, FID, INP, CLS, TTFB, FCP) */
  name: WebVitalName;
  /** Metric value (milliseconds for most, dimensionless for CLS) */
  value: number;
  /** Performance rating based on thresholds */
  rating: WebVitalRating;
  /** Delta since last report (for CLS this accumulates) */
  delta: number;
  /** Unique identifier for this metric instance */
  id: string;
  /** Navigation type (navigate, reload, back_forward, prerender) */
  navigationType?: string;
  /** Page path where metric was measured */
  path?: string;
}

/**
 * Configuration options for the RUM service.
 */
export interface RUMConfig {
  /** Backend endpoint for RUM data ingestion (default: '/api/rum') */
  endpoint: string;
  /** Whether RUM collection is enabled (default: true) */
  enabled: boolean;
  /** Number of metrics to accumulate before flushing (default: 5) */
  batchSize: number;
  /** Interval in ms between automatic flushes (default: 10000) */
  flushIntervalMs: number;
  /** Optional session identifier for correlating metrics */
  sessionId?: string;
  /** Maximum queue size to prevent memory issues (default: 50) */
  maxQueueSize: number;
}

const defaultConfig: RUMConfig = {
  endpoint: '/api/rum',
  enabled: true,
  batchSize: 5,
  flushIntervalMs: 10000,
  maxQueueSize: 50,
};

/**
 * RUM service class for collecting and sending Core Web Vitals.
 *
 * This class provides batched metric collection with:
 * - Automatic flushing when batch size is reached
 * - Periodic flushing on a timer
 * - Reliable delivery via sendBeacon on page unload
 * - Queue size limits to prevent memory issues
 */
export class RUM {
  private queue: WebVitalMetric[] = [];
  private config: RUMConfig;
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private isDestroyed: boolean = false;
  private boundBeforeUnload: (() => void) | null = null;

  constructor(config: Partial<RUMConfig> = {}) {
    this.config = { ...defaultConfig, ...config };
    if (this.config.enabled) {
      this.startFlushTimer();
      this.setupUnloadHandler();
    }
  }

  /**
   * Start the periodic flush timer.
   */
  private startFlushTimer(): void {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
    }
    this.flushTimer = setInterval(() => {
      void this.flush();
    }, this.config.flushIntervalMs);
  }

  /**
   * Setup beforeunload handler to flush metrics when page is closing.
   */
  private setupUnloadHandler(): void {
    if (typeof window !== 'undefined') {
      this.boundBeforeUnload = () => {
        this.flushWithBeacon();
      };
      window.addEventListener('beforeunload', this.boundBeforeUnload);
      // Also handle visibilitychange for mobile browsers
      window.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') {
          this.flushWithBeacon();
        }
      });
    }
  }

  /**
   * Report a Core Web Vital metric.
   *
   * This is the main entry point for reporting metrics. Call this with
   * the metric object from web-vitals callbacks.
   *
   * @param metric - Web Vital metric to report
   */
  reportMetric(metric: WebVitalMetric): void {
    if (!this.config.enabled || this.isDestroyed) {
      return;
    }

    // Add current path to metric if not already set
    const metricWithPath: WebVitalMetric = {
      ...metric,
      path: metric.path || (typeof window !== 'undefined' ? window.location.pathname : '/'),
    };

    // Enforce max queue size
    if (this.queue.length >= this.config.maxQueueSize) {
      this.queue.shift();
    }

    this.queue.push(metricWithPath);

    // Auto-flush if batch size reached
    if (this.queue.length >= this.config.batchSize) {
      void this.flush();
    }
  }

  /**
   * Flush queued metrics to the backend.
   */
  async flush(): Promise<void> {
    if (this.queue.length === 0 || this.isDestroyed) {
      return;
    }

    const metrics = [...this.queue];
    this.queue = [];

    const payload: {
      metrics: WebVitalMetric[];
      session_id?: string;
    } = {
      metrics,
    };

    if (this.config.sessionId) {
      payload.session_id = this.config.sessionId;
    }

    try {
      await fetch(this.config.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (err) {
      // On failure, preserve metrics if queue isn't full
      if (this.queue.length + metrics.length <= this.config.maxQueueSize) {
        this.queue.unshift(...metrics);
      }
      console.error('Failed to flush RUM metrics:', err);
    }
  }

  /**
   * Flush metrics using navigator.sendBeacon for reliable delivery.
   *
   * This is used during page unload when async requests may not complete.
   * Falls back to regular fetch with keepalive if sendBeacon is unavailable.
   */
  flushWithBeacon(): void {
    if (this.queue.length === 0) {
      return;
    }

    const metrics = [...this.queue];
    this.queue = [];

    const payload: {
      metrics: WebVitalMetric[];
      session_id?: string;
    } = {
      metrics,
    };

    if (this.config.sessionId) {
      payload.session_id = this.config.sessionId;
    }

    const payloadString = JSON.stringify(payload);

    // Try sendBeacon first (most reliable during page unload)
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      const blob = new Blob([payloadString], { type: 'application/json' });
      const sent = navigator.sendBeacon(this.config.endpoint, blob);
      if (sent) {
        return;
      }
      // If sendBeacon fails, fall through to fetch
    }

    // Fallback to async fetch with keepalive
    void fetch(this.config.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payloadString,
      keepalive: true,
    }).catch(() => {
      // Silently fail - we're unloading anyway
    });
  }

  /**
   * Get the current queue size.
   *
   * @returns Number of metrics currently queued
   */
  getQueueSize(): number {
    return this.queue.length;
  }

  /**
   * Destroy the RUM service, stopping timers and flushing remaining metrics.
   */
  destroy(): void {
    if (this.isDestroyed) {
      return;
    }

    this.isDestroyed = true;

    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }

    if (this.boundBeforeUnload && typeof window !== 'undefined') {
      window.removeEventListener('beforeunload', this.boundBeforeUnload);
    }

    // Final flush attempt
    this.flushWithBeacon();
  }
}

/**
 * Initialize RUM collection with optional configuration.
 *
 * This function creates a RUM instance and optionally sets up
 * web-vitals library callbacks if the library is available.
 *
 * @param config - Optional RUM configuration
 * @returns RUM instance
 */
export function initRUM(config: Partial<RUMConfig> = {}): RUM {
  const rum = new RUM(config);

  // If web-vitals library is available, set up callbacks
  // This is done dynamically to avoid requiring the library as a dependency
  // for environments that don't need RUM (e.g., tests)
  // Note: FID was deprecated in web-vitals v4 and removed in v5 (replaced by INP)
  if (rum['config'].enabled && typeof window !== 'undefined') {
    void import('web-vitals')
      .then(({ onLCP, onINP, onCLS, onTTFB, onFCP }) => {
        const reportToRUM = (metric: {
          name: string;
          value: number;
          rating: string;
          delta: number;
          id: string;
          navigationType?: string;
        }) => {
          rum.reportMetric({
            name: metric.name as WebVitalName,
            value: metric.value,
            rating: metric.rating as WebVitalRating,
            delta: metric.delta,
            id: metric.id,
            navigationType: metric.navigationType,
          });
        };

        onLCP(reportToRUM);
        onINP(reportToRUM);
        onCLS(reportToRUM);
        onTTFB(reportToRUM);
        onFCP(reportToRUM);
        // Note: FID is no longer reported in web-vitals v5 (replaced by INP)
        // Manual FID reporting is still supported via reportMetric()
      })
      .catch((err) => {
        // web-vitals not available, RUM will still work with manual reportMetric calls
        console.warn('web-vitals library not available for RUM:', err);
      });
  }

  return rum;
}

// Export a default singleton for convenience
export default initRUM;
