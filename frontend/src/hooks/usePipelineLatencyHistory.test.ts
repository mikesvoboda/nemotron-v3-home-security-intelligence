/**
 * Integration tests for usePipelineLatencyHistory hook (NEM-4825)
 *
 * These tests verify that the hook correctly:
 * 1. Calls the GET /api/system/pipeline-latency/history endpoint
 * 2. Passes the correct since and bucket_seconds query parameters
 * 3. Transforms the API response into the expected format
 * 4. Handles loading and error states
 * 5. Supports refetch functionality
 * 6. Formats data for Tremor chart consumption with stage breakdowns
 *
 * RED PHASE: These tests will FAIL until the hook is implemented.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { usePipelineLatencyHistory } from './usePipelineLatencyHistory';
import * as pipelineLatencyApi from '../services/pipelineLatencyApi';

// Mock the API module
vi.mock('../services/pipelineLatencyApi', () => ({
  getPipelineLatencyHistory: vi.fn(),
}));

describe('usePipelineLatencyHistory', () => {
  const mockLatencyHistoryResponse = {
    snapshots: [
      {
        timestamp: '2025-01-31T10:00:00Z',
        stages: {
          watch_to_detect: {
            avg_ms: 150,
            p50_ms: 140,
            p95_ms: 200,
            p99_ms: 250,
            sample_count: 100,
          },
          detect_to_batch: {
            avg_ms: 50,
            p50_ms: 45,
            p95_ms: 80,
            p99_ms: 100,
            sample_count: 100,
          },
          batch_to_analyze: {
            avg_ms: 500,
            p50_ms: 450,
            p95_ms: 700,
            p99_ms: 900,
            sample_count: 100,
          },
          total_pipeline: {
            avg_ms: 700,
            p50_ms: 635,
            p95_ms: 980,
            p99_ms: 1250,
            sample_count: 100,
          },
        },
      },
      {
        timestamp: '2025-01-31T10:01:00Z',
        stages: {
          watch_to_detect: {
            avg_ms: 155,
            p50_ms: 145,
            p95_ms: 205,
            p99_ms: 255,
            sample_count: 105,
          },
          detect_to_batch: {
            avg_ms: 52,
            p50_ms: 47,
            p95_ms: 82,
            p99_ms: 102,
            sample_count: 105,
          },
          batch_to_analyze: {
            avg_ms: 510,
            p50_ms: 460,
            p95_ms: 710,
            p99_ms: 910,
            sample_count: 105,
          },
          total_pipeline: {
            avg_ms: 717,
            p50_ms: 652,
            p95_ms: 997,
            p99_ms: 1267,
            sample_count: 105,
          },
        },
      },
    ],
    window_minutes: 60,
    bucket_seconds: 60,
    timestamp: '2025-01-31T10:01:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization and loading', () => {
    it('should return loading state initially', () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();
      expect(result.current.error).toBeNull();
    });

    it('should use default parameters when not specified', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Default: since=60 (minutes), bucket_seconds=60
      expect(pipelineLatencyApi.getPipelineLatencyHistory).toHaveBeenCalledWith({
        since: 60,
        bucket_seconds: 60,
      });
    });
  });

  describe('successful data fetching', () => {
    it('should fetch and return pipeline latency history data', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockLatencyHistoryResponse);
      expect(result.current.error).toBeNull();
    });

    it('should call API with custom since parameter', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() =>
        usePipelineLatencyHistory({ since: 120, bucket_seconds: 60 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(pipelineLatencyApi.getPipelineLatencyHistory).toHaveBeenCalledWith({
        since: 120,
        bucket_seconds: 60,
      });
    });

    it('should call API with custom bucket_seconds parameter', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() =>
        usePipelineLatencyHistory({ since: 60, bucket_seconds: 30 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(pipelineLatencyApi.getPipelineLatencyHistory).toHaveBeenCalledWith({
        since: 60,
        bucket_seconds: 30,
      });
    });

    it('should handle empty snapshots array', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue({
        snapshots: [],
        window_minutes: 60,
        bucket_seconds: 60,
        timestamp: '2025-01-31T10:00:00Z',
      });

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data?.snapshots).toEqual([]);
      expect(result.current.error).toBeNull();
    });

    it('should preserve all stage metrics', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const firstSnapshot = result.current.data?.snapshots[0];
      expect(firstSnapshot?.stages).toHaveProperty('watch_to_detect');
      expect(firstSnapshot?.stages).toHaveProperty('detect_to_batch');
      expect(firstSnapshot?.stages).toHaveProperty('batch_to_analyze');
      expect(firstSnapshot?.stages).toHaveProperty('total_pipeline');
    });

    it('should preserve percentile metrics for each stage', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const stage = result.current.data?.snapshots[0].stages.watch_to_detect;
      expect(stage).toHaveProperty('avg_ms');
      expect(stage).toHaveProperty('p50_ms');
      expect(stage).toHaveProperty('p95_ms');
      expect(stage).toHaveProperty('p99_ms');
      expect(stage).toHaveProperty('sample_count');
    });
  });

  describe('error handling', () => {
    it('should handle API errors', async () => {
      const mockError = new Error('Failed to fetch pipeline latency history');
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockRejectedValue(mockError);

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
      expect(result.current.error?.message).toContain('Failed to fetch pipeline latency history');
      expect(result.current.data).toBeUndefined();
    });

    it('should handle network errors', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockRejectedValue(
        new Error('Network request failed')
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
      expect(result.current.data).toBeUndefined();
    });

    it('should handle 500 server errors', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockRejectedValue(
        new Error('Internal server error')
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
    });
  });

  describe('refetch functionality', () => {
    it('should provide a refetch function', () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      expect(result.current.refetch).toBeDefined();
      expect(typeof result.current.refetch).toBe('function');
    });

    it('should refetch data when refetch is called', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(pipelineLatencyApi.getPipelineLatencyHistory).toHaveBeenCalledTimes(1);

      // Call refetch
      result.current.refetch();

      await waitFor(() => {
        expect(pipelineLatencyApi.getPipelineLatencyHistory).toHaveBeenCalledTimes(2);
      });
    });

    it('should set loading state during refetch', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Mock a slower response for refetch
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve(mockLatencyHistoryResponse), 100)
          )
      );

      result.current.refetch();

      // Should be loading immediately after refetch
      await waitFor(() => {
        expect(result.current.isLoading).toBe(true);
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('data transformation for charts', () => {
    it('should transform data into Tremor-compatible format', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should have chartData property formatted for Tremor
      expect(result.current.chartData).toBeDefined();
      expect(Array.isArray(result.current.chartData)).toBe(true);
    });

    it('should format timestamps for chart display', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Chart data should have formatted timestamps
      result.current.chartData?.forEach((point) => {
        expect(point).toHaveProperty('timestamp');
        expect(typeof point.timestamp).toBe('string');
      });
    });

    it('should include all stage latencies in chart data', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      result.current.chartData?.forEach((point) => {
        expect(point).toHaveProperty('watch_to_detect');
        expect(point).toHaveProperty('detect_to_batch');
        expect(point).toHaveProperty('batch_to_analyze');
        expect(point).toHaveProperty('total_pipeline');
      });
    });

    it('should use average latency for chart values', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const firstPoint = result.current.chartData?.[0];
      expect(firstPoint?.watch_to_detect).toBe(150);
      expect(firstPoint?.detect_to_batch).toBe(50);
      expect(firstPoint?.batch_to_analyze).toBe(500);
      expect(firstPoint?.total_pipeline).toBe(700);
    });

    it('should convert milliseconds to seconds for readability', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result } = renderHook(() => usePipelineLatencyHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // If converting to seconds, values should be divided by 1000
      const firstPoint = result.current.chartData?.[0];
      // This test depends on implementation choice - could be ms or seconds
      expect(typeof firstPoint?.watch_to_detect).toBe('number');
    });
  });

  describe('parameter changes', () => {
    it('should refetch when since parameter changes', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result, rerender } = renderHook(
        ({ since, bucket_seconds }) =>
          usePipelineLatencyHistory({ since, bucket_seconds }),
        {
          initialProps: { since: 60, bucket_seconds: 60 },
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(pipelineLatencyApi.getPipelineLatencyHistory).toHaveBeenCalledWith({
        since: 60,
        bucket_seconds: 60,
      });

      // Change since parameter
      rerender({ since: 120, bucket_seconds: 60 });

      await waitFor(() => {
        expect(pipelineLatencyApi.getPipelineLatencyHistory).toHaveBeenCalledWith({
          since: 120,
          bucket_seconds: 60,
        });
      });

      expect(pipelineLatencyApi.getPipelineLatencyHistory).toHaveBeenCalledTimes(2);
    });

    it('should refetch when bucket_seconds parameter changes', async () => {
      vi.mocked(pipelineLatencyApi.getPipelineLatencyHistory).mockResolvedValue(
        mockLatencyHistoryResponse
      );

      const { result, rerender } = renderHook(
        ({ since, bucket_seconds }) =>
          usePipelineLatencyHistory({ since, bucket_seconds }),
        {
          initialProps: { since: 60, bucket_seconds: 60 },
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Change bucket_seconds parameter
      rerender({ since: 60, bucket_seconds: 30 });

      await waitFor(() => {
        expect(pipelineLatencyApi.getPipelineLatencyHistory).toHaveBeenCalledWith({
          since: 60,
          bucket_seconds: 30,
        });
      });

      expect(pipelineLatencyApi.getPipelineLatencyHistory).toHaveBeenCalledTimes(2);
    });
  });
});
