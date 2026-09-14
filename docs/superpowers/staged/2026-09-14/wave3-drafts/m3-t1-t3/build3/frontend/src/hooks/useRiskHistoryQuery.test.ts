/**
 * Tests for useRiskHistoryQuery hook.
 *
 * Tests the React Query hook for fetching risk history data
 * from GET /api/analytics/risk-history.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useRiskHistoryQuery } from './useRiskHistoryQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchRiskHistory: vi.fn(),
}));

describe('useRiskHistoryQuery', () => {
  const mockRiskHistoryResponse = {
    data_points: [
      { date: '2026-01-10', low: 12, medium: 8, high: 3, critical: 1 },
      { date: '2026-01-11', low: 15, medium: 10, high: 5, critical: 0 },
      { date: '2026-01-12', low: 8, medium: 6, high: 2, critical: 2 },
    ],
    start_date: '2026-01-10',
    end_date: '2026-01-12',
  };

  const defaultParams = {
    start_date: '2026-01-10',
    end_date: '2026-01-12',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchRiskHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockRiskHistoryResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchRiskHistory as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRiskHistoryQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchRiskHistory as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRiskHistoryQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with empty dataPoints array', () => {
      (api.fetchRiskHistory as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRiskHistoryQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.dataPoints).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches risk history on mount with correct params', async () => {
      renderHook(() => useRiskHistoryQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchRiskHistory).toHaveBeenCalledTimes(1);
        expect(api.fetchRiskHistory).toHaveBeenCalledWith(defaultParams);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useRiskHistoryQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockRiskHistoryResponse);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useRiskHistoryQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('provides dataPoints array from response', async () => {
      const { result } = renderHook(() => useRiskHistoryQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.dataPoints).toEqual(mockRiskHistoryResponse.data_points);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch risk history';
      (api.fetchRiskHistory as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useRiskHistoryQuery(defaultParams), {
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
      renderHook(() => useRiskHistoryQuery(defaultParams, { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchRiskHistory).not.toHaveBeenCalled();
    });

    it('fetches when enabled is true', async () => {
      renderHook(() => useRiskHistoryQuery(defaultParams, { enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchRiskHistory).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('date range changes', () => {
    it('refetches when date range changes', async () => {
      const { rerender } = renderHook(({ params }) => useRiskHistoryQuery(params), {
        wrapper: createQueryWrapper(),
        initialProps: { params: defaultParams },
      });

      await waitFor(() => {
        expect(api.fetchRiskHistory).toHaveBeenCalledWith(defaultParams);
      });

      const newParams = {
        start_date: '2026-01-05',
        end_date: '2026-01-17',
      };

      rerender({ params: newParams });

      await waitFor(() => {
        expect(api.fetchRiskHistory).toHaveBeenCalledWith(newParams);
      });
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useRiskHistoryQuery(defaultParams), {
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
        () => useRiskHistoryQuery(defaultParams, { staleTime: customStaleTime }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // The hook should accept the staleTime option without error
      expect(result.current.data).toEqual(mockRiskHistoryResponse);
    });
  });
});
