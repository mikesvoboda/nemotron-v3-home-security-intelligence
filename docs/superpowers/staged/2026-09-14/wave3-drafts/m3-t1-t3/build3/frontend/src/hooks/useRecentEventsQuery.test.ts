/**
 * Tests for useRecentEventsQuery hook.
 *
 * This hook provides optimized fetching of recent events with server-side limiting,
 * designed for dashboard use cases where a small number of recent events is needed.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useRecentEventsQuery, recentEventsQueryKeys } from './useRecentEventsQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchEvents: vi.fn(),
}));

describe('useRecentEventsQuery', () => {
  const mockEvents = [
    {
      id: 1,
      camera_id: 'cam-1',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected at front door',
      started_at: '2025-12-28T10:00:00Z',
      ended_at: null,
      reviewed: false,
    },
    {
      id: 2,
      camera_id: 'cam-2',
      risk_score: 25,
      risk_level: 'low',
      summary: 'Motion in backyard - probably a cat',
      started_at: '2025-12-28T09:30:00Z',
      ended_at: '2025-12-28T09:32:00Z',
      reviewed: true,
    },
    {
      id: 3,
      camera_id: 'cam-1',
      risk_score: 90,
      risk_level: 'critical',
      summary: 'Unknown vehicle in driveway',
      started_at: '2025-12-28T09:00:00Z',
      ended_at: null,
      reviewed: false,
    },
  ];

  const mockEventListResponse = {
    items: mockEvents,
    pagination: {
      total: 100,
      limit: 10,
      offset: null,
      cursor: null,
      next_cursor: 'cursor-next',
      has_more: true,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchEvents as ReturnType<typeof vi.fn>).mockResolvedValue(mockEventListResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('query key factory', () => {
    it('generates correct base key', () => {
      expect(recentEventsQueryKeys.all).toEqual(['events', 'recent']);
    });

    it('generates correct list key without camera filter', () => {
      expect(recentEventsQueryKeys.list(10)).toEqual(['events', 'recent', { limit: 10 }]);
    });

    it('generates correct list key with camera filter', () => {
      expect(recentEventsQueryKeys.list(10, 'cam-1')).toEqual([
        'events',
        'recent',
        { limit: 10, cameraId: 'cam-1' },
      ]);
    });

    it('generates different keys for different limits', () => {
      const key5 = recentEventsQueryKeys.list(5);
      const key10 = recentEventsQueryKeys.list(10);
      expect(key5).not.toEqual(key10);
    });
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with empty events array', () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.events).toEqual([]);
    });

    it('starts with totalCount of 0', () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.totalCount).toBe(0);
    });
  });

  describe('fetching data', () => {
    it('fetches events on mount', async () => {
      renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledTimes(1);
      });
    });

    it('uses default limit of 10', async () => {
      renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith({ limit: 10 });
      });
    });

    it('respects custom limit option', async () => {
      renderHook(() => useRecentEventsQuery({ limit: 25 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith({ limit: 25 });
      });
    });

    it('includes camera_id when cameraId option is provided', async () => {
      renderHook(() => useRecentEventsQuery({ cameraId: 'front-door' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith({
          limit: 10,
          camera_id: 'front-door',
        });
      });
    });

    it('updates events after successful fetch', async () => {
      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.events).toEqual(mockEvents);
      });
    });

    it('updates totalCount from pagination metadata', async () => {
      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.totalCount).toBe(100);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets isFetching true during fetch', () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isFetching).toBe(true);
    });
  });

  describe('error handling', () => {
    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch events';
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useRecentEventsQuery(), {
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

    it('sets isError true on failure', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );
    });

    it('returns empty events array on error', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Server error'));

      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );

      expect(result.current.events).toEqual([]);
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useRecentEventsQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchEvents).not.toHaveBeenCalled();
    });

    it('sets isLoading to false when disabled', () => {
      const { result } = renderHook(() => useRecentEventsQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      // When query is disabled, isLoading should be false since it's not actually loading
      expect(result.current.isLoading).toBe(false);
    });

    it('fetches when enabled changes from false to true', async () => {
      const { rerender } = renderHook(({ enabled }) => useRecentEventsQuery({ enabled }), {
        wrapper: createQueryWrapper(),
        initialProps: { enabled: false },
      });

      await new Promise((r) => setTimeout(r, 50));
      expect(api.fetchEvents).not.toHaveBeenCalled();

      rerender({ enabled: true });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new fetch', async () => {
      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEvents).toHaveBeenCalledTimes(1);

      // Trigger refetch
      void result.current.refetch();

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('refetchInterval option', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('refetches at specified interval', async () => {
      renderHook(
        () =>
          useRecentEventsQuery({
            refetchInterval: 5000,
          }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      // Initial fetch
      await vi.advanceTimersByTimeAsync(0);
      expect(api.fetchEvents).toHaveBeenCalledTimes(1);

      // Advance time to trigger refetch
      await vi.advanceTimersByTimeAsync(5000);
      expect(api.fetchEvents).toHaveBeenCalledTimes(2);

      // Another interval
      await vi.advanceTimersByTimeAsync(5000);
      expect(api.fetchEvents).toHaveBeenCalledTimes(3);
    });

    it('does not refetch when refetchInterval is false', async () => {
      renderHook(
        () =>
          useRecentEventsQuery({
            refetchInterval: false,
          }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      // Initial fetch
      await vi.advanceTimersByTimeAsync(0);
      expect(api.fetchEvents).toHaveBeenCalledTimes(1);

      // Advance time - no refetch should happen
      await vi.advanceTimersByTimeAsync(10000);
      expect(api.fetchEvents).toHaveBeenCalledTimes(1);
    });
  });

  describe('staleTime option', () => {
    it('uses default stale time of 30 seconds', async () => {
      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Query should have been called once
      expect(api.fetchEvents).toHaveBeenCalledTimes(1);
    });

    it('accepts custom stale time', async () => {
      const { result } = renderHook(
        () =>
          useRecentEventsQuery({
            staleTime: 60000, // 1 minute
          }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Query should work normally with custom stale time
      expect(result.current.events).toEqual(mockEvents);
    });
  });

  describe('cache behavior', () => {
    it('deduplicates concurrent requests', async () => {
      const wrapper = createQueryWrapper();

      // Render two hooks with the same options
      const { result: result1 } = renderHook(() => useRecentEventsQuery({ limit: 10 }), {
        wrapper,
      });
      const { result: result2 } = renderHook(() => useRecentEventsQuery({ limit: 10 }), {
        wrapper,
      });

      await waitFor(() => {
        expect(result1.current.isLoading).toBe(false);
        expect(result2.current.isLoading).toBe(false);
      });

      // Should only have made one request due to deduplication
      expect(api.fetchEvents).toHaveBeenCalledTimes(1);
    });

    it('makes separate requests for different limits', async () => {
      const wrapper = createQueryWrapper();

      const { result: result1 } = renderHook(() => useRecentEventsQuery({ limit: 5 }), {
        wrapper,
      });
      const { result: result2 } = renderHook(() => useRecentEventsQuery({ limit: 10 }), {
        wrapper,
      });

      await waitFor(() => {
        expect(result1.current.isLoading).toBe(false);
        expect(result2.current.isLoading).toBe(false);
      });

      // Should have made two separate requests
      expect(api.fetchEvents).toHaveBeenCalledTimes(2);
    });

    it('makes separate requests for different camera IDs', async () => {
      const wrapper = createQueryWrapper();

      renderHook(() => useRecentEventsQuery({ cameraId: 'cam-1' }), {
        wrapper,
      });
      renderHook(() => useRecentEventsQuery({ cameraId: 'cam-2' }), {
        wrapper,
      });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledTimes(2);
      });

      expect(api.fetchEvents).toHaveBeenCalledWith({ limit: 10, camera_id: 'cam-1' });
      expect(api.fetchEvents).toHaveBeenCalledWith({ limit: 10, camera_id: 'cam-2' });
    });
  });

  describe('return type contract', () => {
    it('returns all expected properties', async () => {
      const { result } = renderHook(() => useRecentEventsQuery(), {
        wrapper: createQueryWrapper(),
      });

      // Check all properties exist (even during loading)
      expect(result.current).toHaveProperty('events');
      expect(result.current).toHaveProperty('totalCount');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('isFetching');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('isError');
      expect(result.current).toHaveProperty('refetch');

      // Verify types
      expect(Array.isArray(result.current.events)).toBe(true);
      expect(typeof result.current.totalCount).toBe('number');
      expect(typeof result.current.isLoading).toBe('boolean');
      expect(typeof result.current.isFetching).toBe('boolean');
      expect(typeof result.current.isError).toBe('boolean');
      expect(typeof result.current.refetch).toBe('function');

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });
});
