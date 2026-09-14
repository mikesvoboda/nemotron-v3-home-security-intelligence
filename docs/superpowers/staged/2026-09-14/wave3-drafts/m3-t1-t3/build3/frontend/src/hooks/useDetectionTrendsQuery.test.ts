import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useDetectionTrendsQuery, detectionTrendsQueryKeys } from './useDetectionTrendsQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { DetectionTrendsResponse } from '../types/analytics';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchDetectionTrends: vi.fn(),
  };
});

describe('useDetectionTrendsQuery', () => {
  const mockDetectionTrends: DetectionTrendsResponse = {
    data_points: [
      { date: '2026-01-10', count: 45 },
      { date: '2026-01-11', count: 67 },
      { date: '2026-01-12', count: 32 },
      { date: '2026-01-13', count: 89 },
      { date: '2026-01-14', count: 54 },
      { date: '2026-01-15', count: 0 },
      { date: '2026-01-16', count: 78 },
    ],
    total_detections: 365,
    start_date: '2026-01-10',
    end_date: '2026-01-16',
  };

  const defaultParams = {
    start_date: '2026-01-10',
    end_date: '2026-01-16',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchDetectionTrends as ReturnType<typeof vi.fn>).mockResolvedValue(mockDetectionTrends);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchDetectionTrends as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchDetectionTrends as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with no error', () => {
      (api.fetchDetectionTrends as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('fetching data', () => {
    it('fetches detection trends on mount when enabled', async () => {
      renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchDetectionTrends).toHaveBeenCalledTimes(1);
      });
    });

    it('passes correct params to fetch function', async () => {
      renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchDetectionTrends).toHaveBeenCalledWith(defaultParams);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockDetectionTrends);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch detection trends';
      (api.fetchDetectionTrends as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(
        () => useDetectionTrendsQuery(defaultParams, { retry: false }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
          expect(result.current.error?.message).toBe(errorMessage);
        },
        { timeout: 5000 }
      );
    });

    it('sets isError to true on failure', async () => {
      (api.fetchDetectionTrends as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(
        () => useDetectionTrendsQuery(defaultParams, { retry: false }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('options', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useDetectionTrendsQuery(defaultParams, { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchDetectionTrends).not.toHaveBeenCalled();
    });

    it('does not fetch when start_date is empty', async () => {
      renderHook(() => useDetectionTrendsQuery({ start_date: '', end_date: '2026-01-16' }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchDetectionTrends).not.toHaveBeenCalled();
    });

    it('does not fetch when end_date is empty', async () => {
      renderHook(() => useDetectionTrendsQuery({ start_date: '2026-01-10', end_date: '' }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchDetectionTrends).not.toHaveBeenCalled();
    });

    it('provides refetch function', async () => {
      const { result } = renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });

  describe('derived values', () => {
    it('derives dataPoints from response', async () => {
      const { result } = renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.dataPoints).toEqual(mockDetectionTrends.data_points);
      });
    });

    it('derives totalDetections from response', async () => {
      const { result } = renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.totalDetections).toBe(365);
      });
    });

    it('returns empty array for dataPoints when data is not loaded', () => {
      (api.fetchDetectionTrends as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.dataPoints).toEqual([]);
    });

    it('returns 0 for totalDetections when data is not loaded', () => {
      (api.fetchDetectionTrends as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.totalDetections).toBe(0);
    });
  });

  describe('query keys', () => {
    it('generates correct query keys', () => {
      expect(detectionTrendsQueryKeys.all).toEqual(['analytics', 'detection-trends']);
      expect(detectionTrendsQueryKeys.byDateRange(defaultParams)).toEqual([
        'analytics',
        'detection-trends',
        defaultParams,
      ]);
    });

    it('refetches when params change', async () => {
      const { rerender } = renderHook(({ params }) => useDetectionTrendsQuery(params), {
        wrapper: createQueryWrapper(),
        initialProps: { params: defaultParams },
      });

      await waitFor(() => {
        expect(api.fetchDetectionTrends).toHaveBeenCalledTimes(1);
      });

      const newParams = { start_date: '2026-01-01', end_date: '2026-01-07' };
      rerender({ params: newParams });

      await waitFor(() => {
        expect(api.fetchDetectionTrends).toHaveBeenCalledTimes(2);
        expect(api.fetchDetectionTrends).toHaveBeenLastCalledWith(newParams);
      });
    });
  });

  describe('return values', () => {
    it('returns all expected properties', async () => {
      const { result } = renderHook(() => useDetectionTrendsQuery(defaultParams), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current).toHaveProperty('data');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('isError');
      expect(result.current).toHaveProperty('isRefetching');
      expect(result.current).toHaveProperty('refetch');
      expect(result.current).toHaveProperty('dataPoints');
      expect(result.current).toHaveProperty('totalDetections');
    });
  });
});
