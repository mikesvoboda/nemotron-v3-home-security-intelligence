/**
 * React Query hook for fetching audit logs with cursor-based pagination.
 *
 * Uses the generic createInfiniteQueryHook factory to reduce boilerplate
 * while maintaining full type safety.
 */

import { createInfiniteQueryHook, type BaseInfiniteQueryOptions } from './useCursorPaginatedQuery';
import { fetchAuditLogs, type AuditLogsQueryParams } from '../services/api';

import type { AuditLogListResponse } from '../types/generated';

export interface AuditLogFilters {
  /** Filter by action type */
  action?: string;
  /** Filter by resource type */
  resource_type?: string;
  /** Filter by resource ID */
  resource_id?: string;
  /** Filter by actor */
  actor?: string;
  /** Filter by status (success/failure) */
  status?: string;
  /** Filter from date (ISO format) */
  start_date?: string;
  /** Filter to date (ISO format) */
  end_date?: string;
}

export interface UseAuditLogsInfiniteQueryOptions extends BaseInfiniteQueryOptions {
  filters?: AuditLogFilters;
}

/**
 * Return type for useAuditLogsInfiniteQuery.
 * Maintains backwards compatibility by using 'logs' instead of 'items'.
 */
export interface UseAuditLogsInfiniteQueryReturn {
  logs: AuditLogListResponse['items'];
  pages: AuditLogListResponse[] | undefined;
  totalCount: number;
  isLoading: boolean;
  isFetching: boolean;
  isFetchingNextPage: boolean;
  hasNextPage: boolean;
  fetchNextPage: () => void;
  error: Error | null;
  isError: boolean;
  refetch: () => void;
}

export const auditLogsQueryKeys = {
  all: ['auditLogs'] as const,
  lists: () => [...auditLogsQueryKeys.all, 'list'] as const,
  list: (filters?: AuditLogFilters) => [...auditLogsQueryKeys.lists(), filters] as const,
  infinite: (filters?: AuditLogFilters, limit?: number) =>
    [...auditLogsQueryKeys.all, 'infinite', { filters, limit }] as const,
};

/**
 * Internal hook created by factory function.
 * Returns the standardized InfiniteQueryHookReturn interface.
 */
const useAuditLogsInfiniteQueryInternal = createInfiniteQueryHook<
  AuditLogListResponse,
  AuditLogListResponse['items'][number],
  UseAuditLogsInfiniteQueryOptions,
  AuditLogFilters
>({
  getQueryKey: (options) => auditLogsQueryKeys.infinite(options.filters, options.limit),
  fetchFn: ({ cursor, limit, filters }) => {
    const params: AuditLogsQueryParams = {
      ...filters,
      limit,
      cursor,
      // Only request total count on first page (no cursor) to display "X of Y results"
      // Subsequent pages don't need total count recalculated for performance
      // NEM-3275: Explicitly set to true (not just truthy) to ensure correct handling
      include_total_count: cursor ? false : true,
    };
    return fetchAuditLogs(params);
  },
  getFilters: (options) => options.filters,
  defaultRetry: 1, // Default to 1 retry for faster failure feedback in list views
  defaultMaxPages: 10, // Limit stored pages for bounded memory (NEM-3362)
});

/**
 * Hook for fetching audit logs with cursor-based infinite pagination.
 *
 * Wraps the factory-generated hook to maintain backwards compatibility
 * by renaming 'items' to 'logs' in the return type.
 *
 * @param options - Query options including filters, limit, and React Query options
 * @returns Audit logs data with pagination controls and query state
 *
 * @example
 * ```tsx
 * const { logs, isLoading, hasNextPage, fetchNextPage } = useAuditLogsInfiniteQuery({
 *   filters: { action: 'acknowledge', status: 'success' },
 *   limit: 50,
 * });
 * ```
 */
export function useAuditLogsInfiniteQuery(
  options: UseAuditLogsInfiniteQueryOptions = {}
): UseAuditLogsInfiniteQueryReturn {
  const result = useAuditLogsInfiniteQueryInternal(options);

  // Rename 'items' to 'logs' for backwards compatibility
  return {
    logs: result.items,
    pages: result.pages,
    totalCount: result.totalCount,
    isLoading: result.isLoading,
    isFetching: result.isFetching,
    isFetchingNextPage: result.isFetchingNextPage,
    hasNextPage: result.hasNextPage,
    fetchNextPage: result.fetchNextPage,
    error: result.error,
    isError: result.isError,
    refetch: result.refetch,
  };
}

export default useAuditLogsInfiniteQuery;
