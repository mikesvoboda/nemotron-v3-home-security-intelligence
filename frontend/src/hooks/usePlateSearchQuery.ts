/**
 * usePlateSearchQuery - TanStack Query hook for searching plate reads
 *
 * This hook provides search functionality for the plate reads feature,
 * including support for debounced input, exact/partial matching, and pagination.
 *
 * @module hooks/usePlateSearchQuery
 * @see frontend/src/services/plateReadsApi.ts - API client
 * @see frontend/src/types/plateRead.ts - Type definitions
 */

import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { useMemo, useState, useEffect, useCallback } from 'react';

import { searchPlateReads, fetchPlateReads } from '../services/plateReadsApi';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

import type {
  PlateReadListResponse,
  PlateSearchParams,
  PlateReadFilters,
  PlateRead,
} from '../types/plateRead';

// ============================================================================
// Query Key Factory
// ============================================================================

/**
 * Query key factory for plate search queries.
 *
 * Keys follow a hierarchical pattern: ['plate-reads', 'search', params?]
 *
 * @example
 * // Invalidate all plate search queries
 * queryClient.invalidateQueries({ queryKey: plateSearchQueryKeys.all });
 *
 * // Invalidate specific search
 * queryClient.invalidateQueries({
 *   queryKey: plateSearchQueryKeys.byText({ text: 'ABC123' })
 * });
 */
export const plateSearchQueryKeys = {
  /** Base key for all plate search queries - use for bulk invalidation */
  all: ['plate-reads'] as const,
  /** Plate reads list with filters */
  list: (filters?: PlateReadFilters) =>
    filters
      ? ([...plateSearchQueryKeys.all, 'list', filters] as const)
      : ([...plateSearchQueryKeys.all, 'list'] as const),
  /** Search by text with params */
  byText: (params: PlateSearchParams) =>
    [...plateSearchQueryKeys.all, 'search', params] as const,
};

// ============================================================================
// Types
// ============================================================================

/**
 * Combined search and filter parameters for plate reads.
 */
export interface PlateSearchFilters {
  /** Plate text to search for (partial match unless exact=true) */
  text?: string;
  /** If true, match exact plate text only */
  exact?: boolean;
  /** Filter by camera ID */
  camera_id?: string;
  /** Filter by start time (ISO 8601 format) */
  start_time?: string;
  /** Filter by end time (ISO 8601 format) */
  end_time?: string;
  /** Minimum OCR confidence threshold (0-1) */
  min_confidence?: number;
  /** Page number (1-indexed, default: 1) */
  page?: number;
  /** Number of items per page (default: 50, max: 1000) */
  page_size?: number;
}

/**
 * Options for configuring the usePlateSearchQuery hook
 */
export interface UsePlateSearchQueryOptions {
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

  /**
   * Debounce delay in milliseconds for text input.
   * @default 300
   */
  debounceMs?: number;
}

/**
 * Return type for the usePlateSearchQuery hook
 */
export interface UsePlateSearchQueryReturn {
  /** Array of plate reads matching the search criteria */
  plateReads: PlateRead[];
  /** Total number of matching plate reads (for pagination) */
  total: number;
  /** Current page number */
  page: number;
  /** Page size */
  pageSize: number;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query is in an error state */
  isError: boolean;
  /** Whether we're showing previous data while loading new data */
  isPlaceholderData: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

// ============================================================================
// Custom Debounce Hook
// ============================================================================

/**
 * Hook to debounce a value.
 *
 * @param value - The value to debounce
 * @param delay - Delay in milliseconds
 * @returns Debounced value
 */
export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

// ============================================================================
// Main Hook
// ============================================================================

/**
 * Hook to search plate reads using TanStack Query.
 *
 * This hook provides:
 * - Automatic caching and request deduplication
 * - Debounced search input (configurable delay)
 * - Pagination support with keepPreviousData
 * - Combined text search and filter support
 *
 * @param filters - Search and filter parameters
 * @param options - Configuration options
 * @returns Search results and query state
 *
 * @example
 * ```tsx
 * // Basic text search
 * const { plateReads, total, isLoading } = usePlateSearchQuery({
 *   text: 'ABC',
 * });
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <Table data={plateReads} total={total} />
 * );
 * ```
 *
 * @example
 * ```tsx
 * // With filters and pagination
 * const { plateReads, total, refetch } = usePlateSearchQuery({
 *   text: searchText,
 *   exact: true,
 *   camera_id: selectedCamera,
 *   start_time: startDate,
 *   end_time: endDate,
 *   min_confidence: 0.8,
 *   page: currentPage,
 *   page_size: 25,
 * });
 * ```
 */
export function usePlateSearchQuery(
  filters: PlateSearchFilters = {},
  options: UsePlateSearchQueryOptions = {}
): UsePlateSearchQueryReturn {
  const {
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
    retry = 1,
    debounceMs = 300,
  } = options;

  // Debounce the search text to avoid excessive API calls
  const debouncedText = useDebouncedValue(filters.text ?? '', debounceMs);

  // Determine if this is a text search or a filtered list
  const isTextSearch = debouncedText.length > 0;

  // Build the query key based on search type
  const queryKey = useMemo(() => {
    if (isTextSearch) {
      return plateSearchQueryKeys.byText({
        text: debouncedText,
        exact: filters.exact,
        page: filters.page,
        page_size: filters.page_size,
      });
    }
    return plateSearchQueryKeys.list({
      camera_id: filters.camera_id,
      start_time: filters.start_time,
      end_time: filters.end_time,
      min_confidence: filters.min_confidence,
      page: filters.page,
      page_size: filters.page_size,
    });
  }, [
    isTextSearch,
    debouncedText,
    filters.exact,
    filters.camera_id,
    filters.start_time,
    filters.end_time,
    filters.min_confidence,
    filters.page,
    filters.page_size,
  ]);

  // Query function that calls the appropriate API
  const queryFn = useCallback(async (): Promise<PlateReadListResponse> => {
    if (isTextSearch) {
      return searchPlateReads({
        text: debouncedText,
        exact: filters.exact,
        page: filters.page,
        page_size: filters.page_size,
      });
    }
    return fetchPlateReads({
      camera_id: filters.camera_id,
      start_time: filters.start_time,
      end_time: filters.end_time,
      min_confidence: filters.min_confidence,
      page: filters.page,
      page_size: filters.page_size,
    });
  }, [
    isTextSearch,
    debouncedText,
    filters.exact,
    filters.camera_id,
    filters.start_time,
    filters.end_time,
    filters.min_confidence,
    filters.page,
    filters.page_size,
  ]);

  const query = useQuery<PlateReadListResponse, Error>({
    queryKey,
    queryFn,
    enabled,
    staleTime,
    retry,
    // Keep showing previous data while loading new data for smooth pagination
    placeholderData: keepPreviousData,
  });

  // Derive values from the response
  const plateReads = useMemo((): PlateRead[] => {
    if (!query.data) return [];
    return query.data.plate_reads;
  }, [query.data]);

  const total = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.total;
  }, [query.data]);

  const page = useMemo((): number => {
    if (!query.data) return 1;
    return query.data.page;
  }, [query.data]);

  const pageSize = useMemo((): number => {
    if (!query.data) return filters.page_size ?? 50;
    return query.data.page_size;
  }, [query.data, filters.page_size]);

  return {
    plateReads,
    total,
    page,
    pageSize,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    isPlaceholderData: query.isPlaceholderData,
    refetch: query.refetch,
  };
}
