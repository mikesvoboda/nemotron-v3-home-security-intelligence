/**
 * useNotificationHistoryQuery - TanStack Query hook for notification delivery history
 *
 * This module provides a hook for fetching notification delivery history with
 * support for filtering and pagination.
 *
 * @module hooks/useNotificationHistoryQuery
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useCallback } from 'react';

import {
  fetchNotificationHistory,
  type NotificationHistoryEntry,
  type NotificationHistoryResponse,
  type NotificationHistoryQueryParams,
  type NotificationChannel,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// Re-export types for consumers
export type {
  NotificationHistoryEntry,
  NotificationHistoryResponse,
  NotificationHistoryQueryParams,
  NotificationChannel,
};

// ============================================================================
// useNotificationHistoryQuery - Notification delivery history
// ============================================================================

/**
 * Filter options for notification history queries.
 */
export interface NotificationHistoryFilters {
  /** Filter by alert ID */
  alertId?: string;
  /** Filter by notification channel */
  channel?: NotificationChannel;
  /** Filter by success status */
  success?: boolean;
}

/**
 * Options for configuring the useNotificationHistoryQuery hook.
 */
export interface UseNotificationHistoryQueryOptions {
  /**
   * Optional filters for the query.
   */
  filters?: NotificationHistoryFilters;

  /**
   * Maximum number of results per page.
   * @default 50
   */
  limit?: number;

  /**
   * Page number (zero-indexed).
   * @default 0
   */
  page?: number;

  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useNotificationHistoryQuery hook.
 */
export interface UseNotificationHistoryQueryReturn {
  /** List of notification history entries */
  entries: NotificationHistoryEntry[];
  /** Total count of entries matching filters */
  totalCount: number;
  /** Current page number (zero-indexed) */
  page: number;
  /** Total number of pages */
  totalPages: number;
  /** Whether there are more pages */
  hasNextPage: boolean;
  /** Whether there is a previous page */
  hasPreviousPage: boolean;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Function to invalidate the history cache */
  invalidate: () => Promise<void>;
}

/**
 * Hook to fetch notification delivery history with filtering and pagination.
 *
 * @param options - Configuration options including filters and pagination
 * @returns History data, query state, and helper functions
 *
 * @example
 * ```tsx
 * // Basic usage - fetch all history
 * const { entries, isLoading, totalCount } = useNotificationHistoryQuery();
 *
 * // With filters - fetch failed webhook notifications
 * const { entries, isLoading } = useNotificationHistoryQuery({
 *   filters: { channel: 'webhook', success: false }
 * });
 *
 * // With pagination
 * const { entries, page, totalPages, hasNextPage } = useNotificationHistoryQuery({
 *   limit: 10,
 *   page: currentPage,
 * });
 *
 * // Filter by alert
 * const { entries } = useNotificationHistoryQuery({
 *   filters: { alertId: 'alert-123' }
 * });
 * ```
 */
export function useNotificationHistoryQuery(
  options: UseNotificationHistoryQueryOptions = {}
): UseNotificationHistoryQueryReturn {
  const {
    filters,
    limit = 50,
    page = 0,
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  const queryClient = useQueryClient();

  // Build query parameters
  const queryParams: NotificationHistoryQueryParams = useMemo(() => {
    const params: NotificationHistoryQueryParams = {
      limit,
      offset: page * limit,
    };

    if (filters?.alertId) {
      params.alert_id = filters.alertId;
    }
    if (filters?.channel) {
      params.channel = filters.channel;
    }
    if (filters?.success !== undefined) {
      params.success = filters.success;
    }

    return params;
  }, [filters, limit, page]);

  // Build query key filters for cache management
  const queryKeyFilters = useMemo(
    () =>
      filters
        ? {
            alert_id: filters.alertId,
            channel: filters.channel,
            success: filters.success,
          }
        : undefined,
    [filters]
  );

  const query = useQuery({
    queryKey: queryKeys.notifications.history.list(queryKeyFilters),
    queryFn: () => fetchNotificationHistory(queryParams),
    enabled,
    staleTime,
    retry: 1,
  });

  // Derived values
  const entries = useMemo(() => query.data?.entries ?? [], [query.data?.entries]);
  const totalCount = useMemo(() => query.data?.count ?? 0, [query.data?.count]);
  const totalPages = useMemo(() => Math.ceil(totalCount / limit) || 1, [totalCount, limit]);
  const hasNextPage = useMemo(() => page < totalPages - 1, [page, totalPages]);
  const hasPreviousPage = useMemo(() => page > 0, [page]);

  // Invalidate cache function
  const invalidate = useCallback(async () => {
    await queryClient.invalidateQueries({
      queryKey: queryKeys.notifications.history.all,
    });
  }, [queryClient]);

  return {
    entries,
    totalCount,
    page,
    totalPages,
    hasNextPage,
    hasPreviousPage,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
    invalidate,
  };
}

// Export default for convenience
export default useNotificationHistoryQuery;
