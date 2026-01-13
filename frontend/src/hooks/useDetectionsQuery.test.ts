import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useDetectionsInfiniteQuery,
  detectionsQueryKeys,
} from './useDetectionsQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { DetectionListResponse } from '../types/generated';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchEventDetections: vi.fn(),
  };
});

describe('useDetectionsInfiniteQuery', () => {
  const mockDetections: DetectionListResponse = {
    items: [
      {
        id: 1,
        camera_id: 'front_door',
        detected_at: '2025-12-28T10:00:00Z',
        object_type: 'person',
        confidence: 0.95,
        bbox_x: 100,
        bbox_y: 200,
        bbox_width: 150,
        bbox_height: 300,
        file_path: '/cameras/front_door/image1.jpg',
        thumbnail_path: null,
        media_type: 'image',
      },
      {
        id: 2,
        camera_id: 'front_door',
        detected_at: '2025-12-28T10:00:05Z',
        object_type: 'car',
        confidence: 0.87,
        bbox_x: 200,
        bbox_y: 150,
        bbox_width: 300,
        bbox_height: 200,
        file_path: '/cameras/front_door/image2.jpg',
        thumbnail_path: null,
        media_type: 'image',
      },
    ],
    pagination: {
      total: 10,
      has_more: true,
      next_cursor: 'cursor-page-2',
      limit: 50,
    },
  };

  const mockDetectionsPage2: DetectionListResponse = {
    items: [
      {
        id: 3,
        camera_id: 'front_door',
        detected_at: '2025-12-28T10:00:10Z',
        object_type: 'dog',
        confidence: 0.92,
        bbox_x: 50,
        bbox_y: 100,
        bbox_width: 100,
        bbox_height: 150,
        file_path: '/cameras/front_door/image3.jpg',
        thumbnail_path: null,
        media_type: 'image',
      },
    ],
    pagination: {
      total: 10,
      has_more: false,
      next_cursor: null,
      limit: 50,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchEventDetections as ReturnType<typeof vi.fn>).mockResolvedValue(mockDetections);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchEventDetections as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with empty detections array', () => {
      (api.fetchEventDetections as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.detections).toEqual([]);
    });

    it('starts with totalCount of 0', () => {
      (api.fetchEventDetections as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.totalCount).toBe(0);
    });
  });

  describe('fetching data', () => {
    it('fetches detections for event on mount', async () => {
      renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 42 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(api.fetchEventDetections).toHaveBeenCalledTimes(1);
        expect(api.fetchEventDetections).toHaveBeenCalledWith(42, {
          limit: 50,
          cursor: undefined,
        });
      });
    });

    it('updates detections after successful fetch', async () => {
      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.detections).toEqual(mockDetections.items);
      });
    });

    it('sets totalCount from pagination', async () => {
      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.totalCount).toBe(10);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets hasNextPage from pagination', async () => {
      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.hasNextPage).toBe(true);
      });
    });
  });

  describe('pagination with cursor', () => {
    it('fetches next page with cursor', async () => {
      (api.fetchEventDetections as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce(mockDetections)
        .mockResolvedValueOnce(mockDetectionsPage2);

      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      // Wait for first page to load
      await waitFor(() => {
        expect(result.current.hasNextPage).toBe(true);
      });

      // Fetch next page
      result.current.fetchNextPage();

      await waitFor(() => {
        expect(api.fetchEventDetections).toHaveBeenCalledTimes(2);
      });

      // Verify cursor was passed for second call
      expect(api.fetchEventDetections).toHaveBeenLastCalledWith(1, {
        limit: 50,
        cursor: 'cursor-page-2',
      });
    });

    it('accumulates detections from multiple pages', async () => {
      (api.fetchEventDetections as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce(mockDetections)
        .mockResolvedValueOnce(mockDetectionsPage2);

      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      // Wait for first page to load
      await waitFor(() => {
        expect(result.current.detections.length).toBe(2);
      });

      // Fetch next page
      result.current.fetchNextPage();

      await waitFor(() => {
        // Should now have all 3 detections
        expect(result.current.detections.length).toBe(3);
        expect(result.current.detections.map((d) => d.id)).toEqual([1, 2, 3]);
      });
    });

    it('sets hasNextPage to false when no more pages', async () => {
      (api.fetchEventDetections as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce(mockDetections)
        .mockResolvedValueOnce(mockDetectionsPage2);

      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      // Wait for first page
      await waitFor(() => {
        expect(result.current.hasNextPage).toBe(true);
      });

      // Fetch second (final) page
      result.current.fetchNextPage();

      await waitFor(() => {
        expect(result.current.hasNextPage).toBe(false);
      });
    });
  });

  describe('error handling', () => {
    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch detections';
      (api.fetchEventDetections as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
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
      (api.fetchEventDetections as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
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
    it('respects custom limit', async () => {
      renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1, limit: 25 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(api.fetchEventDetections).toHaveBeenCalledWith(1, {
          limit: 25,
          cursor: undefined,
        });
      });
    });

    it('does not fetch when enabled is false', async () => {
      renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1, enabled: false }),
        { wrapper: createQueryWrapper() }
      );

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchEventDetections).not.toHaveBeenCalled();
    });

    it('provides refetch function', async () => {
      const { result } = renderHook(
        () => useDetectionsInfiniteQuery({ eventId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });

  describe('query keys', () => {
    it('generates correct query keys', () => {
      expect(detectionsQueryKeys.all).toEqual(['detections']);
      expect(detectionsQueryKeys.lists()).toEqual(['detections', 'list']);
      expect(detectionsQueryKeys.byEvent(42)).toEqual(['detections', 'list', 'event', 42]);
      expect(detectionsQueryKeys.infinite(42, 25)).toEqual([
        'detections',
        'infinite',
        { eventId: 42, limit: 25 },
      ]);
      expect(detectionsQueryKeys.detail(123)).toEqual(['detections', 'detail', 123]);
    });
  });
});
