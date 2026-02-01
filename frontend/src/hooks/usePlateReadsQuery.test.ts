import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { usePlateReadsQuery, plateReadsQueryKeys } from './usePlateReadsQuery';
import * as plateReadsApi from '../services/plateReadsApi';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { PlateReadListResponse, PlateReadFilters } from '../types/plateRead';

// Mock the API module
vi.mock('../services/plateReadsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/plateReadsApi')>();
  return {
    ...actual,
    fetchPlateReads: vi.fn(),
  };
});

describe('usePlateReadsQuery', () => {
  const mockPlateReads: PlateReadListResponse = {
    plate_reads: [
      {
        id: 1,
        camera_id: 'cam-front',
        timestamp: '2026-01-15T10:30:00Z',
        plate_text: 'ABC123',
        raw_text: 'ABC-123',
        detection_confidence: 0.95,
        ocr_confidence: 0.92,
        bbox: [100, 200, 300, 400],
        image_quality_score: 0.88,
        is_enhanced: false,
        is_blurry: false,
        created_at: '2026-01-15T10:30:00Z',
      },
      {
        id: 2,
        camera_id: 'cam-front',
        timestamp: '2026-01-15T10:35:00Z',
        plate_text: 'XYZ789',
        raw_text: 'XYZ-789',
        detection_confidence: 0.91,
        ocr_confidence: 0.87,
        bbox: [150, 250, 350, 450],
        image_quality_score: 0.75,
        is_enhanced: true,
        is_blurry: false,
        created_at: '2026-01-15T10:35:00Z',
      },
    ],
    total: 150,
    page: 1,
    page_size: 50,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockResolvedValue(mockPlateReads);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with no error', () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('fetching data', () => {
    it('fetches plate reads on mount when enabled', async () => {
      renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(plateReadsApi.fetchPlateReads).toHaveBeenCalledTimes(1);
      });
    });

    it('passes filters to fetch function', async () => {
      const filters: PlateReadFilters = {
        camera_id: 'cam-front',
        min_confidence: 0.8,
        page: 2,
        page_size: 25,
      };

      renderHook(() => usePlateReadsQuery(filters), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(plateReadsApi.fetchPlateReads).toHaveBeenCalledWith(filters);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockPlateReads);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch plate reads';
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => usePlateReadsQuery(undefined, { retry: false }), {
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
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => usePlateReadsQuery(undefined, { retry: false }), {
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
      renderHook(() => usePlateReadsQuery(undefined, { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(plateReadsApi.fetchPlateReads).not.toHaveBeenCalled();
    });

    it('provides refetch function', async () => {
      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });

  describe('derived values', () => {
    it('derives plateReads from response', async () => {
      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.plateReads).toEqual(mockPlateReads.plate_reads);
      });
    });

    it('derives total from response', async () => {
      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.total).toBe(150);
      });
    });

    it('derives page from response', async () => {
      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.page).toBe(1);
      });
    });

    it('derives pageSize from response', async () => {
      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.pageSize).toBe(50);
      });
    });

    it('derives totalPages from response', async () => {
      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        // 150 total / 50 per page = 3 pages
        expect(result.current.totalPages).toBe(3);
      });
    });

    it('derives hasNextPage correctly when more pages exist', async () => {
      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        // page 1 of 3, so hasNextPage should be true
        expect(result.current.hasNextPage).toBe(true);
      });
    });

    it('derives hasNextPage correctly when on last page', async () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockPlateReads,
        page: 3,
        total: 150,
        page_size: 50,
      });

      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        // page 3 * 50 = 150, total = 150, so no more pages
        expect(result.current.hasNextPage).toBe(false);
      });
    });

    it('derives hasPrevPage correctly when on first page', async () => {
      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.hasPrevPage).toBe(false);
      });
    });

    it('derives hasPrevPage correctly when not on first page', async () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockPlateReads,
        page: 2,
      });

      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.hasPrevPage).toBe(true);
      });
    });

    it('returns empty array for plateReads when data is not loaded', () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.plateReads).toEqual([]);
    });

    it('returns 0 for total when data is not loaded', () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.total).toBe(0);
    });

    it('returns 1 for page when data is not loaded', () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.page).toBe(1);
    });

    it('returns 50 for pageSize when data is not loaded', () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => usePlateReadsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.pageSize).toBe(50);
    });
  });

  describe('query keys', () => {
    it('generates correct query keys without filters', () => {
      expect(plateReadsQueryKeys.all).toEqual(['plate-reads']);
      expect(plateReadsQueryKeys.list()).toEqual(['plate-reads', 'list']);
    });

    it('generates correct query keys with filters', () => {
      const filters: PlateReadFilters = {
        camera_id: 'cam-1',
        min_confidence: 0.8,
      };
      expect(plateReadsQueryKeys.list(filters)).toEqual(['plate-reads', 'list', filters]);
    });

    it('refetches when filters change', async () => {
      const { rerender } = renderHook(
        ({ filters }) => usePlateReadsQuery(filters),
        {
          wrapper: createQueryWrapper(),
          initialProps: { filters: undefined as PlateReadFilters | undefined },
        }
      );

      await waitFor(() => {
        expect(plateReadsApi.fetchPlateReads).toHaveBeenCalledTimes(1);
      });

      const newFilters: PlateReadFilters = { camera_id: 'cam-1' };
      rerender({ filters: newFilters });

      await waitFor(() => {
        expect(plateReadsApi.fetchPlateReads).toHaveBeenCalledTimes(2);
        expect(plateReadsApi.fetchPlateReads).toHaveBeenLastCalledWith(newFilters);
      });
    });
  });

  describe('return values', () => {
    it('returns all expected properties', async () => {
      const { result } = renderHook(() => usePlateReadsQuery(), {
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
      expect(result.current).toHaveProperty('plateReads');
      expect(result.current).toHaveProperty('total');
      expect(result.current).toHaveProperty('page');
      expect(result.current).toHaveProperty('pageSize');
      expect(result.current).toHaveProperty('totalPages');
      expect(result.current).toHaveProperty('hasNextPage');
      expect(result.current).toHaveProperty('hasPrevPage');
    });
  });
});
