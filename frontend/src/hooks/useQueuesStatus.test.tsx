/**
 * Tests for useQueuesStatus hook.
 *
 * Tests fetching queue status data with automatic polling
 * and derived state computation.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { ReactNode } from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useQueuesStatus, QUEUES_STATUS_QUERY_KEY } from './useQueuesStatus';
import * as api from '../services/api';

import type { QueuesStatusResponse } from '../types/queue';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchQueuesStatus: vi.fn(),
}));

// Create a mock response
const createMockQueuesStatus = (
  overrides: Partial<QueuesStatusResponse> = {}
): QueuesStatusResponse => ({
  queues: [
    {
      name: 'detection',
      status: 'healthy',
      depth: 5,
      running: 2,
      workers: 4,
      throughput: {
        jobs_per_minute: 12.5,
        avg_processing_seconds: 4.8,
      },
      oldest_job: {
        id: 'job_123',
        queued_at: '2026-01-25T10:00:00Z',
        wait_seconds: 15.5,
      },
    },
    {
      name: 'ai_analysis',
      status: 'warning',
      depth: 20,
      running: 3,
      workers: 4,
      throughput: {
        jobs_per_minute: 8.2,
        avg_processing_seconds: 7.3,
      },
      oldest_job: {
        id: 'job_456',
        queued_at: '2026-01-25T09:55:00Z',
        wait_seconds: 45.2,
      },
    },
  ],
  summary: {
    total_queued: 25,
    total_running: 5,
    total_workers: 8,
    overall_status: 'warning',
  },
  ...overrides,
});

describe('useQueuesStatus', () => {
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

  it('should fetch queue status on mount', async () => {
    const mockData = createMockQueuesStatus();
    vi.mocked(api.fetchQueuesStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => useQueuesStatus(), { wrapper });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(api.fetchQueuesStatus).toHaveBeenCalledTimes(1);
    expect(result.current.data).toEqual(mockData);
  });

  it('should compute derived state correctly', async () => {
    const mockData = createMockQueuesStatus({
      queues: [
        {
          name: 'detection',
          status: 'critical',
          depth: 100,
          running: 4,
          workers: 4,
          throughput: { jobs_per_minute: 5.0, avg_processing_seconds: 12.0 },
          oldest_job: { id: 'old_job', queued_at: '2026-01-25T08:00:00Z', wait_seconds: 120 },
        },
        {
          name: 'ai_analysis',
          status: 'warning',
          depth: 30,
          running: 2,
          workers: 4,
          throughput: { jobs_per_minute: 6.0, avg_processing_seconds: 10.0 },
          oldest_job: { id: 'job_2', queued_at: '2026-01-25T09:00:00Z', wait_seconds: 60 },
        },
      ],
      summary: {
        total_queued: 130,
        total_running: 6,
        total_workers: 8,
        overall_status: 'critical',
      },
    });
    vi.mocked(api.fetchQueuesStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => useQueuesStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Check derived state
    expect(result.current.derivedState.criticalQueues).toHaveLength(1);
    expect(result.current.derivedState.criticalQueues[0].name).toBe('detection');
    expect(result.current.derivedState.warningQueues).toHaveLength(1);
    expect(result.current.derivedState.hasCritical).toBe(true);
    expect(result.current.derivedState.hasIssues).toBe(true);
    expect(result.current.derivedState.longestWaitTime).toBe(120);
    expect(result.current.derivedState.longestWaitQueue?.name).toBe('detection');
  });

  it('should expose criticalQueues shortcut', async () => {
    const mockData = createMockQueuesStatus({
      queues: [
        {
          name: 'detection',
          status: 'critical',
          depth: 100,
          running: 4,
          workers: 4,
          throughput: { jobs_per_minute: 5.0, avg_processing_seconds: 12.0 },
          oldest_job: null,
        },
      ],
      summary: {
        total_queued: 100,
        total_running: 4,
        total_workers: 4,
        overall_status: 'critical',
      },
    });
    vi.mocked(api.fetchQueuesStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => useQueuesStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.criticalQueues).toHaveLength(1);
    expect(result.current.criticalQueues[0].name).toBe('detection');
  });

  it('should expose longestWaitTime shortcut', async () => {
    const mockData = createMockQueuesStatus();
    vi.mocked(api.fetchQueuesStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => useQueuesStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // The mock has analysis queue with 45.2s wait time
    expect(result.current.longestWaitTime).toBe(45.2);
  });

  it('should handle fetch error', async () => {
    const error = new Error('Network error');
    vi.mocked(api.fetchQueuesStatus).mockRejectedValue(error);

    const { result } = renderHook(() => useQueuesStatus(), { wrapper });

    // Wait for error to be set (hook uses retry: 1)
    await waitFor(
      () => {
        expect(result.current.error).toBeTruthy();
      },
      { timeout: 5000 }
    );

    expect(result.current.data).toBeNull();
  });

  it('should return empty derived state when data is null', async () => {
    const error = new Error('Network error');
    vi.mocked(api.fetchQueuesStatus).mockRejectedValue(error);

    const { result } = renderHook(() => useQueuesStatus(), { wrapper });

    // Wait for error to be set (hook uses retry: 1)
    await waitFor(
      () => {
        expect(result.current.error).toBeTruthy();
      },
      { timeout: 5000 }
    );

    expect(result.current.derivedState.criticalQueues).toHaveLength(0);
    expect(result.current.derivedState.warningQueues).toHaveLength(0);
    expect(result.current.derivedState.longestWaitTime).toBe(0);
    expect(result.current.derivedState.hasCritical).toBe(false);
    expect(result.current.derivedState.hasIssues).toBe(false);
  });

  it('should respect enabled option', () => {
    const mockData = createMockQueuesStatus();
    vi.mocked(api.fetchQueuesStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => useQueuesStatus({ enabled: false }), {
      wrapper,
    });

    // Should not be loading because query is disabled
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeNull();
    expect(api.fetchQueuesStatus).not.toHaveBeenCalled();
  });

  it('should use correct query key', async () => {
    const mockData = createMockQueuesStatus();
    vi.mocked(api.fetchQueuesStatus).mockResolvedValue(mockData);

    renderHook(() => useQueuesStatus(), { wrapper });

    await waitFor(() => {
      const queryState = queryClient.getQueryState(QUEUES_STATUS_QUERY_KEY);
      expect(queryState).toBeDefined();
    });
  });

  it('should provide refetch function', async () => {
    const mockData1 = createMockQueuesStatus({
      summary: { total_queued: 10, total_running: 2, total_workers: 8, overall_status: 'healthy' },
    });
    const mockData2 = createMockQueuesStatus({
      summary: { total_queued: 20, total_running: 4, total_workers: 8, overall_status: 'warning' },
    });

    vi.mocked(api.fetchQueuesStatus)
      .mockResolvedValueOnce(mockData1)
      .mockResolvedValueOnce(mockData2);

    const { result } = renderHook(() => useQueuesStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.data?.summary.total_queued).toBe(10);
    });

    // Trigger refetch
    void result.current.refetch();

    await waitFor(() => {
      expect(result.current.data?.summary.total_queued).toBe(20);
    });

    expect(api.fetchQueuesStatus).toHaveBeenCalledTimes(2);
  });

  it('should track isFetching state during refetch', async () => {
    const mockData = createMockQueuesStatus();
    vi.mocked(api.fetchQueuesStatus).mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(mockData), 100))
    );

    const { result } = renderHook(() => useQueuesStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Trigger refetch
    void result.current.refetch();

    // Should be fetching during refetch
    await waitFor(() => {
      expect(result.current.isFetching).toBe(true);
    });

    // Wait for refetch to complete
    await waitFor(() => {
      expect(result.current.isFetching).toBe(false);
    });
  });
});
