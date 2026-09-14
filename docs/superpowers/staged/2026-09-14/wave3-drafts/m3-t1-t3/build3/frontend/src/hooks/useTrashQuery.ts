/**
 * useTrashQuery - TanStack Query hooks for trash (soft-deleted events) management
 *
 * This module provides hooks for fetching and managing soft-deleted events:
 * - useDeletedEventsQuery: Fetch all soft-deleted events
 * - useRestoreEventMutation: Restore a soft-deleted event
 * - usePermanentDeleteMutation: Permanently delete an event
 *
 * Benefits:
 * - Automatic cache management
 * - Optimistic updates support
 * - Built-in loading and error states
 *
 * @module hooks/useTrashQuery
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchDeletedEvents,
  restoreEvent,
  permanentlyDeleteEvent,
  type DeletedEvent,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

/**
 * Query key for deleted events.
 * Defined here to avoid dependency on queryKeys being updated.
 */
export const DELETED_EVENTS_QUERY_KEY = ['events', 'deleted'] as const;

// ============================================================================
// useDeletedEventsQuery - Fetch all soft-deleted events
// ============================================================================

/**
 * Options for configuring the useDeletedEventsQuery hook
 */
export interface UseDeletedEventsQueryOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default false
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useDeletedEventsQuery hook
 */
export interface UseDeletedEventsQueryReturn {
  /** List of soft-deleted events, empty array if not yet fetched */
  deletedEvents: DeletedEvent[];
  /** Total count of deleted events */
  total: number;
  /** Whether the trash is empty (no deleted events) */
  isEmpty: boolean;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch all soft-deleted events using TanStack Query.
 *
 * @param options - Configuration options
 * @returns Deleted events list and query state
 *
 * @example
 * ```tsx
 * const { deletedEvents, isLoading, isEmpty } = useDeletedEventsQuery();
 *
 * if (isLoading) return <Spinner />;
 * if (isEmpty) return <EmptyState title="Trash is empty" />;
 *
 * return (
 *   <ul>
 *     {deletedEvents.map(event => (
 *       <DeletedEventCard key={event.id} event={event} />
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useDeletedEventsQuery(
  options: UseDeletedEventsQueryOptions = {}
): UseDeletedEventsQueryReturn {
  const { enabled = true, refetchInterval = false, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: DELETED_EVENTS_QUERY_KEY,
    queryFn: fetchDeletedEvents,
    enabled,
    refetchInterval,
    staleTime,
    retry: 1,
  });

  // Provide empty array as default to avoid null checks
  const deletedEvents = useMemo(() => query.data?.events ?? [], [query.data]);
  const total = query.data?.total ?? 0;
  const isEmpty = deletedEvents.length === 0 && !query.isLoading;

  return {
    deletedEvents,
    total,
    isEmpty,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useRestoreEventMutation - Restore a soft-deleted event
// ============================================================================

/**
 * Return type for the useRestoreEventMutation hook
 */
export interface UseRestoreEventMutationReturn {
  /** Execute the restore mutation */
  mutateAsync: (eventId: number) => Promise<void>;
  /** Synchronous mutation trigger */
  mutate: (eventId: number) => void;
  /** Whether the mutation is in progress */
  isPending: boolean;
  /** Error object if the mutation failed */
  error: Error | null;
  /** Reset mutation state */
  reset: () => void;
}

/**
 * Hook providing a mutation to restore a soft-deleted event.
 *
 * Restoring an event removes it from trash and makes it visible again.
 * Automatically invalidates the deleted events cache on success.
 *
 * @returns Mutation object for restoring events
 *
 * @example
 * ```tsx
 * const { mutateAsync, isPending } = useRestoreEventMutation();
 *
 * const handleRestore = async (eventId: number) => {
 *   try {
 *     await mutateAsync(eventId);
 *     toast.success('Event restored');
 *   } catch (error) {
 *     toast.error('Failed to restore event');
 *   }
 * };
 * ```
 */
export function useRestoreEventMutation(): UseRestoreEventMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (eventId: number) => restoreEvent(eventId),
    onSuccess: () => {
      // Invalidate deleted events to remove the restored event from trash
      void queryClient.invalidateQueries({ queryKey: DELETED_EVENTS_QUERY_KEY });
      // Also invalidate the main events list to show the restored event
      void queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
    },
  });

  return {
    mutateAsync: async (eventId: number) => {
      await mutation.mutateAsync(eventId);
    },
    mutate: mutation.mutate,
    isPending: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset,
  };
}

// ============================================================================
// usePermanentDeleteMutation - Permanently delete an event
// ============================================================================

/**
 * Return type for the usePermanentDeleteMutation hook
 */
export interface UsePermanentDeleteMutationReturn {
  /** Execute the permanent delete mutation */
  mutateAsync: (eventId: number) => Promise<void>;
  /** Synchronous mutation trigger */
  mutate: (eventId: number) => void;
  /** Whether the mutation is in progress */
  isPending: boolean;
  /** Error object if the mutation failed */
  error: Error | null;
  /** Reset mutation state */
  reset: () => void;
}

/**
 * Hook providing a mutation to permanently delete an event.
 *
 * This action cannot be undone - the event and all associated data are removed.
 * Automatically invalidates the deleted events cache on success.
 *
 * @returns Mutation object for permanent deletion
 *
 * @example
 * ```tsx
 * const { mutateAsync, isPending } = usePermanentDeleteMutation();
 *
 * const handlePermanentDelete = async (eventId: number) => {
 *   if (!confirm('This cannot be undone. Are you sure?')) return;
 *
 *   try {
 *     await mutateAsync(eventId);
 *     toast.success('Event permanently deleted');
 *   } catch (error) {
 *     toast.error('Failed to delete event');
 *   }
 * };
 * ```
 */
export function usePermanentDeleteMutation(): UsePermanentDeleteMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (eventId: number) => permanentlyDeleteEvent(eventId),
    onSuccess: () => {
      // Invalidate deleted events to remove the deleted event from trash
      void queryClient.invalidateQueries({ queryKey: DELETED_EVENTS_QUERY_KEY });
    },
  });

  return {
    mutateAsync: async (eventId: number) => {
      await mutation.mutateAsync(eventId);
    },
    mutate: mutation.mutate,
    isPending: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset,
  };
}
