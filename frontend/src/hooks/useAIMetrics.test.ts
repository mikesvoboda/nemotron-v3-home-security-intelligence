import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useAIMetrics, type AIPerformanceState } from './useAIMetrics';
import * as api from '../services/api';
import * as metricsParser from '../services/metricsParser';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchTelemetry: vi.fn(),
  fetchHealth: vi.fn(),
  fetchDlqStats: vi.fn(),
  fetchDetectionStats: vi.fn(),
}));

// Mock the metricsParser module
vi.mock('../services/metricsParser', () => ({
  fetchAIMetrics: vi.fn(),
}));

// Mock fetch for pipeline latency endpoint - use vi.fn() and stub in beforeEach for test isolation
const mockFetch = vi.fn();

describe('useAIMetrics', () => {
  // Mock response data for each endpoint
  const mockMetricsResponse: metricsParser.AIMetrics = {
    detection_latency: {
      avg_ms: 45.2,
      p50_ms: 42.0,
      p95_ms: 78.5,
      p99_ms: 120.3,
      sample_count: 1500,
    },
    analysis_latency: {
      avg_ms: 2100.5,
      p50_ms: 1800.0,
      p95_ms: 4200.0,
      p99_ms: 6500.0,
      sample_count: 500,
    },
    total_detections: 15000,
    total_events: 3000,
    detection_queue_depth: 5,
    analysis_queue_depth: 2,
    pipeline_errors: { timeout: 12, model_error: 3 },
    queue_overflows: { detection_queue: 5, analysis_queue: 1 },
    dlq_items: { 'dlq:detection_queue': 8, 'dlq:analysis_queue': 2 },
    timestamp: '2025-12-28T10:30:00Z',
  };

  const mockTelemetryResponse: api.TelemetryResponse = {
    queues: {
      detection_queue: 7,
      analysis_queue: 3,
    },
    timestamp: '2025-12-28T10:30:00Z',
  } as api.TelemetryResponse;

  const mockHealthResponse: api.HealthResponse = {
    status: 'healthy',
    timestamp: '2025-12-28T10:30:00Z',
    services: {
      database: { status: 'healthy', message: 'Database operational' },
      redis: { status: 'healthy', message: 'Redis connected' },
      ai: {
        status: 'healthy',
        message: 'AI services operational',
        details: {
          rtdetr: 'healthy',
          nemotron: 'healthy',
        },
      },
    },
  };

  const mockPipelineLatencyResponse = {
    watch_to_detect: {
      avg_ms: 25.5,
      min_ms: 10.2,
      max_ms: 85.3,
      p50_ms: 22.0,
      p95_ms: 65.8,
      p99_ms: 78.2,
      sample_count: 1200,
    },
    detect_to_batch: {
      avg_ms: 15.2,
      min_ms: 5.0,
      max_ms: 45.0,
      p50_ms: 12.0,
      p95_ms: 35.0,
      p99_ms: 42.0,
      sample_count: 1200,
    },
    batch_to_analyze: {
      avg_ms: 2050.0,
      min_ms: 1200.0,
      max_ms: 5500.0,
      p50_ms: 1800.0,
      p95_ms: 4000.0,
      p99_ms: 5000.0,
      sample_count: 400,
    },
    total_pipeline: {
      avg_ms: 2800.0,
      min_ms: 1500.0,
      max_ms: 8000.0,
      p50_ms: 2500.0,
      p95_ms: 5500.0,
      p99_ms: 7000.0,
      sample_count: 400,
    },
    window_minutes: 60,
    timestamp: '2025-12-28T10:30:00Z',
  };

  const mockDlqStatsResponse: api.DLQStatsResponse = {
    detection_queue_count: 1611,
    analysis_queue_count: 5,
    total_count: 1616,
  };

  const mockDetectionStatsResponse: api.DetectionStatsResponse = {
    total_detections: 25000,
    detections_by_class: { person: 15000, car: 8000, truck: 2000 },
    average_confidence: 0.87,
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Stub global fetch for proper test isolation in parallel execution
    vi.stubGlobal('fetch', mockFetch);

    // Default mock implementations - all endpoints succeed
    vi.mocked(metricsParser.fetchAIMetrics).mockResolvedValue(mockMetricsResponse);
    vi.mocked(api.fetchTelemetry).mockResolvedValue(mockTelemetryResponse);
    vi.mocked(api.fetchHealth).mockResolvedValue(mockHealthResponse);
    vi.mocked(api.fetchDlqStats).mockResolvedValue(mockDlqStatsResponse);
    vi.mocked(api.fetchDetectionStats).mockResolvedValue(mockDetectionStatsResponse);
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockPipelineLatencyResponse),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  describe('initial state', () => {
    it('should start with isLoading true', () => {
      // Don't let fetches resolve
      vi.mocked(metricsParser.fetchAIMetrics).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchTelemetry).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchHealth).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchDlqStats).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchDetectionStats).mockReturnValue(new Promise(() => {}));
      mockFetch.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      expect(result.current.isLoading).toBe(true);
    });

    it('should start with default AI model status as unknown', () => {
      // Don't let fetches resolve to test initial state
      vi.mocked(metricsParser.fetchAIMetrics).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchTelemetry).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchHealth).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchDlqStats).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchDetectionStats).mockReturnValue(new Promise(() => {}));
      mockFetch.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      expect(result.current.data.rtdetr.status).toBe('unknown');
      expect(result.current.data.nemotron.status).toBe('unknown');
    });

    it('should start with null latency metrics', () => {
      // Don't let fetches resolve
      vi.mocked(metricsParser.fetchAIMetrics).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchTelemetry).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchHealth).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchDlqStats).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchDetectionStats).mockReturnValue(new Promise(() => {}));
      mockFetch.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      expect(result.current.data.detectionLatency).toBeNull();
      expect(result.current.data.analysisLatency).toBeNull();
      expect(result.current.data.pipelineLatency).toBeNull();
    });

    it('should start with zero counters and empty error maps', () => {
      // Don't let fetches resolve
      vi.mocked(metricsParser.fetchAIMetrics).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchTelemetry).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchHealth).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchDlqStats).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchDetectionStats).mockReturnValue(new Promise(() => {}));
      mockFetch.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      expect(result.current.data.totalDetections).toBe(0);
      expect(result.current.data.totalEvents).toBe(0);
      expect(result.current.data.detectionQueueDepth).toBe(0);
      expect(result.current.data.analysisQueueDepth).toBe(0);
      expect(result.current.data.pipelineErrors).toEqual({});
      expect(result.current.data.queueOverflows).toEqual({});
      expect(result.current.data.dlqItems).toEqual({});
      expect(result.current.data.detectionsByClass).toEqual({});
    });

    it('should start with null lastUpdated', () => {
      // Don't let fetches resolve
      vi.mocked(metricsParser.fetchAIMetrics).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchTelemetry).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchHealth).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchDlqStats).mockReturnValue(new Promise(() => {}));
      vi.mocked(api.fetchDetectionStats).mockReturnValue(new Promise(() => {}));
      mockFetch.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      expect(result.current.data.lastUpdated).toBeNull();
    });
  });

  describe('successful data fetching', () => {
    it('should fetch all 6 endpoints on mount', async () => {
      renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(metricsParser.fetchAIMetrics).toHaveBeenCalledTimes(1);
      });

      expect(api.fetchTelemetry).toHaveBeenCalledTimes(1);
      expect(api.fetchHealth).toHaveBeenCalledTimes(1);
      expect(api.fetchDlqStats).toHaveBeenCalledTimes(1);
      expect(api.fetchDetectionStats).toHaveBeenCalledTimes(1);
      // Fetch may be called with a string URL or Request object depending on environment
      expect(mockFetch).toHaveBeenCalled();
      const fetchCall = mockFetch.mock.calls[0][0];
      const url = typeof fetchCall === 'string' ? fetchCall : fetchCall.url;
      expect(url).toBe('/api/system/pipeline-latency?window_minutes=60');
    });

    it('should set isLoading to false after fetch completes', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('should populate detection latency from metrics endpoint', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.data.detectionLatency).not.toBeNull();
      });

      expect(result.current.data.detectionLatency?.avg_ms).toBe(45.2);
      expect(result.current.data.detectionLatency?.p50_ms).toBe(42.0);
      expect(result.current.data.detectionLatency?.p95_ms).toBe(78.5);
      expect(result.current.data.detectionLatency?.p99_ms).toBe(120.3);
      expect(result.current.data.detectionLatency?.sample_count).toBe(1500);
    });

    it('should populate analysis latency from metrics endpoint', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.data.analysisLatency).not.toBeNull();
      });

      expect(result.current.data.analysisLatency?.avg_ms).toBe(2100.5);
      expect(result.current.data.analysisLatency?.sample_count).toBe(500);
    });

    it('should populate pipeline latency from pipeline-latency endpoint', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.data.pipelineLatency).not.toBeNull();
      });

      expect(result.current.data.pipelineLatency?.total_pipeline?.avg_ms).toBe(2800.0);
      expect(result.current.data.pipelineLatency?.watch_to_detect?.avg_ms).toBe(25.5);
      expect(result.current.data.pipelineLatency?.window_minutes).toBe(60);
    });

    it('should prefer telemetry queue depths over metrics endpoint', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should use telemetry values (7, 3) instead of metrics values (5, 2)
      expect(result.current.data.detectionQueueDepth).toBe(7);
      expect(result.current.data.analysisQueueDepth).toBe(3);
    });

    it('should populate AI model statuses from health endpoint', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.data.rtdetr.status).toBe('healthy');
      });

      expect(result.current.data.rtdetr.name).toBe('RT-DETRv2');
      expect(result.current.data.nemotron.status).toBe('healthy');
      expect(result.current.data.nemotron.name).toBe('Nemotron');
    });

    it('should populate counters and error maps from metrics, DLQ stats, and detection stats', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // totalDetections should come from detection stats API (25000) not metrics (15000)
      expect(result.current.data.totalDetections).toBe(25000);
      expect(result.current.data.totalEvents).toBe(3000);
      expect(result.current.data.pipelineErrors).toEqual({ timeout: 12, model_error: 3 });
      expect(result.current.data.queueOverflows).toEqual({
        detection_queue: 5,
        analysis_queue: 1,
      });
      // DLQ items should come from /api/dlq/stats (actual current counts: 1611, 5)
      // NOT from Prometheus metrics (cumulative counter: 8, 2)
      expect(result.current.data.dlqItems).toEqual({
        'dlq:detection_queue': 1611,
        'dlq:analysis_queue': 5,
      });
      // detectionsByClass should come from detection stats API
      expect(result.current.data.detectionsByClass).toEqual({
        person: 15000,
        car: 8000,
        truck: 2000,
      });
    });

    it('should set lastUpdated timestamp after fetch', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.data.lastUpdated).not.toBeNull();
      });

      // Should be a valid ISO timestamp
      const timestamp = new Date(result.current.data.lastUpdated!);
      expect(timestamp.getTime()).not.toBeNaN();
    });
  });

  describe('partial failures (fault tolerance)', () => {
    it('should handle metrics endpoint failure gracefully', async () => {
      vi.mocked(metricsParser.fetchAIMetrics).mockRejectedValue(
        new Error('Metrics unavailable')
      );

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should still have data from other endpoints
      expect(result.current.data.rtdetr.status).toBe('healthy');
      expect(result.current.data.pipelineLatency).not.toBeNull();
      // Latency from metrics should be null
      expect(result.current.data.detectionLatency).toBeNull();
      // No error should be set since we got partial data
      expect(result.current.error).toBeNull();
    });

    it('should handle telemetry endpoint failure gracefully', async () => {
      vi.mocked(api.fetchTelemetry).mockRejectedValue(
        new Error('Telemetry unavailable')
      );

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should fall back to metrics queue depths
      expect(result.current.data.detectionQueueDepth).toBe(5);
      expect(result.current.data.analysisQueueDepth).toBe(2);
      expect(result.current.error).toBeNull();
    });

    it('should handle health endpoint failure gracefully', async () => {
      vi.mocked(api.fetchHealth).mockRejectedValue(
        new Error('Health unavailable')
      );

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // AI model statuses should remain unknown
      expect(result.current.data.rtdetr.status).toBe('unknown');
      expect(result.current.data.nemotron.status).toBe('unknown');
      // Other data should still be available
      expect(result.current.data.detectionLatency).not.toBeNull();
      expect(result.current.error).toBeNull();
    });

    it('should handle pipeline latency endpoint failure gracefully', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      });

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Pipeline latency should be null
      expect(result.current.data.pipelineLatency).toBeNull();
      // Other data should still be available
      expect(result.current.data.detectionLatency).not.toBeNull();
      expect(result.current.error).toBeNull();
    });

    it('should handle multiple endpoint failures', async () => {
      vi.mocked(metricsParser.fetchAIMetrics).mockRejectedValue(new Error('Failed'));
      vi.mocked(api.fetchHealth).mockRejectedValue(new Error('Failed'));

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should still have telemetry and pipeline latency data
      expect(result.current.data.pipelineLatency).not.toBeNull();
      // Queue depths from telemetry
      expect(result.current.data.detectionQueueDepth).toBe(7);
    });

    it('should handle all endpoints failing', async () => {
      vi.mocked(metricsParser.fetchAIMetrics).mockRejectedValue(new Error('Failed'));
      vi.mocked(api.fetchTelemetry).mockRejectedValue(new Error('Failed'));
      vi.mocked(api.fetchHealth).mockRejectedValue(new Error('Failed'));
      vi.mocked(api.fetchDlqStats).mockRejectedValue(new Error('Failed'));
      vi.mocked(api.fetchDetectionStats).mockRejectedValue(new Error('Failed'));
      mockFetch.mockRejectedValue(new Error('Failed'));

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // All data should be defaults/null
      expect(result.current.data.detectionLatency).toBeNull();
      expect(result.current.data.analysisLatency).toBeNull();
      expect(result.current.data.pipelineLatency).toBeNull();
      expect(result.current.data.rtdetr.status).toBe('unknown');
      expect(result.current.data.dlqItems).toEqual({});
      expect(result.current.data.detectionsByClass).toEqual({});
      // No error set since Promise.allSettled handles failures gracefully
      expect(result.current.error).toBeNull();
    });
  });

  describe('AI model status extraction', () => {
    it('should extract unhealthy status from health response', async () => {
      vi.mocked(api.fetchHealth).mockResolvedValue({
        ...mockHealthResponse,
        services: {
          ...mockHealthResponse.services,
          ai: {
            status: 'unhealthy',
            message: 'AI service degraded',
            details: {
              rtdetr: 'connection refused',
              nemotron: 'healthy',
            },
          },
        },
      });

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data.rtdetr.status).toBe('unhealthy');
      expect(result.current.data.rtdetr.message).toBe('connection refused');
      expect(result.current.data.nemotron.status).toBe('healthy');
    });

    it('should handle missing AI service in health response', async () => {
      vi.mocked(api.fetchHealth).mockResolvedValue({
        ...mockHealthResponse,
        services: {
          database: mockHealthResponse.services?.database,
          redis: mockHealthResponse.services?.redis,
          // ai service missing
        },
      });

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data.rtdetr.status).toBe('unknown');
      expect(result.current.data.nemotron.status).toBe('unknown');
    });

    it('should handle missing details in AI service', async () => {
      vi.mocked(api.fetchHealth).mockResolvedValue({
        ...mockHealthResponse,
        services: {
          ...mockHealthResponse.services,
          ai: {
            status: 'healthy',
            message: 'OK',
            // details missing
          },
        },
      });

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data.rtdetr.status).toBe('unknown');
      expect(result.current.data.nemotron.status).toBe('unknown');
    });
  });

  describe('polling behavior', () => {
    it('should set up polling with default 5000ms interval', () => {
      const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');

      renderHook(() => useAIMetrics());

      expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 5000);

      setIntervalSpy.mockRestore();
    });

    it('should respect custom polling interval', () => {
      const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');

      renderHook(() => useAIMetrics({ pollingInterval: 10000 }));

      expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 10000);

      setIntervalSpy.mockRestore();
    });

    it('should not set up polling when enablePolling is false', () => {
      const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');

      renderHook(() => useAIMetrics({ enablePolling: false }));

      // setInterval should not be called with our pollingInterval
      const pollCalls = setIntervalSpy.mock.calls.filter(
        (call) => typeof call[1] === 'number' && call[1] >= 1000
      );
      expect(pollCalls.length).toBe(0);

      setIntervalSpy.mockRestore();
    });

    it('should not set up polling when pollingInterval is 0', () => {
      const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');

      renderHook(() => useAIMetrics({ pollingInterval: 0 }));

      // setInterval should not be called with 0 or with our typical intervals
      const pollCalls = setIntervalSpy.mock.calls.filter(
        (call) => call[1] === 0 || (typeof call[1] === 'number' && call[1] >= 1000)
      );
      expect(pollCalls.length).toBe(0);

      setIntervalSpy.mockRestore();
    });
  });

  describe('manual refresh', () => {
    it('should manually trigger a refresh', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      // Wait for initial fetch
      await waitFor(() => {
        expect(metricsParser.fetchAIMetrics).toHaveBeenCalledTimes(1);
      });

      // Manual refresh
      await act(async () => {
        await result.current.refresh();
      });

      expect(metricsParser.fetchAIMetrics).toHaveBeenCalledTimes(2);
    });

    it('should set isLoading true during refresh', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Setup slow response for refresh
      let resolveMetrics: () => void;
      const metricsPromise = new Promise<metricsParser.AIMetrics>((resolve) => {
        resolveMetrics = () => resolve(mockMetricsResponse);
      });
      vi.mocked(metricsParser.fetchAIMetrics).mockReturnValue(metricsPromise);

      // Start refresh - should be loading
      let refreshPromise: Promise<void>;
      act(() => {
        refreshPromise = result.current.refresh();
      });

      expect(result.current.isLoading).toBe(true);

      // Complete the fetch
      await act(async () => {
        resolveMetrics!();
        await refreshPromise;
      });

      expect(result.current.isLoading).toBe(false);
    });

    it('should update data after refresh', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const originalDetections = result.current.data.totalDetections;

      // Update mock to return different data - need to update detection stats API
      // since it takes priority over metrics for totalDetections
      vi.mocked(api.fetchDetectionStats).mockResolvedValue({
        ...mockDetectionStatsResponse,
        total_detections: 30000,
      });

      await act(async () => {
        await result.current.refresh();
      });

      expect(result.current.data.totalDetections).toBe(30000);
      expect(result.current.data.totalDetections).not.toBe(originalDetections);
    });
  });

  describe('cleanup on unmount', () => {
    it('should clear interval on unmount', () => {
      const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');

      const { unmount } = renderHook(() => useAIMetrics({ pollingInterval: 5000 }));

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
      clearIntervalSpy.mockRestore();
    });

    it('should not update state after unmount', () => {
      // Create a delayed promise that resolves after unmount
      let resolveMetrics: (value: metricsParser.AIMetrics) => void;
      const metricsPromise = new Promise<metricsParser.AIMetrics>((resolve) => {
        resolveMetrics = resolve;
      });
      vi.mocked(metricsParser.fetchAIMetrics).mockReturnValue(metricsPromise);

      const { result, unmount } = renderHook(() => useAIMetrics({ enablePolling: false }));

      expect(result.current.isLoading).toBe(true);

      // Unmount before promise resolves
      unmount();

      // Now resolve the promise - this should not throw errors
      act(() => {
        resolveMetrics!(mockMetricsResponse);
      });

      // Test passes if no error is thrown (React warning about updating unmounted component)
    });
  });

  describe('error handling', () => {
    it('should log error to console when fetch throws synchronously', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      // Force an actual error in the try block (synchronous throw)
      const mockError = new Error('Fetch setup error');
      vi.mocked(metricsParser.fetchAIMetrics).mockImplementation(() => {
        throw mockError;
      });

      renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalledWith('Error fetching AI metrics:', mockError);
      });

      consoleErrorSpy.mockRestore();
    });

    it('should set error message when fetchAllMetrics throws', async () => {
      const mockError = new Error('Synchronous error');
      vi.mocked(metricsParser.fetchAIMetrics).mockImplementation(() => {
        throw mockError;
      });

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.error).toBe('Synchronous error');
      });
    });

    it('should handle Error objects with message', async () => {
      vi.mocked(metricsParser.fetchAIMetrics).mockImplementation(() => {
        throw new Error('Custom error message');
      });

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.error).toBe('Custom error message');
      });
    });
  });

  describe('data transformation and combining', () => {
    it('should use metrics queue depth when telemetry is unavailable', async () => {
      vi.mocked(api.fetchTelemetry).mockRejectedValue(new Error('Failed'));

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should fall back to metrics values
      expect(result.current.data.detectionQueueDepth).toBe(5);
      expect(result.current.data.analysisQueueDepth).toBe(2);
    });

    it('should handle null metrics latency gracefully', async () => {
      vi.mocked(metricsParser.fetchAIMetrics).mockResolvedValue({
        ...mockMetricsResponse,
        detection_latency: null,
        analysis_latency: null,
      });

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data.detectionLatency).toBeNull();
      expect(result.current.data.analysisLatency).toBeNull();
    });

    it('should handle null pipeline latency stages', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            watch_to_detect: null,
            detect_to_batch: null,
            batch_to_analyze: null,
            total_pipeline: {
              avg_ms: 2800.0,
              min_ms: 1500.0,
              max_ms: 8000.0,
              p50_ms: 2500.0,
              p95_ms: 5500.0,
              p99_ms: 7000.0,
              sample_count: 400,
            },
            window_minutes: 60,
            timestamp: '2025-12-28T10:30:00Z',
          }),
      });

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data.pipelineLatency?.watch_to_detect).toBeNull();
      expect(result.current.data.pipelineLatency?.total_pipeline?.avg_ms).toBe(2800.0);
    });

    it('should handle empty error maps from metrics', async () => {
      vi.mocked(metricsParser.fetchAIMetrics).mockResolvedValue({
        ...mockMetricsResponse,
        pipeline_errors: {},
        queue_overflows: {},
        dlq_items: {},
      });
      // Even with empty metrics dlq_items, should still use DLQ stats API
      vi.mocked(api.fetchDlqStats).mockResolvedValue({
        detection_queue_count: 0,
        analysis_queue_count: 0,
        total_count: 0,
      });

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data.pipelineErrors).toEqual({});
      expect(result.current.data.queueOverflows).toEqual({});
      expect(result.current.data.dlqItems).toEqual({});
    });

    it('should fallback to metrics dlq_items when DLQ stats API fails', async () => {
      vi.mocked(api.fetchDlqStats).mockRejectedValue(new Error('DLQ API unavailable'));

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should fall back to metrics dlq_items (cumulative counter values)
      expect(result.current.data.dlqItems).toEqual({
        'dlq:detection_queue': 8,
        'dlq:analysis_queue': 2,
      });
      // No error since partial data is still available
      expect(result.current.error).toBeNull();
    });

    it('should handle missing queues in telemetry response', async () => {
      vi.mocked(api.fetchTelemetry).mockResolvedValue({
        timestamp: '2025-12-28T10:30:00Z',
        // queues property missing
      } as api.TelemetryResponse);

      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should fall back to metrics values
      expect(result.current.data.detectionQueueDepth).toBe(5);
      expect(result.current.data.analysisQueueDepth).toBe(2);
    });
  });

  describe('return type', () => {
    it('should return all expected properties', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current).toHaveProperty('data');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('refresh');
      expect(typeof result.current.refresh).toBe('function');
    });

    it('should return data with correct structure', async () => {
      const { result } = renderHook(() => useAIMetrics({ enablePolling: false }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const data: AIPerformanceState = result.current.data;

      expect(data).toHaveProperty('rtdetr');
      expect(data).toHaveProperty('nemotron');
      expect(data).toHaveProperty('detectionLatency');
      expect(data).toHaveProperty('analysisLatency');
      expect(data).toHaveProperty('pipelineLatency');
      expect(data).toHaveProperty('totalDetections');
      expect(data).toHaveProperty('totalEvents');
      expect(data).toHaveProperty('detectionQueueDepth');
      expect(data).toHaveProperty('analysisQueueDepth');
      expect(data).toHaveProperty('pipelineErrors');
      expect(data).toHaveProperty('queueOverflows');
      expect(data).toHaveProperty('dlqItems');
      expect(data).toHaveProperty('lastUpdated');
    });
  });
});
