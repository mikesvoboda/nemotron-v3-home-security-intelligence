import { describe, it, expect, beforeEach, vi } from 'vitest';

import { fetchMonitoringHealth, fetchMonitoringTargets } from './monitoringApi';

import type { MonitoringHealthResponse, MonitoringTargetsResponse } from './monitoringApi';

// Mock the global fetch function
const mockFetch = vi.fn();
global.fetch = mockFetch as any;

/**
 * Helper to create a mock Response object with all required methods
 */
function createMockResponse<T>(data: T, options: { ok: boolean; status?: number; statusText?: string } = { ok: true }) {
  const response = {
    ok: options.ok,
    status: options.status ?? (options.ok ? 200 : 500),
    statusText: options.statusText ?? (options.ok ? 'OK' : 'Internal Server Error'),
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
    clone: function() { return { ...this }; },
    headers: new Headers(),
    body: null,
    bodyUsed: false,
    redirected: false,
    type: 'basic' as ResponseType,
    url: '',
    arrayBuffer: () => Promise.resolve(new ArrayBuffer(0)),
    blob: () => Promise.resolve(new Blob()),
    formData: () => Promise.resolve(new FormData()),
  };
  return response;
}

describe('monitoringApi', () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  describe('fetchMonitoringHealth', () => {
    it('should fetch monitoring health successfully', async () => {
      const mockResponse: MonitoringHealthResponse = {
        healthy: true,
        prometheus_reachable: true,
        prometheus_url: 'http://prometheus:9090',
        targets_summary: [
          { job: 'backend', total: 1, up: 1, down: 0, unknown: 0 },
          { job: 'redis-exporter', total: 1, up: 1, down: 0, unknown: 0 },
        ],
        exporters: [
          {
            name: 'redis-exporter',
            status: 'up',
            endpoint: 'redis-exporter:9121',
            last_scrape: '2025-01-31T10:30:00Z',
            error: null,
          },
        ],
        metrics_collection: {
          collecting: true,
          last_successful_scrape: '2025-01-31T10:30:00Z',
          scrape_interval_seconds: 15,
          total_series: 15000,
        },
        issues: [],
        timestamp: '2025-01-31T10:30:00Z',
      };

      mockFetch.mockResolvedValueOnce(createMockResponse(mockResponse, { ok: true }));

      const result = await fetchMonitoringHealth();

      expect(mockFetch).toHaveBeenCalled();
      expect(result).toEqual(mockResponse);
    });

    it('should handle Prometheus unreachable scenario', async () => {
      const mockResponse: MonitoringHealthResponse = {
        healthy: false,
        prometheus_reachable: false,
        prometheus_url: 'http://prometheus:9090',
        targets_summary: [],
        exporters: [],
        metrics_collection: {
          collecting: false,
          last_successful_scrape: null,
          scrape_interval_seconds: 15,
          total_series: 0,
        },
        issues: ['Prometheus is not reachable at http://prometheus:9090'],
        timestamp: '2025-01-31T10:30:00Z',
      };

      mockFetch.mockResolvedValueOnce(createMockResponse(mockResponse, { ok: true }));

      const result = await fetchMonitoringHealth();

      expect(result.prometheus_reachable).toBe(false);
      expect(result.healthy).toBe(false);
      expect(result.issues.length).toBeGreaterThan(0);
    });

    it('should handle unhealthy state with down targets', async () => {
      const mockResponse: MonitoringHealthResponse = {
        healthy: false,
        prometheus_reachable: true,
        prometheus_url: 'http://prometheus:9090',
        targets_summary: [
          { job: 'backend', total: 1, up: 0, down: 1, unknown: 0 },
          { job: 'redis-exporter', total: 1, up: 1, down: 0, unknown: 0 },
        ],
        exporters: [
          {
            name: 'backend',
            status: 'down',
            endpoint: 'backend:8000',
            last_scrape: '2025-01-31T10:25:00Z',
            error: 'Connection refused',
          },
        ],
        metrics_collection: {
          collecting: true,
          last_successful_scrape: '2025-01-31T10:30:00Z',
          scrape_interval_seconds: 15,
          total_series: 12000,
        },
        issues: ['1 target(s) are down: backend'],
        timestamp: '2025-01-31T10:30:00Z',
      };

      mockFetch.mockResolvedValueOnce(createMockResponse(mockResponse, { ok: true }));

      const result = await fetchMonitoringHealth();

      expect(result.healthy).toBe(false);
      expect(result.targets_summary.some((t) => t.down > 0)).toBe(true);
      expect(result.exporters.some((e) => e.status === 'down')).toBe(true);
    });

    it('should throw error on network failure', async () => {
      mockFetch.mockRejectedValueOnce(
        new Error('Network error')
      );

      await expect(fetchMonitoringHealth()).rejects.toThrow('Network error');
    });

    it('should throw error on non-ok response', async () => {
      mockFetch.mockResolvedValueOnce(createMockResponse({}, { ok: false, status: 500, statusText: 'Internal Server Error' }));

      await expect(fetchMonitoringHealth()).rejects.toThrow();
    });

    it('should handle empty targets and exporters', async () => {
      const mockResponse: MonitoringHealthResponse = {
        healthy: true,
        prometheus_reachable: true,
        prometheus_url: 'http://prometheus:9090',
        targets_summary: [],
        exporters: [],
        metrics_collection: {
          collecting: true,
          last_successful_scrape: '2025-01-31T10:30:00Z',
          scrape_interval_seconds: 15,
          total_series: 0,
        },
        issues: [],
        timestamp: '2025-01-31T10:30:00Z',
      };

      mockFetch.mockResolvedValueOnce(createMockResponse(mockResponse, { ok: true }));

      const result = await fetchMonitoringHealth();

      expect(result.targets_summary).toEqual([]);
      expect(result.exporters).toEqual([]);
    });
  });

  describe('fetchMonitoringTargets', () => {
    it('should fetch monitoring targets successfully', async () => {
      const mockResponse: MonitoringTargetsResponse = {
        targets: [
          {
            job: 'backend',
            instance: 'backend:8000',
            health: 'up',
            labels: { env: 'production' },
            last_scrape: '2025-01-31T10:30:00Z',
            last_error: null,
            scrape_duration_seconds: 0.045,
          },
          {
            job: 'redis-exporter',
            instance: 'redis-exporter:9121',
            health: 'up',
            labels: { env: 'production' },
            last_scrape: '2025-01-31T10:30:00Z',
            last_error: null,
            scrape_duration_seconds: 0.023,
          },
        ],
        total: 2,
        up: 2,
        down: 0,
        jobs: ['backend', 'redis-exporter'],
        timestamp: '2025-01-31T10:30:00Z',
      };

      mockFetch.mockResolvedValueOnce(createMockResponse(mockResponse, { ok: true }));

      const result = await fetchMonitoringTargets();

      expect(mockFetch).toHaveBeenCalled();
      expect(result).toEqual(mockResponse);
      expect(result.targets.length).toBe(2);
      expect(result.up).toBe(2);
      expect(result.down).toBe(0);
    });

    it('should handle targets with different health states', async () => {
      const mockResponse: MonitoringTargetsResponse = {
        targets: [
          {
            job: 'backend',
            instance: 'backend:8000',
            health: 'up',
            labels: {},
            last_scrape: '2025-01-31T10:30:00Z',
            last_error: null,
            scrape_duration_seconds: 0.045,
          },
          {
            job: 'redis-exporter',
            instance: 'redis-exporter:9121',
            health: 'down',
            labels: {},
            last_scrape: '2025-01-31T10:25:00Z',
            last_error: 'Connection refused',
            scrape_duration_seconds: 0.0,
          },
          {
            job: 'postgres-exporter',
            instance: 'postgres-exporter:9187',
            health: 'unknown',
            labels: {},
            last_scrape: null,
            last_error: 'No data',
            scrape_duration_seconds: 0.0,
          },
        ],
        total: 3,
        up: 1,
        down: 2,
        jobs: ['backend', 'redis-exporter', 'postgres-exporter'],
        timestamp: '2025-01-31T10:30:00Z',
      };

      mockFetch.mockResolvedValueOnce(createMockResponse(mockResponse, { ok: true }));

      const result = await fetchMonitoringTargets();

      expect(result.targets.length).toBe(3);
      expect(result.up).toBe(1);
      expect(result.down).toBe(2);
      expect(result.targets.filter((t) => t.health === 'up').length).toBe(1);
      expect(result.targets.filter((t) => t.health === 'down').length).toBe(1);
      expect(result.targets.filter((t) => t.health === 'unknown').length).toBe(1);
    });

    it('should handle empty targets list', async () => {
      const mockResponse: MonitoringTargetsResponse = {
        targets: [],
        total: 0,
        up: 0,
        down: 0,
        jobs: [],
        timestamp: '2025-01-31T10:30:00Z',
      };

      mockFetch.mockResolvedValueOnce(createMockResponse(mockResponse, { ok: true }));

      const result = await fetchMonitoringTargets();

      expect(result.targets).toEqual([]);
      expect(result.total).toBe(0);
      expect(result.jobs).toEqual([]);
    });

    it('should throw error when Prometheus unreachable (503)', async () => {
      mockFetch.mockResolvedValueOnce(createMockResponse({}, { ok: false, status: 503, statusText: 'Service Unavailable' }));

      await expect(fetchMonitoringTargets()).rejects.toThrow();
    });

    it('should handle targets with labels', async () => {
      const mockResponse: MonitoringTargetsResponse = {
        targets: [
          {
            job: 'backend',
            instance: 'backend:8000',
            health: 'up',
            labels: {
              env: 'production',
              region: 'us-west',
              version: 'v1.2.3',
            },
            last_scrape: '2025-01-31T10:30:00Z',
            last_error: null,
            scrape_duration_seconds: 0.045,
          },
        ],
        total: 1,
        up: 1,
        down: 0,
        jobs: ['backend'],
        timestamp: '2025-01-31T10:30:00Z',
      };

      mockFetch.mockResolvedValueOnce(createMockResponse(mockResponse, { ok: true }));

      const result = await fetchMonitoringTargets();

      expect(result.targets[0].labels).toHaveProperty('env', 'production');
      expect(result.targets[0].labels).toHaveProperty('region', 'us-west');
    });

    it('should throw error on network failure', async () => {
      mockFetch.mockRejectedValueOnce(
        new Error('Network error')
      );

      await expect(fetchMonitoringTargets()).rejects.toThrow('Network error');
    });

    it('should handle multiple jobs with multiple instances', async () => {
      const mockResponse: MonitoringTargetsResponse = {
        targets: [
          {
            job: 'backend',
            instance: 'backend-1:8000',
            health: 'up',
            labels: {},
            last_scrape: '2025-01-31T10:30:00Z',
            last_error: null,
            scrape_duration_seconds: 0.045,
          },
          {
            job: 'backend',
            instance: 'backend-2:8000',
            health: 'up',
            labels: {},
            last_scrape: '2025-01-31T10:30:00Z',
            last_error: null,
            scrape_duration_seconds: 0.038,
          },
          {
            job: 'redis-exporter',
            instance: 'redis-exporter-1:9121',
            health: 'up',
            labels: {},
            last_scrape: '2025-01-31T10:30:00Z',
            last_error: null,
            scrape_duration_seconds: 0.023,
          },
        ],
        total: 3,
        up: 3,
        down: 0,
        jobs: ['backend', 'redis-exporter'],
        timestamp: '2025-01-31T10:30:00Z',
      };

      mockFetch.mockResolvedValueOnce(createMockResponse(mockResponse, { ok: true }));

      const result = await fetchMonitoringTargets();

      expect(result.jobs.length).toBe(2);
      expect(result.targets.filter((t) => t.job === 'backend').length).toBe(2);
      expect(result.targets.filter((t) => t.job === 'redis-exporter').length).toBe(1);
    });
  });
});
