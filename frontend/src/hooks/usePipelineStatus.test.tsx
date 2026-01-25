/**
 * Tests for usePipelineStatus hook.
 *
 * Tests fetching pipeline status data with automatic polling
 * and derived batch aggregator state computation.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { ReactNode } from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { usePipelineStatus, PIPELINE_STATUS_QUERY_KEY } from './usePipelineStatus';
import * as api from '../services/api';

import type { PipelineStatusResponse } from '../types/queue';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchPipelineStatus: vi.fn(),
}));

// Create a mock response matching PipelineStatusResponse from OpenAPI
const createMockPipelineStatus = (
  overrides: Partial<PipelineStatusResponse> = {}
): PipelineStatusResponse => ({
  file_watcher: {
    running: true,
    camera_root: '/export/foscam',
    pending_tasks: 2,
    observer_type: 'native',
  },
  batch_aggregator: {
    active_batches: 2,
    batch_window_seconds: 90,
    idle_timeout_seconds: 30,
    batches: [
      {
        batch_id: 'batch_001',
        camera_id: 'front_door',
        detection_count: 5,
        started_at: Date.now() / 1000 - 30,
        age_seconds: 30,
        last_activity_seconds: 5,
      },
      {
        batch_id: 'batch_002',
        camera_id: 'backyard',
        detection_count: 3,
        started_at: Date.now() / 1000 - 75,
        age_seconds: 75,
        last_activity_seconds: 10,
      },
    ],
  },
  degradation: {
    mode: 'normal',
    is_degraded: false,
    redis_healthy: true,
    memory_queue_size: 0,
    fallback_queues: {},
    services: [],
    available_features: ['detection', 'analysis', 'events', 'media'],
  },
  timestamp: '2026-01-25T10:30:00Z',
  ...overrides,
});

describe('usePipelineStatus', () => {
  let queryClient: QueryClient;

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    queryClient.clear();
  });

  it('should fetch pipeline status on mount', async () => {
    const mockData = createMockPipelineStatus();
    vi.mocked(api.fetchPipelineStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => usePipelineStatus(), { wrapper });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(api.fetchPipelineStatus).toHaveBeenCalledTimes(1);
    expect(result.current.data).toEqual(mockData);
  });

  it('should compute batch aggregator state correctly', async () => {
    const mockData = createMockPipelineStatus();
    vi.mocked(api.fetchPipelineStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => usePipelineStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Check batch aggregator state
    expect(result.current.batchAggregatorState.activeBatchCount).toBe(2);
    expect(result.current.batchAggregatorState.batches).toHaveLength(2);
    expect(result.current.batchAggregatorState.batchWindowSeconds).toBe(90);
    expect(result.current.batchAggregatorState.idleTimeoutSeconds).toBe(30);
  });

  it('should identify batches approaching timeout', async () => {
    const mockData = createMockPipelineStatus({
      batch_aggregator: {
        active_batches: 2,
        batch_window_seconds: 90,
        idle_timeout_seconds: 30,
        batches: [
          {
            batch_id: 'batch_001',
            camera_id: 'front_door',
            detection_count: 5,
            started_at: Date.now() / 1000 - 30,
            age_seconds: 30, // 33% of window
            last_activity_seconds: 5,
          },
          {
            batch_id: 'batch_002',
            camera_id: 'backyard',
            detection_count: 3,
            started_at: Date.now() / 1000 - 80,
            age_seconds: 80, // 89% of window - approaching timeout
            last_activity_seconds: 10,
          },
        ],
      },
    });
    vi.mocked(api.fetchPipelineStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => usePipelineStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // batch_002 is at 89% (>80%), so it should be approaching timeout
    expect(result.current.batchAggregatorState.batchesApproachingTimeout).toHaveLength(1);
    expect(result.current.batchAggregatorState.batchesApproachingTimeout[0].batch_id).toBe(
      'batch_002'
    );
    expect(result.current.batchAggregatorState.hasTimeoutWarning).toBe(true);
  });

  it('should expose fileWatcherRunning state', async () => {
    const mockData = createMockPipelineStatus();
    vi.mocked(api.fetchPipelineStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => usePipelineStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.fileWatcherRunning).toBe(true);
  });

  it('should detect when file watcher is not running', async () => {
    const mockData = createMockPipelineStatus({
      file_watcher: {
        running: false,
        camera_root: '/export/foscam',
        pending_tasks: 0,
        observer_type: 'native',
      },
    });
    vi.mocked(api.fetchPipelineStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => usePipelineStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.fileWatcherRunning).toBe(false);
  });

  it('should expose isDegraded state', async () => {
    const mockData = createMockPipelineStatus();
    vi.mocked(api.fetchPipelineStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => usePipelineStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isDegraded).toBe(false);
  });

  it('should detect degraded mode', async () => {
    const mockData = createMockPipelineStatus({
      degradation: {
        mode: 'degraded',
        is_degraded: true,
        redis_healthy: false,
        memory_queue_size: 50,
        fallback_queues: { detection: 25, analysis: 25 },
        services: [],
        available_features: ['detection', 'events'],
      },
    });
    vi.mocked(api.fetchPipelineStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => usePipelineStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isDegraded).toBe(true);
  });

  it('should handle null batch_aggregator', async () => {
    const mockData = createMockPipelineStatus({
      batch_aggregator: null,
    });
    vi.mocked(api.fetchPipelineStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => usePipelineStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should return default values
    expect(result.current.batchAggregatorState.activeBatchCount).toBe(0);
    expect(result.current.batchAggregatorState.batches).toHaveLength(0);
    expect(result.current.batchAggregatorState.hasTimeoutWarning).toBe(false);
  });

  it('should handle null file_watcher', async () => {
    const mockData = createMockPipelineStatus({
      file_watcher: null,
    });
    vi.mocked(api.fetchPipelineStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => usePipelineStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.fileWatcherRunning).toBe(false);
  });

  it('should handle fetch error', async () => {
    const error = new Error('Network error');
    vi.mocked(api.fetchPipelineStatus).mockRejectedValue(error);

    const { result } = renderHook(() => usePipelineStatus(), { wrapper });

    // Wait for error to be set (hook uses retry: 1)
    await waitFor(
      () => {
        expect(result.current.error).toBeTruthy();
      },
      { timeout: 5000 }
    );

    expect(result.current.data).toBeNull();
  });

  it('should return default batch state when data is null', async () => {
    const error = new Error('Network error');
    vi.mocked(api.fetchPipelineStatus).mockRejectedValue(error);

    const { result } = renderHook(() => usePipelineStatus(), { wrapper });

    // Wait for error to be set (hook uses retry: 1)
    await waitFor(
      () => {
        expect(result.current.error).toBeTruthy();
      },
      { timeout: 5000 }
    );

    expect(result.current.batchAggregatorState.activeBatchCount).toBe(0);
    expect(result.current.batchAggregatorState.batches).toHaveLength(0);
    expect(result.current.batchAggregatorState.batchWindowSeconds).toBe(90);
    expect(result.current.fileWatcherRunning).toBe(false);
    expect(result.current.isDegraded).toBe(false);
  });

  it('should respect enabled option', () => {
    const mockData = createMockPipelineStatus();
    vi.mocked(api.fetchPipelineStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => usePipelineStatus({ enabled: false }), {
      wrapper,
    });

    // Should not be loading because query is disabled
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeNull();
    expect(api.fetchPipelineStatus).not.toHaveBeenCalled();
  });

  it('should use correct query key', async () => {
    const mockData = createMockPipelineStatus();
    vi.mocked(api.fetchPipelineStatus).mockResolvedValue(mockData);

    renderHook(() => usePipelineStatus(), { wrapper });

    await waitFor(() => {
      const queryState = queryClient.getQueryState(PIPELINE_STATUS_QUERY_KEY);
      expect(queryState).toBeDefined();
    });
  });

  it('should provide refetch function', async () => {
    const mockData1 = createMockPipelineStatus({
      batch_aggregator: {
        active_batches: 1,
        batch_window_seconds: 90,
        idle_timeout_seconds: 30,
        batches: [],
      },
    });
    const mockData2 = createMockPipelineStatus({
      batch_aggregator: {
        active_batches: 3,
        batch_window_seconds: 90,
        idle_timeout_seconds: 30,
        batches: [],
      },
    });

    vi.mocked(api.fetchPipelineStatus)
      .mockResolvedValueOnce(mockData1)
      .mockResolvedValueOnce(mockData2);

    const { result } = renderHook(() => usePipelineStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.batchAggregatorState.activeBatchCount).toBe(1);
    });

    // Trigger refetch
    void result.current.refetch();

    await waitFor(() => {
      expect(result.current.batchAggregatorState.activeBatchCount).toBe(3);
    });

    expect(api.fetchPipelineStatus).toHaveBeenCalledTimes(2);
  });
});
