import { Card, Title, Text, Badge, AreaChart } from '@tremor/react';
import { clsx } from 'clsx';
import { Activity, Layers, Clock, AlertTriangle, Zap, TrendingUp } from 'lucide-react';

/**
 * Queue depths data
 */
export interface QueueDepths {
  detection_queue: number;
  analysis_queue: number;
}

/**
 * Latency data for a pipeline stage
 */
export interface StageLatency {
  avg_ms?: number | null | undefined;
  p95_ms?: number | null | undefined;
  p99_ms?: number | null | undefined;
  sample_count?: number;
}

/**
 * Latency data for all stages
 */
export interface PipelineLatencies {
  detect?: StageLatency | null;
  batch?: StageLatency | null;
  analyze?: StageLatency | null;
}

/**
 * Throughput data point
 */
export interface ThroughputPoint {
  time: string;
  detections: number;
  analyses: number;
}

/**
 * Props for PipelineMetricsPanel component
 */
export interface PipelineMetricsPanelProps {
  /** Queue depths */
  queues: QueueDepths;
  /** Pipeline stage latencies */
  latencies?: PipelineLatencies | null;
  /** Throughput history data for chart */
  throughputHistory?: ThroughputPoint[];
  /** Last update timestamp */
  timestamp?: string | null;
  /** Warning threshold for queue depth (default: 10) */
  queueWarningThreshold?: number;
  /** Warning threshold for latency in ms (default: 10000) */
  latencyWarningThreshold?: number;
  /** Additional CSS classes */
  className?: string;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
}

const DEFAULT_QUEUE_THRESHOLD = 10;
const DEFAULT_LATENCY_THRESHOLD = 10000;

/**
 * Formats latency value in milliseconds to human-readable format
 */
function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '-';
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Gets badge color based on queue depth
 */
function getQueueBadgeColor(depth: number, threshold: number): 'gray' | 'green' | 'yellow' | 'red' {
  if (depth === 0) return 'gray';
  if (depth <= threshold / 2) return 'green';
  if (depth <= threshold) return 'yellow';
  return 'red';
}

/**
 * Gets badge color based on latency value
 */
function getLatencyColor(
  ms: number | null | undefined,
  threshold: number
): 'gray' | 'green' | 'yellow' | 'red' {
  if (ms === null || ms === undefined) return 'gray';
  if (ms < threshold / 2) return 'green';
  if (ms < threshold) return 'yellow';
  return 'red';
}

/**
 * PipelineMetricsPanel - Combined panel for pipeline queues, latency, and throughput
 *
 * This is a compact, information-dense component that combines:
 * - Queue depths (Detection + Analysis)
 * - Processing latency (avg/p95/p99 for detect, batch, analyze)
 * - Throughput metrics with sparkline chart
 *
 * Designed for the dense system monitoring dashboard layout.
 */
export default function PipelineMetricsPanel({
  queues,
  latencies,
  throughputHistory = [],
  timestamp,
  queueWarningThreshold = DEFAULT_QUEUE_THRESHOLD,
  latencyWarningThreshold = DEFAULT_LATENCY_THRESHOLD,
  className,
  'data-testid': testId = 'pipeline-metrics-panel',
}: PipelineMetricsPanelProps) {
  const { detection_queue, analysis_queue } = queues;

  // Check for warnings
  const detectionBackingUp = detection_queue > queueWarningThreshold;
  const analysisBackingUp = analysis_queue > queueWarningThreshold;
  const anyQueueWarning = detectionBackingUp || analysisBackingUp;

  const detectLatencyWarning = (latencies?.detect?.avg_ms ?? 0) > latencyWarningThreshold;
  const analyzeLatencyWarning = (latencies?.analyze?.avg_ms ?? 0) > latencyWarningThreshold;
  const anyLatencyWarning = detectLatencyWarning || analyzeLatencyWarning;

  const anyWarning = anyQueueWarning || anyLatencyWarning;

  // Get latest throughput values
  const latestThroughput = throughputHistory.length > 0
    ? throughputHistory[throughputHistory.length - 1]
    : null;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid={testId}
    >
      <Title className="mb-3 flex items-center gap-2 text-white">
        <Activity className="h-5 w-5 text-[#76B900]" />
        Pipeline Metrics
        {anyWarning && (
          <AlertTriangle
            className="h-4 w-4 animate-pulse text-yellow-500"
            data-testid="pipeline-warning-icon"
            aria-label="Pipeline warning"
          />
        )}
      </Title>

      <div className="space-y-4">
        {/* Queue Depths Row - Compact inline display */}
        <div className="flex items-center justify-between rounded-lg bg-gray-800/30 px-3 py-2">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-[#76B900]" />
            <Text className="text-sm font-medium text-gray-300">Queues</Text>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5" data-testid="detection-queue-inline">
              <Text className="text-xs text-gray-500">Detect:</Text>
              <Badge
                color={getQueueBadgeColor(detection_queue, queueWarningThreshold)}
                size="sm"
                data-testid="detection-queue-badge"
              >
                {detection_queue}
              </Badge>
              {detectionBackingUp && (
                <AlertTriangle className="h-3 w-3 text-red-500" aria-label="Detection queue backing up" />
              )}
            </div>
            <div className="flex items-center gap-1.5" data-testid="analysis-queue-inline">
              <Text className="text-xs text-gray-500">Analyze:</Text>
              <Badge
                color={getQueueBadgeColor(analysis_queue, queueWarningThreshold)}
                size="sm"
                data-testid="analysis-queue-badge"
              >
                {analysis_queue}
              </Badge>
              {analysisBackingUp && (
                <AlertTriangle className="h-3 w-3 text-red-500" aria-label="Analysis queue backing up" />
              )}
            </div>
          </div>
        </div>

        {/* Latency Grid - Compact 3-column layout */}
        <div>
          <div className="mb-2 flex items-center gap-2">
            <Clock className="h-4 w-4 text-[#76B900]" />
            <Text className="text-xs font-medium text-gray-400">Latency (avg / p95 / p99)</Text>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {/* Detection Latency */}
            <div
              className={clsx(
                'rounded-lg p-2 text-center',
                detectLatencyWarning ? 'border border-yellow-500/30 bg-yellow-500/10' : 'bg-gray-800/50'
              )}
              data-testid="detect-latency-card"
            >
              <Text className="text-xs text-gray-500">Detection</Text>
              <div className="mt-1">
                <Badge
                  color={getLatencyColor(latencies?.detect?.avg_ms, latencyWarningThreshold)}
                  size="sm"
                  data-testid="detect-latency-badge"
                >
                  {formatLatency(latencies?.detect?.avg_ms)}
                </Badge>
              </div>
              <Text className="mt-1 text-xs text-gray-500">
                {formatLatency(latencies?.detect?.p95_ms)} / {formatLatency(latencies?.detect?.p99_ms)}
              </Text>
            </div>

            {/* Batch Latency */}
            <div
              className="rounded-lg bg-gray-800/50 p-2 text-center"
              data-testid="batch-latency-card"
            >
              <Text className="text-xs text-gray-500">Batch</Text>
              <div className="mt-1">
                <Badge
                  color={getLatencyColor(latencies?.batch?.avg_ms, latencyWarningThreshold)}
                  size="sm"
                  data-testid="batch-latency-badge"
                >
                  {formatLatency(latencies?.batch?.avg_ms)}
                </Badge>
              </div>
              <Text className="mt-1 text-xs text-gray-500">
                {formatLatency(latencies?.batch?.p95_ms)} / {formatLatency(latencies?.batch?.p99_ms)}
              </Text>
            </div>

            {/* Analysis Latency */}
            <div
              className={clsx(
                'rounded-lg p-2 text-center',
                analyzeLatencyWarning ? 'border border-yellow-500/30 bg-yellow-500/10' : 'bg-gray-800/50'
              )}
              data-testid="analyze-latency-card"
            >
              <Text className="text-xs text-gray-500">Analysis</Text>
              <div className="mt-1">
                <Badge
                  color={getLatencyColor(latencies?.analyze?.avg_ms, latencyWarningThreshold)}
                  size="sm"
                  data-testid="analyze-latency-badge"
                >
                  {formatLatency(latencies?.analyze?.avg_ms)}
                </Badge>
              </div>
              <Text className="mt-1 text-xs text-gray-500">
                {formatLatency(latencies?.analyze?.p95_ms)} / {formatLatency(latencies?.analyze?.p99_ms)}
              </Text>
            </div>
          </div>
        </div>

        {/* Throughput Row - Inline stats with mini sparkline */}
        <div className="rounded-lg bg-gray-800/30 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-[#76B900]" />
              <Text className="text-sm font-medium text-gray-300">Throughput</Text>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-1.5" data-testid="detections-throughput">
                <span className="text-xs text-gray-500">Detect:</span>
                <span className="font-medium text-white">
                  {latestThroughput ? `${latestThroughput.detections}/min` : '-'}
                </span>
              </div>
              <div className="flex items-center gap-1.5" data-testid="analyses-throughput">
                <span className="text-xs text-gray-500">Analyze:</span>
                <span className="font-medium text-white">
                  {latestThroughput ? `${latestThroughput.analyses}/min` : '-'}
                </span>
              </div>
            </div>
          </div>

          {/* Mini Sparkline Chart */}
          {throughputHistory.length > 0 ? (
            <div data-testid="throughput-chart">
              <AreaChart
                className="h-16"
                data={throughputHistory}
                index="time"
                categories={['detections', 'analyses']}
                colors={['emerald', 'blue']}
                showLegend={false}
                showGridLines={false}
                showXAxis={false}
                showYAxis={false}
                curveType="monotone"
                valueFormatter={(value) => `${value}/min`}
              />
            </div>
          ) : (
            <div className="flex h-16 items-center justify-center" data-testid="throughput-chart-empty">
              <div className="flex items-center gap-1 text-gray-500">
                <TrendingUp className="h-4 w-4" />
                <Text className="text-xs">Collecting data...</Text>
              </div>
            </div>
          )}
        </div>

        {/* Queue Warning Banner */}
        {anyQueueWarning && (
          <div
            className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2"
            role="alert"
            data-testid="queue-backup-warning"
          >
            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-red-500" />
            <Text className="text-xs text-red-400">
              Queue backup detected. Processing may be delayed.
            </Text>
          </div>
        )}

        {/* Timestamp */}
        {timestamp && (
          <p className="text-right text-xs text-gray-500" data-testid="pipeline-timestamp">
            Updated: {new Date(timestamp).toLocaleTimeString()}
          </p>
        )}
      </div>
    </Card>
  );
}
