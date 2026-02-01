/**
 * Tests for usePerformanceHistory hook
 *
 * Tests cover:
 * - Initial loading state
 * - Successful data fetch
 * - Error handling
 * - Time range parameter changes
 * - Refetch functionality
 * - Data transformation
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { usePerformanceHistory } from './usePerformanceHistory';
import * as performanceHistoryApi from '../services/performanceHistoryApi';

// Mock the API module
vi.mock('../services/performanceHistoryApi', () => ({
  getPerformanceHistory: vi.fn(),
}));

describe('usePerformanceHistory', () => {
  const mockSnapshots = [
    {
      timestamp: '2026-01-31T10:00:00Z',
      gpu: {
        utilization: 45,
        temperature: 62,
        vram_used_gb: 8.5,
        vram_total_gb: 24.0,
      },
      host: {
        cpu_percent: 35,
        ram_used_gb: 12.3,
        ram_total_gb: 32.0,
      },
      databases: {
        postgres: { status: 'healthy', connections_active: 5 },
        redis: { status: 'healthy', connected_clients: 8 },
      },
      alerts: [],
    },
    {
      timestamp: '2026-01-31T10:00:05Z',
      gpu: {
        utilization: 48,
        temperature: 63,
        vram_used_gb: 8.6,
        vram_total_gb: 24.0,
      },
      host: {
        cpu_percent: 37,
        ram_used_gb: 12.4,
        ram_total_gb: 32.0,
      },
      databases: {
        postgres: { status: 'healthy', connections_active: 6 },
        redis: { status: 'healthy', connected_clients: 8 },
      },
      alerts: [],
    },
  ];

  const mockApiResponse = {
    snapshots: mockSnapshots,
    time_range: '5m',
    count: 2,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization and loading', () => {
    it('should return loading state initially', () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      expect(result.current.isLoading).toBe(true);
      expect(result.current.snapshots).toEqual([]);
      expect(result.current.error).toBeNull();
      expect(result.current.timeRange).toBe('5m');
    });

    it('should use default time range of 5m when not specified', () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue(mockApiResponse);

      const { result } = renderHook(() => usePerformanceHistory());

      expect(result.current.timeRange).toBe('5m');
    });
  });

  describe('successful data fetching', () => {
    it('should fetch and return performance history data', async () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue(mockApiResponse);

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.snapshots).toEqual(mockSnapshots);
      expect(result.current.error).toBeNull();
      expect(performanceHistoryApi.getPerformanceHistory).toHaveBeenCalledWith('5m');
    });

    it('should call API with correct time range parameter', async () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue({
        ...mockApiResponse,
        time_range: '15m',
      });

      const { result } = renderHook(() => usePerformanceHistory('15m'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(performanceHistoryApi.getPerformanceHistory).toHaveBeenCalledWith('15m');
      expect(result.current.timeRange).toBe('15m');
    });

    it('should handle empty snapshots array', async () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue({
        snapshots: [],
        time_range: '5m',
        count: 0,
      });

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.snapshots).toEqual([]);
      expect(result.current.error).toBeNull();
    });

    it('should handle snapshots with null GPU data', async () => {
      const snapshotsWithNullGpu = [
        {
          ...mockSnapshots[0],
          gpu: null,
        },
      ];

      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue({
        snapshots: snapshotsWithNullGpu,
        time_range: '5m',
        count: 1,
      });

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.snapshots[0].gpu).toBeNull();
      expect(result.current.error).toBeNull();
    });

    it('should handle snapshots with alerts', async () => {
      const snapshotsWithAlerts = [
        {
          ...mockSnapshots[0],
          alerts: [
            {
              severity: 'warning',
              metric: 'gpu_temperature',
              value: 82,
              threshold: 80,
              message: 'GPU temperature high',
            },
          ],
        },
      ];

      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue({
        snapshots: snapshotsWithAlerts,
        time_range: '5m',
        count: 1,
      });

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.snapshots[0].alerts).toHaveLength(1);
      expect(result.current.snapshots[0].alerts[0].severity).toBe('warning');
    });
  });

  describe('error handling', () => {
    it('should handle API errors', async () => {
      const mockError = new Error('Failed to fetch performance history');
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockRejectedValue(mockError);

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
      expect(result.current.error?.message).toContain('Failed to fetch performance history');
      expect(result.current.snapshots).toEqual([]);
    });

    it('should handle network errors', async () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockRejectedValue(
        new Error('Network request failed')
      );

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBeTruthy();
      expect(result.current.snapshots).toEqual([]);
    });

    it('should handle malformed API responses', async () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue({
        snapshots: null as unknown as performanceHistoryApi.PerformanceSnapshot[],
        time_range: '5m',
        count: 0,
      });

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should either handle gracefully or set error
      expect(result.current.error !== null || result.current.snapshots === null).toBe(true);
    });
  });

  describe('time range changes', () => {
    it('should refetch when time range changes', async () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue(mockApiResponse);

      const { result, rerender } = renderHook(
        ({ timeRange }: { timeRange: '5m' | '15m' | '60m' }) => usePerformanceHistory(timeRange),
        {
          initialProps: { timeRange: '5m' },
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(performanceHistoryApi.getPerformanceHistory).toHaveBeenCalledWith('5m');

      // Change time range
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue({
        ...mockApiResponse,
        time_range: '15m',
      });

      rerender({ timeRange: '15m' });

      await waitFor(() => {
        expect(performanceHistoryApi.getPerformanceHistory).toHaveBeenCalledWith('15m');
      });

      expect(performanceHistoryApi.getPerformanceHistory).toHaveBeenCalledTimes(2);
    });

    it('should support all three time ranges', async () => {
      const timeRanges = ['5m', '15m', '60m'] as const;

      for (const timeRange of timeRanges) {
        vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue({
          ...mockApiResponse,
          time_range: timeRange,
        });

        const { result } = renderHook(() => usePerformanceHistory(timeRange));

        await waitFor(() => {
          expect(result.current.isLoading).toBe(false);
        });

        expect(result.current.timeRange).toBe(timeRange);
        expect(performanceHistoryApi.getPerformanceHistory).toHaveBeenCalledWith(timeRange);

        vi.clearAllMocks();
      }
    });
  });

  describe('refetch functionality', () => {
    it('should provide a refetch function', () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue(mockApiResponse);

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      expect(result.current.refetch).toBeDefined();
      expect(typeof result.current.refetch).toBe('function');
    });

    it('should refetch data when refetch is called', async () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue(mockApiResponse);

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(performanceHistoryApi.getPerformanceHistory).toHaveBeenCalledTimes(1);

      // Call refetch
      result.current.refetch();

      await waitFor(() => {
        expect(performanceHistoryApi.getPerformanceHistory).toHaveBeenCalledTimes(2);
      });
    });

    it('should set loading state during refetch', async () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue(mockApiResponse);

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Mock a slower response for refetch
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve(mockApiResponse), 100)
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

  describe('data transformation', () => {
    it('should preserve snapshot timestamps', async () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue(mockApiResponse);

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.snapshots[0].timestamp).toBe('2026-01-31T10:00:00Z');
      expect(result.current.snapshots[1].timestamp).toBe('2026-01-31T10:00:05Z');
    });

    it('should preserve nested database metrics', async () => {
      vi.mocked(performanceHistoryApi.getPerformanceHistory).mockResolvedValue(mockApiResponse);

      const { result } = renderHook(() => usePerformanceHistory('5m'));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.snapshots[0].databases.postgres).toBeDefined();
      expect(result.current.snapshots[0].databases.redis).toBeDefined();
    });
  });
});
