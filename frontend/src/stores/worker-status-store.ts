/**
 * Worker Status State Management Store (NEM-3127)
 *
 * Provides central state management for pipeline worker health status across frontend components.
 * Uses Zustand for reactive state management, allowing components to subscribe to worker events
 * and display pipeline health indicators.
 *
 * Worker events are received via WebSocket and update the store state:
 * - WORKER_STARTED: Worker is running (healthy/green)
 * - WORKER_STOPPED: Worker has stopped (warning/yellow)
 * - WORKER_ERROR: Worker encountered an error (error/red)
 * - WORKER_HEALTH_CHECK_FAILED: Health check failed (error/red)
 * - WORKER_RESTARTING: Worker is restarting (warning/yellow)
 * - WORKER_RECOVERED: Worker recovered from error (healthy/green)
 *
 * Enhancements (NEM-3399, NEM-3400, NEM-3428):
 * - DevTools middleware for debugging
 * - useShallow hooks for selective subscriptions
 * - Memoized selectors for derived state
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { useShallow } from 'zustand/shallow';

import type {
  WorkerType,
  WorkerState,
  WorkerStartedPayload,
  WorkerStoppedPayload,
  WorkerErrorPayload,
  WorkerHealthCheckFailedPayload,
  WorkerRestartingPayload,
  WorkerRecoveredPayload,
} from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/**
 * Health status for the pipeline.
 */
export type PipelineHealthStatus = 'healthy' | 'warning' | 'error' | 'unknown';

/**
 * Individual worker status information.
 */
export interface WorkerStatus {
  /** Worker instance name */
  name: string;
  /** Type of worker */
  type: WorkerType;
  /** Current state of the worker */
  state: WorkerState;
  /** Last error message if in error state */
  lastError?: string;
  /** Last error type if in error state */
  lastErrorType?: string;
  /** Number of consecutive health check failures */
  failureCount?: number;
  /** Current restart attempt if restarting */
  restartAttempt?: number;
  /** Maximum restart attempts allowed */
  maxRestartAttempts?: number;
  /** ISO 8601 timestamp of last status update */
  lastUpdated: string;
  /** Whether the last error was recoverable */
  recoverable?: boolean;
}

/**
 * Worker status store state and actions.
 */
export interface WorkerStatusState {
  /** Map of worker name to status */
  workers: Record<string, WorkerStatus>;
  /** Overall pipeline health status */
  pipelineHealth: PipelineHealthStatus;
  /** Whether any worker has an error */
  hasError: boolean;
  /** Whether any worker is in warning state (stopped/restarting) */
  hasWarning: boolean;
  /** Number of workers currently running */
  runningCount: number;
  /** Total number of tracked workers */
  totalCount: number;

  // Actions
  /** Handle worker.started event */
  handleWorkerStarted: (payload: WorkerStartedPayload) => void;
  /** Handle worker.stopped event */
  handleWorkerStopped: (payload: WorkerStoppedPayload) => void;
  /** Handle worker.error event */
  handleWorkerError: (payload: WorkerErrorPayload) => void;
  /** Handle worker.health_check_failed event */
  handleWorkerHealthCheckFailed: (payload: WorkerHealthCheckFailedPayload) => void;
  /** Handle worker.restarting event */
  handleWorkerRestarting: (payload: WorkerRestartingPayload) => void;
  /** Handle worker.recovered event */
  handleWorkerRecovered: (payload: WorkerRecoveredPayload) => void;
  /** Clear all worker state */
  clear: () => void;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Calculate derived state from workers map.
 */
function calculateDerivedState(workers: Record<string, WorkerStatus>): {
  pipelineHealth: PipelineHealthStatus;
  hasError: boolean;
  hasWarning: boolean;
  runningCount: number;
  totalCount: number;
} {
  const workerList = Object.values(workers);
  const totalCount = workerList.length;

  if (totalCount === 0) {
    return {
      pipelineHealth: 'unknown',
      hasError: false,
      hasWarning: false,
      runningCount: 0,
      totalCount: 0,
    };
  }

  const errorWorkers = workerList.filter((w) => w.state === 'error');
  const warningWorkers = workerList.filter(
    (w) => w.state === 'stopped' || w.state === 'stopping' || w.state === 'starting'
  );
  const runningWorkers = workerList.filter((w) => w.state === 'running');

  const hasError = errorWorkers.length > 0;
  const hasWarning = warningWorkers.length > 0;

  let pipelineHealth: PipelineHealthStatus = 'healthy';
  if (hasError) {
    pipelineHealth = 'error';
  } else if (hasWarning) {
    pipelineHealth = 'warning';
  } else if (runningWorkers.length === totalCount) {
    pipelineHealth = 'healthy';
  }

  return {
    pipelineHealth,
    hasError,
    hasWarning,
    runningCount: runningWorkers.length,
    totalCount,
  };
}

// ============================================================================
// Store (NEM-3400: DevTools middleware)
// ============================================================================

/**
 * Zustand store for worker status state management.
 *
 * Features:
 * - Tracks status of all pipeline workers
 * - Calculates overall pipeline health
 * - Provides flags for error/warning states
 * - Shared across components for consistent health display
 * - DevTools integration for debugging (NEM-3400)
 *
 * @example
 * ```tsx
 * import { useWorkerStatusStore } from '@/stores/worker-status-store';
 *
 * // In a component
 * const { pipelineHealth, workers, hasError } = useWorkerStatusStore();
 *
 * // Display health indicator
 * if (pipelineHealth === 'healthy') {
 *   return <Badge color="green">Pipeline Healthy</Badge>;
 * }
 * ```
 */
export const useWorkerStatusStore = create<WorkerStatusState>()(
  devtools(
    (set, get) => ({
      workers: {},
      pipelineHealth: 'unknown',
      hasError: false,
      hasWarning: false,
      runningCount: 0,
      totalCount: 0,

      handleWorkerStarted: (payload: WorkerStartedPayload) => {
        const workers = {
          ...get().workers,
          [payload.worker_name]: {
            name: payload.worker_name,
            type: payload.worker_type,
            state: 'running' as WorkerState,
            lastUpdated: payload.timestamp,
            lastError: undefined,
            lastErrorType: undefined,
            failureCount: undefined,
            restartAttempt: undefined,
            maxRestartAttempts: undefined,
            recoverable: undefined,
          },
        };

        set(
          {
            workers,
            ...calculateDerivedState(workers),
          },
          undefined,
          'handleWorkerStarted'
        );
      },

      handleWorkerStopped: (payload: WorkerStoppedPayload) => {
        const workers = {
          ...get().workers,
          [payload.worker_name]: {
            ...get().workers[payload.worker_name],
            name: payload.worker_name,
            type: payload.worker_type,
            state: 'stopped' as WorkerState,
            lastUpdated: payload.timestamp,
            lastError: payload.reason,
          },
        };

        set(
          {
            workers,
            ...calculateDerivedState(workers),
          },
          undefined,
          'handleWorkerStopped'
        );
      },

      handleWorkerError: (payload: WorkerErrorPayload) => {
        const workers = {
          ...get().workers,
          [payload.worker_name]: {
            ...get().workers[payload.worker_name],
            name: payload.worker_name,
            type: payload.worker_type,
            state: 'error' as WorkerState,
            lastError: payload.error,
            lastErrorType: payload.error_type,
            lastUpdated: payload.timestamp,
            recoverable: payload.recoverable,
          },
        };

        set(
          {
            workers,
            ...calculateDerivedState(workers),
          },
          undefined,
          'handleWorkerError'
        );
      },

      handleWorkerHealthCheckFailed: (payload: WorkerHealthCheckFailedPayload) => {
        const currentWorker = get().workers[payload.worker_name];
        const workers = {
          ...get().workers,
          [payload.worker_name]: {
            ...currentWorker,
            name: payload.worker_name,
            type: payload.worker_type,
            // Only change to error state if enough failures
            state:
              payload.failure_count >= 3
                ? ('error' as WorkerState)
                : (currentWorker?.state ?? 'running'),
            lastError: payload.error,
            lastErrorType: payload.error_type,
            failureCount: payload.failure_count,
            lastUpdated: payload.timestamp,
          },
        };

        set(
          {
            workers,
            ...calculateDerivedState(workers),
          },
          undefined,
          'handleWorkerHealthCheckFailed'
        );
      },

      handleWorkerRestarting: (payload: WorkerRestartingPayload) => {
        const workers = {
          ...get().workers,
          [payload.worker_name]: {
            ...get().workers[payload.worker_name],
            name: payload.worker_name,
            type: payload.worker_type,
            state: 'starting' as WorkerState,
            restartAttempt: payload.attempt,
            maxRestartAttempts: payload.max_attempts,
            lastError: payload.reason,
            lastUpdated: payload.timestamp,
          },
        };

        set(
          {
            workers,
            ...calculateDerivedState(workers),
          },
          undefined,
          'handleWorkerRestarting'
        );
      },

      handleWorkerRecovered: (payload: WorkerRecoveredPayload) => {
        const workers = {
          ...get().workers,
          [payload.worker_name]: {
            name: payload.worker_name,
            type: payload.worker_type,
            state: 'running' as WorkerState,
            lastUpdated: payload.timestamp,
            lastError: undefined,
            lastErrorType: undefined,
            failureCount: undefined,
            restartAttempt: undefined,
            maxRestartAttempts: undefined,
            recoverable: undefined,
          },
        };

        set(
          {
            workers,
            ...calculateDerivedState(workers),
          },
          undefined,
          'handleWorkerRecovered'
        );
      },

      clear: () => {
        set(
          {
            workers: {},
            pipelineHealth: 'unknown',
            hasError: false,
            hasWarning: false,
            runningCount: 0,
            totalCount: 0,
          },
          undefined,
          'clear'
        );
      },
    }),
    { name: 'worker-status-store', enabled: import.meta.env.DEV }
  )
);

// ============================================================================
// Selectors
// ============================================================================

/**
 * Selector for workers with errors.
 */
export const selectErrorWorkers = (state: WorkerStatusState): WorkerStatus[] => {
  return Object.values(state.workers).filter((w) => w.state === 'error');
};

/**
 * Selector for workers in warning state (stopped/restarting).
 */
export const selectWarningWorkers = (state: WorkerStatusState): WorkerStatus[] => {
  return Object.values(state.workers).filter(
    (w) => w.state === 'stopped' || w.state === 'stopping' || w.state === 'starting'
  );
};

/**
 * Selector for running workers.
 */
export const selectRunningWorkers = (state: WorkerStatusState): WorkerStatus[] => {
  return Object.values(state.workers).filter((w) => w.state === 'running');
};

/**
 * Selector for a specific worker by name.
 */
export const selectWorkerByName = (
  state: WorkerStatusState,
  name: string
): WorkerStatus | undefined => {
  return state.workers[name];
};

/**
 * Selector for workers by type.
 */
export const selectWorkersByType = (
  state: WorkerStatusState,
  type: WorkerType
): WorkerStatus[] => {
  return Object.values(state.workers).filter((w) => w.type === type);
};

// ============================================================================
// Memoized Selectors (NEM-3428)
// ============================================================================

/**
 * Cache for memoized selector results.
 */
const workerSelectorCache = {
  errorWorkers: {
    workers: {} as Record<string, WorkerStatus>,
    result: [] as WorkerStatus[],
  },
  warningWorkers: {
    workers: {} as Record<string, WorkerStatus>,
    result: [] as WorkerStatus[],
  },
  runningWorkers: {
    workers: {} as Record<string, WorkerStatus>,
    result: [] as WorkerStatus[],
  },
};

/**
 * Memoized selector for workers with errors.
 * Returns cached result if workers haven't changed.
 */
export const selectErrorWorkersMemoized = (state: WorkerStatusState): WorkerStatus[] => {
  if (state.workers === workerSelectorCache.errorWorkers.workers) {
    return workerSelectorCache.errorWorkers.result;
  }
  const result = Object.values(state.workers).filter((w) => w.state === 'error');
  workerSelectorCache.errorWorkers = { workers: state.workers, result };
  return result;
};

/**
 * Memoized selector for workers in warning state.
 * Returns cached result if workers haven't changed.
 */
export const selectWarningWorkersMemoized = (state: WorkerStatusState): WorkerStatus[] => {
  if (state.workers === workerSelectorCache.warningWorkers.workers) {
    return workerSelectorCache.warningWorkers.result;
  }
  const result = Object.values(state.workers).filter(
    (w) => w.state === 'stopped' || w.state === 'stopping' || w.state === 'starting'
  );
  workerSelectorCache.warningWorkers = { workers: state.workers, result };
  return result;
};

/**
 * Memoized selector for running workers.
 * Returns cached result if workers haven't changed.
 */
export const selectRunningWorkersMemoized = (state: WorkerStatusState): WorkerStatus[] => {
  if (state.workers === workerSelectorCache.runningWorkers.workers) {
    return workerSelectorCache.runningWorkers.result;
  }
  const result = Object.values(state.workers).filter((w) => w.state === 'running');
  workerSelectorCache.runningWorkers = { workers: state.workers, result };
  return result;
};

// ============================================================================
// Shallow Hooks for Selective Subscriptions (NEM-3399)
// ============================================================================

/**
 * Hook to select pipeline health status with shallow equality.
 * Prevents re-renders when only worker details change but health state stays the same.
 *
 * @example
 * ```tsx
 * const { pipelineHealth, hasError, hasWarning } = usePipelineHealth();
 * ```
 */
export function usePipelineHealth() {
  return useWorkerStatusStore(
    useShallow((state) => ({
      pipelineHealth: state.pipelineHealth,
      hasError: state.hasError,
      hasWarning: state.hasWarning,
      runningCount: state.runningCount,
      totalCount: state.totalCount,
    }))
  );
}

/**
 * Hook to select only the workers map.
 *
 * @example
 * ```tsx
 * const workers = useWorkers();
 * ```
 */
export function useWorkers() {
  return useWorkerStatusStore((state) => state.workers);
}

/**
 * Hook to select worker actions only.
 * Actions are stable references and don't cause re-renders.
 *
 * @example
 * ```tsx
 * const { handleWorkerStarted, handleWorkerError, clear } = useWorkerActions();
 * ```
 */
export function useWorkerActions() {
  return useWorkerStatusStore(
    useShallow((state) => ({
      handleWorkerStarted: state.handleWorkerStarted,
      handleWorkerStopped: state.handleWorkerStopped,
      handleWorkerError: state.handleWorkerError,
      handleWorkerHealthCheckFailed: state.handleWorkerHealthCheckFailed,
      handleWorkerRestarting: state.handleWorkerRestarting,
      handleWorkerRecovered: state.handleWorkerRecovered,
      clear: state.clear,
    }))
  );
}
