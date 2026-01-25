/**
 * Queue Status Types
 *
 * Types for queue status monitoring, including detailed metrics about
 * job queues, worker counts, throughput, and health status.
 *
 * These types match the backend schemas in backend/api/schemas/queue_status.py
 */

import type { components } from './generated/api';

// Re-export generated types from OpenAPI spec
export type QueueHealthStatus = components['schemas']['QueueHealthStatus'];
export type ThroughputMetrics = components['schemas']['ThroughputMetrics'];
export type OldestJobInfo = components['schemas']['OldestJobInfo'];
export type QueueStatus = components['schemas']['QueueStatus'];
export type QueueStatusSummary = components['schemas']['QueueStatusSummary'];
export type QueuesStatusResponse = components['schemas']['QueuesStatusResponse'];

// Pipeline status types for batch aggregator
export type BatchInfoResponse = components['schemas']['BatchInfoResponse'];
export type BatchAggregatorStatusResponse = components['schemas']['BatchAggregatorStatusResponse'];
export type PipelineStatusResponse = components['schemas']['PipelineStatusResponse'];

/**
 * Derived state computed from QueuesStatusResponse for UI display.
 */
export interface DerivedQueueState {
  /** Queues with critical health status */
  criticalQueues: QueueStatus[];
  /** Queues with warning health status */
  warningQueues: QueueStatus[];
  /** Maximum wait time across all queues in seconds */
  longestWaitTime: number;
  /** Queue with the oldest waiting job (if any) */
  longestWaitQueue: QueueStatus | null;
  /** Whether any queue has critical status */
  hasCritical: boolean;
  /** Whether any queue has warning or critical status */
  hasIssues: boolean;
  /** Total jobs across all queues */
  totalJobs: number;
  /** Total workers across all queues */
  totalWorkers: number;
}

/**
 * Batch aggregator status for UI display.
 */
export interface BatchAggregatorUIState {
  /** Number of active batches */
  activeBatchCount: number;
  /** Active batch details */
  batches: BatchInfoResponse[];
  /** Configured batch window timeout in seconds */
  batchWindowSeconds: number;
  /** Configured idle timeout in seconds */
  idleTimeoutSeconds: number;
  /** Batches approaching timeout (>80% of window elapsed) */
  batchesApproachingTimeout: BatchInfoResponse[];
  /** Whether any batch is approaching timeout */
  hasTimeoutWarning: boolean;
}

/**
 * Computes derived queue state from the queues status response.
 * @param response - The raw queues status response from the API
 * @returns Derived state useful for UI display
 */
export function computeDerivedQueueState(
  response: QueuesStatusResponse | null
): DerivedQueueState {
  if (!response) {
    return {
      criticalQueues: [],
      warningQueues: [],
      longestWaitTime: 0,
      longestWaitQueue: null,
      hasCritical: false,
      hasIssues: false,
      totalJobs: 0,
      totalWorkers: 0,
    };
  }

  const criticalQueues = response.queues.filter((q) => q.status === 'critical');
  const warningQueues = response.queues.filter((q) => q.status === 'warning');

  let longestWaitTime = 0;
  let longestWaitQueue: QueueStatus | null = null;

  for (const queue of response.queues) {
    const waitTime = queue.oldest_job?.wait_seconds ?? 0;
    if (waitTime > longestWaitTime) {
      longestWaitTime = waitTime;
      longestWaitQueue = queue;
    }
  }

  return {
    criticalQueues,
    warningQueues,
    longestWaitTime,
    longestWaitQueue,
    hasCritical: criticalQueues.length > 0,
    hasIssues: criticalQueues.length > 0 || warningQueues.length > 0,
    totalJobs: response.summary.total_queued + response.summary.total_running,
    totalWorkers: response.summary.total_workers,
  };
}

/**
 * Computes batch aggregator UI state from the pipeline status response.
 * @param batchAggregator - The batch aggregator status from pipeline response
 * @returns Derived state useful for UI display
 */
export function computeBatchAggregatorState(
  batchAggregator: BatchAggregatorStatusResponse | null | undefined
): BatchAggregatorUIState {
  if (!batchAggregator) {
    return {
      activeBatchCount: 0,
      batches: [],
      batchWindowSeconds: 90,
      idleTimeoutSeconds: 30,
      batchesApproachingTimeout: [],
      hasTimeoutWarning: false,
    };
  }

  const batches = batchAggregator.batches ?? [];
  const timeoutThreshold = batchAggregator.batch_window_seconds * 0.8;
  const batchesApproachingTimeout = batches.filter(
    (batch) => batch.age_seconds >= timeoutThreshold
  );

  return {
    activeBatchCount: batchAggregator.active_batches,
    batches,
    batchWindowSeconds: batchAggregator.batch_window_seconds,
    idleTimeoutSeconds: batchAggregator.idle_timeout_seconds,
    batchesApproachingTimeout,
    hasTimeoutWarning: batchesApproachingTimeout.length > 0,
  };
}

/**
 * Type guard to check if a health status is critical.
 */
export function isCriticalStatus(status: QueueHealthStatus): boolean {
  return status === 'critical';
}

/**
 * Type guard to check if a health status is warning.
 */
export function isWarningStatus(status: QueueHealthStatus): boolean {
  return status === 'warning';
}

/**
 * Type guard to check if a health status is healthy.
 */
export function isHealthyStatus(status: QueueHealthStatus): boolean {
  return status === 'healthy';
}

/**
 * Get badge color for queue health status.
 */
export function getHealthStatusBadgeColor(
  status: QueueHealthStatus
): 'green' | 'yellow' | 'red' {
  switch (status) {
    case 'healthy':
      return 'green';
    case 'warning':
      return 'yellow';
    case 'critical':
      return 'red';
  }
}

/**
 * Format wait time in seconds to a human-readable string.
 */
export function formatWaitTime(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) {
    return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

/**
 * Format throughput to a human-readable string.
 */
export function formatThroughput(jobsPerMinute: number): string {
  if (jobsPerMinute < 0.1) {
    return '<0.1/min';
  }
  if (jobsPerMinute < 10) {
    return `${jobsPerMinute.toFixed(1)}/min`;
  }
  return `${Math.round(jobsPerMinute)}/min`;
}
