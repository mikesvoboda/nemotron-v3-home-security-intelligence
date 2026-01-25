/**
 * useBatchProcessingStatus - WebSocket hook for real-time batch analysis status events
 *
 * NEM-3607: Consumes batch.analysis_started, batch.analysis_completed, and batch.analysis_failed
 * WebSocket events to provide UI feedback during batch processing.
 *
 * Events handled:
 * - batch.analysis_started: When a batch is dequeued and LLM analysis begins
 * - batch.analysis_completed: When LLM analysis finishes successfully
 * - batch.analysis_failed: When LLM analysis fails with an error
 *
 * @module hooks/useBatchProcessingStatus
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { logger } from '../services/logger';
import {
  isHeartbeatMessage,
  isErrorMessage,
} from '../types/websocket';

import type {
  BatchAnalysisStartedPayload,
  BatchAnalysisCompletedPayload,
  BatchAnalysisFailedPayload,
} from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/**
 * Batch processing state values
 */
export type BatchProcessingState = 'batching' | 'queued' | 'analyzing' | 'completed' | 'failed';

/**
 * State for a single batch being processed
 */
export interface BatchStatus {
  /** Unique batch identifier */
  batchId: string;
  /** Camera ID that captured the detections */
  cameraId: string;
  /** Current processing state */
  state: BatchProcessingState;
  /** Number of detections in the batch */
  detectionCount: number;
  /** ISO 8601 timestamp when the state last changed */
  updatedAt: string;
  /** Event ID if analysis completed successfully */
  eventId?: number;
  /** Risk score if analysis completed successfully */
  riskScore?: number;
  /** Risk level if analysis completed successfully */
  riskLevel?: 'low' | 'medium' | 'high' | 'critical';
  /** Analysis duration in milliseconds if completed */
  durationMs?: number;
  /** Error message if analysis failed */
  error?: string;
  /** Error type if analysis failed */
  errorType?: string;
  /** Whether the failed analysis can be retried */
  retryable?: boolean;
}

/**
 * Callback type for batch analysis started events
 */
export type BatchAnalysisStartedHandler = (data: BatchAnalysisStartedPayload) => void;

/**
 * Callback type for batch analysis completed events
 */
export type BatchAnalysisCompletedHandler = (data: BatchAnalysisCompletedPayload) => void;

/**
 * Callback type for batch analysis failed events
 */
export type BatchAnalysisFailedHandler = (data: BatchAnalysisFailedPayload) => void;

/**
 * Options for configuring the useBatchProcessingStatus hook
 */
export interface UseBatchProcessingStatusOptions {
  /**
   * Whether to enable the WebSocket connection
   * @default true
   */
  enabled?: boolean;

  /**
   * Maximum number of completed/failed batches to keep in memory
   * @default 50
   */
  maxHistory?: number;

  /**
   * Filter events to only those from this camera
   * If not provided, all cameras are included
   */
  filterCameraId?: string;

  /**
   * Called when batch analysis starts
   */
  onAnalysisStarted?: BatchAnalysisStartedHandler;

  /**
   * Called when batch analysis completes successfully
   */
  onAnalysisCompleted?: BatchAnalysisCompletedHandler;

  /**
   * Called when batch analysis fails
   */
  onAnalysisFailed?: BatchAnalysisFailedHandler;
}

/**
 * Return type for the useBatchProcessingStatus hook
 */
export interface UseBatchProcessingStatusReturn {
  /** Map of all batch statuses by batch_id */
  batchStatuses: Map<string, BatchStatus>;

  /** Array of batches currently being analyzed */
  processingBatches: BatchStatus[];

  /** Array of batches that completed successfully (most recent first) */
  completedBatches: BatchStatus[];

  /** Array of batches that failed (most recent first) */
  failedBatches: BatchStatus[];

  /** Total count of batches currently being analyzed */
  activeCount: number;

  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** Get the status of a specific batch */
  getBatchStatus: (batchId: string) => BatchStatus | undefined;

  /** Clear all batch history */
  clearHistory: () => void;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_MAX_HISTORY = 50;

// ============================================================================
// Type Guards
// ============================================================================

interface BatchAnalysisStartedMessage {
  type: 'batch.analysis_started';
  data: BatchAnalysisStartedPayload;
}

interface BatchAnalysisCompletedMessage {
  type: 'batch.analysis_completed';
  data: BatchAnalysisCompletedPayload;
}

interface BatchAnalysisFailedMessage {
  type: 'batch.analysis_failed';
  data: BatchAnalysisFailedPayload;
}

function isBatchAnalysisStartedMessage(value: unknown): value is BatchAnalysisStartedMessage {
  if (!value || typeof value !== 'object') return false;
  const msg = value as Record<string, unknown>;
  return msg.type === 'batch.analysis_started' && typeof msg.data === 'object' && msg.data !== null;
}

function isBatchAnalysisCompletedMessage(value: unknown): value is BatchAnalysisCompletedMessage {
  if (!value || typeof value !== 'object') return false;
  const msg = value as Record<string, unknown>;
  return msg.type === 'batch.analysis_completed' && typeof msg.data === 'object' && msg.data !== null;
}

function isBatchAnalysisFailedMessage(value: unknown): value is BatchAnalysisFailedMessage {
  if (!value || typeof value !== 'object') return false;
  const msg = value as Record<string, unknown>;
  return msg.type === 'batch.analysis_failed' && typeof msg.data === 'object' && msg.data !== null;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to subscribe to real-time batch processing status WebSocket events.
 *
 * Provides access to batch analysis lifecycle events from the backend pipeline:
 * - batch.analysis_started: When a batch is dequeued and enters LLM analysis
 * - batch.analysis_completed: When LLM analysis finishes successfully
 * - batch.analysis_failed: When LLM analysis fails with an error
 *
 * @param options - Configuration options
 * @returns Batch processing status state and utilities
 *
 * @example
 * ```tsx
 * const {
 *   processingBatches,
 *   completedBatches,
 *   failedBatches,
 *   activeCount,
 *   isConnected,
 * } = useBatchProcessingStatus({
 *   onAnalysisStarted: (data) => {
 *     console.log('Analysis started:', data.batch_id);
 *   },
 *   onAnalysisCompleted: (data) => {
 *     console.log('Analysis completed:', data.batch_id, 'risk:', data.risk_score);
 *   },
 *   onAnalysisFailed: (data) => {
 *     console.log('Analysis failed:', data.batch_id, 'error:', data.error);
 *   },
 *   filterCameraId: 'front_door',
 * });
 * ```
 */
export function useBatchProcessingStatus(
  options: UseBatchProcessingStatusOptions = {}
): UseBatchProcessingStatusReturn {
  const {
    enabled = true,
    maxHistory = DEFAULT_MAX_HISTORY,
    filterCameraId,
    onAnalysisStarted,
    onAnalysisCompleted,
    onAnalysisFailed,
  } = options;

  // State - use Map for efficient batch_id lookups
  const [batchStatuses, setBatchStatuses] = useState<Map<string, BatchStatus>>(new Map());

  // Track mounted state to prevent updates after unmount
  const isMountedRef = useRef(true);

  // Store callbacks in refs to avoid stale closures
  const onAnalysisStartedRef = useRef(onAnalysisStarted);
  const onAnalysisCompletedRef = useRef(onAnalysisCompleted);
  const onAnalysisFailedRef = useRef(onAnalysisFailed);

  // Update refs when callbacks change
  useEffect(() => {
    onAnalysisStartedRef.current = onAnalysisStarted;
    onAnalysisCompletedRef.current = onAnalysisCompleted;
    onAnalysisFailedRef.current = onAnalysisFailed;
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

      // Handle batch.analysis_started messages
      if (isBatchAnalysisStartedMessage(data)) {
        const payload = data.data;

        // Filter by camera if specified
        if (filterCameraId && payload.camera_id !== filterCameraId) {
          return;
        }

        logger.debug('Batch.analysis_started event received', {
          component: 'useBatchProcessingStatus',
          batch_id: payload.batch_id,
          camera_id: payload.camera_id,
          detection_count: payload.detection_count,
        });

        setBatchStatuses((prev) => {
          const updated = new Map(prev);
          updated.set(payload.batch_id, {
            batchId: payload.batch_id,
            cameraId: payload.camera_id,
            state: 'analyzing',
            detectionCount: payload.detection_count,
            updatedAt: payload.started_at,
          });
          return updated;
        });

        onAnalysisStartedRef.current?.(payload);
        return;
      }

      // Handle batch.analysis_completed messages
      if (isBatchAnalysisCompletedMessage(data)) {
        const payload = data.data;

        // Filter by camera if specified
        if (filterCameraId && payload.camera_id !== filterCameraId) {
          return;
        }

        logger.debug('Batch.analysis_completed event received', {
          component: 'useBatchProcessingStatus',
          batch_id: payload.batch_id,
          camera_id: payload.camera_id,
          event_id: payload.event_id,
          risk_score: payload.risk_score,
          duration_ms: payload.duration_ms,
        });

        setBatchStatuses((prev) => {
          const updated = new Map(prev);
          const existing = updated.get(payload.batch_id);
          updated.set(payload.batch_id, {
            batchId: payload.batch_id,
            cameraId: payload.camera_id,
            state: 'completed',
            detectionCount: existing?.detectionCount ?? 0,
            updatedAt: payload.completed_at,
            eventId: payload.event_id,
            riskScore: payload.risk_score,
            riskLevel: payload.risk_level,
            durationMs: payload.duration_ms,
          });

          // Trim completed/failed batches if we have too many
          const entries = Array.from(updated.entries());
          const nonActive = entries.filter(([_, status]) =>
            status.state === 'completed' || status.state === 'failed'
          );
          if (nonActive.length > maxHistory) {
            // Sort by updatedAt (oldest first) and remove excess
            nonActive.sort((a, b) =>
              new Date(a[1].updatedAt).getTime() - new Date(b[1].updatedAt).getTime()
            );
            const toRemove = nonActive.slice(0, nonActive.length - maxHistory);
            toRemove.forEach(([batchId]) => updated.delete(batchId));
          }

          return updated;
        });

        onAnalysisCompletedRef.current?.(payload);
        return;
      }

      // Handle batch.analysis_failed messages
      if (isBatchAnalysisFailedMessage(data)) {
        const payload = data.data;

        // Filter by camera if specified
        if (filterCameraId && payload.camera_id !== filterCameraId) {
          return;
        }

        logger.debug('Batch.analysis_failed event received', {
          component: 'useBatchProcessingStatus',
          batch_id: payload.batch_id,
          camera_id: payload.camera_id,
          error_type: payload.error_type,
          retryable: payload.retryable,
        });

        setBatchStatuses((prev) => {
          const updated = new Map(prev);
          const existing = updated.get(payload.batch_id);
          updated.set(payload.batch_id, {
            batchId: payload.batch_id,
            cameraId: payload.camera_id,
            state: 'failed',
            detectionCount: existing?.detectionCount ?? 0,
            updatedAt: payload.failed_at,
            error: payload.error,
            errorType: payload.error_type,
            retryable: payload.retryable,
          });

          // Trim completed/failed batches if we have too many
          const entries = Array.from(updated.entries());
          const nonActive = entries.filter(([_, status]) =>
            status.state === 'completed' || status.state === 'failed'
          );
          if (nonActive.length > maxHistory) {
            // Sort by updatedAt (oldest first) and remove excess
            nonActive.sort((a, b) =>
              new Date(a[1].updatedAt).getTime() - new Date(b[1].updatedAt).getTime()
            );
            const toRemove = nonActive.slice(0, nonActive.length - maxHistory);
            toRemove.forEach(([batchId]) => updated.delete(batchId));
          }

          return updated;
        });

        onAnalysisFailedRef.current?.(payload);
        return;
      }

      // Handle other message types (silently ignore)
      if (isHeartbeatMessage(data)) {
        // Heartbeats handled by useWebSocket
        return;
      }

      if (isErrorMessage(data)) {
        logger.warn('Batch processing status WebSocket error', {
          component: 'useBatchProcessingStatus',
          message: (data as { message?: string }).message,
        });
        return;
      }

      // Unknown messages are silently ignored
    },
    [filterCameraId, maxHistory]
  );

  // Build WebSocket options - reuse the events channel
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

  // Clear history
  const clearHistory = useCallback(() => {
    if (!isMountedRef.current) return;
    setBatchStatuses(new Map());
  }, []);

  // Get batch status by ID
  const getBatchStatus = useCallback(
    (batchId: string): BatchStatus | undefined => {
      return batchStatuses.get(batchId);
    },
    [batchStatuses]
  );

  // Compute derived arrays
  const processingBatches = useMemo(() => {
    return Array.from(batchStatuses.values())
      .filter((status) => status.state === 'analyzing')
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
  }, [batchStatuses]);

  const completedBatches = useMemo(() => {
    return Array.from(batchStatuses.values())
      .filter((status) => status.state === 'completed')
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
  }, [batchStatuses]);

  const failedBatches = useMemo(() => {
    return Array.from(batchStatuses.values())
      .filter((status) => status.state === 'failed')
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
  }, [batchStatuses]);

  const activeCount = useMemo(() => {
    return Array.from(batchStatuses.values()).filter(
      (status) => status.state === 'analyzing'
    ).length;
  }, [batchStatuses]);

  return {
    batchStatuses,
    processingBatches,
    completedBatches,
    failedBatches,
    activeCount,
    isConnected,
    getBatchStatus,
    clearHistory,
  };
}

export default useBatchProcessingStatus;
