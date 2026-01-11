/**
 * Hook for pagination state management with URL persistence.
 *
 * Supports both cursor-based and offset-based pagination,
 * syncing state to URL query parameters for shareable links.
 */

import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * Pagination type determines which parameters are used.
 * - 'cursor': Uses cursor-based pagination (cursor, limit)
 * - 'offset': Uses offset-based pagination (page, limit)
 */
export type PaginationType = 'cursor' | 'offset';

/**
 * Options for configuring the pagination state hook.
 */
export interface UsePaginationStateOptions {
  /**
   * Type of pagination to use.
   * @default 'cursor'
   */
  type?: PaginationType;

  /**
   * Default page size (limit).
   * @default 20
   */
  defaultLimit?: number;

  /**
   * URL parameter names for customization.
   * Useful when multiple paginated lists exist on the same page.
   */
  paramNames?: {
    /** Parameter name for cursor. @default 'cursor' */
    cursor?: string;
    /** Parameter name for page number. @default 'page' */
    page?: string;
    /** Parameter name for limit/page size. @default 'limit' */
    limit?: string;
  };

  /**
   * Whether to persist the limit to URL.
   * Set to false if you want to keep limit as local state only.
   * @default true
   */
  persistLimit?: boolean;

  /**
   * Callback when pagination state changes.
   * Useful for triggering data fetches or analytics.
   */
  onStateChange?: (state: PaginationState) => void;
}

/**
 * Base pagination state shared by all pagination types.
 */
export interface BasePaginationState {
  /** Number of items per page. */
  limit: number;
}

/**
 * Cursor-based pagination state.
 */
export interface CursorPaginationState extends BasePaginationState {
  type: 'cursor';
  /** Current cursor value. Undefined for first page. */
  cursor: string | undefined;
}

/**
 * Offset-based pagination state.
 */
export interface OffsetPaginationState extends BasePaginationState {
  type: 'offset';
  /** Current page number (1-indexed for user-friendliness). */
  page: number;
  /** Calculated offset based on page and limit. */
  offset: number;
}

/**
 * Union type for pagination state.
 */
export type PaginationState = CursorPaginationState | OffsetPaginationState;

/**
 * Return type for cursor-based pagination.
 */
export interface UseCursorPaginationStateReturn {
  type: 'cursor';
  /** Current cursor value. */
  cursor: string | undefined;
  /** Number of items per page. */
  limit: number;
  /** Set the cursor value. */
  setCursor: (cursor: string | undefined) => void;
  /** Set the limit/page size. */
  setLimit: (limit: number) => void;
  /** Reset pagination to initial state. */
  reset: () => void;
  /** Navigate to next page with the given cursor. */
  goToNextPage: (nextCursor: string) => void;
  /** Navigate to first page (clear cursor). */
  goToFirstPage: () => void;
  /** Current pagination state. */
  state: CursorPaginationState;
  /** Whether we're on the first page. */
  isFirstPage: boolean;
}

/**
 * Return type for offset-based pagination.
 */
export interface UseOffsetPaginationStateReturn {
  type: 'offset';
  /** Current page number (1-indexed). */
  page: number;
  /** Current offset. */
  offset: number;
  /** Number of items per page. */
  limit: number;
  /** Set the page number. */
  setPage: (page: number) => void;
  /** Set the limit/page size. */
  setLimit: (limit: number) => void;
  /** Reset pagination to initial state. */
  reset: () => void;
  /** Navigate to next page. */
  goToNextPage: () => void;
  /** Navigate to previous page. */
  goToPreviousPage: () => void;
  /** Navigate to first page. */
  goToFirstPage: () => void;
  /** Navigate to last page (requires total count). */
  goToLastPage: (totalItems: number) => void;
  /** Current pagination state. */
  state: OffsetPaginationState;
  /** Whether we're on the first page. */
  isFirstPage: boolean;
  /** Check if we're on the last page (requires total count). */
  isLastPage: (totalItems: number) => boolean;
  /** Get total number of pages (requires total count). */
  getTotalPages: (totalItems: number) => number;
}

/**
 * Return type union for the hook.
 */
export type UsePaginationStateReturn = UseCursorPaginationStateReturn | UseOffsetPaginationStateReturn;

/**
 * Default parameter names for URL query parameters.
 */
const DEFAULT_PARAM_NAMES = {
  cursor: 'cursor',
  page: 'page',
  limit: 'limit',
} as const;

/**
 * Type for merged parameter names (allows custom string values).
 */
type ParamNames = {
  cursor: string;
  page: string;
  limit: string;
};

/**
 * Default values for pagination.
 */
const DEFAULT_LIMIT = 20;
const DEFAULT_PAGE = 1;

/**
 * Internal hook for cursor-based pagination.
 * Called unconditionally to satisfy React hooks rules.
 */
function useCursorPaginationInternal(
  searchParams: URLSearchParams,
  updateParams: (updates: Record<string, string | undefined>) => void,
  params: ParamNames,
  limit: number,
  defaultLimit: number,
  persistLimit: boolean,
  onStateChange?: (state: PaginationState) => void
): UseCursorPaginationStateReturn {
  const cursor = searchParams.get(params.cursor) ?? undefined;

  const state: CursorPaginationState = useMemo(
    () => ({
      type: 'cursor',
      cursor,
      limit,
    }),
    [cursor, limit]
  );

  const setCursor = useCallback(
    (newCursor: string | undefined) => {
      updateParams({ [params.cursor]: newCursor });
      onStateChange?.({ type: 'cursor', cursor: newCursor, limit });
    },
    [updateParams, params.cursor, limit, onStateChange]
  );

  const setLimit = useCallback(
    (newLimit: number) => {
      const updates: Record<string, string | undefined> = {};
      if (persistLimit) {
        updates[params.limit] = String(newLimit);
      }
      // Reset cursor when limit changes
      updates[params.cursor] = undefined;
      updateParams(updates);
      onStateChange?.({ type: 'cursor', cursor: undefined, limit: newLimit });
    },
    [updateParams, params.cursor, params.limit, persistLimit, onStateChange]
  );

  const reset = useCallback(() => {
    const updates: Record<string, string | undefined> = {
      [params.cursor]: undefined,
    };
    if (persistLimit) {
      updates[params.limit] = undefined;
    }
    updateParams(updates);
    onStateChange?.({ type: 'cursor', cursor: undefined, limit: defaultLimit });
  }, [updateParams, params.cursor, params.limit, persistLimit, defaultLimit, onStateChange]);

  const goToNextPage = useCallback(
    (nextCursor: string) => {
      setCursor(nextCursor);
    },
    [setCursor]
  );

  const goToFirstPage = useCallback(() => {
    setCursor(undefined);
  }, [setCursor]);

  const isFirstPage = cursor === undefined;

  return {
    type: 'cursor',
    cursor,
    limit,
    setCursor,
    setLimit,
    reset,
    goToNextPage,
    goToFirstPage,
    state,
    isFirstPage,
  };
}

/**
 * Internal hook for offset-based pagination.
 * Called unconditionally to satisfy React hooks rules.
 */
function useOffsetPaginationInternal(
  searchParams: URLSearchParams,
  updateParams: (updates: Record<string, string | undefined>) => void,
  params: ParamNames,
  limit: number,
  defaultLimit: number,
  persistLimit: boolean,
  onStateChange?: (state: PaginationState) => void
): UseOffsetPaginationStateReturn {
  const pageParam = searchParams.get(params.page);
  const page = useMemo(() => {
    if (pageParam) {
      const parsed = parseInt(pageParam, 10);
      if (!isNaN(parsed) && parsed >= 1) {
        return parsed;
      }
    }
    return DEFAULT_PAGE;
  }, [pageParam]);

  const offset = (page - 1) * limit;

  const state: OffsetPaginationState = useMemo(
    () => ({
      type: 'offset',
      page,
      offset,
      limit,
    }),
    [page, offset, limit]
  );

  const setPage = useCallback(
    (newPage: number) => {
      const validPage = Math.max(1, newPage);
      updateParams({
        [params.page]: validPage === 1 ? undefined : String(validPage),
      });
      const newOffset = (validPage - 1) * limit;
      onStateChange?.({ type: 'offset', page: validPage, offset: newOffset, limit });
    },
    [updateParams, params.page, limit, onStateChange]
  );

  const setLimit = useCallback(
    (newLimit: number) => {
      const updates: Record<string, string | undefined> = {
        // Reset to page 1 when limit changes
        [params.page]: undefined,
      };
      if (persistLimit) {
        updates[params.limit] = String(newLimit);
      }
      updateParams(updates);
      onStateChange?.({ type: 'offset', page: 1, offset: 0, limit: newLimit });
    },
    [updateParams, params.page, params.limit, persistLimit, onStateChange]
  );

  const reset = useCallback(() => {
    const updates: Record<string, string | undefined> = {
      [params.page]: undefined,
    };
    if (persistLimit) {
      updates[params.limit] = undefined;
    }
    updateParams(updates);
    onStateChange?.({ type: 'offset', page: 1, offset: 0, limit: defaultLimit });
  }, [updateParams, params.page, params.limit, persistLimit, defaultLimit, onStateChange]);

  const goToNextPage = useCallback(() => {
    setPage(page + 1);
  }, [setPage, page]);

  const goToPreviousPage = useCallback(() => {
    if (page > 1) {
      setPage(page - 1);
    }
  }, [setPage, page]);

  const goToFirstPage = useCallback(() => {
    setPage(1);
  }, [setPage]);

  const goToLastPage = useCallback(
    (totalItems: number) => {
      const totalPages = Math.ceil(totalItems / limit);
      if (totalPages > 0) {
        setPage(totalPages);
      }
    },
    [setPage, limit]
  );

  const isFirstPage = page === 1;

  const isLastPage = useCallback(
    (totalItems: number) => {
      const totalPages = Math.ceil(totalItems / limit);
      return page >= totalPages;
    },
    [page, limit]
  );

  const getTotalPages = useCallback(
    (totalItems: number) => {
      return Math.ceil(totalItems / limit);
    },
    [limit]
  );

  return {
    type: 'offset',
    page,
    offset,
    limit,
    setPage,
    setLimit,
    reset,
    goToNextPage,
    goToPreviousPage,
    goToFirstPage,
    goToLastPage,
    state,
    isFirstPage,
    isLastPage,
    getTotalPages,
  };
}

/**
 * Hook for managing pagination state with URL persistence.
 *
 * @example Cursor-based pagination (default)
 * ```tsx
 * function EventList() {
 *   const pagination = usePaginationState({ type: 'cursor' });
 *
 *   const { data, fetchNextPage } = useEventsQuery({
 *     cursor: pagination.cursor,
 *     limit: pagination.limit,
 *   });
 *
 *   const handleLoadMore = () => {
 *     if (data?.pagination.next_cursor) {
 *       pagination.goToNextPage(data.pagination.next_cursor);
 *     }
 *   };
 *
 *   return (
 *     <div>
 *       {data?.items.map(item => <EventCard key={item.id} event={item} />)}
 *       {data?.pagination.has_more && (
 *         <button onClick={handleLoadMore}>Load More</button>
 *       )}
 *     </div>
 *   );
 * }
 * ```
 *
 * @example Offset-based pagination
 * ```tsx
 * function PaginatedList() {
 *   const pagination = usePaginationState({ type: 'offset', defaultLimit: 10 });
 *
 *   const { data } = useItemsQuery({
 *     offset: pagination.offset,
 *     limit: pagination.limit,
 *   });
 *
 *   return (
 *     <div>
 *       {data?.items.map(item => <Item key={item.id} item={item} />)}
 *       <div>
 *         <button
 *           onClick={pagination.goToPreviousPage}
 *           disabled={pagination.isFirstPage}
 *         >
 *           Previous
 *         </button>
 *         <span>Page {pagination.page} of {pagination.getTotalPages(data?.total ?? 0)}</span>
 *         <button
 *           onClick={pagination.goToNextPage}
 *           disabled={pagination.isLastPage(data?.total ?? 0)}
 *         >
 *           Next
 *         </button>
 *       </div>
 *     </div>
 *   );
 * }
 * ```
 *
 * @example Multiple paginated lists on the same page
 * ```tsx
 * function Dashboard() {
 *   const eventsPagination = usePaginationState({
 *     type: 'cursor',
 *     paramNames: { cursor: 'events_cursor', limit: 'events_limit' },
 *   });
 *
 *   const alertsPagination = usePaginationState({
 *     type: 'offset',
 *     paramNames: { page: 'alerts_page', limit: 'alerts_limit' },
 *   });
 *
 *   // Use independently...
 * }
 * ```
 */
export function usePaginationState(options: UsePaginationStateOptions & { type: 'cursor' }): UseCursorPaginationStateReturn;
export function usePaginationState(options: UsePaginationStateOptions & { type: 'offset' }): UseOffsetPaginationStateReturn;
export function usePaginationState(options?: UsePaginationStateOptions): UsePaginationStateReturn;
export function usePaginationState(options: UsePaginationStateOptions = {}): UsePaginationStateReturn {
  const {
    type = 'cursor',
    defaultLimit = DEFAULT_LIMIT,
    paramNames = {},
    persistLimit = true,
    onStateChange,
  } = options;

  const [searchParams, setSearchParams] = useSearchParams();

  // Merge parameter names with defaults
  const params = useMemo(
    () => ({
      ...DEFAULT_PARAM_NAMES,
      ...paramNames,
    }),
    [paramNames]
  );

  // Parse limit from URL or use default
  const limit = useMemo(() => {
    if (!persistLimit) return defaultLimit;
    const limitParam = searchParams.get(params.limit);
    if (limitParam) {
      const parsed = parseInt(limitParam, 10);
      if (!isNaN(parsed) && parsed > 0 && parsed <= 100) {
        return parsed;
      }
    }
    return defaultLimit;
  }, [searchParams, params.limit, defaultLimit, persistLimit]);

  // Helper to update search params while preserving other params
  const updateParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      setSearchParams(
        (prev) => {
          const newParams = new URLSearchParams(prev);
          Object.entries(updates).forEach(([key, value]) => {
            if (value === undefined || value === '') {
              newParams.delete(key);
            } else {
              newParams.set(key, value);
            }
          });
          return newParams;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  // Call both internal hooks unconditionally to satisfy React hooks rules
  const cursorResult = useCursorPaginationInternal(
    searchParams,
    updateParams,
    params,
    limit,
    defaultLimit,
    persistLimit,
    onStateChange
  );

  const offsetResult = useOffsetPaginationInternal(
    searchParams,
    updateParams,
    params,
    limit,
    defaultLimit,
    persistLimit,
    onStateChange
  );

  // Return the appropriate result based on type
  return type === 'cursor' ? cursorResult : offsetResult;
}

export default usePaginationState;
