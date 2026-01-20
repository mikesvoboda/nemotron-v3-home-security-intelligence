/**
 * useWorkerEvents - Hook for subscribing to WORKER_* WebSocket events (NEM-3127)
 *
 * This hook subscribes to all worker-related WebSocket events and updates
 * the worker status store. It also shows toast notifications for worker
 * stopped and error events.
 *
 * Events handled:
 * - WORKER_STARTED: Update pipeline health indicator to green/healthy
 * - WORKER_STOPPED: Update pipeline health indicator to yellow/warning, show toast
 * - WORKER_ERROR: Show error toast, update indicator to red/error
 * - WORKER_HEALTH_CHECK_FAILED: Update status based on failure count
 * - WORKER_RESTARTING: Update indicator to yellow/warning
 * - WORKER_RECOVERED: Update pipeline health indicator to green/healthy
 *
 * @module hooks/useWorkerEvents
 *
 * @example
 * ```tsx
 * function App() {
 *   // Subscribe to worker events at app level
 *   useWorkerEvents();
 *
 *   return <Dashboard />;
 * }
 * ```
 */

import { useEffect, useRef } from 'react';

import { useToast } from './useToast';
import { useWebSocketEvents } from './useWebSocketEvent';
import { useWorkerStatusStore } from '../stores/worker-status-store';
import { WSEventType } from '../types/websocket-events';

import type {
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
 * Options for the useWorkerEvents hook.
 */
export interface UseWorkerEventsOptions {
  /**
   * Whether to show toast notifications for worker events.
   * @default true
   */
  showToasts?: boolean;

  /**
   * Whether to enable the WebSocket connection.
   * @default true
   */
  enabled?: boolean;

  /**
   * Called when any worker event is received.
   */
  onWorkerEvent?: (type: string, payload: unknown) => void;
}

/**
 * Return type for the useWorkerEvents hook.
 */
export interface UseWorkerEventsReturn {
  /** Whether the WebSocket is currently connected */
  isConnected: boolean;
  /** Number of reconnection attempts */
  reconnectCount: number;
  /** Whether max reconnection attempts have been exhausted */
  hasExhaustedRetries: boolean;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for subscribing to worker WebSocket events and updating the worker status store.
 *
 * This hook should be used at the app level to ensure worker status is tracked
 * globally. It updates the Zustand store and shows toast notifications for
 * worker stopped and error events.
 *
 * @param options - Configuration options
 * @returns WebSocket connection state
 *
 * @example
 * ```tsx
 * function App() {
 *   const { isConnected } = useWorkerEvents({
 *     showToasts: true,
 *     onWorkerEvent: (type, payload) => {
 *       console.log('Worker event:', type, payload);
 *     },
 *   });
 *
 *   return (
 *     <div>
 *       <WorkerStatusIndicator />
 *       {!isConnected && <ConnectionWarning />}
 *     </div>
 *   );
 * }
 * ```
 */
export function useWorkerEvents(options: UseWorkerEventsOptions = {}): UseWorkerEventsReturn {
  const { showToasts = true, enabled = true, onWorkerEvent } = options;

  // Get store actions
  const {
    handleWorkerStarted,
    handleWorkerStopped,
    handleWorkerError,
    handleWorkerHealthCheckFailed,
    handleWorkerRestarting,
    handleWorkerRecovered,
  } = useWorkerStatusStore();

  // Get toast functions
  const toast = useToast();

  // Use refs to avoid stale closures in handlers
  const showToastsRef = useRef(showToasts);
  const onWorkerEventRef = useRef(onWorkerEvent);
  const toastRef = useRef(toast);

  useEffect(() => {
    showToastsRef.current = showToasts;
    onWorkerEventRef.current = onWorkerEvent;
    toastRef.current = toast;
  });

  // Subscribe to worker events
  const { isConnected, reconnectCount, hasExhaustedRetries } = useWebSocketEvents(
    {
      [WSEventType.WORKER_STARTED]: (payload: WorkerStartedPayload) => {
        handleWorkerStarted(payload);
        onWorkerEventRef.current?.('worker.started', payload);
        // No toast for worker started (silent)
      },

      [WSEventType.WORKER_STOPPED]: (payload: WorkerStoppedPayload) => {
        handleWorkerStopped(payload);
        onWorkerEventRef.current?.('worker.stopped', payload);

        // Show warning toast
        if (showToastsRef.current) {
          const reason = payload.reason ? `: ${payload.reason}` : '';
          toastRef.current.warning(`Worker stopped: ${payload.worker_name}${reason}`, {
            description: `${payload.worker_type} worker has stopped`,
          });
        }
      },

      [WSEventType.WORKER_ERROR]: (payload: WorkerErrorPayload) => {
        handleWorkerError(payload);
        onWorkerEventRef.current?.('worker.error', payload);

        // Show error toast
        if (showToastsRef.current) {
          toastRef.current.error(`Worker error: ${payload.worker_name}`, {
            description: payload.error,
            duration: 10000, // Show error toasts longer
          });
        }
      },

      [WSEventType.WORKER_HEALTH_CHECK_FAILED]: (payload: WorkerHealthCheckFailedPayload) => {
        handleWorkerHealthCheckFailed(payload);
        onWorkerEventRef.current?.('worker.health_check_failed', payload);

        // Show error toast if multiple failures
        if (showToastsRef.current && payload.failure_count >= 3) {
          toastRef.current.error(`Worker health check failed: ${payload.worker_name}`, {
            description: `${payload.failure_count} consecutive failures`,
          });
        }
      },

      [WSEventType.WORKER_RESTARTING]: (payload: WorkerRestartingPayload) => {
        handleWorkerRestarting(payload);
        onWorkerEventRef.current?.('worker.restarting', payload);

        // Show info toast for restart
        if (showToastsRef.current) {
          const attemptInfo = payload.max_attempts
            ? ` (attempt ${payload.attempt}/${payload.max_attempts})`
            : ` (attempt ${payload.attempt})`;
          toastRef.current.info(`Worker restarting: ${payload.worker_name}${attemptInfo}`);
        }
      },

      [WSEventType.WORKER_RECOVERED]: (payload: WorkerRecoveredPayload) => {
        handleWorkerRecovered(payload);
        onWorkerEventRef.current?.('worker.recovered', payload);

        // Show success toast for recovery
        if (showToastsRef.current) {
          const durationInfo = payload.recovery_duration_ms
            ? ` in ${Math.round(payload.recovery_duration_ms)}ms`
            : '';
          toastRef.current.success(`Worker recovered: ${payload.worker_name}${durationInfo}`);
        }
      },
    },
    { enabled }
  );

  return {
    isConnected,
    reconnectCount,
    hasExhaustedRetries,
  };
}

export default useWorkerEvents;
