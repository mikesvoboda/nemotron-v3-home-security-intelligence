/**
 * usePlateReadsQuery - TanStack Query hook for paginated plate reads
 *
 * This hook fetches plate reads from the LPR API endpoint with support for
 * filtering by camera, date range, and confidence threshold.
 *
 * @module hooks/usePlateReadsQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchPlateReads } from '../services/plateReadsApi';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

import type { PlateRead, PlateReadFilters, PlateReadListResponse } from '../types/plateRead';

/**
 * Query key factory for plate reads queries.
 *
 * Keys follow a hierarchical pattern: ['plate-reads', 'list', filters?]
 *
 * @example
 * // Invalidate all plate reads queries
 * queryClient.invalidateQueries({ queryKey: plateReadsQueryKeys.all });
 *
 * // Invalidate specific filtered query
 * queryClient.invalidateQueries({
 *   queryKey: plateReadsQueryKeys.list({ camera_id: 'cam-1' })
 * });
 */
export const plateReadsQueryKeys = {
  /** Base key for all plate reads queries - use for bulk invalidation */
  all: ['plate-reads'] as const,
  /** List of plate reads with optional filters */
  list: (filters?: PlateReadFilters) =>
    filters ? ([...plateReadsQueryKeys.all, 'list', filters] as const) : ([...plateReadsQueryKeys.all, 'list'] as const),
};

/**
 * Options for configuring the usePlateReadsQuery hook
 */
export interface UsePlateReadsQueryOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * Data older than this will be refetched in the background.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;

  /**
   * Number of retry attempts on failure.
   * Set to false or 0 to disable retries.
   * @default 1
   */
  retry?: number | boolean;
}

/**
 * Return type for the usePlateReadsQuery hook
 */
export interface UsePlateReadsQueryReturn {
  /** Raw API response data, undefined if not yet fetched */
  data: PlateReadListResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query is in an error state */
  isError: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Derived: Array of plate reads, empty if data not loaded */
  plateReads: PlateRead[];
  /** Derived: Total count of matching plate reads */
  total: number;
  /** Derived: Current page number */
  page: number;
  /** Derived: Page size */
  pageSize: number;
  /** Derived: Total number of pages */
  totalPages: number;
  /** Derived: Whether there are more pages after the current one */
  hasNextPage: boolean;
  /** Derived: Whether there are pages before the current one */
  hasPrevPage: boolean;
}

/**
 * Hook to fetch paginated plate reads using TanStack Query.
 *
 * This hook fetches from GET /api/plate-reads and provides:
 * - Automatic caching and request deduplication
 * - Filter support for camera, date range, and confidence
 * - Derived pagination values
 * - Loading, error, and refetching states
 *
 * @param filters - Filter and pagination parameters
 * @param options - Configuration options
 * @returns Plate reads data and query state
 *
 * @example
 * ```tsx
 * // Basic usage - fetch all plate reads
 * const { plateReads, total, isLoading, error } = usePlateReadsQuery();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return <Table data={plateReads} totalCount={total} />;
 * ```
 *
 * @example
 * ```tsx
 * // With filters
 * const { plateReads, hasNextPage, page } = usePlateReadsQuery({
 *   camera_id: 'cam-front',
 *   min_confidence: 0.8,
 *   page: 1,
 *   page_size: 25,
 * });
 * ```
 *
 * @example
 * ```tsx
 * // With date range
 * const { plateReads, total } = usePlateReadsQuery({
 *   start_time: '2026-01-01T00:00:00Z',
 *   end_time: '2026-01-31T23:59:59Z',
 * });
 * ```
 */
export function usePlateReadsQuery(
  filters?: PlateReadFilters,
  options: UsePlateReadsQueryOptions = {}
): UsePlateReadsQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, retry = 1 } = options;

  const query = useQuery<PlateReadListResponse, Error>({
    queryKey: plateReadsQueryKeys.list(filters),
    queryFn: () => fetchPlateReads(filters),
    enabled,
    staleTime,
    retry,
  });

  // Derive plate reads array from the response
  const plateReads = useMemo((): PlateRead[] => {
    if (!query.data) return [];
    return query.data.plate_reads;
  }, [query.data]);

  // Derive total count from the response
  const total = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.total;
  }, [query.data]);

  // Derive current page from the response
  const page = useMemo((): number => {
    if (!query.data) return 1;
    return query.data.page;
  }, [query.data]);

  // Derive page size from the response
  const pageSize = useMemo((): number => {
    if (!query.data) return 50;
    return query.data.page_size;
  }, [query.data]);

  // Derive total pages from the response
  const totalPages = useMemo((): number => {
    if (!query.data || query.data.page_size === 0) return 0;
    return Math.ceil(query.data.total / query.data.page_size);
  }, [query.data]);

  // Derive hasNextPage from the response
  const hasNextPage = useMemo((): boolean => {
    if (!query.data) return false;
    const currentTotal = query.data.page * query.data.page_size;
    return currentTotal < query.data.total;
  }, [query.data]);

  // Derive hasPrevPage from the response
  const hasPrevPage = useMemo((): boolean => {
    if (!query.data) return false;
    return query.data.page > 1;
  }, [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    plateReads,
    total,
    page,
    pageSize,
    totalPages,
    hasNextPage,
    hasPrevPage,
  };
}
