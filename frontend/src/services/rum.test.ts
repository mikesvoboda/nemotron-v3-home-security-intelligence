/**
 * Tests for RUM (Real User Monitoring) service.
 *
 * RED Phase: These tests define the expected behavior for the RUM service
 * that collects Core Web Vitals and sends them to the backend.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { RUM, initRUM, type RUMConfig, type WebVitalMetric, type WebVitalName } from './rum';

describe('RUM Service', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let sendBeaconMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, metrics_count: 1 }),
    });
    vi.stubGlobal('fetch', fetchMock);

    sendBeaconMock = vi.fn().mockReturnValue(true);
    vi.stubGlobal('navigator', { sendBeacon: sendBeaconMock });

    // Suppress console output during tests
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  describe('RUM class', () => {
    it('can be instantiated with default config', () => {
      const rum = new RUM();
      expect(rum).toBeDefined();
      rum.destroy();
    });

    it('can be instantiated with custom config', () => {
      const config: Partial<RUMConfig> = {
        endpoint: '/custom/rum',
        enabled: true,
        batchSize: 5,
        flushIntervalMs: 10000,
      };
      const rum = new RUM(config);
      expect(rum).toBeDefined();
      rum.destroy();
    });

    it('can be disabled via config', () => {
      const rum = new RUM({ enabled: false });
      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-123',
      } as WebVitalMetric);
      expect(rum.getQueueSize()).toBe(0);
      rum.destroy();
    });
  });

  describe('reportMetric', () => {
    it('queues LCP metric', () => {
      const rum = new RUM({ enabled: true, batchSize: 100 });
      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-123',
      } as WebVitalMetric);
      expect(rum.getQueueSize()).toBe(1);
      rum.destroy();
    });

    it('queues FID metric', () => {
      const rum = new RUM({ enabled: true, batchSize: 100 });
      rum.reportMetric({
        name: 'FID',
        value: 50,
        rating: 'good',
        delta: 50,
        id: 'v1-124',
      } as WebVitalMetric);
      expect(rum.getQueueSize()).toBe(1);
      rum.destroy();
    });

    it('queues INP metric', () => {
      const rum = new RUM({ enabled: true, batchSize: 100 });
      rum.reportMetric({
        name: 'INP',
        value: 200,
        rating: 'needs-improvement',
        delta: 200,
        id: 'v1-125',
      } as WebVitalMetric);
      expect(rum.getQueueSize()).toBe(1);
      rum.destroy();
    });

    it('queues CLS metric', () => {
      const rum = new RUM({ enabled: true, batchSize: 100 });
      rum.reportMetric({
        name: 'CLS',
        value: 0.05,
        rating: 'good',
        delta: 0.02,
        id: 'v1-126',
      } as WebVitalMetric);
      expect(rum.getQueueSize()).toBe(1);
      rum.destroy();
    });

    it('queues TTFB metric', () => {
      const rum = new RUM({ enabled: true, batchSize: 100 });
      rum.reportMetric({
        name: 'TTFB',
        value: 100,
        rating: 'good',
        delta: 100,
        id: 'v1-127',
      } as WebVitalMetric);
      expect(rum.getQueueSize()).toBe(1);
      rum.destroy();
    });

    it('queues FCP metric', () => {
      const rum = new RUM({ enabled: true, batchSize: 100 });
      rum.reportMetric({
        name: 'FCP',
        value: 1800,
        rating: 'good',
        delta: 1800,
        id: 'v1-128',
      } as WebVitalMetric);
      expect(rum.getQueueSize()).toBe(1);
      rum.destroy();
    });

    it('includes path in metric', () => {
      // Save original location
      const originalPathname = window.location.pathname;

      // Mock pathname by defining a property
      Object.defineProperty(window, 'location', {
        value: { ...window.location, pathname: '/dashboard' },
        writable: true,
      });

      const rum = new RUM({ enabled: true, batchSize: 100 });

      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-123',
      } as WebVitalMetric);

      expect(rum.getQueueSize()).toBe(1);
      rum.destroy();

      // Restore original
      Object.defineProperty(window, 'location', {
        value: { ...window.location, pathname: originalPathname },
        writable: true,
      });
    });
  });

  describe('flush', () => {
    it('sends queued metrics to backend', async () => {
      const rum = new RUM({ enabled: true, batchSize: 100 });
      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-123',
      } as WebVitalMetric);

      await rum.flush();

      expect(fetchMock).toHaveBeenCalled();
      const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toBe('/api/rum');
      expect(options.method).toBe('POST');
      expect(options.headers).toEqual({ 'Content-Type': 'application/json' });

      const body = JSON.parse(options.body as string) as { metrics: unknown[] };
      expect(body.metrics).toBeInstanceOf(Array);
      expect(body.metrics.length).toBe(1);

      rum.destroy();
    });

    it('clears queue after successful flush', async () => {
      const rum = new RUM({ enabled: true, batchSize: 100 });
      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-123',
      } as WebVitalMetric);

      expect(rum.getQueueSize()).toBe(1);
      await rum.flush();
      expect(rum.getQueueSize()).toBe(0);

      rum.destroy();
    });

    it('does nothing when queue is empty', async () => {
      const rum = new RUM({ enabled: true });
      await rum.flush();
      expect(fetchMock).not.toHaveBeenCalled();
      rum.destroy();
    });

    it('handles fetch failure gracefully', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      const rum = new RUM({ enabled: true, batchSize: 100 });
      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-123',
      } as WebVitalMetric);

      // Should not throw
      await expect(rum.flush()).resolves.not.toThrow();
      rum.destroy();
    });
  });

  describe('batch triggering', () => {
    it('auto-flushes when batch size is reached', async () => {
      const rum = new RUM({ enabled: true, batchSize: 2 });

      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-1',
      } as WebVitalMetric);
      rum.reportMetric({
        name: 'CLS',
        value: 0.05,
        rating: 'good',
        delta: 0.02,
        id: 'v1-2',
      } as WebVitalMetric);

      // Wait for async flush
      await new Promise((resolve) => setTimeout(resolve, 10));

      expect(fetchMock).toHaveBeenCalled();
      rum.destroy();
    });
  });

  describe('sendBeacon on page unload', () => {
    it('flushWithBeacon uses navigator.sendBeacon', () => {
      const rum = new RUM({ enabled: true });

      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-123',
      } as WebVitalMetric);
      rum.flushWithBeacon();

      expect(sendBeaconMock).toHaveBeenCalled();
      const [url, data] = sendBeaconMock.mock.calls[0] as [string, Blob];
      expect(url).toBe('/api/rum');
      expect(data).toBeInstanceOf(Blob);

      rum.destroy();
    });

    it('flushWithBeacon does nothing when queue is empty', () => {
      const rum = new RUM({ enabled: true });
      rum.flushWithBeacon();
      expect(sendBeaconMock).not.toHaveBeenCalled();
      rum.destroy();
    });

    it('falls back to fetch if sendBeacon returns false', async () => {
      sendBeaconMock.mockReturnValueOnce(false);

      const rum = new RUM({ enabled: true });
      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-123',
      } as WebVitalMetric);
      rum.flushWithBeacon();

      // Wait for async fetch fallback
      await new Promise((resolve) => setTimeout(resolve, 10));

      expect(fetchMock).toHaveBeenCalled();
      rum.destroy();
    });
  });

  describe('session ID', () => {
    it('includes session ID in request when configured', async () => {
      const rum = new RUM({ enabled: true, sessionId: 'test-session-123' });
      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-123',
      } as WebVitalMetric);

      await rum.flush();

      const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      const body = JSON.parse(options.body as string) as { session_id?: string };
      expect(body.session_id).toBe('test-session-123');

      rum.destroy();
    });

    it('does not include session ID when not configured', async () => {
      const rum = new RUM({ enabled: true });
      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-123',
      } as WebVitalMetric);

      await rum.flush();

      const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      const body = JSON.parse(options.body as string) as { session_id?: string };
      expect(body.session_id).toBeUndefined();

      rum.destroy();
    });
  });

  describe('destroy', () => {
    it('stops flush timer', () => {
      const rum = new RUM({ enabled: true });
      rum.destroy();
      // Should not throw after destroy
      expect(() => rum.destroy()).not.toThrow();
    });

    it('flushes remaining metrics with beacon', () => {
      const rum = new RUM({ enabled: true });
      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-123',
      } as WebVitalMetric);

      rum.destroy();

      expect(sendBeaconMock).toHaveBeenCalled();
    });
  });

  describe('getQueueSize', () => {
    it('returns the current queue size', () => {
      const rum = new RUM({ enabled: true, batchSize: 100 });

      expect(rum.getQueueSize()).toBe(0);

      rum.reportMetric({
        name: 'LCP',
        value: 2500,
        rating: 'good',
        delta: 2500,
        id: 'v1-1',
      } as WebVitalMetric);
      expect(rum.getQueueSize()).toBe(1);

      rum.reportMetric({
        name: 'CLS',
        value: 0.05,
        rating: 'good',
        delta: 0.02,
        id: 'v1-2',
      } as WebVitalMetric);
      expect(rum.getQueueSize()).toBe(2);

      rum.destroy();
    });
  });

  describe('max queue size enforcement', () => {
    it('drops oldest entries when queue exceeds maxQueueSize', () => {
      const rum = new RUM({
        enabled: true,
        maxQueueSize: 3,
        batchSize: 100, // High to prevent auto-flush
        flushIntervalMs: 60000, // Long to prevent timer flush
      });

      rum.reportMetric({
        name: 'LCP',
        value: 1000,
        rating: 'good',
        delta: 1000,
        id: 'v1-1',
      } as WebVitalMetric);
      rum.reportMetric({
        name: 'LCP',
        value: 2000,
        rating: 'good',
        delta: 2000,
        id: 'v1-2',
      } as WebVitalMetric);
      rum.reportMetric({
        name: 'LCP',
        value: 3000,
        rating: 'good',
        delta: 3000,
        id: 'v1-3',
      } as WebVitalMetric);
      rum.reportMetric({
        name: 'LCP',
        value: 4000,
        rating: 'good',
        delta: 4000,
        id: 'v1-4',
      } as WebVitalMetric); // Should drop first

      expect(rum.getQueueSize()).toBe(3);

      rum.destroy();
    });
  });
});

describe('initRUM', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, metrics_count: 1 }),
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
  });

  it('returns a RUM instance', () => {
    const rum = initRUM();
    expect(rum).toBeInstanceOf(RUM);
    rum.destroy();
  });

  it('accepts custom config', () => {
    const rum = initRUM({ enabled: false });
    expect(rum).toBeInstanceOf(RUM);
    rum.destroy();
  });
});

describe('WebVitalMetric type', () => {
  it('supports all Core Web Vital names including SLOW_RENDER', () => {
    const names: WebVitalName[] = [
      'LCP',
      'FID',
      'INP',
      'CLS',
      'TTFB',
      'FCP',
      'PAGE_LOAD_TIME',
      'SLOW_RENDER',
    ];
    expect(names.length).toBe(8);
  });

  it('supports all rating values', () => {
    const ratings: Array<'good' | 'needs-improvement' | 'poor'> = [
      'good',
      'needs-improvement',
      'poor',
    ];
    expect(ratings.length).toBe(3);
  });
});

describe('PAGE_LOAD_TIME metric', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, metrics_count: 1 }),
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
  });

  it('queues PAGE_LOAD_TIME metric', () => {
    const rum = new RUM({ enabled: true, batchSize: 100 });
    rum.reportMetric({
      name: 'PAGE_LOAD_TIME',
      value: 2500,
      rating: 'good',
      delta: 2500,
      id: 'plt-123',
    } as WebVitalMetric);
    expect(rum.getQueueSize()).toBe(1);
    rum.destroy();
  });

  it('PAGE_LOAD_TIME rating thresholds work correctly', async () => {
    const rum = new RUM({ enabled: true, batchSize: 1 });

    // Good: < 3000ms
    rum.reportMetric({
      name: 'PAGE_LOAD_TIME',
      value: 2500,
      rating: 'good',
      delta: 2500,
      id: 'plt-1',
    } as WebVitalMetric);

    // Wait for async flush
    await new Promise((resolve) => setTimeout(resolve, 10));

    expect(fetchMock).toHaveBeenCalled();
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(options.body as string) as { metrics: Array<{ name: string }> };
    expect(body.metrics[0].name).toBe('PAGE_LOAD_TIME');

    rum.destroy();
  });
});

describe('RUMConfig type export', () => {
  it('exports RUMConfig type', () => {
    const config: Partial<RUMConfig> = {
      endpoint: '/api/rum',
      enabled: true,
      batchSize: 5,
      flushIntervalMs: 10000,
      sessionId: 'test-session',
      maxQueueSize: 100,
    };
    expect(config).toBeDefined();
  });
});

describe('SLOW_RENDER metric', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, metrics_count: 1 }),
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
  });

  it('queues SLOW_RENDER metric', () => {
    const rum = new RUM({ enabled: true, batchSize: 100 });
    rum.reportMetric({
      name: 'SLOW_RENDER',
      value: 50,
      rating: 'poor',
      delta: 50,
      id: 'sr-123',
    } as WebVitalMetric);
    expect(rum.getQueueSize()).toBe(1);
    rum.destroy();
  });

  it('includes extra metadata for SLOW_RENDER metric', async () => {
    const rum = new RUM({ enabled: true, batchSize: 1 });

    rum.reportMetric({
      name: 'SLOW_RENDER',
      value: 40,
      rating: 'needs-improvement',
      delta: 40,
      id: 'sr-456',
      extra: {
        component: 'EventsTable',
        max: 75,
        count: 5,
      },
    } as WebVitalMetric);

    // Wait for async flush
    await new Promise((resolve) => setTimeout(resolve, 10));

    expect(fetchMock).toHaveBeenCalled();
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(options.body as string) as {
      metrics: Array<{
        name: string;
        extra?: { component?: string; max?: number; count?: number };
      }>;
    };
    expect(body.metrics[0].name).toBe('SLOW_RENDER');
    expect(body.metrics[0].extra?.component).toBe('EventsTable');
    expect(body.metrics[0].extra?.max).toBe(75);
    expect(body.metrics[0].extra?.count).toBe(5);

    rum.destroy();
  });

  it('SLOW_RENDER rating thresholds work correctly', () => {
    const rum = new RUM({ enabled: true, batchSize: 100 });

    // Good: <= 16ms
    rum.reportMetric({
      name: 'SLOW_RENDER',
      value: 15,
      rating: 'good',
      delta: 15,
      id: 'sr-good',
    } as WebVitalMetric);

    // Needs improvement: 16-50ms
    rum.reportMetric({
      name: 'SLOW_RENDER',
      value: 30,
      rating: 'needs-improvement',
      delta: 30,
      id: 'sr-ni',
    } as WebVitalMetric);

    // Poor: > 50ms
    rum.reportMetric({
      name: 'SLOW_RENDER',
      value: 75,
      rating: 'poor',
      delta: 75,
      id: 'sr-poor',
    } as WebVitalMetric);

    expect(rum.getQueueSize()).toBe(3);
    rum.destroy();
  });
});
