import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useCursorPaginatedQuery, type CursorPaginatedResponse } from './useCursorPaginatedQuery';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Test response type that extends CursorPaginatedResponse
interface TestItem {
  id: number;
  name: string;
}

interface TestResponse extends CursorPaginatedResponse {
  items: TestItem[];
}

interface TestFilters {
  category?: string;
  status?: string;
}

describe('useCursorPaginatedQuery', () => {
  const mockPage1: TestResponse = {
    items: [
      { id: 1, name: 'Item 1' },
      { id: 2, name: 'Item 2' },
    ],
    pagination: {
      total: 5,
      has_more: true,
      next_cursor: 'cursor-page-2',
    },
  };

  const mockPage2: TestResponse = {
    items: [
      { id: 3, name: 'Item 3' },
      { id: 4, name: 'Item 4' },
    ],
    pagination: {
      total: 5,
      has_more: true,
      next_cursor: 'cursor-page-3',
    },
  };

  const mockPage3: TestResponse = {
    items: [{ id: 5, name: 'Item 5' }],
    pagination: {
      total: 5,
      has_more: false,
      next_cursor: null,
    },
  };

  let mockQueryFn: ReturnType<
    typeof vi.fn<(params: { cursor?: string; filters?: TestFilters }) => Promise<TestResponse>>
  >;

  beforeEach(() => {
    vi.clearAllMocks();
    mockQueryFn =
      vi.fn<(params: { cursor?: string; filters?: TestFilters }) => Promise<TestResponse>>();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('initializes with first page (undefined cursor)', async () => {
      mockQueryFn.mockResolvedValue(mockPage1);

      renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(mockQueryFn).toHaveBeenCalledWith({
          cursor: undefined,
          filters: undefined,
        });
      });
    });

    it('starts with isLoading true', () => {
      mockQueryFn.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
          }),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      mockQueryFn.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
          }),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.data).toBeUndefined();
    });
  });

  describe('getNextPageParam logic', () => {
    it('extracts next_cursor when has_more is true', async () => {
      mockQueryFn.mockResolvedValueOnce(mockPage1).mockResolvedValueOnce(mockPage2);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
          }),
        { wrapper: createQueryWrapper() }
      );

      // Wait for first page
      await waitFor(() => {
        expect(result.current.hasNextPage).toBe(true);
      });

      // Fetch next page
      result.current.fetchNextPage();

      await waitFor(() => {
        expect(mockQueryFn).toHaveBeenCalledTimes(2);
      });

      // Second call should include the cursor from page 1
      expect(mockQueryFn).toHaveBeenLastCalledWith({
        cursor: 'cursor-page-2',
        filters: undefined,
      });
    });

    it('returns undefined when has_more is false', async () => {
      const lastPage: TestResponse = {
        items: [{ id: 1, name: 'Only Item' }],
        pagination: {
          total: 1,
          has_more: false,
          next_cursor: null,
        },
      };
      mockQueryFn.mockResolvedValue(lastPage);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.hasNextPage).toBe(false);
      });
    });

    it('returns undefined when next_cursor is null even if has_more is true', async () => {
      const inconsistentPage: TestResponse = {
        items: [{ id: 1, name: 'Item' }],
        pagination: {
          total: 10,
          has_more: true, // Inconsistent with next_cursor being null
          next_cursor: null,
        },
      };
      mockQueryFn.mockResolvedValue(inconsistentPage);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.hasNextPage).toBe(false);
      });
    });
  });

  describe('cursor extraction', () => {
    it('correctly passes cursor to queryFn across multiple pages', async () => {
      mockQueryFn
        .mockResolvedValueOnce(mockPage1)
        .mockResolvedValueOnce(mockPage2)
        .mockResolvedValueOnce(mockPage3);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
          }),
        { wrapper: createQueryWrapper() }
      );

      // Wait for first page
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
      expect(mockQueryFn).toHaveBeenNthCalledWith(1, { cursor: undefined, filters: undefined });

      // Fetch page 2
      result.current.fetchNextPage();
      await waitFor(() => {
        expect(mockQueryFn).toHaveBeenCalledTimes(2);
      });
      expect(mockQueryFn).toHaveBeenNthCalledWith(2, {
        cursor: 'cursor-page-2',
        filters: undefined,
      });

      // Fetch page 3
      result.current.fetchNextPage();
      await waitFor(() => {
        expect(mockQueryFn).toHaveBeenCalledTimes(3);
      });
      expect(mockQueryFn).toHaveBeenNthCalledWith(3, {
        cursor: 'cursor-page-3',
        filters: undefined,
      });
    });
  });

  describe('page accumulation', () => {
    it('accumulates pages in data.pages array', async () => {
      mockQueryFn
        .mockResolvedValueOnce(mockPage1)
        .mockResolvedValueOnce(mockPage2)
        .mockResolvedValueOnce(mockPage3);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
          }),
        { wrapper: createQueryWrapper() }
      );

      // Wait for first page
      await waitFor(() => {
        expect(result.current.data?.pages?.length).toBe(1);
      });
      expect(result.current.data?.pages?.[0].items).toEqual(mockPage1.items);

      // Fetch page 2
      result.current.fetchNextPage();
      await waitFor(() => {
        expect(result.current.data?.pages?.length).toBe(2);
      });
      expect(result.current.data?.pages?.[1].items).toEqual(mockPage2.items);

      // Fetch page 3
      result.current.fetchNextPage();
      await waitFor(() => {
        expect(result.current.data?.pages?.length).toBe(3);
      });
      expect(result.current.data?.pages?.[2].items).toEqual(mockPage3.items);
    });

    it('maintains correct pageParams array', async () => {
      mockQueryFn.mockResolvedValueOnce(mockPage1).mockResolvedValueOnce(mockPage2);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
          }),
        { wrapper: createQueryWrapper() }
      );

      // Wait for first page
      await waitFor(() => {
        expect(result.current.data?.pageParams?.length).toBe(1);
      });
      expect(result.current.data?.pageParams?.[0]).toBeUndefined();

      // Fetch page 2
      result.current.fetchNextPage();
      await waitFor(() => {
        expect(result.current.data?.pageParams?.length).toBe(2);
      });
      expect(result.current.data?.pageParams?.[1]).toBe('cursor-page-2');
    });
  });

  describe('filters', () => {
    it('passes filters to queryFn', async () => {
      mockQueryFn.mockResolvedValue(mockPage1);
      const filters: TestFilters = { category: 'electronics', status: 'active' };

      renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse, TestFilters>({
            queryKey: ['test', 'items', filters],
            queryFn: mockQueryFn,
            filters,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(mockQueryFn).toHaveBeenCalledWith({
          cursor: undefined,
          filters,
        });
      });
    });

    it('passes filters with cursor on subsequent pages', async () => {
      mockQueryFn.mockResolvedValueOnce(mockPage1).mockResolvedValueOnce(mockPage2);
      const filters: TestFilters = { category: 'electronics' };

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse, TestFilters>({
            queryKey: ['test', 'items', filters],
            queryFn: mockQueryFn,
            filters,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.hasNextPage).toBe(true);
      });

      result.current.fetchNextPage();

      await waitFor(() => {
        expect(mockQueryFn).toHaveBeenLastCalledWith({
          cursor: 'cursor-page-2',
          filters,
        });
      });
    });
  });

  describe('options', () => {
    it('does not fetch when enabled is false', async () => {
      mockQueryFn.mockResolvedValue(mockPage1);

      renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
            enabled: false,
          }),
        { wrapper: createQueryWrapper() }
      );

      await new Promise((r) => setTimeout(r, 100));
      expect(mockQueryFn).not.toHaveBeenCalled();
    });

    it('respects custom staleTime', async () => {
      mockQueryFn.mockResolvedValue(mockPage1);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
            staleTime: 60000, // 1 minute
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Data should not be stale immediately
      // Note: Testing staleTime behavior requires more complex setup
      // This test verifies the option is accepted without errors
      expect(mockQueryFn).toHaveBeenCalledTimes(1);
    });

    it('respects custom retry option', async () => {
      const error = new Error('Network error');
      mockQueryFn.mockRejectedValue(error);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
            retry: 0, // Disable retries
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );

      // With retry: 0, should only be called once
      expect(mockQueryFn).toHaveBeenCalledTimes(1);
    });
  });

  describe('error handling', () => {
    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch items';
      mockQueryFn.mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
            retry: 0,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
          expect(result.current.error?.message).toBe(errorMessage);
        },
        { timeout: 5000 }
      );
    });

    it('sets isError to true on failure', async () => {
      mockQueryFn.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
            retry: 0,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      mockQueryFn.mockResolvedValue(mockPage1);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new data fetch', async () => {
      mockQueryFn.mockResolvedValue(mockPage1);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(mockQueryFn).toHaveBeenCalledTimes(1);
      });

      result.current.refetch();

      await waitFor(() => {
        expect(mockQueryFn).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('isFetchingNextPage', () => {
    it('is true while fetching next page', async () => {
      mockQueryFn.mockResolvedValueOnce(mockPage1);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items'],
            queryFn: mockQueryFn,
          }),
        { wrapper: createQueryWrapper() }
      );

      // Wait for first page
      await waitFor(() => {
        expect(result.current.hasNextPage).toBe(true);
      });

      // Now set up a delayed response for page 2
      let resolveNextPage: (value: TestResponse) => void;
      mockQueryFn.mockReturnValue(
        new Promise<TestResponse>((resolve) => {
          resolveNextPage = resolve;
        })
      );

      // Start fetching next page
      result.current.fetchNextPage();

      // Should be fetching
      await waitFor(() => {
        expect(result.current.isFetchingNextPage).toBe(true);
      });

      // Resolve the promise
      resolveNextPage!(mockPage2);

      // Should no longer be fetching
      await waitFor(() => {
        expect(result.current.isFetchingNextPage).toBe(false);
      });
    });
  });

  describe('maxPages option (TanStack Query v5 feature)', () => {
    it('accepts maxPages option without errors', async () => {
      mockQueryFn.mockResolvedValue(mockPage1);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items', 'with-max-pages'],
            queryFn: mockQueryFn,
            maxPages: 5,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Verify the query was successful and option was accepted
      expect(result.current.data?.pages?.length).toBe(1);
      expect(result.current.isError).toBe(false);
    });

    it('works correctly with maxPages set to 2', async () => {
      // Create pages with unique cursors
      const page1: TestResponse = {
        items: [{ id: 1, name: 'Item 1' }],
        pagination: { total: 5, has_more: true, next_cursor: 'cursor-2' },
      };
      const page2: TestResponse = {
        items: [{ id: 2, name: 'Item 2' }],
        pagination: { total: 5, has_more: true, next_cursor: 'cursor-3' },
      };
      const page3: TestResponse = {
        items: [{ id: 3, name: 'Item 3' }],
        pagination: { total: 5, has_more: true, next_cursor: 'cursor-4' },
      };

      mockQueryFn
        .mockResolvedValueOnce(page1)
        .mockResolvedValueOnce(page2)
        .mockResolvedValueOnce(page3);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items', 'max-pages-2'],
            queryFn: mockQueryFn,
            maxPages: 2, // Limit to 2 pages
          }),
        { wrapper: createQueryWrapper() }
      );

      // Wait for first page
      await waitFor(() => {
        expect(result.current.data?.pages?.length).toBe(1);
      });

      // Fetch page 2
      result.current.fetchNextPage();
      await waitFor(() => {
        expect(result.current.data?.pages?.length).toBe(2);
      });

      // Fetch page 3 - with maxPages=2, TanStack Query should keep only 2 pages
      result.current.fetchNextPage();
      await waitFor(() => {
        // maxPages limits stored pages - oldest page should be dropped
        expect(result.current.data?.pages?.length).toBe(2);
      });

      // Verify the newest pages are kept (page 2 and page 3)
      expect(result.current.data?.pages?.[0].items[0].id).toBe(2);
      expect(result.current.data?.pages?.[1].items[0].id).toBe(3);
    });

    it('does not limit pages when maxPages is undefined', async () => {
      mockQueryFn
        .mockResolvedValueOnce(mockPage1)
        .mockResolvedValueOnce(mockPage2)
        .mockResolvedValueOnce(mockPage3);

      const { result } = renderHook(
        () =>
          useCursorPaginatedQuery<TestResponse>({
            queryKey: ['test', 'items', 'no-max-pages'],
            queryFn: mockQueryFn,
            // No maxPages - should accumulate all pages
          }),
        { wrapper: createQueryWrapper() }
      );

      // Wait for first page
      await waitFor(() => {
        expect(result.current.data?.pages?.length).toBe(1);
      });

      // Fetch page 2
      result.current.fetchNextPage();
      await waitFor(() => {
        expect(result.current.data?.pages?.length).toBe(2);
      });

      // Fetch page 3
      result.current.fetchNextPage();
      await waitFor(() => {
        // All 3 pages should be accumulated
        expect(result.current.data?.pages?.length).toBe(3);
      });
    });
  });
});
