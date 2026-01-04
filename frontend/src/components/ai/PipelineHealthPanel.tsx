/**
 * PipelineHealthPanel - Displays queue depths, error counts, and DLQ status
 *
 * Shows pipeline health metrics including queue backlogs, error breakdowns,
 * and dead letter queue items.
 */

import { Card, Title, Text, Badge, Metric, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Layers,
  AlertTriangle,
  Inbox,
  TrendingUp,
  TrendingDown,
  Activity,
} from 'lucide-react';

export interface PipelineHealthPanelProps {
  /** Detection queue depth */
  detectionQueueDepth: number;
  /** Analysis queue depth */
  analysisQueueDepth: number;
  /** Total detections processed */
  totalDetections: number;
  /** Total events created */
  totalEvents: number;
  /** Pipeline errors by type */
  pipelineErrors: Record<string, number>;
  /** Queue overflow counts */
  queueOverflows: Record<string, number>;
  /** Items in DLQ by queue */
  dlqItems: Record<string, number>;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get queue status color based on depth
 */
function getQueueColor(depth: number): 'green' | 'yellow' | 'red' {
  if (depth >= 50) return 'red';
  if (depth >= 10) return 'yellow';
  return 'green';
}

/**
 * Format DLQ queue name for display
 */
function formatDlqQueueName(key: string): string {
  // Convert 'dlq:detection_queue' -> 'Detection Queue'
  // Convert 'dlq:analysis_queue' -> 'Analysis Queue'
  const name = key.replace('dlq:', '').replace(/_/g, ' ');
  return name
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Format large numbers with K/M suffixes
 */
function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

/**
 * QueueDepthCard - Shows a single queue's depth with status
 */
interface QueueDepthCardProps {
  name: string;
  depth: number;
  maxDepth?: number;
  icon?: React.ReactNode;
}

function QueueDepthCard({ name, depth, maxDepth = 100, icon }: QueueDepthCardProps) {
  const color = getQueueColor(depth);
  const percent = Math.min((depth / maxDepth) * 100, 100);

  return (
    <div className="rounded-lg bg-gray-800/50 p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon || <Layers className="h-4 w-4 text-gray-500" />}
          <Text className="text-sm font-medium text-gray-300">{name}</Text>
        </div>
        <Badge color={color} size="sm">
          {depth} items
        </Badge>
      </div>
      <ProgressBar value={percent} color={color} className="h-2" />
      <Text className="mt-1 text-xs text-gray-500">
        {depth >= 50 ? 'Queue backlog detected' : depth >= 10 ? 'Moderate load' : 'Healthy'}
      </Text>
    </div>
  );
}

/**
 * PipelineHealthPanel - Comprehensive pipeline health display
 */
export default function PipelineHealthPanel({
  detectionQueueDepth,
  analysisQueueDepth,
  totalDetections,
  totalEvents,
  pipelineErrors,
  queueOverflows,
  dlqItems,
  className,
}: PipelineHealthPanelProps) {
  // Calculate total errors
  const totalErrors = Object.values(pipelineErrors).reduce((sum, count) => sum + count, 0);

  // Calculate total DLQ items
  const totalDlqItems = Object.values(dlqItems).reduce((sum, count) => sum + count, 0);

  // Calculate total overflows
  const totalOverflows = Object.values(queueOverflows).reduce((sum, count) => sum + count, 0);

  return (
    <div className={clsx('space-y-4', className)} data-testid="pipeline-health-panel">
      {/* Queue Depths */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="queue-depths-card">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Layers className="h-5 w-5 text-[#76B900]" />
          Queue Depths
        </Title>

        <div className="grid gap-4 md:grid-cols-2">
          <QueueDepthCard
            name="Detection Queue"
            depth={detectionQueueDepth}
            icon={<Activity className="h-4 w-4 text-blue-500" />}
          />
          <QueueDepthCard
            name="Analysis Queue"
            depth={analysisQueueDepth}
            icon={<Activity className="h-4 w-4 text-purple-500" />}
          />
        </div>
      </Card>

      {/* Throughput Stats */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="throughput-card">
        <Title className="mb-4 flex items-center gap-2 text-white">
          <TrendingUp className="h-5 w-5 text-[#76B900]" />
          Pipeline Throughput
        </Title>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-lg bg-gray-800/50 p-4">
            <div className="flex items-center justify-between">
              <Text className="text-sm text-gray-400">Total Detections</Text>
              <TrendingUp className="h-4 w-4 text-green-500" />
            </div>
            <Metric className="mt-2 text-2xl text-white">{formatNumber(totalDetections)}</Metric>
            <Text className="text-xs text-gray-500">Objects detected by RT-DETRv2</Text>
          </div>

          <div className="rounded-lg bg-gray-800/50 p-4">
            <div className="flex items-center justify-between">
              <Text className="text-sm text-gray-400">Total Events</Text>
              <TrendingUp className="h-4 w-4 text-green-500" />
            </div>
            <Metric className="mt-2 text-2xl text-white">{formatNumber(totalEvents)}</Metric>
            <Text className="text-xs text-gray-500">Security events generated</Text>
          </div>
        </div>
      </Card>

      {/* Error & DLQ Status */}
      {(totalErrors > 0 || totalDlqItems > 0 || totalOverflows > 0) && (
        <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="errors-card">
          <Title className="mb-4 flex items-center gap-2 text-white">
            <AlertTriangle className="h-5 w-5 text-yellow-500" />
            Errors & Dead Letter Queue
          </Title>

          <div className="space-y-4">
            {/* Pipeline Errors */}
            {totalErrors > 0 && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
                <div className="mb-2 flex items-center justify-between">
                  <Text className="font-medium text-red-400">Pipeline Errors</Text>
                  <Badge color="red">{totalErrors} total</Badge>
                </div>
                <div className="space-y-1">
                  {Object.entries(pipelineErrors).map(([type, count]) => (
                    <div key={type} className="flex justify-between text-sm">
                      <Text className="text-gray-400">{type.replace(/_/g, ' ')}</Text>
                      <Text className="text-red-300">{count}</Text>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Queue Overflows */}
            {totalOverflows > 0 && (
              <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4">
                <div className="mb-2 flex items-center justify-between">
                  <Text className="font-medium text-yellow-400">Queue Overflows</Text>
                  <Badge color="yellow">{totalOverflows} total</Badge>
                </div>
                <div className="space-y-1">
                  {Object.entries(queueOverflows).map(([queue, count]) => (
                    <div key={queue} className="flex justify-between text-sm">
                      <Text className="text-gray-400">{queue}</Text>
                      <Text className="text-yellow-300">{count}</Text>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* DLQ Items */}
            {totalDlqItems > 0 && (
              <div className="rounded-lg border border-orange-500/30 bg-orange-500/10 p-4" data-testid="dlq-items-section">
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Inbox className="h-4 w-4 text-orange-400" />
                    <Text className="font-medium text-orange-400">Dead Letter Queue</Text>
                  </div>
                  <Badge color="orange" data-testid="dlq-total-badge">{totalDlqItems.toLocaleString()} items</Badge>
                </div>
                <div className="space-y-1">
                  {Object.entries(dlqItems).map(([queue, count]) => (
                    <div key={queue} className="flex justify-between text-sm" data-testid={`dlq-queue-${queue}`}>
                      <Text className="text-gray-400">{formatDlqQueueName(queue)}</Text>
                      <Text className="text-orange-300">{count.toLocaleString()}</Text>
                    </div>
                  ))}
                </div>
                <Text className="mt-2 text-xs text-gray-500">
                  Failed jobs can be reviewed in Settings &gt; DLQ Monitor
                </Text>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* All Clear Status */}
      {totalErrors === 0 && totalDlqItems === 0 && totalOverflows === 0 && (
        <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="all-clear-card">
          <div className="flex items-center gap-3 p-4">
            <div className="rounded-full bg-green-500/20 p-2">
              <TrendingDown className="h-5 w-5 text-green-500" />
            </div>
            <div>
              <Text className="font-medium text-green-400">Pipeline Healthy</Text>
              <Text className="text-sm text-gray-500">
                No errors, overflows, or DLQ items detected
              </Text>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
