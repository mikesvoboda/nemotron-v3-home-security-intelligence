import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useWorkerActions } from './useWorkerActions';
import * as supervisorApi from '../services/supervisorApi';

vi.mock('../services/supervisorApi');

describe('useWorkerActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('startWorker calls correct API endpoint', async () => {
    const mockResponse = {
      success: true,
      message: "Worker 'file_watcher' started successfully",
      worker_name: 'file_watcher',
    };

    vi.mocked(supervisorApi.startWorker).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useWorkerActions());

    await result.current.startWorker('file_watcher');

    await waitFor(() => {
      expect(supervisorApi.startWorker).toHaveBeenCalledWith('file_watcher');
      expect(supervisorApi.startWorker).toHaveBeenCalledTimes(1);
    });
  });

  it('stopWorker calls correct API endpoint', async () => {
    const mockResponse = {
      success: true,
      message: "Worker 'detection_worker' stopped successfully",
      worker_name: 'detection_worker',
    };

    vi.mocked(supervisorApi.stopWorker).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useWorkerActions());

    await result.current.stopWorker('detection_worker');

    await waitFor(() => {
      expect(supervisorApi.stopWorker).toHaveBeenCalledWith('detection_worker');
      expect(supervisorApi.stopWorker).toHaveBeenCalledTimes(1);
    });
  });

  it('restartWorker calls correct API endpoint', async () => {
    const mockResponse = {
      success: true,
      message: "Worker 'file_watcher' restarted successfully",
      worker_name: 'file_watcher',
    };

    vi.mocked(supervisorApi.restartWorker).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useWorkerActions());

    await result.current.restartWorker('file_watcher');

    await waitFor(() => {
      expect(supervisorApi.restartWorker).toHaveBeenCalledWith('file_watcher');
      expect(supervisorApi.restartWorker).toHaveBeenCalledTimes(1);
    });
  });

  it('resetWorker calls correct API endpoint', async () => {
    const mockResponse = {
      success: true,
      message: "Worker 'detection_worker' restart count reset successfully",
      worker_name: 'detection_worker',
    };

    vi.mocked(supervisorApi.resetWorkerRestartCount).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useWorkerActions());

    await result.current.resetWorker('detection_worker');

    await waitFor(() => {
      expect(supervisorApi.resetWorkerRestartCount).toHaveBeenCalledWith(
        'detection_worker'
      );
      expect(supervisorApi.resetWorkerRestartCount).toHaveBeenCalledTimes(1);
    });
  });

  it('returns loading state during operations', async () => {
    vi.mocked(supervisorApi.startWorker).mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(
            () =>
              resolve({
                success: true,
                message: 'Started',
                worker_name: 'worker1',
              }),
            100
          );
        })
    );

    const { result } = renderHook(() => useWorkerActions());

    const startPromise = result.current.startWorker('worker1');

    // Check loading state (wait for React to process state update)
    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    await startPromise;

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('returns error state on failure', async () => {
    const errorMessage = 'Failed to start worker';
    vi.mocked(supervisorApi.startWorker).mockRejectedValue(
      new Error(errorMessage)
    );

    const { result } = renderHook(() => useWorkerActions());

    await expect(result.current.startWorker('worker1')).rejects.toThrow();

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe(errorMessage);
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('clears error state on retry', async () => {
    const errorMessage = 'Failed to start worker';
    vi.mocked(supervisorApi.startWorker)
      .mockRejectedValueOnce(new Error(errorMessage))
      .mockResolvedValueOnce({
        success: true,
        message: 'Started',
        worker_name: 'worker1',
      });

    const { result } = renderHook(() => useWorkerActions());

    // First attempt fails
    await expect(result.current.startWorker('worker1')).rejects.toThrow();

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(Error);
    });

    // Second attempt succeeds
    await result.current.startWorker('worker1');

    await waitFor(() => {
      expect(result.current.error).toBeNull();
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('handles stopWorker errors', async () => {
    const errorMessage = 'Worker not found';
    vi.mocked(supervisorApi.stopWorker).mockRejectedValue(
      new Error(errorMessage)
    );

    const { result } = renderHook(() => useWorkerActions());

    await expect(result.current.stopWorker('unknown_worker')).rejects.toThrow();

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  it('handles restartWorker errors', async () => {
    const errorMessage = 'Worker is not running';
    vi.mocked(supervisorApi.restartWorker).mockRejectedValue(
      new Error(errorMessage)
    );

    const { result } = renderHook(() => useWorkerActions());

    await expect(result.current.restartWorker('stopped_worker')).rejects.toThrow();

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  it('handles resetWorker errors', async () => {
    const errorMessage = 'Cannot reset running worker';
    vi.mocked(supervisorApi.resetWorkerRestartCount).mockRejectedValue(
      new Error(errorMessage)
    );

    const { result } = renderHook(() => useWorkerActions());

    await expect(result.current.resetWorker('running_worker')).rejects.toThrow();

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  it('allows multiple operations sequentially', async () => {
    vi.mocked(supervisorApi.startWorker).mockResolvedValue({
      success: true,
      message: 'Started',
      worker_name: 'worker1',
    });

    vi.mocked(supervisorApi.stopWorker).mockResolvedValue({
      success: true,
      message: 'Stopped',
      worker_name: 'worker1',
    });

    const { result } = renderHook(() => useWorkerActions());

    await result.current.startWorker('worker1');

    await waitFor(() => {
      expect(supervisorApi.startWorker).toHaveBeenCalledTimes(1);
    });

    await result.current.stopWorker('worker1');

    await waitFor(() => {
      expect(supervisorApi.stopWorker).toHaveBeenCalledTimes(1);
    });
  });

  it('tracks loading state correctly for multiple operations', async () => {
    let startResolver: (value: { success: boolean; message: string; worker_name: string }) => void;
    let restartResolver: (value: { success: boolean; message: string; worker_name: string }) => void;

    vi.mocked(supervisorApi.startWorker).mockImplementation(
      () =>
        new Promise((resolve) => {
          startResolver = resolve;
        })
    );

    vi.mocked(supervisorApi.restartWorker).mockImplementation(
      () =>
        new Promise((resolve) => {
          restartResolver = resolve;
        })
    );

    const { result } = renderHook(() => useWorkerActions());

    // Start first operation
    const startPromise = result.current.startWorker('worker1');

    // Wait for loading state to become true
    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    // Resolve the first operation
    startResolver!({
      success: true,
      message: 'Started',
      worker_name: 'worker1',
    });

    await startPromise;

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Start second operation
    const restartPromise = result.current.restartWorker('worker1');

    // Wait for loading state to become true again
    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    // Resolve the second operation
    restartResolver!({
      success: true,
      message: 'Restarted',
      worker_name: 'worker1',
    });

    await restartPromise;

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('returns success response from API', async () => {
    const mockResponse = {
      success: true,
      message: "Worker 'file_watcher' started successfully",
      worker_name: 'file_watcher',
    };

    vi.mocked(supervisorApi.startWorker).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useWorkerActions());

    const response = await result.current.startWorker('file_watcher');

    expect(response).toEqual(mockResponse);
  });

  it('handles API errors with detailed messages', async () => {
    const detailedError = {
      message: 'Worker operation failed',
      details: 'Worker is in failed state and cannot be started',
    };

    vi.mocked(supervisorApi.startWorker).mockRejectedValue(detailedError);

    const { result } = renderHook(() => useWorkerActions());

    await expect(result.current.startWorker('failed_worker')).rejects.toEqual(
      detailedError
    );

    await waitFor(() => {
      expect(result.current.error).toEqual(detailedError);
    });
  });
});
