/**
 * React Query hook for searching jobs with filtering and aggregations.
 *
 * Provides a hook for searching and filtering background jobs using the
 * /api/jobs/search endpoint with support for text search, status filtering,
 * and type filtering.
 */

import { useQuery, type UseQueryOptions } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { searchJobs, type JobsSearchQueryParams } from '../services/api';

import type { JobSearchResponse, JobSearchAggregations, JobStatusEnum } from '../types/generated';

/**
 * Filters for job search.
 */
export interface JobsSearchFilters {
  /** Search query text */
  q?: string;
  /** Filter by job status */
  status?: JobStatusEnum;
  /** Filter by job type (e.g., 'export', 'batch_audit', 'cleanup', 're_evaluation') */
  type?: string;
}

/**
 * Options for useJobsSearchQuery hook.
 */
export interface UseJobsSearchQueryOptions {
  /** Search filters */
  filters?: JobsSearchFilters;
  /** Maximum number of jobs to return (default 50) */
  limit?: number;
  /** Whether to enable the query (default true) */
  enabled?: boolean;
  /** Number of retries on failure */
  retry?: number;
  /** Debounce delay in milliseconds for search query changes */
  debounceMs?: number;
}

/**
 * Return type for useJobsSearchQuery.
 */
export interface UseJobsSearchQueryReturn {
  /** List of jobs matching the search criteria */
  jobs: JobSearchResponse['data'];
  /** Total count of matching jobs */
  totalCount: number;
  /** Aggregations for faceted filtering */
  aggregations: JobSearchAggregations;
  /** Whether the query is loading */
  isLoading: boolean;
  /** Whether the query is fetching (including background refetches) */
  isFetching: boolean;
  /** Error if the query failed */
  error: Error | null;
  /** Whether the query has an error */
  isError: boolean;
  /** Function to manually refetch */
  refetch: () => void;
}

/**
 * Query keys for job search.
 */
export const jobsSearchQueryKeys = {
  all: ['jobs-search'] as const,
  lists: () => [...jobsSearchQueryKeys.all, 'list'] as const,
  list: (filters?: JobsSearchFilters, limit?: number) =>
    [...jobsSearchQueryKeys.lists(), { filters, limit }] as const,
};

/**
 * Default empty aggregations for initial state.
 */
const EMPTY_AGGREGATIONS: JobSearchAggregations = {
  by_status: {},
  by_type: {},
};

/**
 * Custom hook for debouncing a value.
 */
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    // If no delay, update immediately
    if (delay === 0) {
      setDebouncedValue(value);
      return;
    }

    // Set timeout to update debounced value
    const timeoutId = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    // Clean up timeout on value or delay change
    return () => {
      clearTimeout(timeoutId);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Hook for searching jobs with filters and aggregations.
 *
 * Features:
 * - Text search across job fields
 * - Status filtering (pending, running, completed, failed)
 * - Type filtering (export, batch_audit, cleanup, re_evaluation)
 * - Aggregations for faceted filtering
 * - Optional debouncing for search input
 *
 * @param options - Query options including filters, limit, and debounce settings
 * @returns Jobs data, aggregations, and query state
 *
 * @example
 * ```tsx
 * const { jobs, aggregations, isLoading } = useJobsSearchQuery({
 *   filters: { q: 'export', status: 'failed' },
 *   limit: 50,
 *   debounceMs: 300,
 * });
 * ```
 */
export function useJobsSearchQuery(
  options: UseJobsSearchQueryOptions = {}
): UseJobsSearchQueryReturn {
  const { filters, limit = 50, enabled = true, retry = 1, debounceMs = 0 } = options;

  // Debounce the search query if debounceMs is provided
  const debouncedQuery = useDebounce(filters?.q, debounceMs);

  // Create the effective filters with debounced query
  const effectiveFilters: JobsSearchFilters | undefined = useMemo(() => {
    if (!filters) return undefined;
    return {
      ...filters,
      q: debounceMs > 0 ? debouncedQuery : filters.q,
    };
  }, [filters, debouncedQuery, debounceMs]);

  const queryKey = jobsSearchQueryKeys.list(effectiveFilters, limit);

  const queryOptions: UseQueryOptions<JobSearchResponse, Error> = {
    queryKey,
    queryFn: async () => {
      const params: JobsSearchQueryParams = {
        ...effectiveFilters,
        limit,
      };
      return searchJobs(params);
    },
    enabled,
    retry,
    staleTime: 30_000, // 30 seconds
  };

  const { data, isLoading, isFetching, error, isError, refetch } = useQuery(queryOptions);

  // Wrap refetch to return void (ESLint: no-misused-promises)
  const handleRefetch = useCallback(() => {
    void refetch();
  }, [refetch]);

  return {
    jobs: data?.data ?? [],
    totalCount: data?.meta?.total ?? 0,
    aggregations: data?.aggregations ?? EMPTY_AGGREGATIONS,
    isLoading,
    isFetching,
    error: error ?? null,
    isError,
    refetch: handleRefetch,
  };
}

export default useJobsSearchQuery;
