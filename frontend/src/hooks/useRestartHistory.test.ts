import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useRestartHistory } from './useRestartHistory';
import * as supervisorApi from '../services/supervisorApi';

vi.mock('../services/supervisorApi');

describe('useRestartHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns loading state initially', () => {
    vi.mocked(supervisorApi.fetchRestartHistory).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    const { result } = renderHook(() => useRestartHistory());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBeNull();
  });

  it('returns restart history items', async () => {
    const mockData = {
      items: [
        {
          worker_name: 'detection_worker',
          timestamp: '2025-01-31T10:30:00Z',
          attempt: 3,
          status: 'success' as const,
          error: null,
        },
        {
          worker_name: 'file_watcher',
          timestamp: '2025-01-31T09:15:00Z',
          attempt: 1,
          status: 'success' as const,
          error: null,
        },
      ],
      pagination: {
        total: 2,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    };

    vi.mocked(supervisorApi.fetchRestartHistory).mockResolvedValue(mockData);

    const { result } = renderHook(() => useRestartHistory());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockData);
    expect(result.current.data?.items).toHaveLength(2);
    expect(result.current.error).toBeNull();
  });

  it('supports pagination with limit and offset', async () => {
    const mockData = {
      items: [
        {
          worker_name: 'worker1',
          timestamp: '2025-01-31T10:00:00Z',
          attempt: 1,
          status: 'success' as const,
          error: null,
        },
      ],
      pagination: {
        total: 100,
        limit: 10,
        offset: 20,
        has_more: true,
      },
    };

    vi.mocked(supervisorApi.fetchRestartHistory).mockResolvedValue(mockData);

    const { result } = renderHook(() =>
      useRestartHistory({ limit: 10, offset: 20 })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(supervisorApi.fetchRestartHistory).toHaveBeenCalledWith({
      limit: 10,
      offset: 20,
    });
    expect(result.current.data?.pagination.has_more).toBe(true);
    expect(result.current.data?.pagination.total).toBe(100);
  });

  it('supports filtering by worker name', async () => {
    const mockData = {
      items: [
        {
          worker_name: 'detection_worker',
          timestamp: '2025-01-31T10:30:00Z',
          attempt: 3,
          status: 'success' as const,
          error: null,
        },
      ],
      pagination: {
        total: 1,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    };

    vi.mocked(supervisorApi.fetchRestartHistory).mockResolvedValue(mockData);

    const { result } = renderHook(() =>
      useRestartHistory({ workerName: 'detection_worker' })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(supervisorApi.fetchRestartHistory).toHaveBeenCalledWith({
      workerName: 'detection_worker',
    });
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0].worker_name).toBe('detection_worker');
  });

  it('handles empty history', async () => {
    const mockData = {
      items: [],
      pagination: {
        total: 0,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    };

    vi.mocked(supervisorApi.fetchRestartHistory).mockResolvedValue(mockData);

    const { result } = renderHook(() => useRestartHistory());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.items).toEqual([]);
    expect(result.current.data?.pagination.total).toBe(0);
  });

  it('handles error states', async () => {
    const errorMessage = 'Failed to fetch restart history';
    vi.mocked(supervisorApi.fetchRestartHistory).mockRejectedValue(
      new Error(errorMessage)
    );

    const { result } = renderHook(() => useRestartHistory());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe(errorMessage);
  });

  it('includes failed restart attempts', async () => {
    const mockData = {
      items: [
        {
          worker_name: 'detection_worker',
          timestamp: '2025-01-31T10:30:00Z',
          attempt: 3,
          status: 'failed' as const,
          error: 'Connection timeout',
        },
        {
          worker_name: 'detection_worker',
          timestamp: '2025-01-31T10:25:00Z',
          attempt: 2,
          status: 'success' as const,
          error: null,
        },
      ],
      pagination: {
        total: 2,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    };

    vi.mocked(supervisorApi.fetchRestartHistory).mockResolvedValue(mockData);

    const { result } = renderHook(() => useRestartHistory());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.items[0].status).toBe('failed');
    expect(result.current.data?.items[0].error).toBe('Connection timeout');
    expect(result.current.data?.items[1].status).toBe('success');
  });

  it('supports refetch functionality', async () => {
    const mockData = {
      items: [],
      pagination: {
        total: 0,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    };

    vi.mocked(supervisorApi.fetchRestartHistory).mockResolvedValue(mockData);

    const { result } = renderHook(() => useRestartHistory());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(supervisorApi.fetchRestartHistory).toHaveBeenCalledTimes(1);

    // Trigger refetch
    await result.current.refetch();

    await waitFor(() => {
      expect(supervisorApi.fetchRestartHistory).toHaveBeenCalledTimes(2);
    });
  });

  it('handles combined filter and pagination parameters', async () => {
    const mockData = {
      items: [
        {
          worker_name: 'file_watcher',
          timestamp: '2025-01-31T09:00:00Z',
          attempt: 1,
          status: 'success' as const,
          error: null,
        },
      ],
      pagination: {
        total: 50,
        limit: 20,
        offset: 10,
        has_more: true,
      },
    };

    vi.mocked(supervisorApi.fetchRestartHistory).mockResolvedValue(mockData);

    const { result } = renderHook(() =>
      useRestartHistory({
        workerName: 'file_watcher',
        limit: 20,
        offset: 10,
      })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(supervisorApi.fetchRestartHistory).toHaveBeenCalledWith({
      workerName: 'file_watcher',
      limit: 20,
      offset: 10,
    });
  });

  it('sorts items by timestamp in descending order', async () => {
    const mockData = {
      items: [
        {
          worker_name: 'worker1',
          timestamp: '2025-01-31T10:30:00Z',
          attempt: 2,
          status: 'success' as const,
          error: null,
        },
        {
          worker_name: 'worker2',
          timestamp: '2025-01-31T10:00:00Z',
          attempt: 1,
          status: 'success' as const,
          error: null,
        },
        {
          worker_name: 'worker1',
          timestamp: '2025-01-31T09:30:00Z',
          attempt: 1,
          status: 'success' as const,
          error: null,
        },
      ],
      pagination: {
        total: 3,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    };

    vi.mocked(supervisorApi.fetchRestartHistory).mockResolvedValue(mockData);

    const { result } = renderHook(() => useRestartHistory());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const timestamps = result.current.data?.items.map((item) => item.timestamp);
    expect(timestamps).toEqual([
      '2025-01-31T10:30:00Z',
      '2025-01-31T10:00:00Z',
      '2025-01-31T09:30:00Z',
    ]);
  });
});
