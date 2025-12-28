import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { Layers, AlertTriangle } from 'lucide-react';

export interface PipelineQueuesProps {
  /** Number of items in detection queue */
  detectionQueue: number;
  /** Number of items in analysis queue */
  analysisQueue: number;
  /** Threshold above which to show warning (default: 10) */
  warningThreshold?: number;
  /** Additional CSS classes */
  className?: string;
}

/** Threshold for queue backup warning */
const DEFAULT_WARNING_THRESHOLD = 10;

/**
 * Gets the badge color based on queue depth
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
 * Shows:
 * - Detection queue: Items waiting for RT-DETRv2 object detection
 * - Analysis queue: Items waiting for Nemotron LLM analysis
 * - Warning indicators when queues exceed threshold (default: 10)
 *
 * Queue status colors:
 * - Gray: Empty queue (0 items)
 * - Green: Healthy queue (1-5 items)
 * - Yellow: Moderate queue (6-10 items)
 * - Red: Backing up (>10 items)
 */
export default function PipelineQueues({
  detectionQueue,
  analysisQueue,
  warningThreshold = DEFAULT_WARNING_THRESHOLD,
  className,
}: PipelineQueuesProps) {
  const detectionBackingUp = isQueueBackingUp(detectionQueue, warningThreshold);
  const analysisBackingUp = isQueueBackingUp(analysisQueue, warningThreshold);
  const anyBackingUp = detectionBackingUp || analysisBackingUp;

  const detectionColor = getQueueBadgeColor(detectionQueue, warningThreshold);
  const analysisColor = getQueueBadgeColor(analysisQueue, warningThreshold);

  return (
    <Card
      className={clsx('bg-[#1A1A1A] border-gray-800 shadow-lg', className)}
      data-testid="pipeline-queues"
    >
      <Title className="text-white mb-4 flex items-center gap-2">
        <Layers className="h-5 w-5 text-[#76B900]" />
        Pipeline Queues
        {anyBackingUp && (
          <AlertTriangle
            className="h-5 w-5 text-red-500 animate-pulse"
            data-testid="queue-warning-icon"
            aria-label="Queue backup warning"
          />
        )}
      </Title>

      <div className="space-y-4">
        {/* Detection Queue */}
        <div
          className={clsx(
            'flex items-center justify-between p-3 rounded-lg',
            detectionBackingUp ? 'bg-red-500/10 border border-red-500/30' : 'bg-gray-800/50'
          )}
          data-testid="detection-queue-row"
        >
          <div className="flex flex-col">
            <Text className="text-gray-300 text-sm font-medium">Detection Queue</Text>
            <Text className="text-gray-500 text-xs">RT-DETRv2 processing</Text>
          </div>
          <div className="flex items-center gap-2">
            {detectionBackingUp && (
              <AlertTriangle
                className="h-4 w-4 text-red-500"
                data-testid="detection-queue-warning"
                aria-label="Detection queue backing up"
              />
            )}
            <Badge
              color={detectionColor}
              size="lg"
              data-testid="detection-queue-badge"
            >
              {detectionQueue}
            </Badge>
          </div>
        </div>

        {/* Analysis Queue */}
        <div
          className={clsx(
            'flex items-center justify-between p-3 rounded-lg',
            analysisBackingUp ? 'bg-red-500/10 border border-red-500/30' : 'bg-gray-800/50'
          )}
          data-testid="analysis-queue-row"
        >
          <div className="flex flex-col">
            <Text className="text-gray-300 text-sm font-medium">Analysis Queue</Text>
            <Text className="text-gray-500 text-xs">Nemotron LLM analysis</Text>
          </div>
          <div className="flex items-center gap-2">
            {analysisBackingUp && (
              <AlertTriangle
                className="h-4 w-4 text-red-500"
                data-testid="analysis-queue-warning"
                aria-label="Analysis queue backing up"
              />
            )}
            <Badge
              color={analysisColor}
              size="lg"
              data-testid="analysis-queue-badge"
            >
              {analysisQueue}
            </Badge>
          </div>
        </div>

        {/* Warning message when queues are backing up */}
        {anyBackingUp && (
          <div
            className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30"
            role="alert"
            data-testid="queue-backup-warning"
          >
            <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0" />
            <Text className="text-red-400 text-sm">
              Queue backup detected. Processing may be delayed.
            </Text>
          </div>
        )}
      </div>
    </Card>
  );
}
