/**
 * useDetectionStream - WebSocket hook for real-time detection events
 *
 * NEM-3169: Consumes detection.new and detection.batch WebSocket events
 * broadcast by the backend AI pipeline.
 *
 * Events handled:
 * - detection.new: Individual AI detections in real-time
 * - detection.batch: Batch completion events when detections are grouped for analysis
 *
 * @module hooks/useDetectionStream
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { logger } from '../services/logger';
import {
  type DetectionNewData,
  type DetectionBatchData,
  isDetectionNewMessage,
  isDetectionBatchMessage,
  isHeartbeatMessage,
  isErrorMessage,
} from '../types/websocket';

// ============================================================================
// Types
// ============================================================================

/**
 * Callback type for detection events
 */
export type DetectionEventHandler = (detection: DetectionNewData) => void;

/**
 * Callback type for batch events
 */
export type BatchEventHandler = (batch: DetectionBatchData) => void;

/**
 * Options for configuring the useDetectionStream hook
 */
export interface UseDetectionStreamOptions {
  /**
   * Whether to enable the WebSocket connection
   * @default true
   */
  enabled?: boolean;

  /**
   * Maximum number of detections to keep in memory
   * @default 100
   */
  maxDetections?: number;

  /**
   * Maximum number of batches to keep in memory
   * @default 50
   */
  maxBatches?: number;

  /**
   * Filter detections and batches to only those from this camera
   * If not provided, all cameras are included
   */
  filterCameraId?: string;

  /**
   * Called when a new detection is received
   */
  onDetection?: DetectionEventHandler;

  /**
   * Called when a batch is completed
   */
  onBatch?: BatchEventHandler;
}

/**
 * Return type for the useDetectionStream hook
 */
export interface UseDetectionStreamReturn {
  /** Array of recent detections (newest first) */
  detections: DetectionNewData[];

  /** The most recent detection received */
  latestDetection: DetectionNewData | null;

  /** Total count of detections received in this session */
  detectionCount: number;

  /** Array of recent batches (newest first) */
  batches: DetectionBatchData[];

  /** The most recent batch received */
  latestBatch: DetectionBatchData | null;

  /** Total count of batches received in this session */
  batchCount: number;

  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** Clear all detections from memory */
  clearDetections: () => void;

  /** Clear all batches from memory */
  clearBatches: () => void;

  /** Clear both detections and batches */
  clearAll: () => void;

  /** Get detections belonging to a specific batch */
  getDetectionsByBatch: (batchId: string) => DetectionNewData[];
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_MAX_DETECTIONS = 100;
const DEFAULT_MAX_BATCHES = 50;

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to subscribe to real-time detection WebSocket events.
 *
 * Provides access to individual AI detections (detection.new) and batch
 * completion events (detection.batch) from the backend pipeline.
 *
 * @param options - Configuration options
 * @returns Detection stream state and utilities
 *
 * @example
 * ```tsx
 * const {
 *   detections,
 *   latestDetection,
 *   batches,
 *   isConnected,
 * } = useDetectionStream({
 *   onDetection: (detection) => {
 *     console.log('New detection:', detection.label, detection.confidence);
 *   },
 *   onBatch: (batch) => {
 *     console.log('Batch completed:', batch.batch_id, batch.detection_count);
 *   },
 *   filterCameraId: 'front_door',
 *   maxDetections: 50,
 * });
 * ```
 */
export function useDetectionStream(
  options: UseDetectionStreamOptions = {}
): UseDetectionStreamReturn {
  const {
    enabled = true,
    maxDetections = DEFAULT_MAX_DETECTIONS,
    maxBatches = DEFAULT_MAX_BATCHES,
    filterCameraId,
    onDetection,
    onBatch,
  } = options;

  // State
  const [detections, setDetections] = useState<DetectionNewData[]>([]);
  const [batches, setBatches] = useState<DetectionBatchData[]>([]);
  const [detectionCount, setDetectionCount] = useState(0);
  const [batchCount, setBatchCount] = useState(0);

  // Track mounted state to prevent updates after unmount
  const isMountedRef = useRef(true);

  // Store callbacks in refs to avoid stale closures
  const onDetectionRef = useRef(onDetection);
  const onBatchRef = useRef(onBatch);

  // Update refs when callbacks change
  useEffect(() => {
    onDetectionRef.current = onDetection;
    onBatchRef.current = onBatch;
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

      // Handle detection.new messages
      if (isDetectionNewMessage(data)) {
        const detection = data.data;

        // Filter by camera if specified
        if (filterCameraId && detection.camera_id !== filterCameraId) {
          return;
        }

        logger.debug('Detection.new event received', {
          component: 'useDetectionStream',
          detection_id: detection.detection_id,
          batch_id: detection.batch_id,
          camera_id: detection.camera_id,
          label: detection.label,
          confidence: detection.confidence,
        });

        setDetections((prev) => {
          const updated = [detection, ...prev];
          return updated.slice(0, maxDetections);
        });
        setDetectionCount((prev) => prev + 1);

        onDetectionRef.current?.(detection);
        return;
      }

      // Handle detection.batch messages
      if (isDetectionBatchMessage(data)) {
        const batch = data.data;

        // Filter by camera if specified
        if (filterCameraId && batch.camera_id !== filterCameraId) {
          return;
        }

        logger.debug('Detection.batch event received', {
          component: 'useDetectionStream',
          batch_id: batch.batch_id,
          camera_id: batch.camera_id,
          detection_count: batch.detection_count,
          close_reason: batch.close_reason,
        });

        setBatches((prev) => {
          const updated = [batch, ...prev];
          return updated.slice(0, maxBatches);
        });
        setBatchCount((prev) => prev + 1);

        onBatchRef.current?.(batch);
        return;
      }

      // Handle other message types (silently ignore)
      if (isHeartbeatMessage(data)) {
        // Heartbeats handled by useWebSocket
        return;
      }

      if (isErrorMessage(data)) {
        logger.warn('Detection stream WebSocket error', {
          component: 'useDetectionStream',
          message: data.message,
        });
        return;
      }

      // Unknown messages are silently ignored
    },
    [filterCameraId, maxDetections, maxBatches]
  );

  // Build WebSocket options
  const wsOptions = buildWebSocketOptions('/ws/detections');

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

  // Clear functions
  const clearDetections = useCallback(() => {
    if (!isMountedRef.current) return;
    setDetections([]);
    setDetectionCount(0);
  }, []);

  const clearBatches = useCallback(() => {
    if (!isMountedRef.current) return;
    setBatches([]);
    setBatchCount(0);
  }, []);

  const clearAll = useCallback(() => {
    clearDetections();
    clearBatches();
  }, [clearDetections, clearBatches]);

  // Get detections by batch ID
  const getDetectionsByBatch = useCallback(
    (batchId: string): DetectionNewData[] => {
      return detections.filter((d) => d.batch_id === batchId);
    },
    [detections]
  );

  // Compute latest detection and batch
  const latestDetection = useMemo(
    () => (detections.length > 0 ? detections[0] : null),
    [detections]
  );

  const latestBatch = useMemo(
    () => (batches.length > 0 ? batches[0] : null),
    [batches]
  );

  return {
    detections,
    latestDetection,
    detectionCount,
    batches,
    latestBatch,
    batchCount,
    isConnected,
    clearDetections,
    clearBatches,
    clearAll,
    getDetectionsByBatch,
  };
}

export default useDetectionStream;
