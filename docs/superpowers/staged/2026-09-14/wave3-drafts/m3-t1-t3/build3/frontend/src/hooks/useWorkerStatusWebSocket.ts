/**
 * useWorkerStatusWebSocket - WebSocket hook for pipeline worker status events
 *
 * NEM-3127: Consumes worker.* WebSocket events broadcast by the backend
 * when pipeline workers change state.
 *
 * Events handled:
 * - worker.started: Worker began running
 * - worker.stopped: Worker stopped
 * - worker.error: Worker encountered an error
 * - worker.health_check_failed: Health check failed
 * - worker.restarting: Worker is restarting
 * - worker.recovered: Worker recovered from error
 *
 * @module hooks/useWorkerStatusWebSocket
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { logger } from '../services/logger';
import { isHeartbeatMessage, isErrorMessage } from '../types/websocket';

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
 * Worker event types
 */
export type WorkerEventType =
  | 'worker.started'
  | 'worker.stopped'
  | 'worker.error'
  | 'worker.health_check_failed'
  | 'worker.restarting'
  | 'worker.recovered';

/**
 * Union of all worker event payloads
 */
export type WorkerEventPayload =
  | WorkerStartedPayload
  | WorkerStoppedPayload
  | WorkerErrorPayload
  | WorkerHealthCheckFailedPayload
  | WorkerRestartingPayload
  | WorkerRecoveredPayload;

/**
 * Worker status entry with all relevant information
 */
export interface WorkerStatusEntry {
  /** Worker instance name */
  name: string;
  /** Type of worker */
  type: WorkerType;
  /** Current state of the worker */
  state: WorkerState;
  /** Last error message if any */
  lastError?: string;
  /** Last error type if any */
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
 * Map of worker names to their status
 */
export type WorkerStatusMap = Record<string, WorkerStatusEntry>;

/**
 * Overall pipeline health status
 */
export type PipelineHealthStatus = 'healthy' | 'warning' | 'error' | 'unknown';

/**
 * Callback type for worker status changes
 */
export type WorkerStatusChangeHandler = (
  eventType: WorkerEventType,
  payload: WorkerEventPayload
) => void;

/**
 * Options for configuring the useWorkerStatusWebSocket hook
 */
export interface UseWorkerStatusWebSocketOptions {
  /**
   * Whether to enable the WebSocket connection
   * @default true
   */
  enabled?: boolean;

  /**
   * Filter to only track status changes for this worker
   * If not provided, all workers are tracked
   */
  filterWorker?: string;

  /**
   * Filter to only track workers of this type
   * If not provided, all worker types are tracked
   */
  filterWorkerType?: WorkerType;

  /**
   * Called when a worker status changes
   */
  onStatusChange?: WorkerStatusChangeHandler;
}

/**
 * Return type for the useWorkerStatusWebSocket hook
 */
export interface UseWorkerStatusWebSocketReturn {
  /** Map of all known worker statuses */
  workers: WorkerStatusMap;

  /** The most recent status change */
  latestChange: { eventType: WorkerEventType; payload: WorkerEventPayload } | null;

  /** Whether the WebSocket is connected */
  isConnected: boolean;

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

  /** Get status for a specific worker */
  getWorkerStatus: (workerName: string) => WorkerStatusEntry | undefined;

  /** Check if a worker is running */
  isWorkerRunning: (workerName: string) => boolean;

  /** Get list of workers in error state */
  getErrorWorkers: () => WorkerStatusEntry[];

  /** Get list of workers in warning state */
  getWarningWorkers: () => WorkerStatusEntry[];

  /** Clear all tracked worker statuses */
  clearWorkers: () => void;
}

// ============================================================================
// Constants
// ============================================================================

const WORKER_EVENT_TYPES: WorkerEventType[] = [
  'worker.started',
  'worker.stopped',
  'worker.error',
  'worker.health_check_failed',
  'worker.restarting',
  'worker.recovered',
];

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for worker event messages
 */
function isWorkerEventMessage(
  value: unknown
): value is { type: WorkerEventType; data: WorkerEventPayload } {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const msg = value as Record<string, unknown>;
  if (!msg.type || typeof msg.type !== 'string') {
    return false;
  }

  if (!WORKER_EVENT_TYPES.includes(msg.type as WorkerEventType)) {
    return false;
  }

  if (!msg.data || typeof msg.data !== 'object') {
    return false;
  }

  const data = msg.data as Record<string, unknown>;
  return typeof data.worker_name === 'string' && typeof data.worker_type === 'string';
}

/**
 * Extract worker name from payload
 */
function getWorkerName(payload: WorkerEventPayload): string {
  return payload.worker_name;
}

/**
 * Extract worker type from payload
 */
function getWorkerType(payload: WorkerEventPayload): WorkerType {
  return payload.worker_type;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Calculate derived state from workers map
 */
function calculateDerivedState(workers: WorkerStatusMap): {
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

/**
 * Create a worker status entry from an event
 */
function createWorkerStatusEntry(
  eventType: WorkerEventType,
  payload: WorkerEventPayload,
  existingEntry?: WorkerStatusEntry
): WorkerStatusEntry {
  const base: Partial<WorkerStatusEntry> = {
    name: getWorkerName(payload),
    type: getWorkerType(payload),
    lastUpdated: payload.timestamp,
  };

  switch (eventType) {
    case 'worker.started':
      return {
        ...base,
        name: payload.worker_name,
        type: payload.worker_type,
        state: 'running',
        lastUpdated: payload.timestamp,
        // Clear error info on start
        lastError: undefined,
        lastErrorType: undefined,
        failureCount: undefined,
        restartAttempt: undefined,
        maxRestartAttempts: undefined,
        recoverable: undefined,
      };

    case 'worker.stopped': {
      const stoppedPayload = payload as WorkerStoppedPayload;
      return {
        ...(existingEntry || {}),
        ...base,
        name: payload.worker_name,
        type: payload.worker_type,
        state: 'stopped',
        lastUpdated: payload.timestamp,
        lastError: stoppedPayload.reason,
      };
    }

    case 'worker.error': {
      const errorPayload = payload as WorkerErrorPayload;
      return {
        ...(existingEntry || {}),
        ...base,
        name: payload.worker_name,
        type: payload.worker_type,
        state: 'error',
        lastUpdated: payload.timestamp,
        lastError: errorPayload.error,
        lastErrorType: errorPayload.error_type,
        recoverable: errorPayload.recoverable,
      };
    }

    case 'worker.health_check_failed': {
      const healthPayload = payload as WorkerHealthCheckFailedPayload;
      // Only change to error state if enough failures
      const newState: WorkerState =
        healthPayload.failure_count >= 3 ? 'error' : (existingEntry?.state ?? 'running');
      return {
        ...(existingEntry || {}),
        ...base,
        name: payload.worker_name,
        type: payload.worker_type,
        state: newState,
        lastUpdated: payload.timestamp,
        lastError: healthPayload.error,
        lastErrorType: healthPayload.error_type,
        failureCount: healthPayload.failure_count,
      };
    }

    case 'worker.restarting': {
      const restartPayload = payload as WorkerRestartingPayload;
      return {
        ...(existingEntry || {}),
        ...base,
        name: payload.worker_name,
        type: payload.worker_type,
        state: 'starting',
        lastUpdated: payload.timestamp,
        restartAttempt: restartPayload.attempt,
        maxRestartAttempts: restartPayload.max_attempts,
        lastError: restartPayload.reason,
      };
    }

    case 'worker.recovered':
      return {
        ...base,
        name: payload.worker_name,
        type: payload.worker_type,
        state: 'running',
        lastUpdated: payload.timestamp,
        // Clear all error info on recovery
        lastError: undefined,
        lastErrorType: undefined,
        failureCount: undefined,
        restartAttempt: undefined,
        maxRestartAttempts: undefined,
        recoverable: undefined,
      };

    default:
      return {
        ...(existingEntry || {}),
        ...base,
        name: payload.worker_name,
        type: payload.worker_type,
        state: existingEntry?.state ?? 'running',
        lastUpdated: payload.timestamp,
      };
  }
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to subscribe to real-time worker status WebSocket events.
 *
 * Tracks pipeline worker health changes and provides utilities for
 * checking worker and pipeline status.
 *
 * @param options - Configuration options
 * @returns Worker status state and utilities
 *
 * @example
 * ```tsx
 * const {
 *   workers,
 *   pipelineHealth,
 *   hasError,
 *   getErrorWorkers,
 * } = useWorkerStatusWebSocket({
 *   onStatusChange: (eventType, payload) => {
 *     if (eventType === 'worker.error') {
 *       showAlert(`Worker ${payload.worker_name} error: ${payload.error}`);
 *     }
 *   },
 * });
 *
 * // Check overall pipeline health
 * if (pipelineHealth === 'error') {
 *   console.log('Pipeline unhealthy!');
 * }
 *
 * // Get specific worker status
 * const detectionWorker = workers['detection-worker-1'];
 * if (detectionWorker?.state === 'error') {
 *   console.log('Detection worker error:', detectionWorker.lastError);
 * }
 * ```
 */
export function useWorkerStatusWebSocket(
  options: UseWorkerStatusWebSocketOptions = {}
): UseWorkerStatusWebSocketReturn {
  const { enabled = true, filterWorker, filterWorkerType, onStatusChange } = options;

  // State
  const [workers, setWorkers] = useState<WorkerStatusMap>({});
  const [latestChange, setLatestChange] = useState<{
    eventType: WorkerEventType;
    payload: WorkerEventPayload;
  } | null>(null);

  // Track mounted state
  const isMountedRef = useRef(true);

  // Store callback in ref
  const onStatusChangeRef = useRef(onStatusChange);

  useEffect(() => {
    onStatusChangeRef.current = onStatusChange;
  });

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback(
    (data: unknown) => {
      if (!isMountedRef.current) {
        return;
      }

      // Handle worker.* messages
      if (isWorkerEventMessage(data)) {
        const eventType = data.type;
        const payload = data.data;
        const workerName = getWorkerName(payload);
        const workerType = getWorkerType(payload);

        // Filter by worker name if specified
        if (filterWorker && workerName !== filterWorker) {
          return;
        }

        // Filter by worker type if specified
        if (filterWorkerType && workerType !== filterWorkerType) {
          return;
        }

        logger.debug('Worker event received', {
          component: 'useWorkerStatusWebSocket',
          eventType,
          workerName,
          workerType,
        });

        setWorkers((prev) => {
          const existingEntry = prev[workerName];
          const newEntry = createWorkerStatusEntry(eventType, payload, existingEntry);
          return {
            ...prev,
            [workerName]: newEntry,
          };
        });

        setLatestChange({ eventType, payload });

        onStatusChangeRef.current?.(eventType, payload);
        return;
      }

      // Handle other message types (silently ignore)
      if (isHeartbeatMessage(data)) {
        return;
      }

      if (isErrorMessage(data)) {
        logger.warn('Worker status WebSocket error', {
          component: 'useWorkerStatusWebSocket',
          message: data.message,
        });
        return;
      }
    },
    [filterWorker, filterWorkerType]
  );

  // Build WebSocket options
  const wsOptions = buildWebSocketOptions('/ws/system');

  // Connect to WebSocket
  const { isConnected } = useWebSocket(
    enabled
      ? {
          url: wsOptions.url,
          protocols: wsOptions.protocols,
          onMessage: handleMessage,
          reconnect: true,
          reconnectInterval: 1000,
          reconnectAttempts: 15,
          connectionTimeout: 10000,
          autoRespondToHeartbeat: true,
        }
      : {
          url: wsOptions.url,
          protocols: wsOptions.protocols,
          onMessage: handleMessage,
          reconnect: false,
        }
  );

  // Helper functions
  const getWorkerStatus = useCallback(
    (workerName: string): WorkerStatusEntry | undefined => {
      return workers[workerName];
    },
    [workers]
  );

  const isWorkerRunning = useCallback(
    (workerName: string): boolean => {
      const status = workers[workerName]?.state;
      return status === 'running';
    },
    [workers]
  );

  const getErrorWorkers = useCallback((): WorkerStatusEntry[] => {
    return Object.values(workers).filter((w) => w.state === 'error');
  }, [workers]);

  const getWarningWorkers = useCallback((): WorkerStatusEntry[] => {
    return Object.values(workers).filter(
      (w) => w.state === 'stopped' || w.state === 'stopping' || w.state === 'starting'
    );
  }, [workers]);

  const clearWorkers = useCallback(() => {
    if (!isMountedRef.current) return;
    setWorkers({});
    setLatestChange(null);
  }, []);

  // Compute derived state
  const derivedState = useMemo(() => calculateDerivedState(workers), [workers]);

  return {
    workers,
    latestChange,
    isConnected,
    pipelineHealth: derivedState.pipelineHealth,
    hasError: derivedState.hasError,
    hasWarning: derivedState.hasWarning,
    runningCount: derivedState.runningCount,
    totalCount: derivedState.totalCount,
    getWorkerStatus,
    isWorkerRunning,
    getErrorWorkers,
    getWarningWorkers,
    clearWorkers,
  };
}

export default useWorkerStatusWebSocket;
