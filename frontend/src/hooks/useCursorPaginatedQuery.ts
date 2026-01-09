/**
 * Generic hook for cursor-based pagination using TanStack Query's useInfiniteQuery.
 */

import {
  useInfiniteQuery,
  type InfiniteData,
  type QueryKey,
} from '@tanstack/react-query';

export interface CursorPaginatedResponse {
  has_more: boolean;
  next_cursor?: string | null;
  count: number;
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
>(
  options: UseCursorPaginatedQueryOptions<TData, TFilters>
): UseCursorPaginatedQueryReturn<TData> {
  const {
    queryKey,
    queryFn,
    filters,
    enabled = true,
    staleTime = 30000,
    gcTime = 300000,
    refetchInterval,
    refetchOnWindowFocus = true,
  } = options;

  const query = useInfiniteQuery<TData, Error, InfiniteData<TData, string | undefined>, QueryKey, string | undefined>({
    queryKey,
    queryFn: ({ pageParam }) => queryFn({ cursor: pageParam, filters }),
    initialPageParam: undefined,
    getNextPageParam: (lastPage: TData) => {
      if (lastPage.has_more && lastPage.next_cursor) {
        return lastPage.next_cursor;
      }
      return undefined;
    },
    enabled,
    staleTime,
    gcTime,
    refetchInterval,
    refetchOnWindowFocus,
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
