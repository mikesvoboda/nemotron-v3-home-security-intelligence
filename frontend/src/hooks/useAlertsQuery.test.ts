/**
 * Tests for useAlertsInfiniteQuery hook (NEM-2552)
 *
 * This hook fetches high and critical risk alerts in parallel,
 * merges them client-side, and provides infinite scroll support.
 */
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useAlertsInfiniteQuery, alertsQueryKeys } from './useAlertsQuery';
import * as api from '../services/api';
import { createQueryClient } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module - need to include all exports used by queryClient.ts
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchEvents: vi.fn(),
  };
});

describe('useAlertsInfiniteQuery', () => {
  // Helper to create mock event data
  const createMockEvent = (overrides: Partial<api.Event> = {}): api.Event => ({
    id: Math.floor(Math.random() * 10000),
    camera_id: 'cam-1',
    risk_score: 75,
    risk_level: 'high',
    summary: 'Test alert',
    reasoning: 'Test reasoning',
    started_at: new Date().toISOString(),
    ended_at: null,
    reviewed: false,
    notes: null,
    detection_count: 1,
    version: 1, // Optimistic locking version (NEM-3625)
    ...overrides,
  });

  // Helper to create mock event list response
  const createMockResponse = (
    items: api.Event[],
    pagination: Partial<api.EventListResponse['pagination']> = {}
  ): api.EventListResponse => ({
    items,
    pagination: {
      total: items.length,
      limit: 25,
      offset: 0,
      has_more: false,
      next_cursor: null,
      ...pagination,
    },
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true when fetching', () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {}) // Never resolving promise
      );

      const { result } = renderHook(() => useAlertsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.alerts).toEqual([]);
    });

    it('starts with empty alerts array', () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAlertsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.alerts).toEqual([]);
      expect(result.current.totalCount).toBe(0);
    });
  });

  describe('parallel fetching of high and critical alerts', () => {
    it('fetches both high and critical alerts in parallel when riskFilter is "all"', async () => {
      const highAlerts = [
        createMockEvent({ id: 1, risk_level: 'high', started_at: '2026-01-13T10:00:00Z' }),
      ];
      const criticalAlerts = [
        createMockEvent({ id: 2, risk_level: 'critical', started_at: '2026-01-13T11:00:00Z' }),
      ];

      (api.fetchEvents as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        (params: api.EventsQueryParams): Promise<api.EventListResponse> => {
          if (params?.risk_level === 'high') {
            return Promise.resolve(createMockResponse(highAlerts, { total: 1 }));
          }
          if (params?.risk_level === 'critical') {
            return Promise.resolve(createMockResponse(criticalAlerts, { total: 1 }));
          }
          return Promise.resolve(createMockResponse([]));
        }
      );

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'all' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Both queries should have been called
      expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ risk_level: 'high' }));
      expect(api.fetchEvents).toHaveBeenCalledWith(
        expect.objectContaining({ risk_level: 'critical' })
      );

      // Both results should be merged
      expect(result.current.alerts).toHaveLength(2);
      expect(result.current.totalCount).toBe(2);
    });

    it('fetches only high alerts when riskFilter is "high"', async () => {
      const highAlerts = [createMockEvent({ id: 1, risk_level: 'high' })];

      (api.fetchEvents as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockResponse(highAlerts, { total: 1 })
      );

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'high' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Only high query should have been called
      expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ risk_level: 'high' }));
      expect(api.fetchEvents).not.toHaveBeenCalledWith(
        expect.objectContaining({ risk_level: 'critical' })
      );

      expect(result.current.alerts).toHaveLength(1);
    });

    it('fetches only critical alerts when riskFilter is "critical"', async () => {
      const criticalAlerts = [createMockEvent({ id: 1, risk_level: 'critical' })];

      (api.fetchEvents as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockResponse(criticalAlerts, { total: 1 })
      );

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'critical' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Only critical query should have been called
      expect(api.fetchEvents).toHaveBeenCalledWith(
        expect.objectContaining({ risk_level: 'critical' })
      );
      expect(api.fetchEvents).not.toHaveBeenCalledWith(
        expect.objectContaining({ risk_level: 'high' })
      );

      expect(result.current.alerts).toHaveLength(1);
    });
  });

  describe('merging and deduplication', () => {
    it('deduplicates alerts by ID when same alert appears in both queries', async () => {
      // Same alert ID in both responses (edge case)
      const duplicateId = 42;
      const duplicateAlert = createMockEvent({
        id: duplicateId,
        risk_level: 'high',
        started_at: '2026-01-13T10:00:00Z',
      });

      (api.fetchEvents as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        (params: api.EventsQueryParams): Promise<api.EventListResponse> => {
          if (params?.risk_level === 'high') {
            return Promise.resolve(createMockResponse([duplicateAlert], { total: 1 }));
          }
          if (params?.risk_level === 'critical') {
            // Same ID returned from critical query (unlikely but possible)
            return Promise.resolve(
              createMockResponse([{ ...duplicateAlert, risk_level: 'critical' }], { total: 1 })
            );
          }
          return Promise.resolve(createMockResponse([]));
        }
      );

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'all' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should only have 1 alert after deduplication
      expect(result.current.alerts).toHaveLength(1);
      expect(result.current.alerts[0].id).toBe(duplicateId);
    });
  });

  describe('sorting', () => {
    it('sorts alerts by timestamp descending (newest first)', async () => {
      const oldAlert = createMockEvent({
        id: 1,
        risk_level: 'high',
        started_at: '2026-01-13T08:00:00Z',
      });
      const newAlert = createMockEvent({
        id: 2,
        risk_level: 'critical',
        started_at: '2026-01-13T12:00:00Z',
      });
      const midAlert = createMockEvent({
        id: 3,
        risk_level: 'high',
        started_at: '2026-01-13T10:00:00Z',
      });

      (api.fetchEvents as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        (params: api.EventsQueryParams): Promise<api.EventListResponse> => {
          if (params?.risk_level === 'high') {
            return Promise.resolve(createMockResponse([oldAlert, midAlert], { total: 2 }));
          }
          if (params?.risk_level === 'critical') {
            return Promise.resolve(createMockResponse([newAlert], { total: 1 }));
          }
          return Promise.resolve(createMockResponse([]));
        }
      );

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'all' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.alerts).toHaveLength(3);
      // Newest first
      expect(result.current.alerts[0].id).toBe(2); // 12:00
      expect(result.current.alerts[1].id).toBe(3); // 10:00
      expect(result.current.alerts[2].id).toBe(1); // 08:00
    });
  });

  describe('pagination and cursor handling', () => {
    it('uses cursor for pagination when has_more is true', async () => {
      const firstPage = createMockResponse(
        [createMockEvent({ id: 1, started_at: '2026-01-13T12:00:00Z' })],
        { has_more: true, next_cursor: 'cursor-page-2' }
      );
      const secondPage = createMockResponse(
        [createMockEvent({ id: 2, started_at: '2026-01-13T11:00:00Z' })],
        { has_more: false, next_cursor: null }
      );

      (api.fetchEvents as ReturnType<typeof vi.fn>).mockImplementation((params) => {
        // Only track calls for high risk (critical follows same pattern)
        if (params?.risk_level === 'high') {
          if (params?.cursor === 'cursor-page-2') {
            return secondPage;
          }
          return firstPage;
        }
        // Critical returns empty to simplify test
        return createMockResponse([]);
      });

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'high' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.hasNextPage).toBe(true);

      // Fetch next page
      act(() => {
        result.current.fetchNextPage();
      });

      await waitFor(() => {
        expect(result.current.isFetchingNextPage).toBe(false);
      });

      // Should have been called with cursor
      expect(api.fetchEvents).toHaveBeenCalledWith(
        expect.objectContaining({ cursor: 'cursor-page-2' })
      );

      expect(result.current.alerts).toHaveLength(2);
    });

    it('hasNextPage is true when either query has more pages', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockImplementation((params) => {
        if (params?.risk_level === 'high') {
          return createMockResponse([createMockEvent({ id: 1, risk_level: 'high' })], {
            has_more: true,
            next_cursor: 'high-cursor',
          });
        }
        if (params?.risk_level === 'critical') {
          return createMockResponse([createMockEvent({ id: 2, risk_level: 'critical' })], {
            has_more: false,
            next_cursor: null,
          });
        }
        return createMockResponse([]);
      });

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'all' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // hasNextPage should be true because high query has more
      expect(result.current.hasNextPage).toBe(true);
    });

    it('hasNextPage is false when neither query has more pages', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockImplementation((params) => {
        if (params?.risk_level === 'high') {
          return createMockResponse([createMockEvent({ id: 1, risk_level: 'high' })], {
            has_more: false,
            next_cursor: null,
          });
        }
        if (params?.risk_level === 'critical') {
          return createMockResponse([createMockEvent({ id: 2, risk_level: 'critical' })], {
            has_more: false,
            next_cursor: null,
          });
        }
        return createMockResponse([]);
      });

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'all' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.hasNextPage).toBe(false);
    });
  });

  describe('fetchNextPage behavior', () => {
    it('fetches next page from both queries when both have more', async () => {
      const highPage1 = createMockResponse(
        [createMockEvent({ id: 1, risk_level: 'high', started_at: '2026-01-13T12:00:00Z' })],
        { has_more: true, next_cursor: 'high-cursor-2' }
      );
      const highPage2 = createMockResponse(
        [createMockEvent({ id: 3, risk_level: 'high', started_at: '2026-01-13T10:00:00Z' })],
        { has_more: false }
      );
      const criticalPage1 = createMockResponse(
        [createMockEvent({ id: 2, risk_level: 'critical', started_at: '2026-01-13T11:00:00Z' })],
        { has_more: true, next_cursor: 'critical-cursor-2' }
      );
      const criticalPage2 = createMockResponse(
        [createMockEvent({ id: 4, risk_level: 'critical', started_at: '2026-01-13T09:00:00Z' })],
        { has_more: false }
      );

      (api.fetchEvents as ReturnType<typeof vi.fn>).mockImplementation((params) => {
        if (params?.risk_level === 'high') {
          return params?.cursor === 'high-cursor-2' ? highPage2 : highPage1;
        }
        if (params?.risk_level === 'critical') {
          return params?.cursor === 'critical-cursor-2' ? criticalPage2 : criticalPage1;
        }
        return createMockResponse([]);
      });

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'all' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.alerts).toHaveLength(2);

      // Fetch next page
      act(() => {
        result.current.fetchNextPage();
      });

      await waitFor(() => {
        expect(result.current.isFetchingNextPage).toBe(false);
      });

      // Should have all 4 alerts now
      expect(result.current.alerts).toHaveLength(4);
      // Still sorted by timestamp
      expect(result.current.alerts.map((a) => a.id)).toEqual([1, 2, 3, 4]);
    });
  });

  describe('loading and fetching states', () => {
    it('isLoading is true only during initial fetch', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockResponse([createMockEvent()])
      );

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'high' }), {
        wrapper: createQueryWrapper(),
      });

      // Initially loading
      expect(result.current.isLoading).toBe(true);
      expect(result.current.isFetching).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isFetching).toBe(false);
    });

    it('isFetching is true during background refetch', async () => {
      const queryClient = createQueryClient();
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockResponse([createMockEvent()])
      );

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'high' }), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Trigger refetch
      await act(async () => {
        await result.current.refetch();
      });

      // After refetch completes
      await waitFor(() => {
        expect(result.current.isFetching).toBe(false);
      });

      expect(result.current.isLoading).toBe(false);
    });

    it('isFetchingNextPage is true while loading next page', async () => {
      let resolveNextPage: (value: api.EventListResponse) => void;
      const nextPagePromise = new Promise<api.EventListResponse>((resolve) => {
        resolveNextPage = resolve;
      });

      (api.fetchEvents as ReturnType<typeof vi.fn>).mockImplementation(
        // eslint-disable-next-line @typescript-eslint/no-misused-promises -- test mock intentionally returns Promise
        (params): Promise<api.EventListResponse> => {
          if (params?.cursor === 'next-cursor') {
            return nextPagePromise;
          }
          return Promise.resolve(
            createMockResponse([createMockEvent({ id: 1 })], {
              has_more: true,
              next_cursor: 'next-cursor',
            })
          );
        }
      );

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'high' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isFetchingNextPage).toBe(false);

      // Start fetching next page
      act(() => {
        result.current.fetchNextPage();
      });

      await waitFor(() => {
        expect(result.current.isFetchingNextPage).toBe(true);
      });

      // Resolve the promise
      act(() => {
        resolveNextPage!(createMockResponse([createMockEvent({ id: 2 })]));
      });

      await waitFor(() => {
        expect(result.current.isFetchingNextPage).toBe(false);
      });
    });
  });

  describe('error handling', () => {
    it('propagates error from failed query', async () => {
      const testError = new Error('Failed to fetch alerts');
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockRejectedValue(testError);

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'high' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );

      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe('Failed to fetch alerts');
    });

    it('isError is true when either query fails', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockImplementation((params) => {
        if (params?.risk_level === 'high') {
          return createMockResponse([createMockEvent({ risk_level: 'high' })]);
        }
        if (params?.risk_level === 'critical') {
          throw new Error('Critical fetch failed');
        }
        return createMockResponse([]);
      });

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'all' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );
    });

    it('error contains first encountered error', async () => {
      const criticalError = new Error('Critical fetch failed');
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockImplementation((params) => {
        if (params?.risk_level === 'high') {
          return createMockResponse([]);
        }
        if (params?.risk_level === 'critical') {
          throw criticalError;
        }
        return createMockResponse([]);
      });

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'all' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).not.toBeNull();
        },
        { timeout: 5000 }
      );

      expect(result.current.error?.message).toBe('Critical fetch failed');
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockResolvedValue(createMockResponse([]));

      const { result } = renderHook(() => useAlertsInfiniteQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));

      expect(api.fetchEvents).not.toHaveBeenCalled();
      expect(result.current.isLoading).toBe(false);
    });

    it('fetches when enabled changes from false to true', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockResponse([createMockEvent()])
      );

      const { rerender } = renderHook(
        ({ enabled }: { enabled: boolean }) => useAlertsInfiniteQuery({ enabled }),
        {
          wrapper: createQueryWrapper(),
          initialProps: { enabled: false },
        }
      );

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchEvents).not.toHaveBeenCalled();

      // Enable the query
      rerender({ enabled: true });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalled();
      });
    });
  });

  describe('limit option', () => {
    it('passes limit parameter to API', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockResolvedValue(createMockResponse([]));

      renderHook(() => useAlertsInfiniteQuery({ limit: 50 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ limit: 50 }));
      });
    });

    it('uses default limit of 25 when not specified', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockResolvedValue(createMockResponse([]));

      renderHook(() => useAlertsInfiniteQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ limit: 25 }));
      });
    });
  });

  describe('refetch function', () => {
    it('refetches all active queries', async () => {
      (api.fetchEvents as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockResponse([createMockEvent()])
      );

      const { result } = renderHook(() => useAlertsInfiniteQuery({ riskFilter: 'all' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Clear mock to track refetch calls
      vi.clearAllMocks();

      await act(async () => {
        await result.current.refetch();
      });

      // Both queries should have been refetched
      expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ risk_level: 'high' }));
      expect(api.fetchEvents).toHaveBeenCalledWith(
        expect.objectContaining({ risk_level: 'critical' })
      );
    });
  });

  describe('alertsQueryKeys', () => {
    it('generates correct query keys', () => {
      expect(alertsQueryKeys.all).toEqual(['alerts']);
      expect(alertsQueryKeys.infinite('high', 25)).toEqual([
        'alerts',
        'infinite',
        { riskLevel: 'high', limit: 25 },
      ]);
      expect(alertsQueryKeys.infinite('critical', 50)).toEqual([
        'alerts',
        'infinite',
        { riskLevel: 'critical', limit: 50 },
      ]);
    });
  });
});
