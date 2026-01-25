/**
 * BatchAggregatorCard Component
 *
 * Displays the status of the BatchAggregator service, showing active batches
 * being collected for LLM analysis. Highlights batches that are approaching
 * their timeout window.
 *
 * @see usePipelineStatus - Hook that provides batch aggregator data
 * @see backend/services/batch_aggregator.py - BatchAggregator service
 */

import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { Layers, Clock, Camera, AlertTriangle } from 'lucide-react';

import { formatWaitTime } from '../../types/queue';

import type { BatchAggregatorUIState, BatchInfoResponse } from '../../types/queue';

export interface BatchAggregatorCardProps {
  /** Batch aggregator state from usePipelineStatus */
  batchState: BatchAggregatorUIState;
  /** Whether data is currently loading */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get badge color based on batch age relative to timeout.
 */
function getBatchAgeBadgeColor(
  ageSeconds: number,
  windowSeconds: number
): 'gray' | 'green' | 'yellow' | 'red' {
  const ratio = ageSeconds / windowSeconds;
  if (ratio >= 0.8) return 'red';
  if (ratio >= 0.5) return 'yellow';
  return 'green';
}

/**
 * Get badge color for active batch count.
 */
function getActiveBatchBadgeColor(count: number): 'gray' | 'green' | 'yellow' | 'red' {
  if (count === 0) return 'gray';
  if (count <= 2) return 'green';
  if (count <= 5) return 'yellow';
  return 'red';
}

/**
 * Format batch age as a percentage of the window.
 */
function formatBatchProgress(ageSeconds: number, windowSeconds: number): string {
  const percentage = Math.min((ageSeconds / windowSeconds) * 100, 100);
  return `${percentage.toFixed(0)}%`;
}

/**
 * BatchAggregatorCard displays the status of the BatchAggregator service.
 *
 * Shows:
 * - Number of active batches being aggregated
 * - Per-batch details (camera, detection count, age)
 * - Warning indicators for batches approaching timeout
 *
 * The batch aggregator collects detections from cameras into time-based
 * batches for efficient LLM analysis. Each batch has a configurable
 * window timeout (default 90s) and idle timeout (default 30s).
 */
export default function BatchAggregatorCard({
  batchState,
  isLoading = false,
  className,
}: BatchAggregatorCardProps) {
  const {
    activeBatchCount,
    batches,
    batchWindowSeconds,
    batchesApproachingTimeout,
    hasTimeoutWarning,
  } = batchState;

  const activeBadgeColor = getActiveBatchBadgeColor(activeBatchCount);

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="batch-aggregator-card"
    >
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Layers className="h-5 w-5 text-[#76B900]" />
        Batch Aggregator
        {hasTimeoutWarning && (
          <AlertTriangle
            className="h-5 w-5 animate-pulse text-yellow-500"
            data-testid="batch-timeout-warning-icon"
            aria-label="Batches approaching timeout"
          />
        )}
      </Title>

      <div className="space-y-4">
        {/* Summary Row */}
        <div
          className="flex items-center justify-between rounded-lg bg-gray-800/50 p-3"
          data-testid="batch-summary-row"
        >
          <div className="flex flex-col">
            <Text className="text-sm font-medium text-gray-300">Active Batches</Text>
            <Text className="text-xs text-gray-500">
              Window: {batchWindowSeconds}s
            </Text>
          </div>
          <Badge
            color={activeBadgeColor}
            size="lg"
            data-testid="active-batch-count-badge"
          >
            {isLoading ? '...' : activeBatchCount}
          </Badge>
        </div>

        {/* Individual Batches */}
        {batches.length > 0 && (
          <div className="space-y-2" data-testid="batch-list">
            <Text className="text-xs font-medium uppercase text-gray-500">
              Active Batches
            </Text>
            {batches.map((batch) => (
              <BatchRow
                key={batch.batch_id}
                batch={batch}
                windowSeconds={batchWindowSeconds}
                isApproachingTimeout={batchesApproachingTimeout.some(
                  (b) => b.batch_id === batch.batch_id
                )}
              />
            ))}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && batches.length === 0 && (
          <div
            className="flex items-center justify-center rounded-lg bg-gray-800/30 p-4"
            data-testid="batch-empty-state"
          >
            <Text className="text-sm text-gray-500">No active batches</Text>
          </div>
        )}

        {/* Timeout Warning */}
        {hasTimeoutWarning && (
          <div
            className="flex items-center gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3"
            role="alert"
            data-testid="batch-timeout-warning"
          >
            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-yellow-500" />
            <Text className="text-sm text-yellow-400">
              {batchesApproachingTimeout.length} batch
              {batchesApproachingTimeout.length === 1 ? '' : 'es'} approaching timeout
            </Text>
          </div>
        )}
      </div>
    </Card>
  );
}

/**
 * Props for the BatchRow component.
 */
interface BatchRowProps {
  /** Batch information */
  batch: BatchInfoResponse;
  /** Configured window timeout in seconds */
  windowSeconds: number;
  /** Whether this batch is approaching timeout */
  isApproachingTimeout: boolean;
}

/**
 * BatchRow displays a single active batch with its details.
 */
function BatchRow({ batch, windowSeconds, isApproachingTimeout }: BatchRowProps) {
  const ageBadgeColor = getBatchAgeBadgeColor(batch.age_seconds, windowSeconds);

  return (
    <div
      className={clsx(
        'flex items-center justify-between rounded-lg p-3',
        isApproachingTimeout
          ? 'border border-yellow-500/30 bg-yellow-500/10'
          : 'bg-gray-800/50'
      )}
      data-testid={`batch-row-${batch.batch_id}`}
    >
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <Camera className="h-4 w-4 text-gray-400" />
          <Text className="text-sm font-medium text-gray-300">
            {batch.camera_id}
          </Text>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span>{batch.detection_count} detections</span>
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatWaitTime(batch.age_seconds)}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {isApproachingTimeout && (
          <AlertTriangle
            className="h-4 w-4 text-yellow-500"
            data-testid={`batch-timeout-icon-${batch.batch_id}`}
          />
        )}
        <Badge
          color={ageBadgeColor}
          size="sm"
          data-testid={`batch-progress-${batch.batch_id}`}
        >
          {formatBatchProgress(batch.age_seconds, windowSeconds)}
        </Badge>
      </div>
    </div>
  );
}
