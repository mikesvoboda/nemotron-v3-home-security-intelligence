/**
 * Integration tests for useGPUMetricsHistory hook (NEM-4825)
 *
 * These tests verify that the hook correctly:
 * 1. Calls the GET /api/system/gpu/history endpoint
 * 2. Passes the correct limit query parameter
 * 3. Transforms the API response into the expected format
 * 4. Handles loading and error states
 * 5. Supports refetch functionality
 * 6. Formats data for Tremor chart consumption
 *
 * RED PHASE: These tests will FAIL until the hook is implemented.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useGPUMetricsHistory } from './useGPUMetricsHistory';
import * as gpuHistoryApi from '../services/gpuHistoryApi';

// Mock the API module
vi.mock('../services/gpuHistoryApi', () => ({
  getGPUHistory: vi.fn(),
}));

describe('useGPUMetricsHistory', () => {
  const mockGPUHistoryResponse = {
    items: [
      {
        recorded_at: '2025-01-31T10:00:00Z',
        gpu_name: 'NVIDIA RTX 4090',
        utilization: 75,
        memory_used: 8192,
        memory_total: 24576,
        temperature: 65,
        power_usage: 350,
        inference_fps: 30,
      },
      {
        recorded_at: '2025-01-31T10:00:05Z',
        gpu_name: 'NVIDIA RTX 4090',
        utilization: 78,
        memory_used: 8500,
        memory_total: 24576,
        temperature: 66,
        power_usage: 355,
        inference_fps: 31,
      },
      {
        recorded_at: '2025-01-31T10:00:10Z',
        gpu_name: 'NVIDIA RTX 4090',
        utilization: 80,
        memory_used: 9000,
        memory_total: 24576,
        temperature: 67,
        power_usage: 360,
        inference_fps: 32,
      },
    ],
    pagination: {
      total: 300,
      limit: 300,
      has_more: false,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization and loading', () => {
    it('should return loading state initially', () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      const { result } = renderHook(() => useGPUMetricsHistory());

      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();
      expect(result.current.error).toBeNull();
    });

    it('should use default limit of 300 when not specified', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(gpuHistoryApi.getGPUHistory).toHaveBeenCalledWith(300);
    });
  });

  describe('successful data fetching', () => {
    it('should fetch and return GPU history data', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockGPUHistoryResponse);
      expect(result.current.error).toBeNull();
      expect(gpuHistoryApi.getGPUHistory).toHaveBeenCalledWith(300);
    });

    it('should call API with custom limit parameter', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory({ limit: 100 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(gpuHistoryApi.getGPUHistory).toHaveBeenCalledWith(100);
    });

    it('should handle empty items array', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue({
        items: [],
        pagination: {
          total: 0,
          limit: 300,
          has_more: false,
        },
      });

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data?.items).toEqual([]);
      expect(result.current.error).toBeNull();
    });

    it('should preserve all GPU metrics fields', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const firstItem = result.current.data?.items[0];
      expect(firstItem).toHaveProperty('recorded_at');
      expect(firstItem).toHaveProperty('gpu_name');
      expect(firstItem).toHaveProperty('utilization');
      expect(firstItem).toHaveProperty('memory_used');
      expect(firstItem).toHaveProperty('memory_total');
      expect(firstItem).toHaveProperty('temperature');
      expect(firstItem).toHaveProperty('power_usage');
      expect(firstItem).toHaveProperty('inference_fps');
    });

    it('should handle pagination metadata', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data?.pagination).toEqual({
        total: 300,
        limit: 300,
        has_more: false,
      });
    });
  });

  describe('error handling', () => {
    it('should handle API errors', async () => {
      const mockError = new Error('Failed to fetch GPU history');
      vi.mocked(gpuHistoryApi.getGPUHistory).mockRejectedValue(mockError);

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
      expect(result.current.error?.message).toContain('Failed to fetch GPU history');
      expect(result.current.data).toBeUndefined();
    });

    it('should handle network errors', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockRejectedValue(
        new Error('Network request failed')
      );

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
      expect(result.current.data).toBeUndefined();
    });

    it('should handle 500 server errors', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockRejectedValue(
        new Error('Internal server error')
      );

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
    });
  });

  describe('refetch functionality', () => {
    it('should provide a refetch function', () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory());

      expect(result.current.refetch).toBeDefined();
      expect(typeof result.current.refetch).toBe('function');
    });

    it('should refetch data when refetch is called', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(gpuHistoryApi.getGPUHistory).toHaveBeenCalledTimes(1);

      // Call refetch
      result.current.refetch();

      await waitFor(() => {
        expect(gpuHistoryApi.getGPUHistory).toHaveBeenCalledTimes(2);
      });
    });

    it('should set loading state during refetch', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Mock a slower response for refetch
      vi.mocked(gpuHistoryApi.getGPUHistory).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve(mockGPUHistoryResponse), 100)
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
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should have chartData property formatted for Tremor
      expect(result.current.chartData).toBeDefined();
      expect(Array.isArray(result.current.chartData)).toBe(true);
    });

    it('should format timestamps for chart display', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Chart data should have formatted timestamps
      result.current.chartData?.forEach((point) => {
        expect(point).toHaveProperty('timestamp');
        expect(typeof point.timestamp).toBe('string');
      });
    });

    it('should include utilization percentage in chart data', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      result.current.chartData?.forEach((point) => {
        expect(point).toHaveProperty('utilization');
        expect(typeof point.utilization).toBe('number');
      });
    });

    it('should include temperature in chart data', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      result.current.chartData?.forEach((point) => {
        expect(point).toHaveProperty('temperature');
        expect(typeof point.temperature).toBe('number');
      });
    });

    it('should calculate memory usage percentage', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result } = renderHook(() => useGPUMetricsHistory());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const firstPoint = result.current.chartData?.[0];
      expect(firstPoint).toHaveProperty('memory_percent');
      // 8192 / 24576 * 100 ≈ 33.33
      expect(firstPoint?.memory_percent).toBeCloseTo(33.33, 1);
    });
  });

  describe('limit parameter changes', () => {
    it('should refetch when limit changes', async () => {
      vi.mocked(gpuHistoryApi.getGPUHistory).mockResolvedValue(mockGPUHistoryResponse);

      const { result, rerender } = renderHook(
        ({ limit }) => useGPUMetricsHistory({ limit }),
        {
          initialProps: { limit: 100 },
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(gpuHistoryApi.getGPUHistory).toHaveBeenCalledWith(100);

      // Change limit
      rerender({ limit: 500 });

      await waitFor(() => {
        expect(gpuHistoryApi.getGPUHistory).toHaveBeenCalledWith(500);
      });

      expect(gpuHistoryApi.getGPUHistory).toHaveBeenCalledTimes(2);
    });
  });
});
