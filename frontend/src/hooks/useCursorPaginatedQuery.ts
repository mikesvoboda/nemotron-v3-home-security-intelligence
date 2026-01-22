/**
 * Generic hook for cursor-based pagination using TanStack Query's useInfiniteQuery.
 *
 * Provides both a low-level hook (useCursorPaginatedQuery) and a factory function
 * (createInfiniteQueryHook) for creating domain-specific hooks with reduced boilerplate.
 */

import { useInfiniteQuery, type InfiniteData, type QueryKey } from '@tanstack/react-query';
import { useMemo } from 'react';

export interface PaginationInfo {
  total: number;
  has_more: boolean;
  next_cursor?: string | null;
}

export interface CursorPaginatedResponse {
  pagination: PaginationInfo;
}

export interface UseCursorPaginatedQueryOptions<
  TData extends CursorPaginatedResponse,
  TFilters = undefined,
> {
  queryKey: QueryKey;
  queryFn: (params: { cursor?: string; filters?: TFilters }) => Promise<TData>;
  filters?: TFilters;
  enabled?: boolean;
  staleTime?: number;
  gcTime?: number;
  refetchInterval?: number | false;
  refetchOnWindowFocus?: boolean;
  /**
   * Number of retry attempts for failed queries.
   * Set to 0 to disable retries, or use a lower number for faster failure feedback.
   * Defaults to the global QueryClient setting (3).
   */
  retry?: number | boolean;
}

export interface UseCursorPaginatedQueryReturn<TData extends CursorPaginatedResponse> {
  data: InfiniteData<TData, string | undefined> | undefined;
  isLoading: boolean;
  isFetching: boolean;
  isFetchingNextPage: boolean;
  hasNextPage: boolean;
  fetchNextPage: () => void;
  error: Error | null;
  isError: boolean;
  refetch: () => void;
}

export type ExtractItemType<T> = T extends { events: infer U }
  ? U
  : T extends { detections: infer U }
    ? U
    : T extends { items: infer U }
      ? U
      : never;

export function useCursorPaginatedQuery<
  TData extends CursorPaginatedResponse,
  TFilters = undefined,
>(options: UseCursorPaginatedQueryOptions<TData, TFilters>): UseCursorPaginatedQueryReturn<TData> {
  const {
    queryKey,
    queryFn,
    filters,
    enabled = true,
    staleTime = 30000,
    gcTime = 300000,
    refetchInterval,
    refetchOnWindowFocus = true,
    retry,
  } = options;

  const query = useInfiniteQuery<
    TData,
    Error,
    InfiniteData<TData, string | undefined>,
    QueryKey,
    string | undefined
  >({
    queryKey,
    queryFn: ({ pageParam }) => queryFn({ cursor: pageParam, filters }),
    initialPageParam: undefined,
    getNextPageParam: (lastPage: TData) => {
      if (lastPage.pagination.has_more && lastPage.pagination.next_cursor) {
        return lastPage.pagination.next_cursor;
      }
      return undefined;
    },
    enabled,
    staleTime,
    gcTime,
    refetchInterval,
    refetchOnWindowFocus,
    ...(retry !== undefined && { retry }),
  });

  const handleFetchNextPage = (): void => {
    void query.fetchNextPage();
  };

  const handleRefetch = (): void => {
    void query.refetch();
  };

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isFetchingNextPage: query.isFetchingNextPage,
    hasNextPage: query.hasNextPage ?? false,
    fetchNextPage: handleFetchNextPage,
    error: query.error,
    isError: query.isError,
    refetch: handleRefetch,
  };
}

export default useCursorPaginatedQuery;

// ============================================================================
// Factory Function for Creating Domain-Specific Infinite Query Hooks
// ============================================================================

/**
 * Configuration for creating an infinite query hook using the factory function.
 */
export interface CreateInfiniteQueryHookConfig<
  TResponse extends CursorPaginatedResponse & { items: TItem[] },
  TItem,
  TOptions,
  TFilters = undefined,
> {
  getQueryKey: (options: TOptions) => QueryKey;
  fetchFn: (params: { cursor?: string; limit: number; filters?: TFilters }) => Promise<TResponse>;
  getFilters?: (options: TOptions) => TFilters | undefined;
  getLimit?: (options: TOptions) => number;
  defaultRetry?: number | boolean;
}

/**
 * Standard options interface for infinite query hooks.
 */
export interface BaseInfiniteQueryOptions {
  limit?: number;
  enabled?: boolean;
  staleTime?: number;
  refetchInterval?: number | false;
  retry?: number | boolean;
}

/**
 * Standard return interface for infinite query hooks with flattened items.
 */
export interface InfiniteQueryHookReturn<TItem, TResponse extends CursorPaginatedResponse> {
  items: TItem[];
  pages: TResponse[] | undefined;
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

/**
 * Creates a domain-specific infinite query hook using the provided configuration.
 */
export function createInfiniteQueryHook<
  TResponse extends CursorPaginatedResponse & { items: TItem[] },
  TItem,
  TOptions extends BaseInfiniteQueryOptions,
  TFilters = undefined,
>(
  config: CreateInfiniteQueryHookConfig<TResponse, TItem, TOptions, TFilters>
): (options?: TOptions) => InfiniteQueryHookReturn<TItem, TResponse> {
  const { getQueryKey, fetchFn, getFilters, getLimit, defaultRetry } = config;

  return function useInfiniteQueryHook(
    options: TOptions = {} as TOptions
  ): InfiniteQueryHookReturn<TItem, TResponse> {
    const {
      limit = 50,
      enabled = true,
      staleTime,
      refetchInterval,
      retry = defaultRetry,
    } = options;

    const actualLimit = getLimit ? getLimit(options) : limit;
    const filters = getFilters ? getFilters(options) : undefined;

    const query = useCursorPaginatedQuery<TResponse, TFilters>({
      queryKey: getQueryKey(options),
      queryFn: ({ cursor, filters: queryFilters }) =>
        fetchFn({ cursor, limit: actualLimit, filters: queryFilters }),
      filters,
      enabled,
      staleTime,
      refetchInterval,
      retry,
    });

    const items = useMemo(() => {
      if (!query.data?.pages) {
        return [];
      }
      return query.data.pages.flatMap((page) => page.items);
    }, [query.data?.pages]);

    const totalCount = useMemo(() => {
      if (!query.data?.pages?.length) {
        return 0;
      }
      // Always use the first page's total count
      // The first page should have include_total_count=true, so it has the accurate total
      // Subsequent pages may have total=0 if they were fetched with a cursor
      return query.data.pages[0].pagination.total;
    }, [query.data?.pages]);

    return {
      items,
      pages: query.data?.pages,
      totalCount,
      isLoading: query.isLoading,
      isFetching: query.isFetching,
      isFetchingNextPage: query.isFetchingNextPage,
      hasNextPage: query.hasNextPage,
      fetchNextPage: query.fetchNextPage,
      error: query.error,
      isError: query.isError,
      refetch: query.refetch,
    };
  };
}
