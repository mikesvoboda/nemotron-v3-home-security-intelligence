/**
 * Performance tracking service for React component render metrics.
 *
 * This service collects render metrics from React Profiler callbacks and:
 * - Logs slow renders immediately for debugging
 * - Aggregates metrics and reports them via the RUM service
 * - Provides configurable thresholds for slow render detection
 *
 * Usage:
 *   import { performanceTracker } from './performanceTracker';
 *
 *   // Record a render metric (typically from React Profiler callback)
 *   performanceTracker.recordRender({
 *     component: 'EventsTable',
 *     phase: 'update',
 *     actualDuration: 25,
 *     baseDuration: 10,
 *     startTime: performance.now(),
 *     commitTime: performance.now() + 25,
 *   });
 *
 * Configuration:
 *   The tracker can be configured via environment variables:
 *   - VITE_PERFORMANCE_TRACKING_ENABLED: Enable/disable tracking (default: development only)
 *   - VITE_SLOW_RENDER_THRESHOLD_MS: Threshold for slow render warnings (default: 16ms)
 */

import { logger } from './logger';

/**
 * Render phase from React Profiler callback.
 * - 'mount': Component is mounting for the first time
 * - 'update': Component is re-rendering due to props/state/context change
 */
export type RenderPhase = 'mount' | 'update';

/**
 * Render metric structure matching React Profiler onRender callback parameters.
 */
export interface RenderMetric {
  /** Component identifier (from Profiler id prop) */
  component: string;
  /** Whether this was a mount or update render */
  phase: RenderPhase;
  /** Actual time spent rendering (ms) */
  actualDuration: number;
  /** Estimated time without memoization (ms) */
  baseDuration: number;
  /** When React started rendering (from performance.now()) */
  startTime: number;
  /** When React committed the output (from performance.now()) */
  commitTime: number;
}

/**
 * Aggregated render statistics for a component.
 */
export interface ComponentRenderStats {
  /** Total number of slow renders */
  count: number;
  /** Sum of all durations for average calculation */
  totalDuration: number;
  /** Maximum render duration */
  maxDuration: number;
  /** Durations for percentile calculations */
  durations: number[];
}

/**
 * Configuration options for PerformanceTracker.
 */
export interface PerformanceTrackerConfig {
  /** Whether tracking is enabled (default: true in development) */
  enabled: boolean;
  /** Threshold in ms for slow render warnings (default: 16ms for 60fps) */
  slowRenderThreshold: number;
  /** Interval in ms between metric flushes (default: 30000ms) */
  flushIntervalMs: number;
  /** Maximum metrics to keep in memory (default: 1000) */
  maxMetrics: number;
}

const defaultConfig: PerformanceTrackerConfig = {
  // Only enable by default in development, or if explicitly enabled
  enabled:
    (typeof import.meta !== 'undefined' &&
      (import.meta.env?.DEV === true ||
        import.meta.env?.VITE_PERFORMANCE_TRACKING_ENABLED === 'true')) ||
    false,
  // 16ms is the frame budget for 60fps
  slowRenderThreshold:
    typeof import.meta !== 'undefined' && import.meta.env?.VITE_SLOW_RENDER_THRESHOLD_MS
      ? Number(import.meta.env.VITE_SLOW_RENDER_THRESHOLD_MS)
      : 16,
  // Flush every 30 seconds
  flushIntervalMs: 30000,
  // Keep up to 1000 metrics in memory
  maxMetrics: 1000,
};

/**
 * Performance tracking service for React component render metrics.
 *
 * Collects render metrics from React Profiler callbacks, logs slow renders
 * for debugging, and aggregates/reports metrics for performance monitoring.
 */
export class PerformanceTracker {
  private config: PerformanceTrackerConfig;
  private renderMetrics: RenderMetric[] = [];
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private isDestroyed: boolean = false;

  constructor(config: Partial<PerformanceTrackerConfig> = {}) {
    this.config = { ...defaultConfig, ...config };

    if (this.config.enabled) {
      this.startFlushTimer();
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
      this.flush();
    }, this.config.flushIntervalMs);
  }

  /**
   * Record a render metric from React Profiler callback.
   *
   * @param metric - Render metric to record
   */
  recordRender(metric: RenderMetric): void {
    if (!this.config.enabled || this.isDestroyed) {
      return;
    }

    // Enforce max metrics to prevent memory issues
    if (this.renderMetrics.length >= this.config.maxMetrics) {
      this.renderMetrics.shift();
    }

    this.renderMetrics.push(metric);

    // Log slow renders immediately for debugging
    if (metric.actualDuration > this.config.slowRenderThreshold) {
      logger.warn('Slow component render', {
        component: metric.component,
        phase: metric.phase,
        duration_ms: Math.round(metric.actualDuration),
        base_duration_ms: Math.round(metric.baseDuration),
      });
    }
  }

  /**
   * Flush aggregated metrics to RUM service.
   *
   * Groups slow renders by component and reports aggregate statistics
   * including average, max, and count.
   */
  flush(): void {
    if (this.renderMetrics.length === 0 || this.isDestroyed) {
      return;
    }

    // Get slow renders from current batch
    const slowRenders = this.renderMetrics.filter(
      (m) => m.actualDuration > this.config.slowRenderThreshold
    );

    // Clear metrics after extracting slow renders
    this.renderMetrics = [];

    if (slowRenders.length === 0) {
      return;
    }

    // Group by component
    const byComponent = slowRenders.reduce(
      (acc, m) => {
        if (!acc[m.component]) {
          acc[m.component] = {
            count: 0,
            totalDuration: 0,
            maxDuration: 0,
            durations: [],
          };
        }
        acc[m.component].count += 1;
        acc[m.component].totalDuration += m.actualDuration;
        acc[m.component].maxDuration = Math.max(acc[m.component].maxDuration, m.actualDuration);
        acc[m.component].durations.push(m.actualDuration);
        return acc;
      },
      {} as Record<string, ComponentRenderStats>
    );

    // Report aggregates via RUM
    // Dynamic import to avoid circular dependencies
    void import('./rum').then(({ initRUM }) => {
      const rum = initRUM({ enabled: true });

      for (const [component, stats] of Object.entries(byComponent)) {
        const avg = stats.totalDuration / stats.count;

        // Report as a custom metric with component metadata
        rum.reportMetric({
          name: 'SLOW_RENDER',
          value: Math.round(avg),
          rating: avg > 50 ? 'poor' : avg > 16 ? 'needs-improvement' : 'good',
          delta: Math.round(avg),
          id: `sr-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
          path: typeof window !== 'undefined' ? window.location.pathname : '/',
          navigationType: undefined,
          extra: {
            component,
            max: Math.round(stats.maxDuration),
            count: stats.count,
          },
        });

        // Also log aggregate for debugging
        logger.info('Component render stats', {
          component,
          avg_duration_ms: Math.round(avg),
          max_duration_ms: Math.round(stats.maxDuration),
          slow_render_count: stats.count,
        });
      }

      rum.destroy();
    });
  }

  /**
   * Get the current number of metrics in the queue.
   *
   * @returns Number of metrics currently queued
   */
  getMetricsCount(): number {
    return this.renderMetrics.length;
  }

  /**
   * Get the current slow render threshold.
   *
   * @returns Slow render threshold in milliseconds
   */
  getSlowRenderThreshold(): number {
    return this.config.slowRenderThreshold;
  }

  /**
   * Check if tracking is enabled.
   *
   * @returns Whether tracking is currently enabled
   */
  isEnabled(): boolean {
    return this.config.enabled && !this.isDestroyed;
  }

  /**
   * Enable or disable tracking at runtime.
   *
   * @param enabled - Whether to enable tracking
   */
  setEnabled(enabled: boolean): void {
    this.config.enabled = enabled;

    if (enabled && !this.flushTimer && !this.isDestroyed) {
      this.startFlushTimer();
    } else if (!enabled && this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
  }

  /**
   * Destroy the tracker, stopping timers and flushing remaining metrics.
   */
  destroy(): void {
    if (this.isDestroyed) {
      return;
    }

    // Stop the timer first
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }

    // Final flush before marking as destroyed
    this.flush();

    // Mark as destroyed after flush to allow the flush to complete
    this.isDestroyed = true;
  }
}

// Export singleton instance for convenience
export const performanceTracker = new PerformanceTracker();
