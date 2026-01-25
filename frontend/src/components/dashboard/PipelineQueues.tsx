/**
 * PipelineQueues Component
 *
 * Displays the current queue depths and status for the AI processing pipeline.
 * Enhanced with detailed metrics including worker counts, throughput, health status,
 * and DLQ information.
 *
 * @see useQueuesStatus - Hook that provides queue status data
 * @see backend/api/routes/queues.py - GET /api/queues/status
 */

import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { Layers, AlertTriangle, Clock, Users, Zap, Skull } from 'lucide-react';

import {
  getHealthStatusBadgeColor,
  formatWaitTime,
  formatThroughput,
} from '../../types/queue';

import type {
  QueueStatus,
  QueueHealthStatus,
  QueuesStatusResponse,
} from '../../types/queue';

export interface PipelineQueuesProps {
  /** Number of items in detection queue (fallback when detailed data unavailable) */
  detectionQueue: number;
  /** Number of items in analysis queue (fallback when detailed data unavailable) */
  analysisQueue: number;
  /** Detailed queue status from useQueuesStatus hook (optional) */
  queuesStatus?: QueuesStatusResponse | null;
  /** Whether queue status data is loading */
  isLoading?: boolean;
  /** Threshold above which to show warning (default: 10) */
  warningThreshold?: number;
  /** Additional CSS classes */
  className?: string;
}

/** Threshold for queue backup warning */
const DEFAULT_WARNING_THRESHOLD = 10;

/**
 * Gets the badge color based on queue depth (legacy fallback)
 */
function getQueueBadgeColor(depth: number, threshold: number): 'gray' | 'green' | 'yellow' | 'red' {
  if (depth === 0) return 'gray';
  if (depth <= threshold / 2) return 'green';
  if (depth <= threshold) return 'yellow';
  return 'red';
}

/**
 * Determines if a queue is backing up (exceeds threshold)
 */
function isQueueBackingUp(depth: number, threshold: number): boolean {
  return depth > threshold;
}

/**
 * PipelineQueues displays the current queue depths for the AI processing pipeline.
 *
 * Enhanced features:
 * - Health status badges (green/yellow/red based on backend health checks)
 * - Worker count per queue
 * - Throughput metrics (jobs/min)
 * - Oldest job wait time
 * - DLQ status section
 *
 * Queue status colors:
 * - Gray: Empty queue (0 items)
 * - Green: Healthy queue
 * - Yellow: Warning status (approaching limits)
 * - Red: Critical status (exceeds limits)
 */
export default function PipelineQueues({
  detectionQueue,
  analysisQueue,
  queuesStatus,
  isLoading = false,
  warningThreshold = DEFAULT_WARNING_THRESHOLD,
  className,
}: PipelineQueuesProps) {
  // Use detailed queue status if available, otherwise fall back to basic counters
  const hasDetailedStatus = queuesStatus !== null && queuesStatus !== undefined;

  // Find specific queues from detailed status
  const detectionQueueStatus = queuesStatus?.queues.find(
    (q) => q.name === 'detection' || q.name === 'detection_queue'
  );
  const analysisQueueStatus = queuesStatus?.queues.find(
    (q) => q.name === 'ai_analysis' || q.name === 'analysis' || q.name === 'analysis_queue'
  );
  const dlqStatus = queuesStatus?.queues.find(
    (q) => q.name === 'dlq' || q.name.includes('dead_letter')
  );

  // Determine overall health status
  const overallStatus = queuesStatus?.summary.overall_status ?? 'healthy';
  const hasCritical = overallStatus === 'critical';
  const hasWarning = overallStatus === 'warning' || hasCritical;

  // Legacy fallback calculations
  const detectionBackingUp = isQueueBackingUp(
    detectionQueueStatus?.depth ?? detectionQueue,
    warningThreshold
  );
  const analysisBackingUp = isQueueBackingUp(
    analysisQueueStatus?.depth ?? analysisQueue,
    warningThreshold
  );
  const anyBackingUp = detectionBackingUp || analysisBackingUp || hasWarning;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="pipeline-queues"
    >
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Layers className="h-5 w-5 text-[#76B900]" />
        Pipeline Queues
        {hasDetailedStatus && (
          <Badge
            color={getHealthStatusBadgeColor(overallStatus)}
            size="sm"
            data-testid="overall-health-badge"
          >
            {overallStatus}
          </Badge>
        )}
        {anyBackingUp && (
          <AlertTriangle
            className="h-5 w-5 animate-pulse text-red-500"
            data-testid="queue-warning-icon"
            aria-label="Queue backup warning"
          />
        )}
      </Title>

      <div className="space-y-4">
        {/* Detection Queue */}
        <QueueRow
          name="Detection Queue"
          description="RT-DETRv2 processing"
          queueStatus={detectionQueueStatus}
          fallbackDepth={detectionQueue}
          isBackingUp={detectionBackingUp}
          warningThreshold={warningThreshold}
          isLoading={isLoading}
          testIdPrefix="detection"
        />

        {/* Analysis Queue */}
        <QueueRow
          name="Analysis Queue"
          description="Nemotron LLM analysis"
          queueStatus={analysisQueueStatus}
          fallbackDepth={analysisQueue}
          isBackingUp={analysisBackingUp}
          warningThreshold={warningThreshold}
          isLoading={isLoading}
          testIdPrefix="analysis"
        />

        {/* DLQ Status (only show if data available and has items) */}
        {dlqStatus && dlqStatus.depth > 0 && (
          <DLQRow queueStatus={dlqStatus} isLoading={isLoading} />
        )}

        {/* Summary Stats */}
        {hasDetailedStatus && (
          <div
            className="grid grid-cols-3 gap-2 rounded-lg bg-gray-800/30 p-3"
            data-testid="queue-summary-stats"
          >
            <div className="flex flex-col items-center">
              <Text className="text-lg font-semibold text-white">
                {queuesStatus.summary.total_queued}
              </Text>
              <Text className="text-xs text-gray-500">Queued</Text>
            </div>
            <div className="flex flex-col items-center">
              <Text className="text-lg font-semibold text-white">
                {queuesStatus.summary.total_running}
              </Text>
              <Text className="text-xs text-gray-500">Running</Text>
            </div>
            <div className="flex flex-col items-center">
              <Text className="text-lg font-semibold text-white">
                {queuesStatus.summary.total_workers}
              </Text>
              <Text className="text-xs text-gray-500">Workers</Text>
            </div>
          </div>
        )}

        {/* Warning message when queues are backing up */}
        {anyBackingUp && (
          <div
            className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3"
            role="alert"
            data-testid="queue-backup-warning"
          >
            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-red-500" />
            <Text className="text-sm text-red-400">
              Queue backup detected. Processing may be delayed.
            </Text>
          </div>
        )}
      </div>
    </Card>
  );
}

/**
 * Props for the QueueRow component.
 */
interface QueueRowProps {
  /** Display name for the queue */
  name: string;
  /** Description of what this queue processes */
  description: string;
  /** Detailed queue status (if available) */
  queueStatus?: QueueStatus;
  /** Fallback depth when detailed status unavailable */
  fallbackDepth: number;
  /** Whether this queue is considered backing up */
  isBackingUp: boolean;
  /** Threshold for warning */
  warningThreshold: number;
  /** Whether data is loading */
  isLoading: boolean;
  /** Prefix for test IDs */
  testIdPrefix: string;
}

/**
 * QueueRow displays a single queue with its details.
 */
function QueueRow({
  name,
  description,
  queueStatus,
  fallbackDepth,
  isBackingUp,
  warningThreshold,
  isLoading,
  testIdPrefix,
}: QueueRowProps) {
  const hasDetailedStatus = queueStatus !== undefined;
  const depth = queueStatus?.depth ?? fallbackDepth;
  const healthStatus: QueueHealthStatus = queueStatus?.status ?? 'healthy';

  // Use health status for badge color if available, otherwise fall back to legacy logic
  const badgeColor = hasDetailedStatus
    ? getHealthStatusBadgeColor(healthStatus)
    : getQueueBadgeColor(depth, warningThreshold);

  const isCritical = healthStatus === 'critical' || isBackingUp;

  return (
    <div
      className={clsx(
        'flex items-center justify-between rounded-lg p-3',
        isCritical ? 'border border-red-500/30 bg-red-500/10' : 'bg-gray-800/50'
      )}
      data-testid={`${testIdPrefix}-queue-row`}
    >
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <Text className="text-sm font-medium text-gray-300">{name}</Text>
          {hasDetailedStatus && (
            <Badge
              color={badgeColor}
              size="xs"
              data-testid={`${testIdPrefix}-health-badge`}
            >
              {healthStatus}
            </Badge>
          )}
        </div>
        <Text className="text-xs text-gray-500">{description}</Text>

        {/* Detailed metrics row */}
        {hasDetailedStatus && queueStatus && (
          <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1" title="Workers">
              <Users className="h-3 w-3" />
              {queueStatus.workers}
            </span>
            <span className="flex items-center gap-1" title="Throughput">
              <Zap className="h-3 w-3" />
              {formatThroughput(queueStatus.throughput.jobs_per_minute)}
            </span>
            {queueStatus.oldest_job && queueStatus.oldest_job.wait_seconds > 0 && (
              <span className="flex items-center gap-1" title="Oldest job wait time">
                <Clock className="h-3 w-3" />
                {formatWaitTime(queueStatus.oldest_job.wait_seconds)}
              </span>
            )}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        {isCritical && (
          <AlertTriangle
            className="h-4 w-4 text-red-500"
            data-testid={`${testIdPrefix}-queue-warning`}
            aria-label={`${name} backing up`}
          />
        )}
        <Badge
          color={badgeColor}
          size="lg"
          data-testid={`${testIdPrefix}-queue-badge`}
        >
          {isLoading ? '...' : depth}
        </Badge>
      </div>
    </div>
  );
}

/**
 * Props for the DLQRow component.
 */
interface DLQRowProps {
  /** DLQ status */
  queueStatus: QueueStatus;
  /** Whether data is loading */
  isLoading: boolean;
}

/**
 * DLQRow displays the dead-letter queue status.
 */
function DLQRow({ queueStatus, isLoading }: DLQRowProps) {
  const healthStatus = queueStatus.status;
  const badgeColor = getHealthStatusBadgeColor(healthStatus);
  const isCritical = healthStatus === 'critical' || queueStatus.depth > 0;

  return (
    <div
      className={clsx(
        'flex items-center justify-between rounded-lg p-3',
        isCritical ? 'border border-red-500/30 bg-red-500/10' : 'bg-gray-800/50'
      )}
      data-testid="dlq-row"
    >
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <Skull className="h-4 w-4 text-red-400" />
          <Text className="text-sm font-medium text-gray-300">Dead Letter Queue</Text>
          <Badge color={badgeColor} size="xs" data-testid="dlq-health-badge">
            {healthStatus}
          </Badge>
        </div>
        <Text className="text-xs text-gray-500">Failed jobs requiring attention</Text>
      </div>
      <div className="flex items-center gap-2">
        {queueStatus.depth > 0 && (
          <AlertTriangle
            className="h-4 w-4 text-red-500"
            data-testid="dlq-warning"
            aria-label="DLQ has failed jobs"
          />
        )}
        <Badge color="red" size="lg" data-testid="dlq-badge">
          {isLoading ? '...' : queueStatus.depth}
        </Badge>
      </div>
    </div>
  );
}
