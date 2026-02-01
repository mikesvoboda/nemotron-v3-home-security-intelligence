import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useSupervisorStatus } from './useSupervisorStatus';
import * as supervisorApi from '../services/supervisorApi';

vi.mock('../services/supervisorApi');

describe('useSupervisorStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns loading state initially', () => {
    vi.mocked(supervisorApi.fetchSupervisorStatus).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    const { result } = renderHook(() => useSupervisorStatus());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBeNull();
  });

  it('returns supervisor data after successful fetch', async () => {
    const mockData = {
      running: true,
      worker_count: 4,
      workers: [
        {
          name: 'file_watcher',
          status: 'running' as const,
          restart_count: 0,
          max_restarts: 5,
          last_started_at: '2025-01-31T10:00:00Z',
          last_crashed_at: null,
          error: null,
        },
        {
          name: 'detection_worker',
          status: 'crashed' as const,
          restart_count: 3,
          max_restarts: 5,
          last_started_at: '2025-01-31T09:00:00Z',
          last_crashed_at: '2025-01-31T10:30:00Z',
          error: 'Connection timeout',
        },
      ],
      timestamp: '2025-01-31T10:35:00Z',
    };

    vi.mocked(supervisorApi.fetchSupervisorStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => useSupervisorStatus());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockData);
    expect(result.current.error).toBeNull();
  });

  it('returns worker list with status and restart counts', async () => {
    const mockData = {
      running: true,
      worker_count: 2,
      workers: [
        {
          name: 'worker1',
          status: 'running' as const,
          restart_count: 1,
          max_restarts: 5,
          last_started_at: '2025-01-31T10:00:00Z',
          last_crashed_at: '2025-01-31T09:30:00Z',
          error: null,
        },
        {
          name: 'worker2',
          status: 'stopped' as const,
          restart_count: 0,
          max_restarts: 5,
          last_started_at: null,
          last_crashed_at: null,
          error: null,
        },
      ],
      timestamp: '2025-01-31T10:35:00Z',
    };

    vi.mocked(supervisorApi.fetchSupervisorStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => useSupervisorStatus());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.workers).toHaveLength(2);
    expect(result.current.data?.workers[0].restart_count).toBe(1);
    expect(result.current.data?.workers[0].status).toBe('running');
    expect(result.current.data?.workers[1].restart_count).toBe(0);
    expect(result.current.data?.workers[1].status).toBe('stopped');
  });

  it('handles error states gracefully', async () => {
    const errorMessage = 'Failed to fetch supervisor status';
    vi.mocked(supervisorApi.fetchSupervisorStatus).mockRejectedValue(
      new Error(errorMessage)
    );

    const { result } = renderHook(() => useSupervisorStatus());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe(errorMessage);
  });

  it('supports refetch functionality', async () => {
    const mockData = {
      running: true,
      worker_count: 1,
      workers: [],
      timestamp: '2025-01-31T10:35:00Z',
    };

    vi.mocked(supervisorApi.fetchSupervisorStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => useSupervisorStatus());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(supervisorApi.fetchSupervisorStatus).toHaveBeenCalledTimes(1);

    // Trigger refetch
    await result.current.refetch();

    await waitFor(() => {
      expect(supervisorApi.fetchSupervisorStatus).toHaveBeenCalledTimes(2);
    });
  });

  it('polls for updates at specified interval', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    const mockData = {
      running: true,
      worker_count: 1,
      workers: [],
      timestamp: '2025-01-31T10:35:00Z',
    };

    vi.mocked(supervisorApi.fetchSupervisorStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => useSupervisorStatus({ pollInterval: 5000 }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(supervisorApi.fetchSupervisorStatus).toHaveBeenCalledTimes(1);

    // Advance time by 5 seconds
    vi.advanceTimersByTime(5000);

    await waitFor(() => {
      expect(supervisorApi.fetchSupervisorStatus).toHaveBeenCalledTimes(2);
    });

    // Advance time by another 5 seconds
    vi.advanceTimersByTime(5000);

    await waitFor(() => {
      expect(supervisorApi.fetchSupervisorStatus).toHaveBeenCalledTimes(3);
    });

    vi.useRealTimers();
  });

  it('handles empty worker list', async () => {
    const mockData = {
      running: true,
      worker_count: 0,
      workers: [],
      timestamp: '2025-01-31T10:35:00Z',
    };

    vi.mocked(supervisorApi.fetchSupervisorStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => useSupervisorStatus());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.workers).toEqual([]);
    expect(result.current.data?.worker_count).toBe(0);
  });

  it('handles failed worker status', async () => {
    const mockData = {
      running: true,
      worker_count: 1,
      workers: [
        {
          name: 'failed_worker',
          status: 'failed' as const,
          restart_count: 5,
          max_restarts: 5,
          last_started_at: '2025-01-31T09:00:00Z',
          last_crashed_at: '2025-01-31T10:30:00Z',
          error: 'Max restarts exceeded',
        },
      ],
      timestamp: '2025-01-31T10:35:00Z',
    };

    vi.mocked(supervisorApi.fetchSupervisorStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => useSupervisorStatus());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.workers[0].status).toBe('failed');
    expect(result.current.data?.workers[0].restart_count).toBe(5);
    expect(result.current.data?.workers[0].error).toBe('Max restarts exceeded');
  });

  it('disables polling when pollInterval is not provided', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    const mockData = {
      running: true,
      worker_count: 1,
      workers: [],
      timestamp: '2025-01-31T10:35:00Z',
    };

    vi.mocked(supervisorApi.fetchSupervisorStatus).mockResolvedValue(mockData);

    const { result } = renderHook(() => useSupervisorStatus());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(supervisorApi.fetchSupervisorStatus).toHaveBeenCalledTimes(1);

    // Advance time - should not trigger additional fetches
    vi.advanceTimersByTime(10000);

    await waitFor(() => {
      expect(supervisorApi.fetchSupervisorStatus).toHaveBeenCalledTimes(1);
    });

    vi.useRealTimers();
  });
});
