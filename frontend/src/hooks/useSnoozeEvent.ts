/**
 * Hook for snoozing events/alerts (NEM-2360, NEM-2361).
 *
 * Provides a mutation function to snooze an event by setting snooze_until
 * to a timestamp in the future, and optionally invalidates related queries.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { alertsQueryKeys } from './useAlertsQuery';
import { eventsQueryKeys } from './useEventsQuery';
import { clearSnooze, snoozeEvent } from '../services/api';

import type { Event } from '../services/api';

export interface UseSnoozeEventOptions {
  /** Callback when snooze succeeds */
  onSuccess?: (event: Event, eventId: number, seconds: number) => void;
  /** Callback when snooze fails */
  onError?: (error: Error, eventId: number, seconds: number) => void;
  /** Whether to invalidate queries on success (default: true) */
  invalidateQueries?: boolean;
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
  const { onSuccess, onError, invalidateQueries = true } = options;
  const queryClient = useQueryClient();

  const snoozeMutation = useMutation({
    mutationFn: ({ eventId, seconds }: { eventId: number; seconds: number }) =>
      snoozeEvent(eventId, seconds),
    onSuccess: (data, { eventId, seconds }) => {
      if (invalidateQueries) {
        // Invalidate alerts and events queries to reflect the snooze
        void queryClient.invalidateQueries({ queryKey: alertsQueryKeys.all });
        void queryClient.invalidateQueries({ queryKey: eventsQueryKeys.all });
      }
      onSuccess?.(data, eventId, seconds);
    },
    onError: (error: unknown, { eventId, seconds }) => {
      onError?.(error instanceof Error ? error : new Error(String(error)), eventId, seconds);
    },
  });

  const unsnoozeMutation = useMutation({
    mutationFn: (eventId: number) => clearSnooze(eventId),
    onSuccess: (data, eventId) => {
      if (invalidateQueries) {
        void queryClient.invalidateQueries({ queryKey: alertsQueryKeys.all });
        void queryClient.invalidateQueries({ queryKey: eventsQueryKeys.all });
      }
      // For unsnooze, pass 0 seconds to indicate clearing
      onSuccess?.(data, eventId, 0);
    },
    onError: (error: unknown, eventId) => {
      onError?.(error instanceof Error ? error : new Error(String(error)), eventId, 0);
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
