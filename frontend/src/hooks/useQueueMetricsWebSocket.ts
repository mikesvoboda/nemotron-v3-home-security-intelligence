/**
 * useQueueMetricsWebSocket - WebSocket hook for real-time queue metrics
 *
 * NEM-3637: Consumes queue.status and pipeline.throughput WebSocket events
 * for real-time pipeline queue monitoring and throughput tracking.
 *
 * Events handled:
 * - queue.status: Queue depths, workers, and health status
 * - pipeline.throughput: Detection, event, and enrichment throughput
 *
 * @module hooks/useQueueMetricsWebSocket
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { logger } from '../services/logger';
import { isHeartbeatMessage, isErrorMessage } from '../types/websocket';

import type {
  QueueStatusPayload,
  PipelineThroughputPayload,
  QueueInfo,
} from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/**
 * Queue status entry with timestamp for history tracking
 */
export interface QueueStatusEntry extends QueueStatusPayload {
  /** ISO timestamp when this update was received */
  received_at: string;
}

/**
 * Throughput entry with timestamp for history tracking
 */
export interface ThroughputEntry extends PipelineThroughputPayload {
  /** ISO timestamp when this update was received */
  received_at: string;
}

/**
 * Options for configuring the useQueueMetricsWebSocket hook
 */
export interface UseQueueMetricsWebSocketOptions {
  /**
   * Whether to enable the WebSocket connection
   * @default true
   */
  enabled?: boolean;

  /**
   * Maximum number of historical entries to keep
   * @default 60
   */
  maxHistory?: number;

  /**
   * Called when queue status updates
   */
  onQueueStatus?: (payload: QueueStatusPayload) => void;

  /**
   * Called when throughput updates
   */
  onThroughput?: (payload: PipelineThroughputPayload) => void;
}

/**
 * Return type for the useQueueMetricsWebSocket hook
 */
export interface UseQueueMetricsWebSocketReturn {
  /** Current queue status (null if not yet received) */
  queueStatus: QueueStatusPayload | null;

  /** Current throughput metrics (null if not yet received) */
  throughput: PipelineThroughputPayload | null;

  /** Historical queue status entries (newest first) */
  queueHistory: QueueStatusEntry[];

  /** Historical throughput entries (newest first) */
  throughputHistory: ThroughputEntry[];

  /** ISO timestamp of last update */
  lastUpdate: string | null;

  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** Total queue depth across all queues */
  totalQueueDepth: number;

  /** Total workers across all queues */
  totalWorkers: number;

  /** Whether system is in warning state */
  isWarning: boolean;

  /** Whether system is in critical state */
  isCritical: boolean;

  /** Get queue info by name */
  getQueueByName: (name: string) => QueueInfo | undefined;

  /** Clear the history buffers */
  clearHistory: () => void;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_MAX_HISTORY = 60;

// ============================================================================
// Type Guards
// ============================================================================

function isQueueStatusMessage(
  value: unknown
): value is { type: 'queue.status'; data: QueueStatusPayload } {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const msg = value as Record<string, unknown>;
  return msg.type === 'queue.status' && !!msg.data && typeof msg.data === 'object';
}

function isPipelineThroughputMessage(
  value: unknown
): value is { type: 'pipeline.throughput'; data: PipelineThroughputPayload } {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const msg = value as Record<string, unknown>;
  return msg.type === 'pipeline.throughput' && !!msg.data && typeof msg.data === 'object';
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to subscribe to real-time queue metrics WebSocket events.
 *
 * Tracks queue depths, worker counts, throughput, and system health
 * with configurable history limits for charting.
 *
 * @param options - Configuration options
 * @returns Queue metrics state and utilities
 *
 * @example
 * ```tsx
 * const {
 *   queueStatus,
 *   throughput,
 *   totalQueueDepth,
 *   isWarning,
 *   isCritical,
 *   getQueueByName,
 * } = useQueueMetricsWebSocket({
 *   onQueueStatus: (status) => {
 *     console.log('Queue depth:', status.total_queued);
 *   },
 * });
 *
 * // Display warning indicator
 * {isCritical && <Alert severity="error">Queue backlog critical!</Alert>}
 * {isWarning && <Alert severity="warning">Queue depth elevated</Alert>}
 * ```
 */
export function useQueueMetricsWebSocket(
  options: UseQueueMetricsWebSocketOptions = {}
): UseQueueMetricsWebSocketReturn {
  const {
    enabled = true,
    maxHistory = DEFAULT_MAX_HISTORY,
    onQueueStatus,
    onThroughput,
  } = options;

  // State
  const [queueStatus, setQueueStatus] = useState<QueueStatusPayload | null>(null);
  const [throughput, setThroughput] = useState<PipelineThroughputPayload | null>(null);
  const [queueHistory, setQueueHistory] = useState<QueueStatusEntry[]>([]);
  const [throughputHistory, setThroughputHistory] = useState<ThroughputEntry[]>([]);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  // Track mounted state
  const isMountedRef = useRef(true);

  // Store callbacks in refs
  const onQueueStatusRef = useRef(onQueueStatus);
  const onThroughputRef = useRef(onThroughput);

  useEffect(() => {
    onQueueStatusRef.current = onQueueStatus;
    onThroughputRef.current = onThroughput;
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

      // Handle queue.status messages
      if (isQueueStatusMessage(data)) {
        const payload = data.data;
        logger.debug('Queue.status event received', {
          component: 'useQueueMetricsWebSocket',
          total_queued: payload.total_queued,
          overall_status: payload.overall_status,
        });

        setQueueStatus(payload);
        setLastUpdate(timestamp);

        const entry: QueueStatusEntry = {
          ...payload,
          received_at: timestamp,
        };

        setQueueHistory((prev) => [entry, ...prev].slice(0, maxHistory));
        onQueueStatusRef.current?.(payload);
        return;
      }

      // Handle pipeline.throughput messages
      if (isPipelineThroughputMessage(data)) {
        const payload = data.data;
        logger.debug('Pipeline.throughput event received', {
          component: 'useQueueMetricsWebSocket',
          detections_per_minute: payload.detections_per_minute,
          events_per_minute: payload.events_per_minute,
        });

        setThroughput(payload);
        setLastUpdate(timestamp);

        const entry: ThroughputEntry = {
          ...payload,
          received_at: timestamp,
        };

        setThroughputHistory((prev) => [entry, ...prev].slice(0, maxHistory));
        onThroughputRef.current?.(payload);
        return;
      }

      // Handle other message types (silently ignore)
      if (isHeartbeatMessage(data)) {
        return;
      }

      if (isErrorMessage(data)) {
        logger.warn('Queue metrics WebSocket error', {
          component: 'useQueueMetricsWebSocket',
          message: data.message,
        });
        return;
      }
    },
    [maxHistory]
  );

  // Build WebSocket options - connect to system channel for queue metrics
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

  // Computed values
  const totalQueueDepth = useMemo((): number => {
    return queueStatus?.total_queued ?? 0;
  }, [queueStatus?.total_queued]);

  const totalWorkers = useMemo((): number => {
    if (queueStatus?.total_workers !== undefined) {
      return queueStatus.total_workers;
    }
    // Fallback: sum workers from individual queues
    return queueStatus?.queues?.reduce((sum, q) => sum + q.workers, 0) ?? 0;
  }, [queueStatus?.total_workers, queueStatus?.queues]);

  const isWarning = useMemo((): boolean => {
    return queueStatus?.overall_status === 'warning';
  }, [queueStatus?.overall_status]);

  const isCritical = useMemo((): boolean => {
    return queueStatus?.overall_status === 'critical';
  }, [queueStatus?.overall_status]);

  // Get queue by name
  const getQueueByName = useCallback(
    (name: string): QueueInfo | undefined => {
      return queueStatus?.queues?.find((q) => q.name === name);
    },
    [queueStatus?.queues]
  );

  // Clear history
  const clearHistory = useCallback(() => {
    if (!isMountedRef.current) return;
    setQueueHistory([]);
    setThroughputHistory([]);
  }, []);

  return {
    queueStatus,
    throughput,
    queueHistory,
    throughputHistory,
    lastUpdate,
    isConnected,
    totalQueueDepth,
    totalWorkers,
    isWarning,
    isCritical,
    getQueueByName,
    clearHistory,
  };
}

export default useQueueMetricsWebSocket;
