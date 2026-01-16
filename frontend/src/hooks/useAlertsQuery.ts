/**
 * useAlertsQuery - React Query hook for fetching high and critical risk alerts
 *
 * This hook provides cursor-based pagination for alerts (high + critical events)
 * using TanStack Query's useInfiniteQuery. It fetches both risk levels in parallel
 * and merges them client-side for optimal performance.
 *
 * @module hooks/useAlertsQuery
 */

import { useInfiniteQuery, type InfiniteData, type QueryKey } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchEvents, type EventListResponse, type Event } from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Risk filter options for alerts - only high and critical
 */
export type AlertRiskFilter = 'all' | 'high' | 'critical';

/**
 * Options for configuring the useAlertsInfiniteQuery hook
 */
export interface UseAlertsInfiniteQueryOptions {
  /**
   * Filter by risk level ('all', 'high', or 'critical')
   * @default 'all'
   */
  riskFilter?: AlertRiskFilter;

  /**
   * Maximum number of results per page
   * @default 25
   */
  limit?: number;

  /**
   * Whether to enable the query
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds
   * @default false (no auto-refetch)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds
   * @default DEFAULT_STALE_TIME
   */
  staleTime?: number;
}

/**
 * Return type for the useAlertsInfiniteQuery hook
 */
export interface UseAlertsInfiniteQueryReturn {
  /** All alerts from all loaded pages, sorted by timestamp (newest first) */
  alerts: Event[];

  /** Total count of alerts across both risk levels */
  totalCount: number;

  /** Whether the initial fetch is in progress */
  isLoading: boolean;

  /** Whether any fetch is in progress (including background refetch) */
  isFetching: boolean;

  /** Whether the next page is being fetched */
  isFetchingNextPage: boolean;

  /** Whether there are more alerts to load */
  hasNextPage: boolean;

  /** Function to fetch the next page of alerts */
  fetchNextPage: () => void;

  /** Error object if the query failed */
  error: Error | null;

  /** Whether the query has errored */
  isError: boolean;

  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

// ============================================================================
// Query Key Factory
// ============================================================================

export const alertsQueryKeys = {
  all: ['alerts'] as const,
  infinite: (riskLevel: 'high' | 'critical', limit: number) =>
    [...alertsQueryKeys.all, 'infinite', { riskLevel, limit }] as const,
};

// ============================================================================
// Internal Hook for Single Risk Level
// ============================================================================

interface UseSingleRiskQueryOptions {
  riskLevel: 'high' | 'critical';
  limit: number;
  enabled: boolean;
  refetchInterval: number | false;
  staleTime: number;
}

interface UseSingleRiskQueryReturn {
  events: Event[];
  totalCount: number;
  isLoading: boolean;
  isFetching: boolean;
  isFetchingNextPage: boolean;
  hasNextPage: boolean;
  fetchNextPage: () => void;
  error: Error | null;
  isError: boolean;
  refetch: () => Promise<unknown>;
}

function useSingleRiskQuery(options: UseSingleRiskQueryOptions): UseSingleRiskQueryReturn {
  const { riskLevel, limit, enabled, refetchInterval, staleTime } = options;

  const queryKey = alertsQueryKeys.infinite(riskLevel, limit);

  const query = useInfiniteQuery<
    EventListResponse,
    Error,
    InfiniteData<EventListResponse, string | null>,
    QueryKey,
    string | null
  >({
    queryKey,
    queryFn: async ({ pageParam }) => {
      return fetchEvents({
        risk_level: riskLevel,
        limit,
        cursor: pageParam ?? undefined,
      });
    },
    initialPageParam: null,
    getNextPageParam: (lastPage) => {
      if (lastPage.pagination.has_more && lastPage.pagination.next_cursor) {
        return lastPage.pagination.next_cursor;
      }
      return undefined;
    },
    enabled,
    refetchInterval,
    staleTime,
  });

  const events = useMemo(() => {
    if (!query.data?.pages) {
      return [];
    }
    return query.data.pages.flatMap((page) => page.items);
  }, [query.data?.pages]);

  const totalCount = useMemo(() => {
    if (!query.data?.pages?.[0]) {
      return 0;
    }
    return query.data.pages[0].pagination.total;
  }, [query.data?.pages]);

  const handleFetchNextPage = (): void => {
    void query.fetchNextPage();
  };

  return {
    events,
    totalCount,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isFetchingNextPage: query.isFetchingNextPage,
    hasNextPage: query.hasNextPage ?? false,
    fetchNextPage: handleFetchNextPage,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}

// ============================================================================
// Main Hook Implementation
// ============================================================================

/**
 * Hook to fetch high and critical risk alerts with infinite scroll support.
 *
 * Fetches both high and critical risk events using parallel queries,
 * then merges and sorts them client-side by timestamp (newest first).
 *
 * @param options - Configuration options
 * @returns Merged alerts data and query state
 *
 * @example
 * ```tsx
 * const {
 *   alerts,
 *   totalCount,
 *   isLoading,
 *   hasNextPage,
 *   fetchNextPage,
 * } = useAlertsInfiniteQuery({ riskFilter: 'all', limit: 25 });
 * ```
 */
export function useAlertsInfiniteQuery(
  options: UseAlertsInfiniteQueryOptions = {}
): UseAlertsInfiniteQueryReturn {
  const {
    riskFilter = 'all',
    limit = 25,
    enabled = true,
    refetchInterval = false,
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  // Determine which queries to run based on filter
  const fetchHigh = riskFilter === 'all' || riskFilter === 'high';
  const fetchCritical = riskFilter === 'all' || riskFilter === 'critical';

  // Fetch high risk alerts
  const highQuery = useSingleRiskQuery({
    riskLevel: 'high',
    limit,
    enabled: enabled && fetchHigh,
    refetchInterval,
    staleTime,
  });

  // Fetch critical risk alerts
  const criticalQuery = useSingleRiskQuery({
    riskLevel: 'critical',
    limit,
    enabled: enabled && fetchCritical,
    refetchInterval,
    staleTime,
  });

  // Merge and sort alerts from both queries
  const alerts = useMemo(() => {
    const allAlerts: Event[] = [];

    if (fetchHigh) {
      allAlerts.push(...highQuery.events);
    }

    if (fetchCritical) {
      allAlerts.push(...criticalQuery.events);
    }

    // Remove duplicates by ID and sort by timestamp (newest first)
    const uniqueAlerts = Array.from(new Map(allAlerts.map((alert) => [alert.id, alert])).values());

    return uniqueAlerts.sort((a, b) => {
      const dateA = new Date(a.started_at).getTime();
      const dateB = new Date(b.started_at).getTime();
      return dateB - dateA;
    });
  }, [highQuery.events, criticalQuery.events, fetchHigh, fetchCritical]);

  // Calculate total count
  const totalCount = useMemo(() => {
    let total = 0;
    if (fetchHigh) {
      total += highQuery.totalCount;
    }
    if (fetchCritical) {
      total += criticalQuery.totalCount;
    }
    return total;
  }, [highQuery.totalCount, criticalQuery.totalCount, fetchHigh, fetchCritical]);

  // Combine loading states
  const isLoading =
    (fetchHigh && highQuery.isLoading) || (fetchCritical && criticalQuery.isLoading);
  const isFetching =
    (fetchHigh && highQuery.isFetching) || (fetchCritical && criticalQuery.isFetching);
  const isFetchingNextPage =
    (fetchHigh && highQuery.isFetchingNextPage) ||
    (fetchCritical && criticalQuery.isFetchingNextPage);

  // Combine hasNextPage - true if either has more
  const hasNextPage =
    (fetchHigh && highQuery.hasNextPage) || (fetchCritical && criticalQuery.hasNextPage);

  // Combine error states
  const error = highQuery.error || criticalQuery.error;
  const isError = highQuery.isError || criticalQuery.isError;

  // Combined fetch next page - fetches from whichever has more
  const fetchNextPage = (): void => {
    if (fetchHigh && highQuery.hasNextPage) {
      highQuery.fetchNextPage();
    }
    if (fetchCritical && criticalQuery.hasNextPage) {
      criticalQuery.fetchNextPage();
    }
  };

  // Combined refetch
  const refetch = async (): Promise<unknown> => {
    const promises: Promise<unknown>[] = [];
    if (fetchHigh) {
      promises.push(highQuery.refetch());
    }
    if (fetchCritical) {
      promises.push(criticalQuery.refetch());
    }
    return Promise.all(promises);
  };

  return {
    alerts,
    totalCount,
    isLoading,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    error,
    isError,
    refetch,
  };
}

export default useAlertsInfiniteQuery;
