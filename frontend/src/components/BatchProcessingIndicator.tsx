/**
 * BatchProcessingIndicator - Shows real-time batch processing status.
 *
 * NEM-3607: This component displays the current state of batch processing
 * in the AI pipeline, providing users with visibility into what's happening
 * between batch creation and event creation.
 *
 * States displayed:
 * - Batching: Detections are being aggregated
 * - Queued: Batch is waiting in the analysis queue
 * - Analyzing: LLM is processing the batch
 * - Complete: Analysis finished successfully
 * - Failed: Analysis encountered an error
 *
 * @example
 * ```tsx
 * // Show indicator for all cameras
 * <BatchProcessingIndicator />
 *
 * // Show indicator for a specific camera
 * <BatchProcessingIndicator filterCameraId="front_door" />
 *
 * // Compact version for status bars
 * <BatchProcessingIndicator compact />
 * ```
 */
import { clsx } from 'clsx';

import {
  useBatchProcessingStatus,
  type BatchStatus,
  type BatchProcessingState,
} from '../hooks/useBatchProcessingStatus';

// ============================================================================
// Types
// ============================================================================

export interface BatchProcessingIndicatorProps {
  /** Filter to only show batches from this camera */
  filterCameraId?: string;
  /** Show compact version (icon + count only) */
  compact?: boolean;
  /** Optional class name for additional styling */
  className?: string;
  /** Whether to enable WebSocket connection */
  enabled?: boolean;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get display label for a batch processing state
 */
function getStateLabel(state: BatchProcessingState): string {
  switch (state) {
    case 'batching':
      return 'Batching';
    case 'queued':
      return 'Queued';
    case 'analyzing':
      return 'Analyzing';
    case 'completed':
      return 'Complete';
    case 'failed':
      return 'Failed';
  }
}

/**
 * Get CSS classes for state styling
 */
function getStateStyles(state: BatchProcessingState): {
  container: string;
  dot: string;
  text: string;
} {
  switch (state) {
    case 'batching':
      return {
        container: 'border-gray-300 bg-gray-50',
        dot: 'bg-gray-500',
        text: 'text-gray-700',
      };
    case 'queued':
      return {
        container: 'border-yellow-300 bg-yellow-50',
        dot: 'bg-yellow-500',
        text: 'text-yellow-700',
      };
    case 'analyzing':
      return {
        container: 'border-blue-300 bg-blue-50',
        dot: 'bg-blue-500 animate-pulse',
        text: 'text-blue-700',
      };
    case 'completed':
      return {
        container: 'border-green-300 bg-green-50',
        dot: 'bg-green-500',
        text: 'text-green-700',
      };
    case 'failed':
      return {
        container: 'border-red-300 bg-red-50',
        dot: 'bg-red-500',
        text: 'text-red-700',
      };
  }
}

/**
 * Get risk level badge color
 */
function getRiskLevelColor(riskLevel?: string): string {
  switch (riskLevel) {
    case 'critical':
      return 'bg-red-600 text-white';
    case 'high':
      return 'bg-orange-500 text-white';
    case 'medium':
      return 'bg-yellow-500 text-white';
    case 'low':
    default:
      return 'bg-green-500 text-white';
  }
}

// ============================================================================
// Subcomponents
// ============================================================================

interface BatchStatusItemProps {
  status: BatchStatus;
  showCamera?: boolean;
}

/**
 * Individual batch status item
 */
function BatchStatusItem({ status, showCamera = true }: BatchStatusItemProps) {
  const styles = getStateStyles(status.state);
  const label = getStateLabel(status.state);

  return (
    <div
      className={clsx(
        'flex items-center gap-2 rounded-md border px-2 py-1 text-xs',
        styles.container
      )}
      data-testid={`batch-status-${status.batchId}`}
    >
      {/* State indicator dot */}
      <span className={clsx('h-2 w-2 rounded-full', styles.dot)} aria-hidden="true" />

      {/* State label */}
      <span className={clsx('font-medium', styles.text)}>{label}</span>

      {/* Camera ID (optional) */}
      {showCamera && (
        <span className="text-gray-500">{status.cameraId}</span>
      )}

      {/* Detection count */}
      {status.detectionCount > 0 && (
        <span className="text-gray-500">({status.detectionCount})</span>
      )}

      {/* Risk score for completed batches */}
      {status.state === 'completed' && status.riskScore !== undefined && (
        <span
          className={clsx(
            'ml-1 rounded px-1.5 py-0.5 text-xs font-medium',
            getRiskLevelColor(status.riskLevel)
          )}
        >
          {status.riskScore}
        </span>
      )}

      {/* Error indicator for failed batches */}
      {status.state === 'failed' && (
        <span className="text-red-600" title={status.error}>
          !
        </span>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * BatchProcessingIndicator shows real-time batch processing status.
 *
 * Displays the current state of batches in the AI pipeline:
 * - How many batches are being analyzed
 * - Recent completions with risk scores
 * - Any failures with error info
 */
export default function BatchProcessingIndicator({
  filterCameraId,
  compact = false,
  className,
  enabled = true,
}: BatchProcessingIndicatorProps) {
  const {
    processingBatches,
    completedBatches,
    failedBatches,
    activeCount,
    isConnected,
  } = useBatchProcessingStatus({
    enabled,
    filterCameraId,
    maxHistory: 10,
  });

  // Don't show anything if not connected or no activity
  if (!isConnected || (activeCount === 0 && completedBatches.length === 0 && failedBatches.length === 0)) {
    return null;
  }

  // Compact mode - just show active count
  if (compact) {
    if (activeCount === 0) {
      return null;
    }

    return (
      <div
        className={clsx(
          'flex items-center gap-1.5 rounded-full border border-blue-300 bg-blue-100 px-2 py-1',
          className
        )}
        data-testid="batch-processing-indicator-compact"
        role="status"
        aria-live="polite"
        aria-label={`${activeCount} batch${activeCount !== 1 ? 'es' : ''} analyzing`}
      >
        <div
          className="h-2 w-2 animate-pulse rounded-full bg-blue-500"
          aria-hidden="true"
        />
        <span className="text-xs font-medium text-blue-700">{activeCount}</span>
      </div>
    );
  }

  // Full mode - show all batch statuses
  return (
    <div
      className={clsx(
        'flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-3 shadow-sm',
        className
      )}
      data-testid="batch-processing-indicator"
      role="region"
      aria-label="Batch processing status"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">AI Analysis</h3>
        {activeCount > 0 && (
          <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
            {activeCount} processing
          </span>
        )}
      </div>

      {/* Processing batches */}
      {processingBatches.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {processingBatches.slice(0, 5).map((status) => (
            <BatchStatusItem
              key={status.batchId}
              status={status}
              showCamera={!filterCameraId}
            />
          ))}
          {processingBatches.length > 5 && (
            <span className="text-xs text-gray-500">
              +{processingBatches.length - 5} more
            </span>
          )}
        </div>
      )}

      {/* Recent completions */}
      {completedBatches.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {completedBatches.slice(0, 3).map((status) => (
            <BatchStatusItem
              key={status.batchId}
              status={status}
              showCamera={!filterCameraId}
            />
          ))}
        </div>
      )}

      {/* Recent failures */}
      {failedBatches.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {failedBatches.slice(0, 3).map((status) => (
            <BatchStatusItem
              key={status.batchId}
              status={status}
              showCamera={!filterCameraId}
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {processingBatches.length === 0 && completedBatches.length === 0 && failedBatches.length === 0 && (
        <p className="text-xs text-gray-500">No recent activity</p>
      )}
    </div>
  );
}

export { BatchStatusItem };
