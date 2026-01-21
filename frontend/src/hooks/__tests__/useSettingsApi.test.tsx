/**
 * Unit tests for useSettingsApi hooks
 *
 * Tests TanStack Query integration for settings API:
 * - useSettingsQuery: Fetch current system settings
 * - useUpdateSettings: Update system settings
 * - useSettingsApi: Combined hook for query and mutation
 *
 * @module hooks/__tests__/useSettingsApi
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  useSettingsQuery,
  useUpdateSettings,
  useSettingsApi,
  type UseSettingsOptions,
  type SettingsResponse,
  type SettingsUpdate,
} from '../useSettingsApi';

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

const mockSettingsResponse: SettingsResponse = {
  detection: {
    confidence_threshold: 0.5,
    fast_path_threshold: 0.85,
  },
  batch: {
    window_seconds: 90,
    idle_timeout_seconds: 30,
  },
  severity: {
    low_max: 30,
    medium_max: 60,
    high_max: 85,
  },
  features: {
    vision_extraction_enabled: true,
    reid_enabled: true,
    scene_change_enabled: true,
    clip_generation_enabled: true,
    image_quality_enabled: false,
    background_eval_enabled: true,
  },
  rate_limiting: {
    enabled: true,
    requests_per_minute: 100,
    burst_size: 20,
  },
  queue: {
    max_size: 1000,
    backpressure_threshold: 0.8,
  },
  retention: {
    days: 30,
    log_days: 7,
  },
};

// ============================================================================
// Setup/Teardown
// ============================================================================

let mockFetch: ReturnType<typeof createMockFetch>;

beforeEach(() => {
  mockFetch = createMockFetch();
  globalThis.fetch = mockFetch;
  vi.clearAllMocks();
  mockFetch.mockResolvedValue({
    ok: true,
    json: async () => mockSettingsResponse,
  } as Response);
});

// ============================================================================
// useSettingsQuery Tests
// ============================================================================

describe('useSettingsQuery', () => {
  it('fetches settings on mount', async () => {
    const { result } = renderHook(() => useSettingsQuery(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.settings).toBeUndefined();

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.settings).toEqual(mockSettingsResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/settings',
      expect.objectContaining({
        method: 'GET',
      })
    );
  });

  it('does not fetch when enabled is false', async () => {
    const options: UseSettingsOptions = { enabled: false };

    renderHook(() => useSettingsQuery(options), {
      wrapper: createTestWrapper(),
    });

    // Wait to ensure no fetch happens
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('handles error state', async () => {
    const errorMessage = 'Failed to fetch settings';
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => ({ detail: errorMessage }),
    } as Response);

    const { result } = renderHook(() => useSettingsQuery(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe(errorMessage);
    expect(result.current.settings).toBeUndefined();
  });

  it('calls endpoint with correct headers', async () => {
    const { result } = renderHook(() => useSettingsQuery(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
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

  it('supports custom stale time', async () => {
    const options: UseSettingsOptions = { staleTime: 60000 };

    const { result } = renderHook(() => useSettingsQuery(options), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.settings).toEqual(mockSettingsResponse);
  });

  it('supports refetch interval for polling', async () => {
    const options: UseSettingsOptions = { refetchInterval: 5000 };

    const { result } = renderHook(() => useSettingsQuery(options), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.settings).toEqual(mockSettingsResponse);
  });

  it('provides refetch function', async () => {
    const { result } = renderHook(() => useSettingsQuery(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);

    await result.current.refetch();

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('tracks fetching state correctly', async () => {
    const { result } = renderHook(() => useSettingsQuery(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isFetching).toBe(false);

    const refetchPromise = result.current.refetch();

    await waitFor(() => {
      expect(result.current.isFetching).toBe(true);
    });

    await refetchPromise;

    await waitFor(() => {
      expect(result.current.isFetching).toBe(false);
    });
  });

  it('returns correct status flags', async () => {
    const { result } = renderHook(() => useSettingsQuery(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isError).toBe(false);
    expect(result.current.isSuccess).toBe(false);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.isError).toBe(false);
  });

  it('extracts error message from API response', async () => {
    const errorDetail = 'Database connection failed';
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      json: async () => ({ detail: errorDetail }),
    } as Response);

    const { result } = renderHook(() => useSettingsQuery(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(Error);
    });

    expect(result.current.error?.message).toBe(errorDetail);
  });

  it('falls back to status text when JSON parsing fails', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => {
        throw new Error('Invalid JSON');
      },
    } as unknown as Response);

    const { result } = renderHook(() => useSettingsQuery(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(Error);
    });

    expect(result.current.error?.message).toContain('500');
    expect(result.current.error?.message).toContain('Internal Server Error');
  });
});

// ============================================================================
// useUpdateSettings Tests
// ============================================================================

describe('useUpdateSettings', () => {
  it('updates settings successfully', async () => {
    const updatedSettings: SettingsResponse = {
      ...mockSettingsResponse,
      detection: {
        confidence_threshold: 0.6,
        fast_path_threshold: 0.9,
      },
    };

    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => updatedSettings,
    } as Response);

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createTestWrapper(),
    });

    const update: SettingsUpdate = {
      detection: {
        confidence_threshold: 0.6,
        fast_path_threshold: 0.9,
      },
    };

    result.current.mutate(update);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(updatedSettings);
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/settings',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify(update),
      })
    );
  });

  it('supports partial updates', async () => {
    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createTestWrapper(),
    });

    const partialUpdate: SettingsUpdate = {
      features: {
        image_quality_enabled: true,
      },
    };

    result.current.mutate(partialUpdate);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify(partialUpdate),
      })
    );
  });

  it('handles validation errors', async () => {
    const errorMessage = 'Confidence threshold must be between 0.0 and 1.0';
    mockFetch.mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      json: async () => ({ detail: errorMessage }),
    } as Response);

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({
      detection: {
        confidence_threshold: 1.5,
      },
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe(errorMessage);
  });

  it('tracks pending state correctly', async () => {
    mockFetch.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: async () => mockSettingsResponse,
              } as Response),
            100
          )
        )
    );

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isPending).toBe(false);

    result.current.mutate({
      detection: { confidence_threshold: 0.6 },
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('supports async mutation', async () => {
    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createTestWrapper(),
    });

    const response = await result.current.mutateAsync({
      retention: { days: 60 },
    });

    expect(response).toEqual(mockSettingsResponse);
    expect(result.current.isSuccess).toBe(true);
  });

  it('resets mutation state', async () => {
    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({
      features: { reid_enabled: false },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    result.current.reset();

    expect(result.current.isSuccess).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  it('updates cache on success', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    const setQueryDataSpy = vi.spyOn(queryClient, 'setQueryData');

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useUpdateSettings(), { wrapper });

    result.current.mutate({
      detection: { confidence_threshold: 0.7 },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Should update cache with new data
    expect(setQueryDataSpy).toHaveBeenCalled();
  });

  it('invalidates cache on success', async () => {
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

    const { result } = renderHook(() => useUpdateSettings(), { wrapper });

    result.current.mutate({
      batch: { window_seconds: 120 },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Should invalidate settings queries
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: expect.arrayContaining(['settings']),
      })
    );
  });

  it('handles network errors', async () => {
    mockFetch.mockRejectedValue(new Error('Network request failed'));

    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({
      features: { reid_enabled: false },
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe('Network request failed');
  });

  it('calls endpoint with correct headers', async () => {
    const { result } = renderHook(() => useUpdateSettings(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({
      detection: { confidence_threshold: 0.6 },
    });

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
});

// ============================================================================
// useSettingsApi Combined Hook Tests
// ============================================================================

describe('useSettingsApi', () => {
  it('returns both query and mutation', async () => {
    const { result } = renderHook(() => useSettingsApi(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Verify query properties
    expect(result.current.settings).toBeDefined();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.isFetching).toBe(false);
    expect(result.current.isSuccess).toBe(true);
    expect(result.current.isError).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.refetch).toBeInstanceOf(Function);

    // Verify mutation object
    expect(result.current.updateMutation).toBeDefined();
    expect(result.current.updateMutation.mutate).toBeInstanceOf(Function);
    expect(result.current.updateMutation.mutateAsync).toBeInstanceOf(Function);
  });

  it('allows fetching and updating independently', async () => {
    const { result } = renderHook(() => useSettingsApi(), {
      wrapper: createTestWrapper(),
    });

    // Wait for initial fetch
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.settings).toEqual(mockSettingsResponse);

    // Trigger update
    const updatedSettings: SettingsResponse = {
      ...mockSettingsResponse,
      retention: { days: 45, log_days: 14 },
    };

    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => updatedSettings,
    } as Response);

    result.current.updateMutation.mutate({
      retention: { days: 45, log_days: 14 },
    });

    await waitFor(() => {
      expect(result.current.updateMutation.isSuccess).toBe(true);
    });

    expect(result.current.updateMutation.data).toEqual(updatedSettings);
  });

  it('passes options to query', async () => {
    const options: UseSettingsOptions = {
      enabled: false,
      staleTime: 60000,
    };

    const { result } = renderHook(() => useSettingsApi(options), {
      wrapper: createTestWrapper(),
    });

    // Wait to ensure no fetch happens
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.current.settings).toBeUndefined();
  });

  it('provides access to all query states', async () => {
    const { result } = renderHook(() => useSettingsApi(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.isError).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('handles query errors', async () => {
    const errorMessage = 'Settings not found';
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: errorMessage }),
    } as Response);

    const { result } = renderHook(() => useSettingsApi(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe(errorMessage);
    expect(result.current.settings).toBeUndefined();
  });

  it('handles mutation errors independently', async () => {
    const { result } = renderHook(() => useSettingsApi(), {
      wrapper: createTestWrapper(),
    });

    // Wait for successful query
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.settings).toBeDefined();

    // Trigger failing mutation
    const errorMessage = 'Invalid settings';
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({ detail: errorMessage }),
    } as Response);

    result.current.updateMutation.mutate({
      detection: { confidence_threshold: -1 },
    });

    await waitFor(() => {
      expect(result.current.updateMutation.isError).toBe(true);
    });

    // Query should still be successful
    expect(result.current.isSuccess).toBe(true);
    expect(result.current.settings).toBeDefined();

    // But mutation should have failed
    expect(result.current.updateMutation.error?.message).toBe(errorMessage);
  });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe('Integration Tests', () => {
  it('updates all settings categories', async () => {
    const { result } = renderHook(() => useSettingsApi(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const fullUpdate: SettingsUpdate = {
      detection: { confidence_threshold: 0.55 },
      batch: { window_seconds: 120 },
      severity: { low_max: 25 },
      features: { reid_enabled: false },
      rate_limiting: { enabled: false },
      queue: { max_size: 2000 },
      retention: { days: 60 },
    };

    const updatedSettings = {
      ...mockSettingsResponse,
      ...fullUpdate,
    } as SettingsResponse;

    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => updatedSettings,
    } as Response);

    result.current.updateMutation.mutate(fullUpdate);

    await waitFor(() => {
      expect(result.current.updateMutation.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify(fullUpdate),
      })
    );
  });

  it('maintains settings structure', async () => {
    const { result } = renderHook(() => useSettingsApi(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.settings).toBeDefined();
    });

    // Verify all expected settings categories exist
    expect(result.current.settings).toHaveProperty('detection');
    expect(result.current.settings).toHaveProperty('batch');
    expect(result.current.settings).toHaveProperty('severity');
    expect(result.current.settings).toHaveProperty('features');
    expect(result.current.settings).toHaveProperty('rate_limiting');
    expect(result.current.settings).toHaveProperty('queue');
    expect(result.current.settings).toHaveProperty('retention');

    // Verify nested structure
    expect(result.current.settings?.detection).toHaveProperty('confidence_threshold');
    expect(result.current.settings?.features).toHaveProperty('reid_enabled');
    expect(result.current.settings?.retention).toHaveProperty('days');
  });
});
