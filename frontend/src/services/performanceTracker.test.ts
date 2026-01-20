/**
 * Tests for PerformanceTracker service.
 *
 * These tests verify the React component render performance tracking
 * functionality including metric collection, slow render detection,
 * and aggregation/reporting.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  PerformanceTracker,
  type PerformanceTrackerConfig,
  type RenderMetric,
  type RenderPhase,
} from './performanceTracker';

describe('PerformanceTracker', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });
    vi.stubGlobal('fetch', fetchMock);

    // Suppress console output during tests
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.clearAllTimers();
  });

  describe('constructor', () => {
    it('can be instantiated with default config', () => {
      const tracker = new PerformanceTracker({ enabled: true });
      expect(tracker).toBeDefined();
      expect(tracker.isEnabled()).toBe(true);
      tracker.destroy();
    });

    it('can be instantiated with custom config', () => {
      const config: Partial<PerformanceTrackerConfig> = {
        enabled: true,
        slowRenderThreshold: 32,
        flushIntervalMs: 60000,
        maxMetrics: 500,
      };
      const tracker = new PerformanceTracker(config);
      expect(tracker).toBeDefined();
      expect(tracker.getSlowRenderThreshold()).toBe(32);
      tracker.destroy();
    });

    it('can be disabled via config', () => {
      const tracker = new PerformanceTracker({ enabled: false });
      expect(tracker.isEnabled()).toBe(false);

      // Should not record metrics when disabled
      tracker.recordRender(createMockMetric({ actualDuration: 50 }));
      expect(tracker.getMetricsCount()).toBe(0);

      tracker.destroy();
    });
  });

  describe('recordRender', () => {
    it('records render metrics when enabled', () => {
      const tracker = new PerformanceTracker({ enabled: true, maxMetrics: 100 });

      tracker.recordRender(createMockMetric({ component: 'TestComponent' }));

      expect(tracker.getMetricsCount()).toBe(1);
      tracker.destroy();
    });

    it('does not record when disabled', () => {
      const tracker = new PerformanceTracker({ enabled: false });

      tracker.recordRender(createMockMetric({ component: 'TestComponent' }));

      expect(tracker.getMetricsCount()).toBe(0);
      tracker.destroy();
    });

    it('logs warning for slow renders', () => {
      const warnSpy = vi.spyOn(console, 'warn');
      const tracker = new PerformanceTracker({
        enabled: true,
        slowRenderThreshold: 16,
        maxMetrics: 100,
      });

      tracker.recordRender(
        createMockMetric({
          component: 'SlowComponent',
          actualDuration: 50,
        })
      );

      // Logger logs to console
      expect(warnSpy).toHaveBeenCalled();
      tracker.destroy();
    });

    it('does not log warning for fast renders', () => {
      const warnSpy = vi.spyOn(console, 'warn');
      const tracker = new PerformanceTracker({
        enabled: true,
        slowRenderThreshold: 16,
        maxMetrics: 100,
      });

      tracker.recordRender(
        createMockMetric({
          component: 'FastComponent',
          actualDuration: 5,
        })
      );

      expect(warnSpy).not.toHaveBeenCalled();
      tracker.destroy();
    });

    it('enforces max metrics limit', () => {
      const tracker = new PerformanceTracker({
        enabled: true,
        maxMetrics: 3,
        flushIntervalMs: 60000, // Long interval to prevent auto-flush
      });

      tracker.recordRender(createMockMetric({ component: 'Component1' }));
      tracker.recordRender(createMockMetric({ component: 'Component2' }));
      tracker.recordRender(createMockMetric({ component: 'Component3' }));
      tracker.recordRender(createMockMetric({ component: 'Component4' }));

      // Should drop oldest to enforce limit
      expect(tracker.getMetricsCount()).toBe(3);
      tracker.destroy();
    });
  });

  describe('flush', () => {
    it('flushes metrics and reports to RUM', async () => {
      const tracker = new PerformanceTracker({
        enabled: true,
        slowRenderThreshold: 16,
        maxMetrics: 100,
        flushIntervalMs: 60000,
      });

      // Record a slow render
      tracker.recordRender(
        createMockMetric({
          component: 'SlowComponent',
          actualDuration: 50,
        })
      );

      tracker.flush();

      // Wait for dynamic import to complete
      await new Promise((resolve) => setTimeout(resolve, 50));

      // Metrics should be cleared after flush
      expect(tracker.getMetricsCount()).toBe(0);
      tracker.destroy();
    });

    it('does nothing when queue is empty', () => {
      const tracker = new PerformanceTracker({ enabled: true });

      // Should not throw
      expect(() => tracker.flush()).not.toThrow();
      tracker.destroy();
    });

    it('does nothing when only fast renders', () => {
      const tracker = new PerformanceTracker({
        enabled: true,
        slowRenderThreshold: 16,
        maxMetrics: 100,
        flushIntervalMs: 60000,
      });

      // Record only fast renders
      tracker.recordRender(
        createMockMetric({
          component: 'FastComponent',
          actualDuration: 5,
        })
      );

      tracker.flush();

      // Metrics should be cleared even though none were reported
      expect(tracker.getMetricsCount()).toBe(0);
      tracker.destroy();
    });

    it('groups metrics by component', async () => {
      const infoSpy = vi.spyOn(console, 'log');
      const tracker = new PerformanceTracker({
        enabled: true,
        slowRenderThreshold: 16,
        maxMetrics: 100,
        flushIntervalMs: 60000,
      });

      // Record multiple slow renders for same component
      tracker.recordRender(
        createMockMetric({
          component: 'SlowComponent',
          actualDuration: 30,
        })
      );
      tracker.recordRender(
        createMockMetric({
          component: 'SlowComponent',
          actualDuration: 50,
        })
      );
      tracker.recordRender(
        createMockMetric({
          component: 'AnotherSlowComponent',
          actualDuration: 25,
        })
      );

      tracker.flush();

      // Wait for dynamic import
      await new Promise((resolve) => setTimeout(resolve, 50));

      // Should have logged stats for both components
      expect(infoSpy).toHaveBeenCalled();
      tracker.destroy();
    });
  });

  describe('setEnabled', () => {
    it('can enable tracking at runtime', () => {
      const tracker = new PerformanceTracker({ enabled: false });
      expect(tracker.isEnabled()).toBe(false);

      tracker.setEnabled(true);
      expect(tracker.isEnabled()).toBe(true);

      tracker.destroy();
    });

    it('can disable tracking at runtime', () => {
      const tracker = new PerformanceTracker({ enabled: true });
      expect(tracker.isEnabled()).toBe(true);

      tracker.setEnabled(false);
      expect(tracker.isEnabled()).toBe(false);

      tracker.destroy();
    });
  });

  describe('getSlowRenderThreshold', () => {
    it('returns the configured threshold', () => {
      const tracker = new PerformanceTracker({ slowRenderThreshold: 32 });
      expect(tracker.getSlowRenderThreshold()).toBe(32);
      tracker.destroy();
    });

    it('returns default threshold when not configured', () => {
      const tracker = new PerformanceTracker({ enabled: true });
      expect(tracker.getSlowRenderThreshold()).toBe(16);
      tracker.destroy();
    });
  });

  describe('getMetricsCount', () => {
    it('returns zero for empty queue', () => {
      const tracker = new PerformanceTracker({ enabled: true });
      expect(tracker.getMetricsCount()).toBe(0);
      tracker.destroy();
    });

    it('returns correct count after adding metrics', () => {
      const tracker = new PerformanceTracker({
        enabled: true,
        maxMetrics: 100,
        flushIntervalMs: 60000,
      });

      tracker.recordRender(createMockMetric({ component: 'A' }));
      expect(tracker.getMetricsCount()).toBe(1);

      tracker.recordRender(createMockMetric({ component: 'B' }));
      expect(tracker.getMetricsCount()).toBe(2);

      tracker.destroy();
    });
  });

  describe('destroy', () => {
    it('stops tracking after destroy', () => {
      const tracker = new PerformanceTracker({ enabled: true, maxMetrics: 100 });
      tracker.destroy();

      expect(tracker.isEnabled()).toBe(false);

      // Should not record after destroy
      tracker.recordRender(createMockMetric({ component: 'Test' }));
      expect(tracker.getMetricsCount()).toBe(0);
    });

    it('can be called multiple times safely', () => {
      const tracker = new PerformanceTracker({ enabled: true });
      tracker.destroy();
      expect(() => tracker.destroy()).not.toThrow();
    });

    it('flushes remaining metrics', async () => {
      const tracker = new PerformanceTracker({
        enabled: true,
        slowRenderThreshold: 16,
        maxMetrics: 100,
        flushIntervalMs: 60000,
      });

      tracker.recordRender(
        createMockMetric({
          component: 'SlowComponent',
          actualDuration: 50,
        })
      );

      tracker.destroy();

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(tracker.getMetricsCount()).toBe(0);
    });
  });

  describe('render phases', () => {
    it('records mount phase', () => {
      const tracker = new PerformanceTracker({ enabled: true, maxMetrics: 100 });

      tracker.recordRender(createMockMetric({ phase: 'mount' }));

      expect(tracker.getMetricsCount()).toBe(1);
      tracker.destroy();
    });

    it('records update phase', () => {
      const tracker = new PerformanceTracker({ enabled: true, maxMetrics: 100 });

      tracker.recordRender(createMockMetric({ phase: 'update' }));

      expect(tracker.getMetricsCount()).toBe(1);
      tracker.destroy();
    });
  });
});

describe('RenderMetric type', () => {
  it('supports all required fields', () => {
    const metric: RenderMetric = {
      component: 'TestComponent',
      phase: 'mount',
      actualDuration: 25,
      baseDuration: 10,
      startTime: 1000,
      commitTime: 1025,
    };

    expect(metric.component).toBe('TestComponent');
    expect(metric.phase).toBe('mount');
    expect(metric.actualDuration).toBe(25);
    expect(metric.baseDuration).toBe(10);
    expect(metric.startTime).toBe(1000);
    expect(metric.commitTime).toBe(1025);
  });
});

describe('RenderPhase type', () => {
  it('supports mount and update phases', () => {
    const phases: RenderPhase[] = ['mount', 'update'];
    expect(phases.length).toBe(2);
  });
});

/**
 * Helper function to create mock render metrics.
 */
function createMockMetric(overrides: Partial<RenderMetric> = {}): RenderMetric {
  return {
    component: 'TestComponent',
    phase: 'update',
    actualDuration: 10,
    baseDuration: 5,
    startTime: performance.now(),
    commitTime: performance.now() + 10,
    ...overrides,
  };
}
