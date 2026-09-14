/**
 * Tests for useRiskScoreDistribution hook.
 *
 * Tests the React Query hook for fetching risk score distribution data
 * from GET /api/analytics/risk-score-distribution.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useRiskScoreDistribution } from './useRiskScoreDistribution';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchRiskScoreDistribution: vi.fn(),
}));

describe('useRiskScoreDistribution', () => {
  const mockDistributionResponse = {
    buckets: [
      { min_score: 0, max_score: 10, count: 5 },
      { min_score: 10, max_score: 20, count: 8 },
      { min_score: 20, max_score: 30, count: 12 },
      { min_score: 30, max_score: 40, count: 6 },
      { min_score: 40, max_score: 50, count: 4 },
      { min_score: 50, max_score: 60, count: 3 },
      { min_score: 60, max_score: 70, count: 2 },
      { min_score: 70, max_score: 80, count: 1 },
      { min_score: 80, max_score: 90, count: 1 },
      { min_score: 90, max_score: 100, count: 0 },
    ],
    total_events: 42,
    start_date: '2026-01-10',
    end_date: '2026-01-17',
    bucket_size: 10,
  };

  const defaultParams = {
    start_date: '2026-01-10',
    end_date: '2026-01-17',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchRiskScoreDistribution as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockDistributionResponse
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchRiskScoreDistribution as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => useRiskScoreDistribution(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchRiskScoreDistribution as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => useRiskScoreDistribution(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with empty buckets array', () => {
      (api.fetchRiskScoreDistribution as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => useRiskScoreDistribution(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.buckets).toEqual([]);
    });

    it('starts with totalEvents as 0', () => {
      (api.fetchRiskScoreDistribution as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => useRiskScoreDistribution(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.totalEvents).toBe(0);
    });
  });

  describe('fetching data', () => {
    it('fetches distribution on mount with correct params', async () => {
      renderHook(() => useRiskScoreDistribution(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchRiskScoreDistribution).toHaveBeenCalledTimes(1);
        expect(api.fetchRiskScoreDistribution).toHaveBeenCalledWith(defaultParams);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useRiskScoreDistribution(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockDistributionResponse);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useRiskScoreDistribution(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('provides buckets array from response', async () => {
      const { result } = renderHook(() => useRiskScoreDistribution(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.buckets).toEqual(mockDistributionResponse.buckets);
      });
    });

    it('provides totalEvents from response', async () => {
      const { result } = renderHook(() => useRiskScoreDistribution(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.totalEvents).toBe(42);
      });
    });

    it('provides bucketSize from response', async () => {
      const { result } = renderHook(() => useRiskScoreDistribution(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.bucketSize).toBe(10);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch risk score distribution';
      (api.fetchRiskScoreDistribution as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useRiskScoreDistribution(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useRiskScoreDistribution(defaultParams, { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchRiskScoreDistribution).not.toHaveBeenCalled();
    });

    it('fetches when enabled is true', async () => {
      renderHook(() => useRiskScoreDistribution(defaultParams, { enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchRiskScoreDistribution).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('custom bucket size', () => {
    it('passes bucket_size parameter to API', async () => {
      const paramsWithBucketSize = {
        ...defaultParams,
        bucket_size: 20,
      };

      renderHook(() => useRiskScoreDistribution(paramsWithBucketSize), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchRiskScoreDistribution).toHaveBeenCalledWith(paramsWithBucketSize);
      });
    });
  });

  describe('date range changes', () => {
    it('refetches when date range changes', async () => {
      const { rerender } = renderHook(({ params }) => useRiskScoreDistribution(params), {
        wrapper: createQueryWrapper(),
        initialProps: { params: defaultParams },
      });

      await waitFor(() => {
        expect(api.fetchRiskScoreDistribution).toHaveBeenCalledWith(defaultParams);
      });

      const newParams = {
        start_date: '2026-01-05',
        end_date: '2026-01-20',
      };

      rerender({ params: newParams });

      await waitFor(() => {
        expect(api.fetchRiskScoreDistribution).toHaveBeenCalledWith(newParams);
      });
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useRiskScoreDistribution(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });
});
