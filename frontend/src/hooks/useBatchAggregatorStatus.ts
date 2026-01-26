/**
 * useBatchAggregatorStatus - Hook for real-time batch aggregator status monitoring
 *
 * Polls /api/system/pipeline for batch aggregator status and provides:
 * - Active batch count and details
 * - Average batch age
 * - Total detection count
 * - Health indicators (green/yellow/red)
 *
 * Supports conditional polling for expand/collapse behavior.
 *
 * @see NEM-3872 - Batch Status Monitoring
 * @module hooks/useBatchAggregatorStatus
 */

import { useState, useCallback, useEffect, useMemo } from 'react';

import { fetchPipelineStatus } from '../services/api';


import type { PipelineStatusResponse, BatchInfoResponse } from '../types/generated';

// ============================================================================
// Types
// ============================================================================

/**
 * Health indicator status
 */
export type HealthIndicator = 'green' | 'yellow' | 'red';

/**
 * Options for the useBatchAggregatorStatus hook
 */
export interface UseBatchAggregatorStatusOptions {
  /**
   * Whether polling is enabled
   * Use this for expand/collapse behavior
   * @default true
   */
  enabled?: boolean;
  /**
   * Polling interval in milliseconds
   * @default 5000
   */
  pollingInterval?: number;
}

/**
 * Return type for the useBatchAggregatorStatus hook
 */
export interface UseBatchAggregatorStatusReturn {
  /** Whether the initial load is in progress */
  isLoading: boolean;
  /** Error message if fetch failed */
  error: string | null;

  /** Number of active batches being aggregated */
  activeBatchCount: number;
  /** Details of active batches */
  batches: BatchInfoResponse[];
  /** Average age of active batches in seconds */
  averageBatchAge: number;
  /** Total detection count across all active batches */
  totalDetectionCount: number;

  /** Configured batch window in seconds */
  batchWindowSeconds: number;
  /** Configured idle timeout in seconds */
  idleTimeoutSeconds: number;

  /** Health indicator based on batch age vs config */
  healthIndicator: HealthIndicator;

  /** Manually refetch data */
  refetch: () => Promise<void>;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_POLLING_INTERVAL = 5000; // 5 seconds

/** Threshold for yellow health (50% of window) */
const YELLOW_THRESHOLD = 0.5;

/** Threshold for red health (80% of window) */
const RED_THRESHOLD = 0.8;

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for monitoring batch aggregator status with health indicators.
 *
 * @param options - Configuration options
 * @returns Batch aggregator status and health indicators
 */
export function useBatchAggregatorStatus(
  options: UseBatchAggregatorStatusOptions = {}
): UseBatchAggregatorStatusReturn {
  const { enabled = true, pollingInterval = DEFAULT_POLLING_INTERVAL } = options;

  // State
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch pipeline status from REST API
  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const data = await fetchPipelineStatus();
      setPipelineStatus(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch batch status';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial fetch when enabled
  useEffect(() => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }

    void fetchData();
  }, [fetchData, enabled]);

  // Polling when enabled
  useEffect(() => {
    if (!enabled || pollingInterval <= 0) return;

    const interval = setInterval(() => {
      void fetchData();
    }, pollingInterval);

    return () => clearInterval(interval);
  }, [fetchData, pollingInterval, enabled]);

  // Extract batch aggregator data
  const batchAggregator = pipelineStatus?.batch_aggregator;

  // Active batches from API
  const batches = useMemo<BatchInfoResponse[]>(() => {
    return batchAggregator?.batches ?? [];
  }, [batchAggregator]);

  // Active batch count
  const activeBatchCount = batchAggregator?.active_batches ?? 0;

  // Configuration values
  const batchWindowSeconds = batchAggregator?.batch_window_seconds ?? 0;
  const idleTimeoutSeconds = batchAggregator?.idle_timeout_seconds ?? 0;

  // Calculate average batch age
  const averageBatchAge = useMemo(() => {
    if (batches.length === 0) return 0;

    const totalAge = batches.reduce((sum, batch) => sum + batch.age_seconds, 0);
    return totalAge / batches.length;
  }, [batches]);

  // Calculate total detection count
  const totalDetectionCount = useMemo(() => {
    return batches.reduce((sum, batch) => sum + batch.detection_count, 0);
  }, [batches]);

  // Calculate health indicator
  const healthIndicator = useMemo<HealthIndicator>(() => {
    // No batches = healthy
    if (batches.length === 0 || batchWindowSeconds === 0) {
      return 'green';
    }

    const ageRatio = averageBatchAge / batchWindowSeconds;

    if (ageRatio >= RED_THRESHOLD) {
      return 'red';
    } else if (ageRatio >= YELLOW_THRESHOLD) {
      return 'yellow';
    } else {
      return 'green';
    }
  }, [averageBatchAge, batchWindowSeconds, batches.length]);

  return {
    isLoading,
    error,
    activeBatchCount,
    batches,
    averageBatchAge,
    totalDetectionCount,
    batchWindowSeconds,
    idleTimeoutSeconds,
    healthIndicator,
    refetch: fetchData,
  };
}

export default useBatchAggregatorStatus;
