/**
 * Hook for snoozing events/alerts (NEM-2360, NEM-2361, NEM-5011).
 *
 * Provides a mutation function to snooze an event by setting snooze_until
 * to a timestamp in the future, with optimistic updates for instant UI feedback.
 *
 * Optimistic update flow:
 * 1. Cancel outgoing refetches to prevent race conditions
 * 2. Snapshot previous data for rollback
 * 3. Apply optimistic update immediately (mark event as snoozed)
 * 4. On error: rollback to snapshot
 * 5. On success: replace optimistic data with server response
 * 6. On settled: invalidate queries for consistency
 */
import { useMutation, type QueryClient, type InfiniteData } from '@tanstack/react-query';

import { alertsQueryKeys } from './useAlertsQuery';
import { eventsQueryKeys } from './useEventsQuery';
import { clearSnooze, snoozeEvent } from '../services/api';

import type { Event, EventListResponse } from '../services/api';

export interface UseSnoozeEventOptions {
  /** Callback when snooze succeeds */
  onSuccess?: (event: Event, eventId: number, seconds: number) => void;
  /** Callback when snooze fails */
  onError?: (error: Error, eventId: number, seconds: number) => void;
  /** Whether to invalidate queries on success (default: true) */
  invalidateQueries?: boolean;
  /** Whether to enable optimistic updates (default: true) */
  enableOptimisticUpdates?: boolean;
}

// =============================================================================
// Optimistic Update Helpers
// =============================================================================

/**
 * Type for infinite query data structure used by events and alerts queries.
 */
type InfiniteEventData = InfiniteData<EventListResponse, string | null>;

/**
 * Helper to cancel outgoing queries for both events and alerts.
 */
async function cancelSnoozeQueries(client: QueryClient): Promise<void> {
  await Promise.all([
    client.cancelQueries({ queryKey: eventsQueryKeys.all }),
    client.cancelQueries({ queryKey: alertsQueryKeys.all }),
  ]);
}

/**
 * Helper to snapshot infinite query data for rollback.
 * Returns a Map of query key hashes to their data.
 *
 * Note: We don't filter by 'active' type to ensure we capture all cached data,
 * including queries that may not have active subscribers during the mutation.
 */
function snapshotInfiniteQueries(
  client: QueryClient,
  queryKey: readonly unknown[]
): Map<string, InfiniteEventData | undefined> {
  const cache = client.getQueryCache();
  const queries = cache.findAll({ queryKey });
  const snapshot = new Map<string, InfiniteEventData | undefined>();

  for (const query of queries) {
    const keyHash = JSON.stringify(query.queryKey);
    snapshot.set(keyHash, client.getQueryData<InfiniteEventData>(query.queryKey));
  }

  return snapshot;
}

/**
 * Helper to apply optimistic update to infinite query data.
 * Updates the event's snooze_until field across all pages.
 *
 * Note: We don't filter by 'active' type to ensure we update all cached data,
 * including queries that may not have active subscribers during the mutation.
 */
function applyOptimisticSnoozeUpdate(
  client: QueryClient,
  queryKey: readonly unknown[],
  eventId: number,
  snoozeUntil: string | null
): void {
  const cache = client.getQueryCache();
  const queries = cache.findAll({ queryKey });

  for (const query of queries) {
    client.setQueryData<InfiniteEventData>(query.queryKey, (oldData) => {
      if (!oldData?.pages) return oldData;

      return {
        ...oldData,
        pages: oldData.pages.map((page) => ({
          ...page,
          items: page.items.map((event) =>
            event.id === eventId ? { ...event, snooze_until: snoozeUntil } : event
          ),
        })),
      };
    });
  }
}

/**
 * Helper to rollback infinite query data from a snapshot.
 */
function rollbackInfiniteQueries(
  client: QueryClient,
  snapshot: Map<string, InfiniteEventData | undefined>
): void {
  for (const [keyHash, data] of snapshot) {
    if (data !== undefined) {
      const queryKey = JSON.parse(keyHash) as readonly unknown[];
      client.setQueryData(queryKey, data);
    }
  }
}

export interface UseSnoozeEventReturn {
  /** Snooze an event for the specified duration */
  snooze: (eventId: number, seconds: number) => Promise<Event>;
  /** Clear snooze on an event */
  unsnooze: (eventId: number) => Promise<Event>;
  /** Whether a snooze operation is in progress */
  isSnoozing: boolean;
  /** Whether an unsnooze operation is in progress */
  isUnsnoozing: boolean;
  /** Error from the last operation */
  error: Error | null;
  /** Reset the error state */
  reset: () => void;
}

/**
 * Hook for snoozing and unsnoozing events.
 *
 * Supports optimistic updates for instant UI feedback (NEM-5011).
 * Uses TanStack Query v5 context.client pattern for QueryClient access.
 *
 * @example
 * ```tsx
 * const { snooze, isSnoozing } = useSnoozeEvent({
 *   onSuccess: (event) => toast.success(`Snoozed until ${event.snooze_until}`),
 * });
 *
 * // Snooze for 1 hour (3600 seconds)
 * await snooze(eventId, 3600);
 * ```
 */
export function useSnoozeEvent(options: UseSnoozeEventOptions = {}): UseSnoozeEventReturn {
  const {
    onSuccess,
    onError,
    invalidateQueries = true,
    enableOptimisticUpdates = true,
  } = options;

  const snoozeMutation = useMutation({
    mutationFn: ({ eventId, seconds }: { eventId: number; seconds: number }) =>
      snoozeEvent(eventId, seconds),

    onMutate: async ({ eventId, seconds }, { client }) => {
      if (!enableOptimisticUpdates) {
        return {
          previousEventsData: new Map<string, InfiniteEventData | undefined>(),
          previousAlertsData: new Map<string, InfiniteEventData | undefined>(),
        };
      }

      // 1. Cancel outgoing refetches to prevent race conditions
      await cancelSnoozeQueries(client);

      // 2. Snapshot previous data for rollback
      const previousEventsData = snapshotInfiniteQueries(client, eventsQueryKeys.all);
      const previousAlertsData = snapshotInfiniteQueries(client, alertsQueryKeys.all);

      // 3. Calculate optimistic snooze_until timestamp
      const snoozeUntil = new Date(Date.now() + seconds * 1000).toISOString();

      // 4. Apply optimistic update to both events and alerts caches
      applyOptimisticSnoozeUpdate(client, eventsQueryKeys.all, eventId, snoozeUntil);
      applyOptimisticSnoozeUpdate(client, alertsQueryKeys.all, eventId, snoozeUntil);

      return { previousEventsData, previousAlertsData };
    },

    onError: (error: unknown, { eventId, seconds }, context, { client }) => {
      // 4. On error: rollback to snapshot
      if (context && enableOptimisticUpdates) {
        rollbackInfiniteQueries(client, context.previousEventsData);
        rollbackInfiniteQueries(client, context.previousAlertsData);
      }
      onError?.(error instanceof Error ? error : new Error(String(error)), eventId, seconds);
    },

    onSuccess: (data, { eventId, seconds }, _context, { client }) => {
      // 5. On success: update cache with actual server response
      if (enableOptimisticUpdates) {
        applyOptimisticSnoozeUpdate(client, eventsQueryKeys.all, eventId, data.snooze_until ?? null);
        applyOptimisticSnoozeUpdate(client, alertsQueryKeys.all, eventId, data.snooze_until ?? null);
      }
      onSuccess?.(data, eventId, seconds);
    },

    onSettled: (_data, _error, _variables, _context, { client }) => {
      // 6. On settled: invalidate queries for consistency
      if (invalidateQueries) {
        void client.invalidateQueries({ queryKey: alertsQueryKeys.all });
        void client.invalidateQueries({ queryKey: eventsQueryKeys.all });
      }
    },
  });

  const unsnoozeMutation = useMutation({
    mutationFn: (eventId: number) => clearSnooze(eventId),

    onMutate: async (eventId, { client }) => {
      if (!enableOptimisticUpdates) {
        return {
          previousEventsData: new Map<string, InfiniteEventData | undefined>(),
          previousAlertsData: new Map<string, InfiniteEventData | undefined>(),
        };
      }

      // 1. Cancel outgoing refetches
      await cancelSnoozeQueries(client);

      // 2. Snapshot previous data for rollback
      const previousEventsData = snapshotInfiniteQueries(client, eventsQueryKeys.all);
      const previousAlertsData = snapshotInfiniteQueries(client, alertsQueryKeys.all);

      // 3. Apply optimistic update (clear snooze)
      applyOptimisticSnoozeUpdate(client, eventsQueryKeys.all, eventId, null);
      applyOptimisticSnoozeUpdate(client, alertsQueryKeys.all, eventId, null);

      return { previousEventsData, previousAlertsData };
    },

    onError: (error: unknown, eventId, context, { client }) => {
      // 4. On error: rollback to snapshot
      if (context && enableOptimisticUpdates) {
        rollbackInfiniteQueries(client, context.previousEventsData);
        rollbackInfiniteQueries(client, context.previousAlertsData);
      }
      onError?.(error instanceof Error ? error : new Error(String(error)), eventId, 0);
    },

    onSuccess: (data, eventId, _context, { client }) => {
      // 5. On success: update cache with actual server response
      if (enableOptimisticUpdates) {
        applyOptimisticSnoozeUpdate(client, eventsQueryKeys.all, eventId, data.snooze_until ?? null);
        applyOptimisticSnoozeUpdate(client, alertsQueryKeys.all, eventId, data.snooze_until ?? null);
      }
      // For unsnooze, pass 0 seconds to indicate clearing
      onSuccess?.(data, eventId, 0);
    },

    onSettled: (_data, _error, _variables, _context, { client }) => {
      // 6. On settled: invalidate queries for consistency
      if (invalidateQueries) {
        void client.invalidateQueries({ queryKey: alertsQueryKeys.all });
        void client.invalidateQueries({ queryKey: eventsQueryKeys.all });
      }
    },
  });

  // Cast error to Error | null for type safety
  const error = (snoozeMutation.error ?? unsnoozeMutation.error) as Error | null;

  return {
    snooze: (eventId: number, seconds: number) => snoozeMutation.mutateAsync({ eventId, seconds }),
    unsnooze: (eventId: number) => unsnoozeMutation.mutateAsync(eventId),
    isSnoozing: snoozeMutation.isPending,
    isUnsnoozing: unsnoozeMutation.isPending,
    error,
    reset: () => {
      snoozeMutation.reset();
      unsnoozeMutation.reset();
    },
  };
}

export default useSnoozeEvent;
