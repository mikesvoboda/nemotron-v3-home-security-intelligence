import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { type ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useEntitiesInfiniteQuery, entitiesInfiniteQueryKeys } from './useEntitiesInfiniteQuery';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../services/api');
  return {
    ...actual,
    fetchEntities: vi.fn(),
  };
});

const mockFetchEntities = vi.mocked(api.fetchEntities);

// Create a wrapper with QueryClientProvider
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('useEntitiesInfiniteQuery', () => {
  const mockEntitiesPage1: api.EntitySummary[] = [
    {
      id: 'entity-001',
      entity_type: 'person',
      first_seen: '2024-01-15T08:00:00Z',
      last_seen: '2024-01-15T10:00:00Z',
      appearance_count: 5,
      cameras_seen: ['front_door', 'back_yard'],
      thumbnail_url: 'https://example.com/thumb1.jpg',
    },
    {
      id: 'entity-002',
      entity_type: 'vehicle',
      first_seen: '2024-01-15T09:00:00Z',
      last_seen: '2024-01-15T09:30:00Z',
      appearance_count: 2,
      cameras_seen: ['driveway'],
      thumbnail_url: null,
    },
  ];

  const mockEntitiesPage2: api.EntitySummary[] = [
    {
      id: 'entity-003',
      entity_type: 'person',
      first_seen: '2024-01-14T08:00:00Z',
      last_seen: '2024-01-14T10:00:00Z',
      appearance_count: 3,
      cameras_seen: ['front_door'],
      thumbnail_url: 'https://example.com/thumb3.jpg',
    },
    {
      id: 'entity-004',
      entity_type: 'vehicle',
      first_seen: '2024-01-14T09:00:00Z',
      last_seen: '2024-01-14T09:30:00Z',
      appearance_count: 1,
      cameras_seen: ['driveway'],
      thumbnail_url: null,
    },
  ];

  const mockResponsePage1: api.EntityListResponse = {
    items: mockEntitiesPage1,
    pagination: {
      total: 4,
      limit: 2,
      offset: 0,
      has_more: true,
      next_cursor: 'cursor_page2',
    },
  };

  const mockResponsePage2: api.EntityListResponse = {
    items: mockEntitiesPage2,
    pagination: {
      total: 4,
      limit: 2,
      offset: 2,
      has_more: false,
      next_cursor: null,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchEntities.mockResolvedValue(mockResponsePage1);
  });

  describe('basic functionality', () => {
    it('fetches initial page on mount', async () => {
      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesInfiniteQuery(), { wrapper });

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.entities).toEqual(mockEntitiesPage1);
      expect(result.current.totalCount).toBe(4);
      expect(result.current.hasNextPage).toBe(true);
      expect(mockFetchEntities).toHaveBeenCalledTimes(1);
    });

    it('returns empty array when no entities', async () => {
      mockFetchEntities.mockResolvedValue({
        items: [],
        pagination: { total: 0, limit: 50, offset: 0, has_more: false },
      });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesInfiniteQuery(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.entities).toEqual([]);
      expect(result.current.totalCount).toBe(0);
      expect(result.current.hasNextPage).toBe(false);
    });

    it('handles error state', async () => {
      const errorMessage = 'Network error';
      mockFetchEntities.mockRejectedValue(new Error(errorMessage));

      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesInfiniteQuery(), { wrapper });

      await waitFor(
        () => {
          expect(result.current.error).not.toBeNull();
        },
        { timeout: 5000 }
      );

      expect(result.current.error?.message).toBe(errorMessage);
      expect(result.current.isError).toBe(true);
      expect(result.current.entities).toEqual([]);
    });
  });

  describe('infinite scroll pagination', () => {
    it('fetches next page with cursor', async () => {
      mockFetchEntities
        .mockResolvedValueOnce(mockResponsePage1)
        .mockResolvedValueOnce(mockResponsePage2);

      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesInfiniteQuery({ limit: 2 }), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.hasNextPage).toBe(true);
      expect(result.current.entities).toHaveLength(2);

      // Fetch next page
      act(() => {
        result.current.fetchNextPage();
      });

      await waitFor(() => {
        expect(result.current.isFetchingNextPage).toBe(false);
      });

      // Should have fetched with cursor
      expect(mockFetchEntities).toHaveBeenCalledTimes(2);
      expect(mockFetchEntities).toHaveBeenLastCalledWith(
        expect.objectContaining({ cursor: 'cursor_page2' })
      );

      // Should have all entities flattened
      expect(result.current.entities).toHaveLength(4);
      expect(result.current.entities).toEqual([...mockEntitiesPage1, ...mockEntitiesPage2]);
      expect(result.current.hasNextPage).toBe(false);
    });

    it('provides isFetchingNextPage state', async () => {
      let resolveSecondPage: (value: api.EntityListResponse) => void;
      const secondPagePromise = new Promise<api.EntityListResponse>((resolve) => {
        resolveSecondPage = resolve;
      });

      mockFetchEntities
        .mockResolvedValueOnce(mockResponsePage1)
        .mockReturnValueOnce(secondPagePromise);

      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesInfiniteQuery({ limit: 2 }), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Fetch next page
      act(() => {
        result.current.fetchNextPage();
      });

      await waitFor(() => {
        expect(result.current.isFetchingNextPage).toBe(true);
      });

      // Resolve second page
      act(() => {
        resolveSecondPage!(mockResponsePage2);
      });

      await waitFor(() => {
        expect(result.current.isFetchingNextPage).toBe(false);
      });
    });

    it('maintains totalCount from first page across pagination', async () => {
      mockFetchEntities
        .mockResolvedValueOnce(mockResponsePage1)
        .mockResolvedValueOnce(mockResponsePage2);

      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesInfiniteQuery({ limit: 2 }), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.totalCount).toBe(4);

      // Fetch next page
      act(() => {
        result.current.fetchNextPage();
      });

      await waitFor(() => {
        expect(result.current.entities).toHaveLength(4);
      });

      // Total count should still be 4 (from first page)
      expect(result.current.totalCount).toBe(4);
    });

    it('stops pagination when has_more is false', async () => {
      mockFetchEntities.mockResolvedValue({
        items: mockEntitiesPage1,
        pagination: { total: 2, limit: 50, offset: 0, has_more: false },
      });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesInfiniteQuery(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.hasNextPage).toBe(false);
    });
  });

  describe('filtering', () => {
    it('passes entity_type filter to API', async () => {
      const wrapper = createWrapper();
      renderHook(
        () => useEntitiesInfiniteQuery({ filters: { entity_type: 'person' } }),
        { wrapper }
      );

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      expect(mockFetchEntities).toHaveBeenCalledWith(
        expect.objectContaining({ entity_type: 'person' })
      );
    });

    it('passes camera_id filter to API', async () => {
      const wrapper = createWrapper();
      renderHook(
        () => useEntitiesInfiniteQuery({ filters: { camera_id: 'front_door' } }),
        { wrapper }
      );

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      expect(mockFetchEntities).toHaveBeenCalledWith(
        expect.objectContaining({ camera_id: 'front_door' })
      );
    });

    it('passes since filter to API', async () => {
      const sinceDate = '2024-01-15T00:00:00Z';
      const wrapper = createWrapper();
      renderHook(
        () => useEntitiesInfiniteQuery({ filters: { since: sinceDate } }),
        { wrapper }
      );

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      expect(mockFetchEntities).toHaveBeenCalledWith(
        expect.objectContaining({ since: sinceDate })
      );
    });

    it('combines multiple filters', async () => {
      const wrapper = createWrapper();
      renderHook(
        () =>
          useEntitiesInfiniteQuery({
            filters: {
              entity_type: 'person',
              camera_id: 'front_door',
              since: '2024-01-15T00:00:00Z',
            },
          }),
        { wrapper }
      );

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      expect(mockFetchEntities).toHaveBeenCalledWith(
        expect.objectContaining({
          entity_type: 'person',
          camera_id: 'front_door',
          since: '2024-01-15T00:00:00Z',
        })
      );
    });
  });

  describe('options', () => {
    it('respects enabled option', async () => {
      const wrapper = createWrapper();
      const { result } = renderHook(
        () => useEntitiesInfiniteQuery({ enabled: false }),
        { wrapper }
      );

      // Wait a bit to ensure no fetch happens
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(mockFetchEntities).not.toHaveBeenCalled();
      expect(result.current.isLoading).toBe(false);
    });

    it('respects limit option', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesInfiniteQuery({ limit: 25 }), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      expect(mockFetchEntities).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 25 })
      );
    });

    it('uses default limit of 50', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesInfiniteQuery(), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      expect(mockFetchEntities).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 50 })
      );
    });
  });

  describe('refetch', () => {
    it('provides refetch function that refreshes data', async () => {
      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesInfiniteQuery(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockFetchEntities).toHaveBeenCalledTimes(1);

      // Trigger refetch
      act(() => {
        result.current.refetch();
      });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('pages property', () => {
    it('exposes raw pages data', async () => {
      mockFetchEntities
        .mockResolvedValueOnce(mockResponsePage1)
        .mockResolvedValueOnce(mockResponsePage2);

      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesInfiniteQuery({ limit: 2 }), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.pages).toHaveLength(1);
      expect(result.current.pages?.[0]).toEqual(mockResponsePage1);

      // Fetch next page
      act(() => {
        result.current.fetchNextPage();
      });

      await waitFor(() => {
        expect(result.current.pages).toHaveLength(2);
      });

      expect(result.current.pages?.[0]).toEqual(mockResponsePage1);
      expect(result.current.pages?.[1]).toEqual(mockResponsePage2);
    });
  });
});

describe('entitiesInfiniteQueryKeys', () => {
  it('generates correct query keys', () => {
    expect(entitiesInfiniteQueryKeys.all).toEqual(['entities']);
    expect(entitiesInfiniteQueryKeys.lists()).toEqual(['entities', 'list']);
    expect(entitiesInfiniteQueryKeys.infinite()).toEqual([
      'entities',
      'infinite',
      { filters: undefined, limit: undefined },
    ]);
    expect(
      entitiesInfiniteQueryKeys.infinite({ entity_type: 'person' }, 25)
    ).toEqual(['entities', 'infinite', { filters: { entity_type: 'person' }, limit: 25 }]);
    expect(entitiesInfiniteQueryKeys.detail('entity-001')).toEqual([
      'entities',
      'detail',
      'entity-001',
    ]);
  });
});
