/**
 * useBatchStatistics - Hook for aggregating batch processing statistics
 *
 * Combines:
 * - REST API data from /api/system/pipeline (BatchAggregator status)
 * - WebSocket events from detection.batch channel for real-time updates
 *
 * Provides:
 * - Active batch count and details
 * - Completed batch history from WebSocket
 * - Closure reason statistics
 * - Per-camera breakdown
 * - Average batch duration
 *
 * @module hooks/useBatchStatistics
 */

import { useState, useCallback, useEffect, useMemo } from 'react';

import { useDetectionStream } from './useDetectionStream';
import { fetchPipelineStatus } from '../services/api';

import type {
  PipelineStatusResponse,
  BatchInfoResponse,
} from '../types/generated';
import type { DetectionBatchData } from '../types/websocket';

// ============================================================================
// Types
// ============================================================================

/**
 * Closure reason statistics
 */
export interface ClosureReasonStats {
  timeout: number;
  idle: number;
  max_size: number;
  [key: string]: number;
}

/**
 * Closure reason percentages
 */
export interface ClosureReasonPercentages {
  timeout: number;
  idle: number;
  max_size: number;
  [key: string]: number;
}

/**
 * Per-camera batch statistics
 */
export interface CameraStats {
  completedBatchCount: number;
  activeBatchCount: number;
  totalDetections: number;
}

/**
 * Per-camera stats mapping
 */
export type PerCameraStats = Record<string, CameraStats>;

/**
 * Options for the useBatchStatistics hook
 */
export interface UseBatchStatisticsOptions {
  /**
   * Polling interval for REST API in milliseconds
   * Set to 0 to disable polling
   * @default 10000
   */
  pollingInterval?: number;
}

/**
 * Return type for the useBatchStatistics hook
 */
export interface UseBatchStatisticsReturn {
  /** Whether the initial load is in progress */
  isLoading: boolean;
  /** Error message if fetch failed */
  error: string | null;

  /** Number of active batches being aggregated */
  activeBatchCount: number;
  /** Details of active batches from API */
  activeBatches: BatchInfoResponse[];

  /** Completed batches from WebSocket history */
  completedBatches: DetectionBatchData[];
  /** Total count of closed batches in session */
  totalClosedCount: number;

  /** Batch window timeout in seconds */
  batchWindowSeconds: number;
  /** Idle timeout in seconds */
  idleTimeoutSeconds: number;

  /** Average batch duration in seconds */
  averageDurationSeconds: number;

  /** Closure reason counts */
  closureReasonStats: ClosureReasonStats;
  /** Closure reason percentages */
  closureReasonPercentages: ClosureReasonPercentages;

  /** Statistics per camera */
  perCameraStats: PerCameraStats;

  /** Whether WebSocket is connected */
  isWebSocketConnected: boolean;

  /** Refetch data from API */
  refetch: () => Promise<void>;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_POLLING_INTERVAL = 10000; // 10 seconds

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to aggregate batch processing statistics from REST API and WebSocket.
 *
 * @param options - Configuration options
 * @returns Batch statistics and status
 */
export function useBatchStatistics(
  options: UseBatchStatisticsOptions = {}
): UseBatchStatisticsReturn {
  const { pollingInterval = DEFAULT_POLLING_INTERVAL } = options;

  // State
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // WebSocket data from detection stream
  const { batches: completedBatches, batchCount, isConnected } = useDetectionStream();

  // Fetch pipeline status from REST API
  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const data = await fetchPipelineStatus();
      setPipelineStatus(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch pipeline status';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  // Polling
  useEffect(() => {
    if (pollingInterval <= 0) return;

    const interval = setInterval(() => {
      void fetchData();
    }, pollingInterval);

    return () => clearInterval(interval);
  }, [fetchData, pollingInterval]);

  // Extract batch aggregator data
  const batchAggregator = pipelineStatus?.batch_aggregator;

  // Active batches from API
  const activeBatches = useMemo<BatchInfoResponse[]>(() => {
    return batchAggregator?.batches ?? [];
  }, [batchAggregator]);

  // Active batch count
  const activeBatchCount = batchAggregator?.active_batches ?? 0;

  // Configuration values
  const batchWindowSeconds = batchAggregator?.batch_window_seconds ?? 0;
  const idleTimeoutSeconds = batchAggregator?.idle_timeout_seconds ?? 0;

  // Calculate closure reason statistics
  const closureReasonStats = useMemo<ClosureReasonStats>(() => {
    const stats: ClosureReasonStats = {
      timeout: 0,
      idle: 0,
      max_size: 0,
    };

    for (const batch of completedBatches) {
      const reason = batch.close_reason ?? 'unknown';
      if (reason in stats) {
        stats[reason]++;
      } else {
        stats[reason] = 1;
      }
    }

    return stats;
  }, [completedBatches]);

  // Calculate closure reason percentages
  const closureReasonPercentages = useMemo<ClosureReasonPercentages>(() => {
    const total = completedBatches.length;
    if (total === 0) {
      return { timeout: 0, idle: 0, max_size: 0 };
    }

    const percentages: ClosureReasonPercentages = {
      timeout: 0,
      idle: 0,
      max_size: 0,
    };

    for (const [reason, count] of Object.entries(closureReasonStats)) {
      percentages[reason] = (count / total) * 100;
    }

    return percentages;
  }, [completedBatches, closureReasonStats]);

  // Calculate per-camera statistics
  const perCameraStats = useMemo<PerCameraStats>(() => {
    const stats: PerCameraStats = {};

    // Count active batches per camera
    for (const batch of activeBatches) {
      const cameraId = batch.camera_id;
      if (!stats[cameraId]) {
        stats[cameraId] = {
          completedBatchCount: 0,
          activeBatchCount: 0,
          totalDetections: 0,
        };
      }
      stats[cameraId].activeBatchCount++;
      stats[cameraId].totalDetections += batch.detection_count;
    }

    // Count completed batches per camera
    for (const batch of completedBatches) {
      const cameraId = batch.camera_id;
      if (!stats[cameraId]) {
        stats[cameraId] = {
          completedBatchCount: 0,
          activeBatchCount: 0,
          totalDetections: 0,
        };
      }
      stats[cameraId].completedBatchCount++;
      stats[cameraId].totalDetections += batch.detection_count;
    }

    return stats;
  }, [activeBatches, completedBatches]);

  // Calculate average batch duration from completed batches
  const averageDurationSeconds = useMemo(() => {
    if (completedBatches.length === 0) return 0;

    let totalDuration = 0;
    for (const batch of completedBatches) {
      const startTime = new Date(batch.started_at).getTime();
      const closedTime = new Date(batch.closed_at).getTime();
      const durationMs = closedTime - startTime;
      totalDuration += durationMs / 1000;
    }

    return totalDuration / completedBatches.length;
  }, [completedBatches]);

  return {
    isLoading,
    error,
    activeBatchCount,
    activeBatches,
    completedBatches,
    totalClosedCount: batchCount,
    batchWindowSeconds,
    idleTimeoutSeconds,
    averageDurationSeconds,
    closureReasonStats,
    closureReasonPercentages,
    perCameraStats,
    isWebSocketConnected: isConnected,
    refetch: fetchData,
  };
}

export default useBatchStatistics;
