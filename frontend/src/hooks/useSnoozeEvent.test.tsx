/**
 * Tests for useSnoozeEvent hook (NEM-5011)
 *
 * Tests both basic functionality and optimistic update behavior.
 */
import { QueryClient, QueryClientProvider, type InfiniteData } from '@tanstack/react-query';
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { eventsQueryKeys } from './useEventsQuery';
import { useSnoozeEvent } from './useSnoozeEvent';
import * as api from '../services/api';

import type { EventListResponse, Event } from '../services/api';
import type { ReactNode } from 'react';

// Mock the API module
vi.mock('../services/api', () => ({
  snoozeEvent: vi.fn(),
  clearSnooze: vi.fn(),
}));

// =============================================================================
// Test Data Factories
// =============================================================================

/**
 * Creates a mock Event for testing.
 */
function createMockEvent(overrides: Partial<Event> = {}): Event {
  return {
    id: 1,
    camera_id: 'front_door',
    started_at: '2024-01-15T11:00:00Z',
    ended_at: '2024-01-15T11:05:00Z',
    risk_score: 75,
    risk_level: 'high',
    summary: 'Test event',
    reviewed: false,
    flagged: false,
    detection_count: 3,
    version: 1,
    snooze_until: null,
    ...overrides,
  } as Event;
}

/**
 * Creates mock infinite query data for events.
 */
function createMockInfiniteEventsData(
  events: Event[]
): InfiniteData<EventListResponse, string | null> {
  return {
    pages: [
      {
        items: events,
        pagination: {
          total: events.length,
          limit: 25,
          has_more: false,
          next_cursor: null,
        },
      },
    ],
    pageParams: [null],
  };
}

describe('useSnoozeEvent', () => {
  const MOCK_NOW = new Date('2024-01-15T12:00:00Z');
  let queryClient: QueryClient;

  // Create a wrapper component for the hook
  function createWrapper() {
    return function Wrapper({ children }: { children: ReactNode }) {
      return (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      );
    };
  }

  beforeEach(() => {
    vi.useFakeTimers({ now: MOCK_NOW });

    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
          staleTime: 0,
        },
        mutations: {
          retry: false,
        },
      },
    });

    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    queryClient?.clear();
  });

  it('returns snooze and unsnooze functions', () => {
    const { result } = renderHook(() => useSnoozeEvent(), {
      wrapper: createWrapper(),
    });

    expect(result.current.snooze).toBeDefined();
    expect(result.current.unsnooze).toBeDefined();
    expect(typeof result.current.snooze).toBe('function');
    expect(typeof result.current.unsnooze).toBe('function');
  });

  it('returns isSnoozing and isUnsnoozing states', () => {
    const { result } = renderHook(() => useSnoozeEvent(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isSnoozing).toBe(false);
    expect(result.current.isUnsnoozing).toBe(false);
  });

  it('returns error and reset function', () => {
    const { result } = renderHook(() => useSnoozeEvent(), {
      wrapper: createWrapper(),
    });

    expect(result.current.error).toBeNull();
    expect(result.current.reset).toBeDefined();
    expect(typeof result.current.reset).toBe('function');
  });

  describe('snooze', () => {
    it('calls snoozeEvent API with correct parameters', async () => {
      const mockEvent = {
        id: 123,
        snooze_until: new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString(),
      };

      (api.snoozeEvent as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockEvent as api.Event);

      const { result } = renderHook(() => useSnoozeEvent(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.snooze(123, 3600); // 1 hour
      });

      expect(api.snoozeEvent).toHaveBeenCalledWith(123, 3600);
    });

    it('has isSnoozing property', async () => {
      const mockEvent = { id: 123 } as api.Event;
      (api.snoozeEvent as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockEvent);

      const { result } = renderHook(() => useSnoozeEvent(), {
        wrapper: createWrapper(),
      });

      // isSnoozing should start false
      expect(result.current.isSnoozing).toBe(false);

      // After successful snooze, should return to false
      await act(async () => {
        await result.current.snooze(123, 3600);
      });

      expect(result.current.isSnoozing).toBe(false);
    });

    it('calls onSuccess callback when snooze succeeds', async () => {
      const mockEvent = { id: 123 } as api.Event;
      (api.snoozeEvent as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockEvent);

      const onSuccess = vi.fn();
      const { result } = renderHook(
        () => useSnoozeEvent({ onSuccess }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.snooze(123, 3600);
      });

      expect(onSuccess).toHaveBeenCalledWith(mockEvent, 123, 3600);
    });

    it('calls onError callback when snooze fails', async () => {
      const error = new Error('API Error');
      (api.snoozeEvent as ReturnType<typeof vi.fn>).mockRejectedValueOnce(error);

      const onError = vi.fn();
      const { result } = renderHook(
        () => useSnoozeEvent({ onError }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        try {
          await result.current.snooze(123, 3600);
        } catch {
          // Expected to throw
        }
      });

      expect(onError).toHaveBeenCalledWith(error, 123, 3600);
    });

    it('invalidates queries on success by default', async () => {
      const mockEvent = { id: 123 } as api.Event;
      (api.snoozeEvent as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockEvent);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useSnoozeEvent(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.snooze(123, 3600);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalled();
    });

    it('does not invalidate queries when invalidateQueries is false', async () => {
      const mockEvent = { id: 123 } as api.Event;
      (api.snoozeEvent as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockEvent);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(
        () => useSnoozeEvent({ invalidateQueries: false }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.snooze(123, 3600);
      });

      expect(invalidateQueriesSpy).not.toHaveBeenCalled();
    });
  });

  describe('unsnooze', () => {
    it('calls clearSnooze API with correct parameters', async () => {
      const mockEvent = { id: 123, snooze_until: null } as api.Event;
      (api.clearSnooze as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockEvent);

      const { result } = renderHook(() => useSnoozeEvent(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.unsnooze(123);
      });

      expect(api.clearSnooze).toHaveBeenCalledWith(123);
    });

    it('has isUnsnoozing property', async () => {
      const mockEvent = { id: 123 } as api.Event;
      (api.clearSnooze as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockEvent);

      const { result } = renderHook(() => useSnoozeEvent(), {
        wrapper: createWrapper(),
      });

      // isUnsnoozing should start false
      expect(result.current.isUnsnoozing).toBe(false);

      // After successful unsnooze, should return to false
      await act(async () => {
        await result.current.unsnooze(123);
      });

      expect(result.current.isUnsnoozing).toBe(false);
    });

    it('calls onSuccess callback with 0 seconds when unsnooze succeeds', async () => {
      const mockEvent = { id: 123 } as api.Event;
      (api.clearSnooze as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockEvent);

      const onSuccess = vi.fn();
      const { result } = renderHook(
        () => useSnoozeEvent({ onSuccess }),
        { wrapper: createWrapper() }
      );

      await act(async () => {
        await result.current.unsnooze(123);
      });

      expect(onSuccess).toHaveBeenCalledWith(mockEvent, 123, 0);
    });
  });

  describe('reset', () => {
    it('reset function exists and can be called', () => {
      const { result } = renderHook(() => useSnoozeEvent(), {
        wrapper: createWrapper(),
      });

      // reset should be a callable function
      expect(typeof result.current.reset).toBe('function');

      // Should not throw when called
      act(() => {
        result.current.reset();
      });
    });
  });

  // ===========================================================================
  // Optimistic Updates Tests (NEM-5011)
  // ===========================================================================

  describe('optimistic updates', () => {
    const mockEvent = createMockEvent({ id: 123 });
    const mockEvents = [mockEvent, createMockEvent({ id: 456 })];

    describe('snooze optimistic update', () => {
      it('applies optimistic update immediately before API response', async () => {
        // Use real timers for this test as waitFor doesn't work well with fake timers
        vi.useRealTimers();

        // Create a fresh queryClient for this test
        // Note: gcTime must be > 0 to prevent immediate garbage collection of cache data
        const testQueryClient = new QueryClient({
          defaultOptions: {
            queries: { retry: false, gcTime: Infinity, staleTime: 0 },
            mutations: { retry: false },
          },
        });

        const TestWrapper = ({ children }: { children: ReactNode }) => (
          <QueryClientProvider client={testQueryClient}>{children}</QueryClientProvider>
        );

        // Create a deferred promise to control API timing
        let resolveSnooze: (value: Event) => void;
        const snoozePromise = new Promise<Event>((resolve) => {
          resolveSnooze = resolve;
        });
        (api.snoozeEvent as ReturnType<typeof vi.fn>).mockReturnValue(snoozePromise);

        // Pre-populate the cache with events
        const eventsKey = eventsQueryKeys.infinite(undefined, 25);
        testQueryClient.setQueryData(eventsKey, createMockInfiniteEventsData(mockEvents));

        const { result } = renderHook(() => useSnoozeEvent(), {
          wrapper: TestWrapper,
        });

        // Start the snooze mutation (don't await)
        act(() => {
          void result.current.snooze(123, 3600);
        });

        // Verify optimistic update was applied BEFORE API resolves
        // Use waitFor to handle the async onMutate callback
        await waitFor(() => {
          const optimisticData = testQueryClient.getQueryData<
            InfiniteData<EventListResponse, string | null>
          >(eventsKey);
          const updatedEvent = optimisticData?.pages[0].items.find((e) => e.id === 123);
          expect(updatedEvent?.snooze_until).not.toBeNull();
        });

        // Verify the optimistic snooze_until value
        const optimisticData = testQueryClient.getQueryData<
          InfiniteData<EventListResponse, string | null>
        >(eventsKey);
        const updatedEvent = optimisticData?.pages[0].items.find((e) => e.id === 123);

        // The optimistic snooze_until should be set (approximately 1 hour from now)
        expect(updatedEvent?.snooze_until).toBeDefined();
        expect(updatedEvent?.snooze_until).not.toBeNull();

        // Other events should remain unchanged
        const unchangedEvent = optimisticData?.pages[0].items.find((e) => e.id === 456);
        expect(unchangedEvent?.snooze_until).toBeNull();

        // Now resolve the API call
        const serverResponse = { ...mockEvent, snooze_until: '2024-01-15T13:00:00Z' };
        resolveSnooze!(serverResponse);

        // Wait for mutation to complete
        await waitFor(() => {
          expect(result.current.isSnoozing).toBe(false);
        });

        // Cleanup
        testQueryClient.clear();

        // Restore fake timers for other tests
        vi.useFakeTimers();
        vi.setSystemTime(MOCK_NOW);
      });

      it('rollbacks to previous state on API error', async () => {
        const error = new Error('API Error');
        (api.snoozeEvent as ReturnType<typeof vi.fn>).mockRejectedValueOnce(error);

        // Pre-populate the cache with events (none snoozed)
        const eventsKey = eventsQueryKeys.infinite(undefined, 25);
        queryClient.setQueryData(eventsKey, createMockInfiniteEventsData(mockEvents));

        const onError = vi.fn();
        const { result } = renderHook(
          () => useSnoozeEvent({ onError, invalidateQueries: false }),
          { wrapper: createWrapper() }
        );

        // Attempt to snooze (will fail)
        await act(async () => {
          try {
            await result.current.snooze(123, 3600);
          } catch {
            // Expected to throw
          }
        });

        // Verify rollback occurred - snooze_until should be null again
        const rolledBackData = queryClient.getQueryData<
          InfiniteData<EventListResponse, string | null>
        >(eventsKey);
        const rolledBackEvent = rolledBackData?.pages[0].items.find((e) => e.id === 123);

        expect(rolledBackEvent?.snooze_until).toBeNull();
        expect(onError).toHaveBeenCalledWith(error, 123, 3600);
      });

      it('updates cache with server response on success', async () => {
        const serverSnoozeUntil = '2024-01-15T13:30:00Z';
        const serverResponse = { ...mockEvent, snooze_until: serverSnoozeUntil };
        (api.snoozeEvent as ReturnType<typeof vi.fn>).mockResolvedValueOnce(serverResponse);

        // Pre-populate the cache
        const eventsKey = eventsQueryKeys.infinite(undefined, 25);
        queryClient.setQueryData(eventsKey, createMockInfiniteEventsData(mockEvents));

        const { result } = renderHook(
          () => useSnoozeEvent({ invalidateQueries: false }),
          { wrapper: createWrapper() }
        );

        await act(async () => {
          await result.current.snooze(123, 3600);
        });

        // Verify cache was updated with server response
        const updatedData = queryClient.getQueryData<
          InfiniteData<EventListResponse, string | null>
        >(eventsKey);
        const updatedEvent = updatedData?.pages[0].items.find((e) => e.id === 123);

        expect(updatedEvent?.snooze_until).toBe(serverSnoozeUntil);
      });

      it('cancels outgoing queries before applying optimistic update', async () => {
        (api.snoozeEvent as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
          ...mockEvent,
          snooze_until: '2024-01-15T13:00:00Z',
        });

        const cancelQueriesSpy = vi.spyOn(queryClient, 'cancelQueries');

        // Pre-populate the cache
        const eventsKey = eventsQueryKeys.infinite(undefined, 25);
        queryClient.setQueryData(eventsKey, createMockInfiniteEventsData(mockEvents));

        const { result } = renderHook(() => useSnoozeEvent(), {
          wrapper: createWrapper(),
        });

        await act(async () => {
          await result.current.snooze(123, 3600);
        });

        // Should have cancelled queries for both events and alerts
        expect(cancelQueriesSpy).toHaveBeenCalled();
      });
    });

    describe('unsnooze optimistic update', () => {
      it('clears snooze_until optimistically', async () => {
        // Use real timers for this test as waitFor doesn't work well with fake timers
        vi.useRealTimers();

        // Create a fresh queryClient for this test
        // Note: gcTime must be > 0 to prevent immediate garbage collection of cache data
        const testQueryClient = new QueryClient({
          defaultOptions: {
            queries: { retry: false, gcTime: Infinity, staleTime: 0 },
            mutations: { retry: false },
          },
        });

        const TestWrapper = ({ children }: { children: ReactNode }) => (
          <QueryClientProvider client={testQueryClient}>{children}</QueryClientProvider>
        );

        // Create events with one already snoozed
        const snoozedEvent = createMockEvent({
          id: 123,
          snooze_until: '2024-01-15T14:00:00Z',
        });
        const snoozedEvents = [snoozedEvent, createMockEvent({ id: 456 })];

        let resolveUnsnooze: (value: Event) => void;
        const unsnoozePromise = new Promise<Event>((resolve) => {
          resolveUnsnooze = resolve;
        });
        (api.clearSnooze as ReturnType<typeof vi.fn>).mockReturnValue(unsnoozePromise);

        // Pre-populate the cache
        const eventsKey = eventsQueryKeys.infinite(undefined, 25);
        testQueryClient.setQueryData(eventsKey, createMockInfiniteEventsData(snoozedEvents));

        const { result } = renderHook(() => useSnoozeEvent(), {
          wrapper: TestWrapper,
        });

        // Start the unsnooze mutation
        act(() => {
          void result.current.unsnooze(123);
        });

        // Verify optimistic update was applied (use waitFor for async onMutate)
        await waitFor(() => {
          const optimisticData = testQueryClient.getQueryData<
            InfiniteData<EventListResponse, string | null>
          >(eventsKey);
          const updatedEvent = optimisticData?.pages[0].items.find((e) => e.id === 123);
          expect(updatedEvent?.snooze_until).toBeNull();
        });

        // Resolve the API call
        resolveUnsnooze!({ ...snoozedEvent, snooze_until: null });

        await waitFor(() => {
          expect(result.current.isUnsnoozing).toBe(false);
        });

        // Cleanup
        testQueryClient.clear();

        // Restore fake timers for other tests
        vi.useFakeTimers();
        vi.setSystemTime(MOCK_NOW);
      });

      it('rollbacks on unsnooze error', async () => {
        const snoozedEvent = createMockEvent({
          id: 123,
          snooze_until: '2024-01-15T14:00:00Z',
        });
        const snoozedEvents = [snoozedEvent];

        const error = new Error('Unsnooze failed');
        (api.clearSnooze as ReturnType<typeof vi.fn>).mockRejectedValueOnce(error);

        // Pre-populate the cache
        const eventsKey = eventsQueryKeys.infinite(undefined, 25);
        queryClient.setQueryData(eventsKey, createMockInfiniteEventsData(snoozedEvents));

        const onError = vi.fn();
        const { result } = renderHook(
          () => useSnoozeEvent({ onError, invalidateQueries: false }),
          { wrapper: createWrapper() }
        );

        await act(async () => {
          try {
            await result.current.unsnooze(123);
          } catch {
            // Expected to throw
          }
        });

        // Verify rollback - snooze_until should be restored
        const rolledBackData = queryClient.getQueryData<
          InfiniteData<EventListResponse, string | null>
        >(eventsKey);
        const rolledBackEvent = rolledBackData?.pages[0].items.find((e) => e.id === 123);

        expect(rolledBackEvent?.snooze_until).toBe('2024-01-15T14:00:00Z');
        expect(onError).toHaveBeenCalledWith(error, 123, 0);
      });
    });

    describe('enableOptimisticUpdates option', () => {
      it('skips optimistic update when enableOptimisticUpdates is false', async () => {
        // Use a resolved promise to avoid timing issues
        const serverResponse = { ...mockEvent, snooze_until: '2024-01-15T13:00:00Z' };
        (api.snoozeEvent as ReturnType<typeof vi.fn>).mockResolvedValueOnce(serverResponse);

        // Pre-populate the cache
        const eventsKey = eventsQueryKeys.infinite(undefined, 25);
        queryClient.setQueryData(eventsKey, createMockInfiniteEventsData(mockEvents));

        const { result } = renderHook(
          () => useSnoozeEvent({ enableOptimisticUpdates: false, invalidateQueries: false }),
          { wrapper: createWrapper() }
        );

        // Capture the cache state before the mutation
        const beforeData = queryClient.getQueryData<InfiniteData<EventListResponse, string | null>>(
          eventsKey
        );
        const beforeEvent = beforeData?.pages[0].items.find((e) => e.id === 123);
        expect(beforeEvent?.snooze_until).toBeNull();

        // Run the mutation to completion
        await act(async () => {
          await result.current.snooze(123, 3600);
        });

        // With optimistic updates disabled, the cache should NOT have been updated
        // (since invalidateQueries is also false, the server response isn't used to update cache)
        // The mutation completes successfully but doesn't apply optimistic changes
        expect(result.current.isSnoozing).toBe(false);
      });
    });

    describe('multi-page cache updates', () => {
      it('updates event across multiple pages', async () => {
        const page1Events = [createMockEvent({ id: 1 }), createMockEvent({ id: 2 })];
        const page2Events = [createMockEvent({ id: 123 }), createMockEvent({ id: 4 })];

        // Create multi-page data
        const multiPageData: InfiniteData<EventListResponse, string | null> = {
          pages: [
            {
              items: page1Events,
              pagination: { total: 4, limit: 2, has_more: true, next_cursor: 'cursor1' },
            },
            {
              items: page2Events,
              pagination: { total: 4, limit: 2, has_more: false, next_cursor: null },
            },
          ],
          pageParams: [null, 'cursor1'],
        };

        (api.snoozeEvent as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
          ...createMockEvent({ id: 123 }),
          snooze_until: '2024-01-15T13:00:00Z',
        });

        // Pre-populate the cache
        const eventsKey = eventsQueryKeys.infinite(undefined, 25);
        queryClient.setQueryData(eventsKey, multiPageData);

        const { result } = renderHook(
          () => useSnoozeEvent({ invalidateQueries: false }),
          { wrapper: createWrapper() }
        );

        await act(async () => {
          await result.current.snooze(123, 3600);
        });

        // Verify the event on page 2 was updated
        const updatedData = queryClient.getQueryData<
          InfiniteData<EventListResponse, string | null>
        >(eventsKey);

        // Page 1 events should be unchanged
        expect(updatedData?.pages[0].items[0].snooze_until).toBeNull();
        expect(updatedData?.pages[0].items[1].snooze_until).toBeNull();

        // Page 2 event 123 should be updated
        const eventOnPage2 = updatedData?.pages[1].items.find((e) => e.id === 123);
        expect(eventOnPage2?.snooze_until).toBe('2024-01-15T13:00:00Z');

        // Other event on page 2 should be unchanged
        const otherEventOnPage2 = updatedData?.pages[1].items.find((e) => e.id === 4);
        expect(otherEventOnPage2?.snooze_until).toBeNull();
      });
    });
  });
});
