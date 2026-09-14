/**
 * Unit tests for useAdminMutations hooks
 *
 * Tests TanStack Query mutations for admin operations including:
 * - useSeedCamerasMutation: Seed test cameras
 * - useSeedEventsMutation: Seed test events
 * - useSeedPipelineLatencyMutation: Seed pipeline latency data
 * - useClearSeededDataMutation: Clear all seeded data
 * - useOrphanCleanupMutation: Run orphan file cleanup
 * - useClearCacheMutation: Clear Redis cache
 * - useFlushQueuesMutation: Flush processing queues
 * - useAdminMutations: Combined hook returning all mutations
 *
 * @module hooks/__tests__/useAdminMutations
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  useSeedCamerasMutation,
  useSeedEventsMutation,
  useSeedPipelineLatencyMutation,
  useClearSeededDataMutation,
  useOrphanCleanupMutation,
  useClearCacheMutation,
  useFlushQueuesMutation,
  useAdminMutations,
  type SeedCamerasRequest,
  type SeedCamerasResponse,
  type SeedEventsRequest,
  type SeedEventsResponse,
  type SeedPipelineLatencyRequest,
  type SeedPipelineLatencyResponse,
  type ClearDataRequest,
  type ClearDataResponse,
  type OrphanCleanupRequest,
  type OrphanCleanupResponse,
  type ClearCacheResponse,
  type FlushQueuesResponse,
} from '../useAdminMutations';

// ============================================================================
// Test Utilities
// ============================================================================

/**
 * Create a test wrapper with a fresh QueryClient for each test.
 * Disables retries and caching to ensure tests are isolated.
 */
function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

/**
 * Create a mock fetch function that can be configured per-test.
 */
function createMockFetch() {
  return vi.fn();
}

// ============================================================================
// Test Data Fixtures
// ============================================================================

const mockSeedCamerasResponse: SeedCamerasResponse = {
  cameras: [
    { id: 'cam-1', name: 'Front Door' },
    { id: 'cam-2', name: 'Backyard' },
  ],
  cleared: 0,
  created: 2,
};

const mockSeedEventsResponse: SeedEventsResponse = {
  events_cleared: 0,
  events_created: 10,
  detections_cleared: 0,
  detections_created: 25,
};

const mockSeedPipelineLatencyResponse: SeedPipelineLatencyResponse = {
  message: 'Successfully seeded pipeline latency data',
  samples_per_stage: 100,
  time_span_hours: 24,
  stages_seeded: ['detection', 'enrichment', 'risk_analysis'],
};

const mockClearDataResponse: ClearDataResponse = {
  cameras_cleared: 5,
  events_cleared: 100,
  detections_cleared: 250,
};

const mockOrphanCleanupResponse: OrphanCleanupResponse = {
  scanned_files: 150,
  orphaned_files: 10,
  deleted_files: 8,
  deleted_bytes: 1048576,
  deleted_bytes_formatted: '1.0 MB',
  failed_count: 2,
  failed_deletions: ['/path/to/file1.jpg', '/path/to/file2.jpg'],
  duration_seconds: 2.5,
  dry_run: false,
  skipped_young: 5,
  skipped_size_limit: 0,
};

const mockClearCacheResponse: ClearCacheResponse = {
  keys_cleared: 42,
  cache_types: ['events', 'detections', 'cameras'],
  duration_seconds: 0.5,
  message: 'Successfully cleared 42 cache keys',
};

const mockFlushQueuesResponse: FlushQueuesResponse = {
  queues_flushed: ['detection_queue', 'enrichment_queue'],
  items_cleared: {
    detection_queue: 10,
    enrichment_queue: 5,
  },
  duration_seconds: 0.3,
  message: 'Successfully flushed 2 queues',
};

// ============================================================================
// Setup/Teardown
// ============================================================================

let mockFetch: ReturnType<typeof createMockFetch>;

beforeEach(() => {
  mockFetch = createMockFetch();
  globalThis.fetch = mockFetch;
  vi.clearAllMocks();
});

// ============================================================================
// useSeedCamerasMutation Tests
// ============================================================================

describe('useSeedCamerasMutation', () => {
  it('seeds cameras successfully', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockSeedCamerasResponse),
    } as Response);

    const { result } = renderHook(() => useSeedCamerasMutation(), {
      wrapper: createTestWrapper(),
    });

    const request: SeedCamerasRequest = {
      count: 2,
      clear_existing: false,
    };

    result.current.mutate(request);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockSeedCamerasResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/admin/seed/cameras',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(request),
      })
    );
  });

  it('handles error response', async () => {
    const errorMessage = 'Invalid camera count';
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.resolve({ detail: errorMessage }),
    } as Response);

    const { result } = renderHook(() => useSeedCamerasMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({ count: 0 });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe(errorMessage);
  });

  it('calls endpoint with correct headers', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockSeedCamerasResponse),
    } as Response);

    const { result } = renderHook(() => useSeedCamerasMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({ count: 2 });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      })
    );
  });

  it('tracks loading state correctly', async () => {
    mockFetch.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: () => Promise.resolve(mockSeedCamerasResponse),
              } as Response),
            100
          )
        )
    );

    const { result } = renderHook(() => useSeedCamerasMutation(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isPending).toBe(false);

    result.current.mutate({ count: 2 });

    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

// ============================================================================
// useSeedEventsMutation Tests
// ============================================================================

describe('useSeedEventsMutation', () => {
  it('seeds events successfully', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockSeedEventsResponse),
    } as Response);

    const { result } = renderHook(() => useSeedEventsMutation(), {
      wrapper: createTestWrapper(),
    });

    const request: SeedEventsRequest = {
      count: 10,
      clear_existing: false,
    };

    result.current.mutate(request);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockSeedEventsResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/admin/seed/events',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(request),
      })
    );
  });

  it('handles validation errors', async () => {
    const errorMessage = 'Event count must be between 1 and 100';
    mockFetch.mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      json: () => Promise.resolve({ detail: errorMessage }),
    } as Response);

    const { result } = renderHook(() => useSeedEventsMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({ count: 150 });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe(errorMessage);
  });
});

// ============================================================================
// useSeedPipelineLatencyMutation Tests
// ============================================================================

describe('useSeedPipelineLatencyMutation', () => {
  it('seeds pipeline latency data successfully', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockSeedPipelineLatencyResponse),
    } as Response);

    const { result } = renderHook(() => useSeedPipelineLatencyMutation(), {
      wrapper: createTestWrapper(),
    });

    const request: SeedPipelineLatencyRequest = {
      num_samples: 100,
      time_span_hours: 24,
    };

    result.current.mutate(request);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockSeedPipelineLatencyResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/admin/seed/pipeline-latency',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(request),
      })
    );
  });

  it('handles optional parameters', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockSeedPipelineLatencyResponse),
    } as Response);

    const { result } = renderHook(() => useSeedPipelineLatencyMutation(), {
      wrapper: createTestWrapper(),
    });

    // Call with empty object (all params optional)
    result.current.mutate({});

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify({}),
      })
    );
  });
});

// ============================================================================
// useClearSeededDataMutation Tests
// ============================================================================

describe('useClearSeededDataMutation', () => {
  it('clears seeded data with confirmation', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockClearDataResponse),
    } as Response);

    const { result } = renderHook(() => useClearSeededDataMutation(), {
      wrapper: createTestWrapper(),
    });

    const request: ClearDataRequest = {
      confirm: 'DELETE_ALL_DATA',
    };

    result.current.mutate(request);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockClearDataResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/admin/seed/clear',
      expect.objectContaining({
        method: 'DELETE',
        body: JSON.stringify(request),
      })
    );
  });

  it('rejects without proper confirmation', async () => {
    const errorMessage = 'Confirmation string must be exactly DELETE_ALL_DATA';
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.resolve({ detail: errorMessage }),
    } as Response);

    const { result } = renderHook(() => useClearSeededDataMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({ confirm: 'WRONG_STRING' });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe(errorMessage);
  });
});

// ============================================================================
// useOrphanCleanupMutation Tests
// ============================================================================

describe('useOrphanCleanupMutation', () => {
  it('runs orphan cleanup successfully', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockOrphanCleanupResponse),
    } as Response);

    const { result } = renderHook(() => useOrphanCleanupMutation(), {
      wrapper: createTestWrapper(),
    });

    const request: OrphanCleanupRequest = {
      dry_run: false,
      min_age_hours: 24,
      max_delete_gb: 10,
    };

    result.current.mutate(request);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockOrphanCleanupResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/admin/cleanup/orphans',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(request),
      })
    );
  });

  it('supports dry run mode', async () => {
    const dryRunResponse: OrphanCleanupResponse = {
      ...mockOrphanCleanupResponse,
      dry_run: true,
      deleted_files: 0,
      deleted_bytes: 0,
    };

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(dryRunResponse),
    } as Response);

    const { result } = renderHook(() => useOrphanCleanupMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({ dry_run: true });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.dry_run).toBe(true);
    expect(result.current.data?.deleted_files).toBe(0);
  });
});

// ============================================================================
// useClearCacheMutation Tests
// ============================================================================

describe('useClearCacheMutation', () => {
  it('clears cache successfully', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockClearCacheResponse),
    } as Response);

    const { result } = renderHook(() => useClearCacheMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockClearCacheResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/admin/maintenance/clear-cache',
      expect.objectContaining({
        method: 'POST',
      })
    );
  });

  it('requires no parameters', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockClearCacheResponse),
    } as Response);

    const { result } = renderHook(() => useClearCacheMutation(), {
      wrapper: createTestWrapper(),
    });

    // Call with no parameters
    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Verify no body sent
    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.not.objectContaining({
        body: expect.anything(),
      })
    );
  });
});

// ============================================================================
// useFlushQueuesMutation Tests
// ============================================================================

describe('useFlushQueuesMutation', () => {
  it('flushes queues successfully', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockFlushQueuesResponse),
    } as Response);

    const { result } = renderHook(() => useFlushQueuesMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockFlushQueuesResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/admin/maintenance/flush-queues',
      expect.objectContaining({
        method: 'POST',
      })
    );
  });

  it('handles empty queues', async () => {
    const emptyResponse: FlushQueuesResponse = {
      queues_flushed: [],
      items_cleared: {},
      duration_seconds: 0.1,
      message: 'No items to flush',
    };

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(emptyResponse),
    } as Response);

    const { result } = renderHook(() => useFlushQueuesMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.queues_flushed).toEqual([]);
  });
});

// ============================================================================
// useAdminMutations Combined Hook Tests
// ============================================================================

describe('useAdminMutations', () => {
  it('returns all mutation hooks', () => {
    const { result } = renderHook(() => useAdminMutations(), {
      wrapper: createTestWrapper(),
    });

    // Verify all mutations are present
    expect(result.current.seedCameras).toBeDefined();
    expect(result.current.seedEvents).toBeDefined();
    expect(result.current.seedPipelineLatency).toBeDefined();
    expect(result.current.clearSeededData).toBeDefined();
    expect(result.current.orphanCleanup).toBeDefined();
    expect(result.current.clearCache).toBeDefined();
    expect(result.current.flushQueues).toBeDefined();

    // Verify they are mutation objects
    expect(result.current.seedCameras.mutate).toBeInstanceOf(Function);
    expect(result.current.seedEvents.mutate).toBeInstanceOf(Function);
    expect(result.current.seedPipelineLatency.mutate).toBeInstanceOf(Function);
    expect(result.current.clearSeededData.mutate).toBeInstanceOf(Function);
    expect(result.current.orphanCleanup.mutate).toBeInstanceOf(Function);
    expect(result.current.clearCache.mutate).toBeInstanceOf(Function);
    expect(result.current.flushQueues.mutate).toBeInstanceOf(Function);
  });

  it('allows using multiple mutations independently', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    } as Response);

    const { result } = renderHook(() => useAdminMutations(), {
      wrapper: createTestWrapper(),
    });

    // Trigger multiple mutations
    result.current.seedCameras.mutate({ count: 2 });

    await waitFor(() => {
      expect(result.current.seedCameras.isSuccess).toBe(true);
    });

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockClearCacheResponse),
    } as Response);

    result.current.clearCache.mutate();

    await waitFor(() => {
      expect(result.current.clearCache.isSuccess).toBe(true);
    });

    // Both mutations should maintain their own state
    expect(result.current.seedCameras.isSuccess).toBe(true);
    expect(result.current.clearCache.isSuccess).toBe(true);
  });
});

// ============================================================================
// Cache Invalidation Tests
// ============================================================================

describe('Cache Invalidation', () => {
  it('invalidates camera queries after seeding cameras', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockSeedCamerasResponse),
    } as Response);

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useSeedCamerasMutation(), { wrapper });

    result.current.mutate({ count: 2 });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Should invalidate camera queries
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: expect.arrayContaining(['cameras']),
      })
    );
  });

  it('invalidates multiple query keys after clearing seeded data', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockClearDataResponse),
    } as Response);

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useClearSeededDataMutation(), { wrapper });

    result.current.mutate({ confirm: 'DELETE_ALL_DATA' });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Should invalidate cameras, events, detections, and system stats
    expect(invalidateSpy).toHaveBeenCalledTimes(5);
  });
});

// ============================================================================
// Error Handling Tests
// ============================================================================

describe('Error Handling', () => {
  it('extracts error message from JSON response', async () => {
    const errorDetail = 'Custom error message from API';
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({ detail: errorDetail }),
    } as Response);

    const { result } = renderHook(() => useSeedCamerasMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({ count: 2 });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe(errorDetail);
  });

  it('falls back to status text when JSON parsing fails', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      json: () => Promise.reject(new Error('Invalid JSON')),
    } as unknown as Response);

    const { result } = renderHook(() => useSeedCamerasMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({ count: 2 });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toContain('503');
    expect(result.current.error?.message).toContain('Service Unavailable');
  });

  it('handles network errors', async () => {
    mockFetch.mockRejectedValue(new Error('Network request failed'));

    const { result } = renderHook(() => useSeedCamerasMutation(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({ count: 2 });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe('Network request failed');
  });
});
