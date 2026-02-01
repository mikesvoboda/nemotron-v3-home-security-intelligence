/**
 * Tests for useBaselineConfig hooks
 *
 * TDD: Tests written first to define the expected behavior (Red phase).
 * Tests React Query hooks for baseline configuration management.
 *
 * @see NEM-4919 - Phase 3: Baseline Tuning UI
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useBaselineConfigQuery, useUpdateBaselineConfig, useResetBaseline } from './useBaselineConfig';
import * as baselineConfigApi from '../services/baselineConfigApi';

import type { ReactNode } from 'react';

// Mock the API module
vi.mock('../services/baselineConfigApi', () => ({
  fetchBaselineConfig: vi.fn(),
  updateBaselineConfig: vi.fn(),
  resetCameraBaseline: vi.fn(),
}));

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });

const createWrapper = () => {
  const queryClient = createTestQueryClient();
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('useBaselineConfigQuery', () => {
  const mockCameraId = 'front_door';

  const mockConfig = {
    threshold_stdev: 2.0,
    min_samples: 10,
    override_global_config: false,
    global_config: {
      threshold_stdev: 2.0,
      min_samples: 10,
      decay_factor: 0.1,
      window_days: 30,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(baselineConfigApi.fetchBaselineConfig).mockResolvedValue(mockConfig);
  });

  it('returns config data', async () => {
    const { result } = renderHook(() => useBaselineConfigQuery(mockCameraId), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockConfig);
    expect(result.current.data?.threshold_stdev).toBe(2.0);
    expect(result.current.data?.min_samples).toBe(10);
    expect(result.current.data?.override_global_config).toBe(false);
  });

  it('handles loading state', () => {
    vi.mocked(baselineConfigApi.fetchBaselineConfig).mockImplementation(() => new Promise(() => {}));

    const { result } = renderHook(() => useBaselineConfigQuery(mockCameraId), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
  });

  it('handles error state', async () => {
    const errorMessage = 'Failed to fetch config';
    vi.mocked(baselineConfigApi.fetchBaselineConfig).mockRejectedValue(new Error(errorMessage));

    const { result } = renderHook(() => useBaselineConfigQuery(mockCameraId), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
    expect(result.current.data).toBeUndefined();
  });

  it('uses correct query key', () => {
    renderHook(() => useBaselineConfigQuery(mockCameraId), {
      wrapper: createWrapper(),
    });

    // Query key should include camera ID for proper cache isolation
    expect(baselineConfigApi.fetchBaselineConfig).toHaveBeenCalledWith(mockCameraId);
  });
});

describe('useUpdateBaselineConfig', () => {
  const mockCameraId = 'front_door';

  const mockUpdatedConfig = {
    threshold_stdev: 3.5,
    min_samples: 20,
    override_global_config: true,
    global_config: {
      threshold_stdev: 2.0,
      min_samples: 10,
      decay_factor: 0.1,
      window_days: 30,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(baselineConfigApi.updateBaselineConfig).mockResolvedValue(mockUpdatedConfig);
  });

  it('updates config', async () => {
    const queryClient = createTestQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useUpdateBaselineConfig(mockCameraId), { wrapper });

    const updateData = {
      threshold_stdev: 3.5,
      min_samples: 20,
    };

    result.current.mutate(updateData);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(baselineConfigApi.updateBaselineConfig).toHaveBeenCalledWith(mockCameraId, updateData);
    expect(result.current.data).toEqual(mockUpdatedConfig);
  });

  it('invalidates query cache on success', async () => {
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useUpdateBaselineConfig(mockCameraId), { wrapper });

    result.current.mutate({ threshold_stdev: 3.5 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Should invalidate the config query to refetch updated data
    expect(invalidateSpy).toHaveBeenCalled();
  });

  it('handles mutation error', async () => {
    const errorMessage = 'Failed to update config';
    vi.mocked(baselineConfigApi.updateBaselineConfig).mockRejectedValue(new Error(errorMessage));

    const queryClient = createTestQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useUpdateBaselineConfig(mockCameraId), { wrapper });

    result.current.mutate({ threshold_stdev: 3.5 });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });

  it('provides loading state during mutation', async () => {
    vi.mocked(baselineConfigApi.updateBaselineConfig).mockImplementation(() => new Promise(() => {}));

    const queryClient = createTestQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useUpdateBaselineConfig(mockCameraId), { wrapper });

    result.current.mutate({ threshold_stdev: 3.5 });

    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
    });
  });
});

describe('useResetBaseline', () => {
  const mockCameraId = 'front_door';

  const mockResetResult = {
    activity_baselines_deleted: 168,
    class_baselines_deleted: 42,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(baselineConfigApi.resetCameraBaseline).mockResolvedValue(mockResetResult);
  });

  it('resets baseline data', async () => {
    const queryClient = createTestQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useResetBaseline(mockCameraId), { wrapper });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(baselineConfigApi.resetCameraBaseline).toHaveBeenCalledWith(mockCameraId);
    expect(result.current.data).toEqual(mockResetResult);
  });

  it('shows deletion counts', async () => {
    const queryClient = createTestQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useResetBaseline(mockCameraId), { wrapper });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.activity_baselines_deleted).toBe(168);
    expect(result.current.data?.class_baselines_deleted).toBe(42);
  });

  it('invalidates baseline queries on success', async () => {
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useResetBaseline(mockCameraId), { wrapper });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Should invalidate baseline-related queries to show fresh data
    expect(invalidateSpy).toHaveBeenCalled();
  });

  it('handles reset error', async () => {
    const errorMessage = 'Failed to reset baseline';
    vi.mocked(baselineConfigApi.resetCameraBaseline).mockRejectedValue(new Error(errorMessage));

    const queryClient = createTestQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useResetBaseline(mockCameraId), { wrapper });

    result.current.mutate();

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });

  it('provides loading state during reset', async () => {
    vi.mocked(baselineConfigApi.resetCameraBaseline).mockImplementation(() => new Promise(() => {}));

    const queryClient = createTestQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useResetBaseline(mockCameraId), { wrapper });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
    });
  });

  it('resets zero counts when no baseline data', async () => {
    vi.mocked(baselineConfigApi.resetCameraBaseline).mockResolvedValue({
      activity_baselines_deleted: 0,
      class_baselines_deleted: 0,
    });

    const queryClient = createTestQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useResetBaseline(mockCameraId), { wrapper });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.activity_baselines_deleted).toBe(0);
    expect(result.current.data?.class_baselines_deleted).toBe(0);
  });
});

describe('hook integration', () => {
  const mockCameraId = 'front_door';

  it('update mutation invalidates query', async () => {
    const mockConfig = {
      threshold_stdev: 2.0,
      min_samples: 10,
      override_global_config: false,
      global_config: {
        threshold_stdev: 2.0,
        min_samples: 10,
        decay_factor: 0.1,
        window_days: 30,
      },
    };

    const updatedConfig = {
      ...mockConfig,
      threshold_stdev: 3.5,
      override_global_config: true,
    };

    vi.mocked(baselineConfigApi.fetchBaselineConfig).mockResolvedValue(mockConfig);
    vi.mocked(baselineConfigApi.updateBaselineConfig).mockResolvedValue(updatedConfig);

    const queryClient = createTestQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result: queryResult } = renderHook(() => useBaselineConfigQuery(mockCameraId), {
      wrapper,
    });
    const { result: mutationResult } = renderHook(() => useUpdateBaselineConfig(mockCameraId), {
      wrapper,
    });

    await waitFor(() => expect(queryResult.current.isSuccess).toBe(true));

    // Update config
    mutationResult.current.mutate({ threshold_stdev: 3.5 });

    await waitFor(() => expect(mutationResult.current.isSuccess).toBe(true));

    // Query should refetch after mutation
    await waitFor(() => {
      expect(baselineConfigApi.fetchBaselineConfig).toHaveBeenCalledTimes(2); // Initial + refetch
    });
  });
});
