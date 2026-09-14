/**
 * Tests for useRiskScoreTrends hook.
 *
 * Tests the React Query hook for fetching risk score trends data
 * from GET /api/analytics/risk-score-trends.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useRiskScoreTrends } from './useRiskScoreTrends';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchRiskScoreTrends: vi.fn(),
}));

describe('useRiskScoreTrends', () => {
  const mockTrendsResponse = {
    data_points: [
      { date: '2026-01-10', avg_score: 35.2, count: 10 },
      { date: '2026-01-11', avg_score: 42.1, count: 15 },
      { date: '2026-01-12', avg_score: 38.7, count: 12 },
      { date: '2026-01-13', avg_score: 45.0, count: 8 },
      { date: '2026-01-14', avg_score: 40.5, count: 11 },
    ],
    start_date: '2026-01-10',
    end_date: '2026-01-14',
  };

  const defaultParams = {
    start_date: '2026-01-10',
    end_date: '2026-01-14',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchRiskScoreTrends as ReturnType<typeof vi.fn>).mockResolvedValue(mockTrendsResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchRiskScoreTrends as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRiskScoreTrends(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchRiskScoreTrends as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRiskScoreTrends(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with empty dataPoints array', () => {
      (api.fetchRiskScoreTrends as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRiskScoreTrends(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.dataPoints).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches trends on mount with correct params', async () => {
      renderHook(() => useRiskScoreTrends(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchRiskScoreTrends).toHaveBeenCalledTimes(1);
        expect(api.fetchRiskScoreTrends).toHaveBeenCalledWith(defaultParams);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useRiskScoreTrends(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockTrendsResponse);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useRiskScoreTrends(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('provides dataPoints array from response', async () => {
      const { result } = renderHook(() => useRiskScoreTrends(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.dataPoints).toEqual(mockTrendsResponse.data_points);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch risk score trends';
      (api.fetchRiskScoreTrends as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useRiskScoreTrends(defaultParams), {
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
      renderHook(() => useRiskScoreTrends(defaultParams, { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchRiskScoreTrends).not.toHaveBeenCalled();
    });

    it('fetches when enabled is true', async () => {
      renderHook(() => useRiskScoreTrends(defaultParams, { enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchRiskScoreTrends).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('date range changes', () => {
    it('refetches when date range changes', async () => {
      const { rerender } = renderHook(({ params }) => useRiskScoreTrends(params), {
        wrapper: createQueryWrapper(),
        initialProps: { params: defaultParams },
      });

      await waitFor(() => {
        expect(api.fetchRiskScoreTrends).toHaveBeenCalledWith(defaultParams);
      });

      const newParams = {
        start_date: '2026-01-05',
        end_date: '2026-01-20',
      };

      rerender({ params: newParams });

      await waitFor(() => {
        expect(api.fetchRiskScoreTrends).toHaveBeenCalledWith(newParams);
      });
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useRiskScoreTrends(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });

  describe('stale time', () => {
    it('uses default stale time from options', async () => {
      const customStaleTime = 60000;
      const { result } = renderHook(
        () => useRiskScoreTrends(defaultParams, { staleTime: customStaleTime }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // The hook should accept the staleTime option without error
      expect(result.current.data).toEqual(mockTrendsResponse);
    });
  });
});
