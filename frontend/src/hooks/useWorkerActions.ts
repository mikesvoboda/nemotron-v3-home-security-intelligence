/**
 * Hook for worker control actions.
 *
 * Provides methods to start, stop, restart, and reset workers with
 * loading and error state management.
 *
 * @example
 * ```typescript
 * const { startWorker, stopWorker, restartWorker, resetWorker, isLoading, error } = useWorkerActions();
 *
 * // Start a stopped worker
 * await startWorker('file_watcher');
 *
 * // Stop a running worker
 * await stopWorker('detection_worker');
 *
 * // Restart a worker
 * await restartWorker('file_watcher');
 *
 * // Reset a failed worker's restart count
 * await resetWorker('failed_worker');
 * ```
 */

import { useState, useCallback } from 'react';

import * as supervisorApi from '../services/supervisorApi';

/**
 * Response from worker control operations.
 */
export interface WorkerControlResponse {
  /** Whether the operation succeeded */
  success: boolean;
  /** Human-readable message about the operation result */
  message: string;
  /** Name of the worker that was affected */
  worker_name: string;
}

/**
 * Return type for useWorkerActions hook.
 */
export interface UseWorkerActionsResult {
  /** Start a stopped worker */
  startWorker: (name: string) => Promise<WorkerControlResponse>;
  /** Stop a running worker */
  stopWorker: (name: string) => Promise<WorkerControlResponse>;
  /** Restart a worker (stop and start) */
  restartWorker: (name: string) => Promise<WorkerControlResponse>;
  /** Reset a failed worker's restart count */
  resetWorker: (name: string) => Promise<WorkerControlResponse>;
  /** Whether any operation is currently in progress */
  isLoading: boolean;
  /** Error from the last failed operation, null if last operation succeeded */
  error: Error | null;
}

/**
 * Hook to control worker lifecycle (start, stop, restart, reset).
 *
 * @returns Object with worker control methods and loading/error state
 */
export function useWorkerActions(): UseWorkerActionsResult {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  /**
   * Wrapper to handle loading state and errors for API calls.
   */
  const executeAction = useCallback(
    async <T>(action: () => Promise<T>): Promise<T> => {
      setIsLoading(true);
      setError(null);

      try {
        const result = await action();
        setIsLoading(false);
        return result;
      } catch (err) {
        setIsLoading(false);
        setError(err instanceof Error ? err : new Error(String(err)));
        throw err;
      }
    },
    []
  );

  const startWorker = useCallback(
    async (name: string): Promise<WorkerControlResponse> => {
      return executeAction(() => supervisorApi.startWorker(name));
    },
    [executeAction]
  );

  const stopWorker = useCallback(
    async (name: string): Promise<WorkerControlResponse> => {
      return executeAction(() => supervisorApi.stopWorker(name));
    },
    [executeAction]
  );

  const restartWorker = useCallback(
    async (name: string): Promise<WorkerControlResponse> => {
      return executeAction(() => supervisorApi.restartWorker(name));
    },
    [executeAction]
  );

  const resetWorker = useCallback(
    async (name: string): Promise<WorkerControlResponse> => {
      return executeAction(() => supervisorApi.resetWorkerRestartCount(name));
    },
    [executeAction]
  );

  return {
    startWorker,
    stopWorker,
    restartWorker,
    resetWorker,
    isLoading,
    error,
  };
}
