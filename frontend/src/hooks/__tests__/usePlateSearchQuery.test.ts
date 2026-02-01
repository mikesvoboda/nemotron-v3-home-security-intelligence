/**
 * @fileoverview Tests for usePlateSearchQuery hook.
 *
 * This hook provides search and filter functionality for plate reads
 * using TanStack Query with debounced input support.
 *
 * @see frontend/src/hooks/usePlateSearchQuery.ts
 */
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import * as plateReadsApi from '../../services/plateReadsApi';
import { createQueryWrapper } from '../../test-utils/renderWithProviders';
import {
  usePlateSearchQuery,
  useDebouncedValue,
  plateSearchQueryKeys,
} from '../usePlateSearchQuery';

import type { PlateReadListResponse, PlateRead } from '../../types/plateRead';

// Mock the API module
vi.mock('../../services/plateReadsApi', () => ({
  searchPlateReads: vi.fn(),
  fetchPlateReads: vi.fn(),
}));

describe('usePlateSearchQuery', () => {
  // Mock data for tests
  const mockPlateRead: PlateRead = {
    id: 1,
    camera_id: 'cam-1',
    timestamp: '2026-01-31T10:00:00Z',
    plate_text: 'ABC123',
    raw_text: 'ABC-123',
    detection_confidence: 0.95,
    ocr_confidence: 0.92,
    bbox: [100, 100, 200, 150],
    image_quality_score: 0.88,
    is_enhanced: false,
    is_blurry: false,
    created_at: '2026-01-31T10:00:01Z',
  };

  const mockResponse: PlateReadListResponse = {
    plate_reads: [mockPlateRead],
    total: 1,
    page: 1,
    page_size: 50,
  };

  const mockEmptyResponse: PlateReadListResponse = {
    plate_reads: [],
    total: 0,
    page: 1,
    page_size: 50,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (plateReadsApi.searchPlateReads as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);
    (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('plateSearchQueryKeys', () => {
    it('generates correct all key', () => {
      expect(plateSearchQueryKeys.all).toEqual(['plate-reads']);
    });

    it('generates correct list key without filters', () => {
      expect(plateSearchQueryKeys.list()).toEqual(['plate-reads', 'list']);
    });

    it('generates correct list key with filters', () => {
      const filters = { camera_id: 'cam-1', page: 2 };
      expect(plateSearchQueryKeys.list(filters)).toEqual(['plate-reads', 'list', filters]);
    });

    it('generates correct byText key', () => {
      const params = { text: 'ABC', exact: true, page: 1 };
      expect(plateSearchQueryKeys.byText(params)).toEqual(['plate-reads', 'search', params]);
    });
  });

  describe('initial loading state', () => {
    it('starts with isLoading true', () => {
      // Don't let fetch resolve immediately
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(
        () => usePlateSearchQuery({}, { enabled: true, debounceMs: 0 }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with empty plateReads array', () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(
        () => usePlateSearchQuery({}, { enabled: true, debounceMs: 0 }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      expect(result.current.plateReads).toEqual([]);
    });

    it('starts with zero total', () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(
        () => usePlateSearchQuery({}, { enabled: true, debounceMs: 0 }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      expect(result.current.total).toBe(0);
    });

    it('starts with no error', () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(
        () => usePlateSearchQuery({}, { enabled: true, debounceMs: 0 }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      expect(result.current.error).toBeNull();
    });
  });

  describe('successful data fetch', () => {
    it('fetches plate reads on mount when enabled', async () => {
      renderHook(() => usePlateSearchQuery({}, { enabled: true, debounceMs: 0 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(plateReadsApi.fetchPlateReads).toHaveBeenCalledTimes(1);
      });
    });

    it('does not fetch when enabled is false', async () => {
      renderHook(() => usePlateSearchQuery({}, { enabled: false, debounceMs: 0 }), {
        wrapper: createQueryWrapper(),
      });

      // Give time for any potential fetch
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(plateReadsApi.fetchPlateReads).not.toHaveBeenCalled();
      expect(plateReadsApi.searchPlateReads).not.toHaveBeenCalled();
    });

    it('updates plateReads after successful fetch', async () => {
      const { result } = renderHook(
        () => usePlateSearchQuery({}, { enabled: true, debounceMs: 0 }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(result.current.plateReads).toEqual([mockPlateRead]);
      });
    });

    it('updates total after successful fetch', async () => {
      const { result } = renderHook(
        () => usePlateSearchQuery({}, { enabled: true, debounceMs: 0 }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(result.current.total).toBe(1);
      });
    });

    it('sets isLoading to false after successful fetch', async () => {
      const { result } = renderHook(
        () => usePlateSearchQuery({}, { enabled: true, debounceMs: 0 }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('handles empty results', async () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockResolvedValue(
        mockEmptyResponse
      );

      const { result } = renderHook(
        () => usePlateSearchQuery({}, { enabled: true, debounceMs: 0 }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(result.current.plateReads).toEqual([]);
        expect(result.current.total).toBe(0);
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('text search with debouncing', () => {
    it('uses searchPlateReads when text is provided', async () => {
      renderHook(() => usePlateSearchQuery({ text: 'ABC' }, { enabled: true, debounceMs: 0 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(plateReadsApi.searchPlateReads).toHaveBeenCalledWith({
          text: 'ABC',
          exact: undefined,
          page: undefined,
          page_size: undefined,
        });
      });
    });

    it('debounces text input', () => {
      vi.useFakeTimers();

      const { rerender } = renderHook(
        ({ text }) => usePlateSearchQuery({ text }, { enabled: true, debounceMs: 300 }),
        {
          wrapper: createQueryWrapper(),
          initialProps: { text: '' },
        }
      );

      // Type first character
      rerender({ text: 'A' });

      // Should not call API yet (fetchPlateReads is called for empty text)
      act(() => {
        vi.advanceTimersByTime(100);
      });

      // Type more characters
      rerender({ text: 'AB' });
      rerender({ text: 'ABC' });

      // Still should not call search API
      act(() => {
        vi.advanceTimersByTime(200);
      });
      expect(plateReadsApi.searchPlateReads).not.toHaveBeenCalled();

      // Now wait for full debounce period
      act(() => {
        vi.advanceTimersByTime(300);
      });

      // Should be called with final value
      expect(plateReadsApi.searchPlateReads).toHaveBeenCalledWith({
        text: 'ABC',
        exact: undefined,
        page: undefined,
        page_size: undefined,
      });

      vi.useRealTimers();
    });

    it('respects exact match parameter', async () => {
      renderHook(
        () => usePlateSearchQuery({ text: 'ABC123', exact: true }, { enabled: true, debounceMs: 0 }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(plateReadsApi.searchPlateReads).toHaveBeenCalledWith({
          text: 'ABC123',
          exact: true,
          page: undefined,
          page_size: undefined,
        });
      });
    });
  });

  describe('filtered list (no text search)', () => {
    it('uses fetchPlateReads when no text is provided', async () => {
      renderHook(
        () =>
          usePlateSearchQuery(
            {
              camera_id: 'cam-1',
              min_confidence: 0.8,
            },
            { enabled: true, debounceMs: 0 }
          ),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(plateReadsApi.fetchPlateReads).toHaveBeenCalledWith({
          camera_id: 'cam-1',
          start_time: undefined,
          end_time: undefined,
          min_confidence: 0.8,
          page: undefined,
          page_size: undefined,
        });
      });
    });

    it('passes date filters correctly', async () => {
      renderHook(
        () =>
          usePlateSearchQuery(
            {
              start_time: '2026-01-01T00:00:00Z',
              end_time: '2026-01-31T23:59:59Z',
            },
            { enabled: true, debounceMs: 0 }
          ),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(plateReadsApi.fetchPlateReads).toHaveBeenCalledWith({
          camera_id: undefined,
          start_time: '2026-01-01T00:00:00Z',
          end_time: '2026-01-31T23:59:59Z',
          min_confidence: undefined,
          page: undefined,
          page_size: undefined,
        });
      });
    });
  });

  describe('pagination', () => {
    it('passes page and page_size to API', async () => {
      renderHook(
        () =>
          usePlateSearchQuery(
            {
              page: 2,
              page_size: 25,
            },
            { enabled: true, debounceMs: 0 }
          ),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(plateReadsApi.fetchPlateReads).toHaveBeenCalledWith({
          camera_id: undefined,
          start_time: undefined,
          end_time: undefined,
          min_confidence: undefined,
          page: 2,
          page_size: 25,
        });
      });
    });

    it('returns page and pageSize from response', async () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockResolvedValue({
        plate_reads: [mockPlateRead],
        total: 100,
        page: 3,
        page_size: 25,
      });

      const { result } = renderHook(
        () =>
          usePlateSearchQuery(
            {
              page: 3,
              page_size: 25,
            },
            { enabled: true, debounceMs: 0 }
          ),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(result.current.page).toBe(3);
        expect(result.current.pageSize).toBe(25);
        expect(result.current.total).toBe(100);
      });
    });
  });

  describe('error handling', () => {
    it('sets error on fetch failure', async () => {
      const errorMessage = 'Network error';
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(
        () => usePlateSearchQuery({}, { enabled: true, debounceMs: 0, retry: false }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(result.current.error).toBeInstanceOf(Error);
        expect(result.current.error?.message).toBe(errorMessage);
        expect(result.current.isError).toBe(true);
      });
    });

    it('maintains empty data when error occurs', async () => {
      (plateReadsApi.fetchPlateReads as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('API Error')
      );

      const { result } = renderHook(
        () => usePlateSearchQuery({}, { enabled: true, debounceMs: 0, retry: false }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(result.current.error).not.toBeNull();
      });

      expect(result.current.plateReads).toEqual([]);
      expect(result.current.total).toBe(0);
    });
  });

  describe('refetch', () => {
    it('provides refetch function that triggers new API call', async () => {
      const { result } = renderHook(
        () => usePlateSearchQuery({}, { enabled: true, debounceMs: 0 }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(plateReadsApi.fetchPlateReads).toHaveBeenCalledTimes(1);
      });

      // Trigger refetch
      await act(async () => {
        await result.current.refetch();
      });

      await waitFor(() => {
        expect(plateReadsApi.fetchPlateReads).toHaveBeenCalledTimes(2);
      });
    });
  });
});

describe('useDebouncedValue', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebouncedValue('initial', 300));

    expect(result.current).toBe('initial');
  });

  it('debounces value changes', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: 'initial' },
    });

    expect(result.current).toBe('initial');

    // Update value
    rerender({ value: 'updated' });

    // Value should not change immediately
    expect(result.current).toBe('initial');

    // Fast-forward time
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Now value should be updated
    expect(result.current).toBe('updated');
  });

  it('cancels previous timeout on rapid changes', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: 'a' },
    });

    // Rapid changes
    rerender({ value: 'ab' });
    act(() => {
      vi.advanceTimersByTime(100);
    });

    rerender({ value: 'abc' });
    act(() => {
      vi.advanceTimersByTime(100);
    });

    rerender({ value: 'abcd' });

    // Still showing initial value
    expect(result.current).toBe('a');

    // Wait for full debounce period after last change
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Should show the final value, not intermediate ones
    expect(result.current).toBe('abcd');
  });
});
