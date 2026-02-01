import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { usePlateStatisticsQuery, plateStatisticsQueryKeys } from './usePlateStatisticsQuery';
import * as plateReadsApi from '../services/plateReadsApi';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { PlateStatisticsResponse } from '../types/plateRead';

// Mock the API module
vi.mock('../services/plateReadsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/plateReadsApi')>();
  return {
    ...actual,
    fetchPlateStatistics: vi.fn(),
  };
});

describe('usePlateStatisticsQuery', () => {
  const mockPlateStatistics: PlateStatisticsResponse = {
    total_reads: 1250,
    unique_plates: 342,
    avg_ocr_confidence: 0.923,
    avg_quality_score: 0.85,
    enhanced_count: 156,
    blurry_count: 43,
    reads_last_hour: 28,
    reads_last_24h: 412,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (plateReadsApi.fetchPlateStatistics as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockPlateStatistics
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (plateReadsApi.fetchPlateStatistics as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (plateReadsApi.fetchPlateStatistics as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with no error', () => {
      (plateReadsApi.fetchPlateStatistics as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('fetching data', () => {
    it('fetches plate statistics on mount when enabled', async () => {
      renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(plateReadsApi.fetchPlateStatistics).toHaveBeenCalledTimes(1);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockPlateStatistics);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch plate statistics';
      (plateReadsApi.fetchPlateStatistics as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => usePlateStatisticsQuery({ retry: false }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
          expect(result.current.error?.message).toBe(errorMessage);
        },
        { timeout: 5000 }
      );
    });

    it('sets isError to true on failure', async () => {
      (plateReadsApi.fetchPlateStatistics as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => usePlateStatisticsQuery({ retry: false }), {
        wrapper: createQueryWrapper(),
      });

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
      renderHook(() => usePlateStatisticsQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(plateReadsApi.fetchPlateStatistics).not.toHaveBeenCalled();
    });

    it('provides refetch function', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });

  describe('derived values', () => {
    it('derives totalReads from response', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.totalReads).toBe(1250);
      });
    });

    it('derives uniquePlates from response', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.uniquePlates).toBe(342);
      });
    });

    it('derives avgConfidence from response', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.avgConfidence).toBe(0.923);
      });
    });

    it('derives avgConfidencePercent from response', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.avgConfidencePercent).toBe(92);
      });
    });

    it('derives readsLastHour from response', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.readsLastHour).toBe(28);
      });
    });

    it('derives readsLast24h from response', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.readsLast24h).toBe(412);
      });
    });

    it('derives enhancedCount from response', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.enhancedCount).toBe(156);
      });
    });

    it('derives blurryCount from response', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.blurryCount).toBe(43);
      });
    });

    it('derives avgQualityScore from response', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.avgQualityScore).toBe(0.85);
      });
    });

    it('returns 0 for totalReads when data is not loaded', () => {
      (plateReadsApi.fetchPlateStatistics as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.totalReads).toBe(0);
    });

    it('returns 0 for uniquePlates when data is not loaded', () => {
      (plateReadsApi.fetchPlateStatistics as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.uniquePlates).toBe(0);
    });

    it('returns 0 for avgConfidencePercent when data is not loaded', () => {
      (plateReadsApi.fetchPlateStatistics as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateStatisticsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.avgConfidencePercent).toBe(0);
    });
  });

  describe('query keys', () => {
    it('generates correct query keys', () => {
      expect(plateStatisticsQueryKeys.all).toEqual(['plate-reads', 'statistics']);
      expect(plateStatisticsQueryKeys.current()).toEqual(['plate-reads', 'statistics']);
    });
  });

  describe('return values', () => {
    it('returns all expected properties', async () => {
      const { result } = renderHook(() => usePlateStatisticsQuery(), {
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
      expect(result.current).toHaveProperty('totalReads');
      expect(result.current).toHaveProperty('uniquePlates');
      expect(result.current).toHaveProperty('avgConfidence');
      expect(result.current).toHaveProperty('avgConfidencePercent');
      expect(result.current).toHaveProperty('readsLastHour');
      expect(result.current).toHaveProperty('readsLast24h');
      expect(result.current).toHaveProperty('enhancedCount');
      expect(result.current).toHaveProperty('blurryCount');
      expect(result.current).toHaveProperty('avgQualityScore');
    });
  });
});
