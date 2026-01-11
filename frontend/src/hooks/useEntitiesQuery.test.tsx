import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useEntitiesQuery, useEntityDetailQuery } from './useEntitiesQuery';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../services/api');
  return {
    ...actual,
    fetchEntities: vi.fn(),
    fetchEntity: vi.fn(),
  };
});

const mockFetchEntities = vi.mocked(api.fetchEntities);
const mockFetchEntity = vi.mocked(api.fetchEntity);

// Create a wrapper with QueryClientProvider
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('useEntitiesQuery', () => {
  const mockEntities: api.EntitySummary[] = [
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

  const mockResponse: api.EntityListResponse = {
    items: mockEntities,
    pagination: {
      total: 2,
      limit: 50,
      offset: 0,
      has_more: false,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchEntities.mockResolvedValue(mockResponse);
  });

  describe('basic functionality', () => {
    it('fetches entities on mount', async () => {
      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesQuery(), { wrapper });

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.entities).toEqual(mockEntities);
      expect(result.current.totalCount).toBe(2);
      expect(result.current.hasMore).toBe(false);
      expect(mockFetchEntities).toHaveBeenCalledTimes(1);
    });

    it('returns empty array when no entities', async () => {
      mockFetchEntities.mockResolvedValue({
        items: [],
        pagination: { total: 0, limit: 50, offset: 0, has_more: false },
      });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesQuery(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.entities).toEqual([]);
      expect(result.current.totalCount).toBe(0);
    });

    it('handles error state', async () => {
      const errorMessage = 'Network error';
      mockFetchEntities.mockRejectedValue(new Error(errorMessage));

      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesQuery(), { wrapper });

      // Wait for the query to fail (including any retries)
      await waitFor(
        () => {
          expect(result.current.error).not.toBeNull();
        },
        { timeout: 5000 }
      );

      expect(result.current.error?.message).toBe(errorMessage);
      expect(result.current.entities).toEqual([]);
    });
  });

  describe('filtering', () => {
    it('filters by entity type person', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesQuery({ entityType: 'person' }), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      expect(mockFetchEntities).toHaveBeenCalledWith(
        expect.objectContaining({ entity_type: 'person' })
      );
    });

    it('filters by entity type vehicle', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesQuery({ entityType: 'vehicle' }), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      expect(mockFetchEntities).toHaveBeenCalledWith(
        expect.objectContaining({ entity_type: 'vehicle' })
      );
    });

    it('does not filter when entity type is all', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesQuery({ entityType: 'all' }), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      const callArgs = mockFetchEntities.mock.calls[0][0];
      expect(callArgs?.entity_type).toBeUndefined();
    });

    it('filters by camera ID', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesQuery({ cameraId: 'front_door' }), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      expect(mockFetchEntities).toHaveBeenCalledWith(
        expect.objectContaining({ camera_id: 'front_door' })
      );
    });

    it('filters by time range 1h', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesQuery({ timeRange: '1h' }), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      const callArgs = mockFetchEntities.mock.calls[0][0];
      expect(callArgs?.since).toBeDefined();
      // Verify it's approximately 1 hour ago
      const sinceDate = new Date(callArgs?.since as string);
      const now = new Date();
      const diffMs = now.getTime() - sinceDate.getTime();
      const diffHours = diffMs / (60 * 60 * 1000);
      expect(diffHours).toBeCloseTo(1, 0);
    });

    it('filters by time range 24h', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesQuery({ timeRange: '24h' }), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      const callArgs = mockFetchEntities.mock.calls[0][0];
      expect(callArgs?.since).toBeDefined();
      const sinceDate = new Date(callArgs?.since as string);
      const now = new Date();
      const diffMs = now.getTime() - sinceDate.getTime();
      const diffHours = diffMs / (60 * 60 * 1000);
      expect(diffHours).toBeCloseTo(24, 0);
    });

    it('filters by time range 7d', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesQuery({ timeRange: '7d' }), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      const callArgs = mockFetchEntities.mock.calls[0][0];
      expect(callArgs?.since).toBeDefined();
      const sinceDate = new Date(callArgs?.since as string);
      const now = new Date();
      const diffMs = now.getTime() - sinceDate.getTime();
      const diffDays = diffMs / (24 * 60 * 60 * 1000);
      expect(diffDays).toBeCloseTo(7, 0);
    });

    it('filters by time range 30d', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesQuery({ timeRange: '30d' }), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      const callArgs = mockFetchEntities.mock.calls[0][0];
      expect(callArgs?.since).toBeDefined();
      const sinceDate = new Date(callArgs?.since as string);
      const now = new Date();
      const diffMs = now.getTime() - sinceDate.getTime();
      const diffDays = diffMs / (24 * 60 * 60 * 1000);
      expect(diffDays).toBeCloseTo(30, 0);
    });

    it('does not filter by time when timeRange is all', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesQuery({ timeRange: 'all' }), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      const callArgs = mockFetchEntities.mock.calls[0][0];
      expect(callArgs?.since).toBeUndefined();
    });

    it('combines multiple filters', async () => {
      const wrapper = createWrapper();
      renderHook(
        () =>
          useEntitiesQuery({
            entityType: 'person',
            cameraId: 'front_door',
            timeRange: '24h',
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
        })
      );

      const callArgs = mockFetchEntities.mock.calls[0][0];
      expect(callArgs?.since).toBeDefined();
    });
  });

  describe('options', () => {
    it('respects enabled option', async () => {
      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesQuery({ enabled: false }), { wrapper });

      // Wait a bit to ensure no fetch happens
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(mockFetchEntities).not.toHaveBeenCalled();
      expect(result.current.isLoading).toBe(false);
    });

    it('respects limit option', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesQuery({ limit: 100 }), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      expect(mockFetchEntities).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 100 })
      );
    });

    it('uses default limit of 50', async () => {
      const wrapper = createWrapper();
      renderHook(() => useEntitiesQuery(), { wrapper });

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalled();
      });

      expect(mockFetchEntities).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 50 })
      );
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const wrapper = createWrapper();
      const { result } = renderHook(() => useEntitiesQuery(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockFetchEntities).toHaveBeenCalledTimes(1);

      // Trigger refetch
      await result.current.refetch();

      expect(mockFetchEntities).toHaveBeenCalledTimes(2);
    });
  });
});

describe('useEntityDetailQuery', () => {
  const mockEntityDetail: api.EntityDetail = {
    id: 'entity-001',
    entity_type: 'person',
    first_seen: '2024-01-15T08:00:00Z',
    last_seen: '2024-01-15T10:00:00Z',
    appearance_count: 5,
    cameras_seen: ['front_door', 'back_yard'],
    thumbnail_url: 'https://example.com/thumb1.jpg',
    appearances: [
      {
        detection_id: 'det-001',
        camera_id: 'front_door',
        camera_name: 'Front Door',
        timestamp: '2024-01-15T10:00:00Z',
        thumbnail_url: 'https://example.com/thumb1.jpg',
        similarity_score: 0.95,
        attributes: {},
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchEntity.mockResolvedValue(mockEntityDetail);
  });

  it('fetches entity detail when ID is provided', async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useEntityDetailQuery('entity-001'), { wrapper });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockEntityDetail);
    expect(mockFetchEntity).toHaveBeenCalledWith('entity-001');
  });

  it('does not fetch when ID is undefined', async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useEntityDetailQuery(undefined), { wrapper });

    // Wait a bit to ensure no fetch happens
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(mockFetchEntity).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  it('respects enabled option', async () => {
    const wrapper = createWrapper();
    renderHook(() => useEntityDetailQuery('entity-001', { enabled: false }), { wrapper });

    // Wait a bit to ensure no fetch happens
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(mockFetchEntity).not.toHaveBeenCalled();
  });

  it('handles error state', async () => {
    const errorMessage = 'Entity not found';
    mockFetchEntity.mockRejectedValue(new Error(errorMessage));

    const wrapper = createWrapper();
    const { result } = renderHook(() => useEntityDetailQuery('entity-001'), { wrapper });

    // Wait for the query to fail (including any retries)
    await waitFor(
      () => {
        expect(result.current.error).not.toBeNull();
      },
      { timeout: 5000 }
    );

    expect(result.current.error?.message).toBe(errorMessage);
    expect(result.current.data).toBeUndefined();
  });
});
