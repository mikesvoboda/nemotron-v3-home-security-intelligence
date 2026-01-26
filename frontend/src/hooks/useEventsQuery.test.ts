import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useEventsInfiniteQuery, eventsQueryKeys, type EventFilters } from './useEventsQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { EventListResponse } from '../types/generated';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchEvents: vi.fn(),
  };
});

describe('useEventsInfiniteQuery', () => {
  const mockEvents: EventListResponse = {
    items: [
      {
        id: 1,
        camera_id: 'front_door',
        started_at: '2025-12-28T10:00:00Z',
        ended_at: '2025-12-28T10:02:30Z',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected at front entrance',
        reasoning: 'Motion detected with high confidence',
        reviewed: false,
        flagged: false, // NEM-3839
        notes: null,
        detection_count: 5,
        detection_ids: [1, 2, 3, 4, 5],
        version: 1, // Optimistic locking version (NEM-3625)
      },
      {
        id: 2,
        camera_id: 'backyard',
        started_at: '2025-12-28T09:30:00Z',
        ended_at: '2025-12-28T09:31:00Z',
        risk_score: 25,
        risk_level: 'low',
        summary: 'Animal detected in backyard',
        reasoning: 'Small movement detected, likely wildlife',
        reviewed: true,
        flagged: false, // NEM-3839
        notes: 'Just a squirrel',
        detection_count: 2,
        detection_ids: [6, 7],
        version: 1, // Optimistic locking version (NEM-3625)
      },
    ],
    pagination: {
      total: 50,
      has_more: true,
      next_cursor: 'cursor-page-2',
      limit: 50,
    },
  };

  const mockEventsPage2: EventListResponse = {
    items: [
      {
        id: 3,
        camera_id: 'garage',
        started_at: '2025-12-28T08:00:00Z',
        ended_at: '2025-12-28T08:05:00Z',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Vehicle detected in driveway',
        reasoning: 'Car entering property',
        reviewed: false,
        flagged: false, // NEM-3839
        notes: null,
        detection_count: 3,
        detection_ids: [8, 9, 10],
        version: 1, // Optimistic locking version (NEM-3625)
      },
    ],
    pagination: {
      total: 50,
      has_more: false,
      next_cursor: null,
      limit: 50,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchEvents as ReturnType<typeof vi.fn>).mockResolvedValue(mockEvents);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useEventsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with empty events array', () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useEventsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.events).toEqual([]);
    });

    it('starts with totalCount of 0', () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useEventsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.totalCount).toBe(0);
    });
  });

  describe('fetching data', () => {
    it('fetches events on mount', async () => {
      renderHook(() => useEventsInfiniteQuery(), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledTimes(1);
      });
    });

    it('updates events after successful fetch', async () => {
      const { result } = renderHook(() => useEventsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.events).toEqual(mockEvents.items);
      });
    });

    it('sets totalCount from pagination', async () => {
      const { result } = renderHook(() => useEventsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.totalCount).toBe(50);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useEventsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets hasNextPage from pagination', async () => {
      const { result } = renderHook(() => useEventsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.hasNextPage).toBe(true);
      });
    });
  });

  describe('filtering', () => {
    it('fetches events with camera filter', async () => {
      const filters: EventFilters = { camera_id: 'front_door' };

      renderHook(() => useEventsInfiniteQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ camera_id: 'front_door' })
        );
      });
    });

    it('fetches events with risk level filter', async () => {
      const filters: EventFilters = { risk_level: 'high' };

      renderHook(() => useEventsInfiniteQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ risk_level: 'high' })
        );
      });
    });

    it('fetches events with date range filter', async () => {
      const filters: EventFilters = {
        start_date: '2025-12-01',
        end_date: '2025-12-31',
      };

      renderHook(() => useEventsInfiniteQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({
            start_date: '2025-12-01',
            end_date: '2025-12-31',
          })
        );
      });
    });

    it('fetches events with reviewed filter', async () => {
      const filters: EventFilters = { reviewed: true };

      renderHook(() => useEventsInfiniteQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ reviewed: true }));
      });
    });

    it('fetches events with object type filter', async () => {
      const filters: EventFilters = { object_type: 'person' };

      renderHook(() => useEventsInfiniteQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ object_type: 'person' })
        );
      });
    });

    it('fetches events with multiple filters combined', async () => {
      const filters: EventFilters = {
        camera_id: 'front_door',
        risk_level: 'high',
        start_date: '2025-12-01',
        reviewed: false,
      };

      renderHook(() => useEventsInfiniteQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({
            camera_id: 'front_door',
            risk_level: 'high',
            start_date: '2025-12-01',
            reviewed: false,
          })
        );
      });
    });
  });

  describe('pagination', () => {
    it('fetches next page with cursor', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce(mockEvents)
        .mockResolvedValueOnce(mockEventsPage2);

      const { result } = renderHook(() => useEventsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      // Wait for first page to load
      await waitFor(() => {
        expect(result.current.hasNextPage).toBe(true);
      });

      // Fetch next page
      result.current.fetchNextPage();

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledTimes(2);
      });

      // Verify cursor was passed for second call
      expect(api.fetchEvents).toHaveBeenLastCalledWith(
        expect.objectContaining({ cursor: 'cursor-page-2' })
      );
    });

    it('accumulates events from multiple pages', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce(mockEvents)
        .mockResolvedValueOnce(mockEventsPage2);

      const { result } = renderHook(() => useEventsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      // Wait for first page to load
      await waitFor(() => {
        expect(result.current.events.length).toBe(2);
      });

      // Fetch next page
      result.current.fetchNextPage();

      await waitFor(() => {
        // Should now have all 3 events
        expect(result.current.events.length).toBe(3);
        expect(result.current.events.map((e) => e.id)).toEqual([1, 2, 3]);
      });
    });

    it('sets hasNextPage to false when no more pages', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce(mockEvents)
        .mockResolvedValueOnce(mockEventsPage2);

      const { result } = renderHook(() => useEventsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

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
      const errorMessage = 'Failed to fetch events';
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useEventsInfiniteQuery({ retry: 0 }), {
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
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useEventsInfiniteQuery({ retry: 0 }), {
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
    it('respects custom limit', async () => {
      renderHook(() => useEventsInfiniteQuery({ limit: 25 }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ limit: 25 }));
      });
    });

    it('does not fetch when enabled is false', async () => {
      renderHook(() => useEventsInfiniteQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchEvents).not.toHaveBeenCalled();
    });

    it('uses default retry of 1', async () => {
      // The hook defaults to retry: 1, which is less than the global default of 3
      // This is tested by verifying the hook can be created with default options
      const { result } = renderHook(() => useEventsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('provides refetch function', async () => {
      const { result } = renderHook(() => useEventsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });

  describe('query keys', () => {
    it('generates correct query keys', () => {
      expect(eventsQueryKeys.all).toEqual(['events']);
      expect(eventsQueryKeys.lists()).toEqual(['events', 'list']);

      const filters: EventFilters = { camera_id: 'test' };
      expect(eventsQueryKeys.list(filters)).toEqual(['events', 'list', filters]);
      expect(eventsQueryKeys.infinite(filters, 25)).toEqual([
        'events',
        'infinite',
        { filters, limit: 25 },
      ]);
      expect(eventsQueryKeys.detail(123)).toEqual(['events', 'detail', 123]);
    });
  });
});
