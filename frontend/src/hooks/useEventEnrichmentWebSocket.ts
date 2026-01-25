/**
 * useEventEnrichmentWebSocket - WebSocket hook for real-time enrichment events
 *
 * NEM-3627: Consumes enrichment.* WebSocket events broadcast by the backend
 * for real-time enrichment pipeline monitoring and progress tracking.
 *
 * Events handled:
 * - enrichment.started: Enrichment pipeline started processing a batch
 * - enrichment.progress: Enrichment step completed with progress update
 * - enrichment.completed: Enrichment pipeline finished successfully
 * - enrichment.failed: Enrichment pipeline encountered an error
 *
 * @module hooks/useEventEnrichmentWebSocket
 */

import { useState, useCallback, useRef, useEffect } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { logger } from '../services/logger';
import { isHeartbeatMessage, isErrorMessage } from '../types/websocket';

import type {
  EnrichmentStartedPayload,
  EnrichmentProgressPayload,
  EnrichmentCompletedPayload,
  EnrichmentFailedPayload,
  EnrichmentStatus,
} from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/**
 * Active enrichment state tracking
 */
export interface ActiveEnrichment {
  /** Unique batch identifier */
  batch_id: string;
  /** Camera identifier */
  camera_id: string;
  /** Number of detections being enriched */
  detection_count: number;
  /** Current progress percentage (0-100) */
  progress: number;
  /** Current enrichment step name */
  current_step?: string;
  /** Total number of enrichment steps */
  total_steps?: number;
  /** ISO timestamp when started */
  started_at: string;
  /** ISO timestamp of last update */
  updated_at: string;
}

/**
 * Completed enrichment history entry
 */
export interface EnrichmentHistoryEntry {
  /** Unique batch identifier */
  batch_id: string;
  /** Camera identifier */
  camera_id: string;
  /** Final status (full, partial, failed) */
  status: EnrichmentStatus | 'error';
  /** Number of enriched detections */
  enriched_count?: number;
  /** Processing duration in milliseconds */
  duration_ms?: number;
  /** Error message if failed */
  error?: string;
  /** ISO timestamp when completed/failed */
  finished_at: string;
}

/**
 * Options for configuring the useEventEnrichmentWebSocket hook
 */
export interface UseEventEnrichmentWebSocketOptions {
  /**
   * Whether to enable the WebSocket connection
   * @default true
   */
  enabled?: boolean;

  /**
   * Maximum number of historical entries to keep
   * @default 50
   */
  maxHistory?: number;

  /**
   * Called when enrichment starts
   */
  onEnrichmentStarted?: (payload: EnrichmentStartedPayload) => void;

  /**
   * Called when enrichment progress updates
   */
  onEnrichmentProgress?: (payload: EnrichmentProgressPayload) => void;

  /**
   * Called when enrichment completes
   */
  onEnrichmentCompleted?: (payload: EnrichmentCompletedPayload) => void;

  /**
   * Called when enrichment fails
   */
  onEnrichmentFailed?: (payload: EnrichmentFailedPayload) => void;
}

/**
 * Return type for the useEventEnrichmentWebSocket hook
 */
export interface UseEventEnrichmentWebSocketReturn {
  /** Currently active enrichments */
  activeEnrichments: ActiveEnrichment[];

  /** Completed/failed enrichment history */
  history: EnrichmentHistoryEntry[];

  /** Total completed enrichments */
  completedCount: number;

  /** Total failed enrichments */
  failedCount: number;

  /** ISO timestamp of last update */
  lastUpdate: string | null;

  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** Get enrichment by batch ID */
  getEnrichmentByBatchId: (batchId: string) => ActiveEnrichment | undefined;

  /** Clear the history buffer */
  clearHistory: () => void;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_MAX_HISTORY = 50;

// ============================================================================
// Type Guards
// ============================================================================

function isEnrichmentStartedMessage(
  value: unknown
): value is { type: 'enrichment.started'; data: EnrichmentStartedPayload } {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const msg = value as Record<string, unknown>;
  return msg.type === 'enrichment.started' && !!msg.data && typeof msg.data === 'object';
}

function isEnrichmentProgressMessage(
  value: unknown
): value is { type: 'enrichment.progress'; data: EnrichmentProgressPayload } {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const msg = value as Record<string, unknown>;
  return msg.type === 'enrichment.progress' && !!msg.data && typeof msg.data === 'object';
}

function isEnrichmentCompletedMessage(
  value: unknown
): value is { type: 'enrichment.completed'; data: EnrichmentCompletedPayload } {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const msg = value as Record<string, unknown>;
  return msg.type === 'enrichment.completed' && !!msg.data && typeof msg.data === 'object';
}

function isEnrichmentFailedMessage(
  value: unknown
): value is { type: 'enrichment.failed'; data: EnrichmentFailedPayload } {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const msg = value as Record<string, unknown>;
  return msg.type === 'enrichment.failed' && !!msg.data && typeof msg.data === 'object';
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to subscribe to real-time enrichment WebSocket events.
 *
 * Tracks active enrichments, progress updates, completions, and failures
 * with configurable history limits.
 *
 * @param options - Configuration options
 * @returns Enrichment state and utilities
 *
 * @example
 * ```tsx
 * const {
 *   activeEnrichments,
 *   history,
 *   completedCount,
 *   failedCount,
 *   getEnrichmentByBatchId,
 * } = useEventEnrichmentWebSocket({
 *   onEnrichmentCompleted: (payload) => {
 *     console.log('Enrichment completed:', payload.batch_id);
 *   },
 * });
 *
 * // Display active enrichments
 * {activeEnrichments.map(e => (
 *   <div key={e.batch_id}>
 *     Camera: {e.camera_id} - Progress: {e.progress}%
 *   </div>
 * ))}
 * ```
 */
export function useEventEnrichmentWebSocket(
  options: UseEventEnrichmentWebSocketOptions = {}
): UseEventEnrichmentWebSocketReturn {
  const {
    enabled = true,
    maxHistory = DEFAULT_MAX_HISTORY,
    onEnrichmentStarted,
    onEnrichmentProgress,
    onEnrichmentCompleted,
    onEnrichmentFailed,
  } = options;

  // State
  const [activeEnrichments, setActiveEnrichments] = useState<ActiveEnrichment[]>([]);
  const [history, setHistory] = useState<EnrichmentHistoryEntry[]>([]);
  const [completedCount, setCompletedCount] = useState(0);
  const [failedCount, setFailedCount] = useState(0);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  // Track mounted state
  const isMountedRef = useRef(true);

  // Store callbacks in refs
  const onEnrichmentStartedRef = useRef(onEnrichmentStarted);
  const onEnrichmentProgressRef = useRef(onEnrichmentProgress);
  const onEnrichmentCompletedRef = useRef(onEnrichmentCompleted);
  const onEnrichmentFailedRef = useRef(onEnrichmentFailed);

  useEffect(() => {
    onEnrichmentStartedRef.current = onEnrichmentStarted;
    onEnrichmentProgressRef.current = onEnrichmentProgress;
    onEnrichmentCompletedRef.current = onEnrichmentCompleted;
    onEnrichmentFailedRef.current = onEnrichmentFailed;
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

      const timestamp = new Date().toISOString();

      // Handle enrichment.started messages
      if (isEnrichmentStartedMessage(data)) {
        const payload = data.data;
        logger.debug('Enrichment.started event received', {
          component: 'useEventEnrichmentWebSocket',
          batch_id: payload.batch_id,
          camera_id: payload.camera_id,
        });

        const newEnrichment: ActiveEnrichment = {
          batch_id: payload.batch_id,
          camera_id: payload.camera_id,
          detection_count: payload.detection_count,
          progress: 0,
          started_at: payload.timestamp,
          updated_at: timestamp,
        };

        setActiveEnrichments((prev) => [...prev, newEnrichment]);
        setLastUpdate(timestamp);
        onEnrichmentStartedRef.current?.(payload);
        return;
      }

      // Handle enrichment.progress messages
      if (isEnrichmentProgressMessage(data)) {
        const payload = data.data;
        logger.debug('Enrichment.progress event received', {
          component: 'useEventEnrichmentWebSocket',
          batch_id: payload.batch_id,
          progress: payload.progress,
        });

        setActiveEnrichments((prev) =>
          prev.map((e) =>
            e.batch_id === payload.batch_id
              ? {
                  ...e,
                  progress: payload.progress,
                  current_step: payload.current_step,
                  total_steps: payload.total_steps,
                  updated_at: timestamp,
                }
              : e
          )
        );
        setLastUpdate(timestamp);
        onEnrichmentProgressRef.current?.(payload);
        return;
      }

      // Handle enrichment.completed messages
      if (isEnrichmentCompletedMessage(data)) {
        const payload = data.data;
        logger.debug('Enrichment.completed event received', {
          component: 'useEventEnrichmentWebSocket',
          batch_id: payload.batch_id,
          status: payload.status,
        });

        // Find and remove from active
        setActiveEnrichments((prev) => {
          const active = prev.find((e) => e.batch_id === payload.batch_id);
          if (active) {
            // Add to history
            const historyEntry: EnrichmentHistoryEntry = {
              batch_id: payload.batch_id,
              camera_id: active.camera_id,
              status: payload.status,
              enriched_count: payload.enriched_count,
              duration_ms: payload.duration_ms,
              finished_at: timestamp,
            };
            setHistory((h) => [historyEntry, ...h].slice(0, maxHistory));
          }
          return prev.filter((e) => e.batch_id !== payload.batch_id);
        });

        setCompletedCount((c) => c + 1);
        setLastUpdate(timestamp);
        onEnrichmentCompletedRef.current?.(payload);
        return;
      }

      // Handle enrichment.failed messages
      if (isEnrichmentFailedMessage(data)) {
        const payload = data.data;
        logger.debug('Enrichment.failed event received', {
          component: 'useEventEnrichmentWebSocket',
          batch_id: payload.batch_id,
          error: payload.error,
        });

        // Find and remove from active
        setActiveEnrichments((prev) => {
          const active = prev.find((e) => e.batch_id === payload.batch_id);
          if (active) {
            // Add to history
            const historyEntry: EnrichmentHistoryEntry = {
              batch_id: payload.batch_id,
              camera_id: active.camera_id,
              status: 'error',
              error: payload.error,
              finished_at: timestamp,
            };
            setHistory((h) => [historyEntry, ...h].slice(0, maxHistory));
          }
          return prev.filter((e) => e.batch_id !== payload.batch_id);
        });

        setFailedCount((c) => c + 1);
        setLastUpdate(timestamp);
        onEnrichmentFailedRef.current?.(payload);
        return;
      }

      // Handle other message types (silently ignore)
      if (isHeartbeatMessage(data)) {
        return;
      }

      if (isErrorMessage(data)) {
        logger.warn('Enrichment WebSocket error', {
          component: 'useEventEnrichmentWebSocket',
          message: data.message,
        });
        return;
      }
    },
    [maxHistory]
  );

  // Build WebSocket options - connect to events channel for enrichment events
  const wsOptions = buildWebSocketOptions('/ws/events');

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

  // Get enrichment by batch ID
  const getEnrichmentByBatchId = useCallback(
    (batchId: string): ActiveEnrichment | undefined => {
      return activeEnrichments.find((e) => e.batch_id === batchId);
    },
    [activeEnrichments]
  );

  // Clear history
  const clearHistory = useCallback(() => {
    if (!isMountedRef.current) return;
    setHistory([]);
  }, []);

  return {
    activeEnrichments,
    history,
    completedCount,
    failedCount,
    lastUpdate,
    isConnected,
    getEnrichmentByBatchId,
    clearHistory,
  };
}

export default useEventEnrichmentWebSocket;
