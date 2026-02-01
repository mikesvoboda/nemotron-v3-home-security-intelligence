/**
 * QueueMetricsPanel - Real-time queue depth and pipeline throughput visualization
 *
 * Displays queue metrics from WebSocket events (queue.status and pipeline.throughput)
 * with visual indicators for queue health status.
 *
 * Features:
 * - Per-queue depth display with progress bars
 * - Throughput metrics (detections/events per minute)
 * - Historical mini-chart for queue depth trends
 * - Color-coded health status (green=healthy, yellow=elevated, red=critical)
 *
 * @module components/system/QueueMetricsPanel
 */

import { Card, Title, Text, Badge, AreaChart, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import { Layers, Activity, Zap, TrendingUp, AlertTriangle, Wifi, WifiOff } from 'lucide-react';
import { useMemo } from 'react';

import { useQueueMetricsWebSocket } from '../../hooks/useQueueMetricsWebSocket';
import { getQueueStatusColor } from '../../theme/colors';

import type {
  QueueStatusEntry,
  ThroughputEntry,
} from '../../hooks/useQueueMetricsWebSocket';
import type { QueueInfo } from '../../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the QueueMetricsPanel component
 */
export interface QueueMetricsPanelProps {
  /** Whether to enable WebSocket connection (default: true) */
  enabled?: boolean;
  /** Maximum number of history points to show in chart (default: 30) */
  maxHistoryPoints?: number;
  /** Queue depth warning threshold (default: 50) */
  warningThreshold?: number;
  /** Queue depth critical threshold (default: 100) */
  criticalThreshold?: number;
  /** Additional CSS classes */
  className?: string;
  /** Test ID for testing */
  'data-testid'?: string;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_WARNING_THRESHOLD = 50;
const DEFAULT_CRITICAL_THRESHOLD = 100;
const DEFAULT_MAX_HISTORY = 30;

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get status color based on queue depth relative to thresholds
 */
function getQueueHealthColor(
  depth: number,
  warningThreshold: number,
  criticalThreshold: number
): 'gray' | 'emerald' | 'yellow' | 'red' {
  if (depth === 0) return 'gray';
  if (depth < warningThreshold) return 'emerald';
  if (depth < criticalThreshold) return 'yellow';
  return 'red';
}

/**
 * Get status label based on overall status string
 */
function getStatusLabel(status: string): string {
  switch (status.toLowerCase()) {
    case 'healthy':
      return 'Healthy';
    case 'warning':
      return 'Elevated';
    case 'critical':
      return 'Critical';
    default:
      return status;
  }
}

/**
 * Format throughput number with appropriate precision
 */
function formatThroughput(value: number): string {
  if (value === 0) return '0';
  if (value < 1) return value.toFixed(2);
  if (value < 10) return value.toFixed(1);
  return Math.round(value).toString();
}

/**
 * Transform queue history for chart display
 */
function transformQueueHistoryForChart(
  history: QueueStatusEntry[],
  maxPoints: number
): Array<{ time: string; total: number }> {
  // History is newest first, reverse for chart (oldest to newest)
  const reversed = [...history].reverse().slice(-maxPoints);
  return reversed.map((entry) => ({
    time: new Date(entry.received_at).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }),
    total: entry.total_queued,
  }));
}

/**
 * Transform throughput history for chart display
 */
function transformThroughputHistoryForChart(
  history: ThroughputEntry[],
  maxPoints: number
): Array<{ time: string; detections: number; events: number }> {
  // History is newest first, reverse for chart (oldest to newest)
  const reversed = [...history].reverse().slice(-maxPoints);
  return reversed.map((entry) => ({
    time: new Date(entry.received_at).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }),
    detections: entry.detections_per_minute,
    events: entry.events_per_minute,
  }));
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Individual queue depth indicator with progress bar
 */
function QueueDepthIndicator({
  queue,
  warningThreshold,
  criticalThreshold,
  testId,
}: {
  queue: QueueInfo;
  warningThreshold: number;
  criticalThreshold: number;
  testId?: string;
}) {
  const color = getQueueHealthColor(queue.depth, warningThreshold, criticalThreshold);
  const percentage = Math.min((queue.depth / criticalThreshold) * 100, 100);

  return (
    <div
      className="rounded-lg bg-gray-800/50 p-3"
      data-testid={testId}
    >
      <div className="mb-2 flex items-center justify-between">
        <Text className="text-sm font-medium capitalize text-gray-300">
          {queue.name.replace(/_/g, ' ')}
        </Text>
        <Badge color={color} size="sm" data-testid={`${testId}-badge`}>
          {queue.depth}
        </Badge>
      </div>
      <ProgressBar
        value={percentage}
        color={color}
        className="h-2"
        data-testid={`${testId}-progress`}
      />
      <div className="mt-1 flex justify-between text-xs text-gray-500">
        <span>{queue.workers} worker{queue.workers !== 1 ? 's' : ''}</span>
        {queue.status && <span>{queue.status}</span>}
      </div>
    </div>
  );
}

/**
 * Connection status indicator
 */
function ConnectionStatus({ isConnected }: { isConnected: boolean }) {
  return (
    <div
      className={clsx(
        'flex items-center gap-1 rounded-full px-2 py-0.5 text-xs',
        isConnected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
      )}
      data-testid="connection-status"
    >
      {isConnected ? (
        <>
          <Wifi className="h-3 w-3" />
          <span>Live</span>
        </>
      ) : (
        <>
          <WifiOff className="h-3 w-3" />
          <span>Disconnected</span>
        </>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * QueueMetricsPanel - Real-time queue depth and throughput visualization
 *
 * @example
 * ```tsx
 * <QueueMetricsPanel
 *   warningThreshold={50}
 *   criticalThreshold={100}
 *   maxHistoryPoints={30}
 * />
 * ```
 */
export default function QueueMetricsPanel({
  enabled = true,
  maxHistoryPoints = DEFAULT_MAX_HISTORY,
  warningThreshold = DEFAULT_WARNING_THRESHOLD,
  criticalThreshold = DEFAULT_CRITICAL_THRESHOLD,
  className,
  'data-testid': testId = 'queue-metrics-panel',
}: QueueMetricsPanelProps) {
  // Subscribe to queue metrics WebSocket
  const {
    queueStatus,
    throughput,
    queueHistory,
    throughputHistory,
    lastUpdate,
    isConnected,
    totalQueueDepth,
    totalWorkers,
    isWarning,
    isCritical,
  } = useQueueMetricsWebSocket({
    enabled,
    maxHistory: maxHistoryPoints * 2, // Keep extra for chart smoothness
  });

  // Transform history for charts
  const queueChartData = useMemo(
    () => transformQueueHistoryForChart(queueHistory, maxHistoryPoints),
    [queueHistory, maxHistoryPoints]
  );

  const throughputChartData = useMemo(
    () => transformThroughputHistoryForChart(throughputHistory, maxHistoryPoints),
    [throughputHistory, maxHistoryPoints]
  );

  // Determine overall health color
  const overallHealthColor = useMemo(() => {
    if (isCritical) return 'red';
    if (isWarning) return 'yellow';
    if (totalQueueDepth === 0) return 'gray';
    return 'emerald';
  }, [isCritical, isWarning, totalQueueDepth]);

  // Get status badge color from centralized theme
  const statusBadgeColor = useMemo(() => {
    return getQueueStatusColor(totalQueueDepth, criticalThreshold);
  }, [totalQueueDepth, criticalThreshold]);

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid={testId}
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Layers className="h-5 w-5 text-[#76B900]" />
          Queue Metrics
          {(isWarning || isCritical) && (
            <AlertTriangle
              className={clsx(
                'h-4 w-4 animate-pulse',
                isCritical ? 'text-red-500' : 'text-yellow-500'
              )}
              data-testid="queue-warning-icon"
              aria-label={isCritical ? 'Queue critical' : 'Queue elevated'}
            />
          )}
        </Title>
        <ConnectionStatus isConnected={isConnected} />
      </div>

      <div className="space-y-4">
        {/* Overall Status Row */}
        <div className="flex items-center justify-between rounded-lg bg-gray-800/30 px-4 py-3">
          <div className="flex items-center gap-4">
            <div data-testid="total-queue-depth">
              <Text className="text-xs text-gray-500">Total Queued</Text>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-white">{totalQueueDepth}</span>
                <Badge color={statusBadgeColor} size="sm" data-testid="overall-status-badge">
                  {queueStatus ? getStatusLabel(queueStatus.overall_status) : 'Unknown'}
                </Badge>
              </div>
            </div>
            <div className="h-10 w-px bg-gray-700" />
            <div data-testid="total-workers">
              <Text className="text-xs text-gray-500">Active Workers</Text>
              <span className="text-2xl font-bold text-white">{totalWorkers}</span>
            </div>
            {queueStatus && (
              <>
                <div className="h-10 w-px bg-gray-700" />
                <div data-testid="processing-count">
                  <Text className="text-xs text-gray-500">Processing</Text>
                  <span className="text-2xl font-bold text-white">{queueStatus.total_processing}</span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Per-Queue Depths */}
        {queueStatus && queueStatus.queues.length > 0 && (
          <div>
            <div className="mb-2 flex items-center gap-2">
              <Activity className="h-4 w-4 text-[#76B900]" />
              <Text className="text-xs font-medium text-gray-400">Queue Depths</Text>
            </div>
            <div
              className="grid gap-3"
              style={{
                gridTemplateColumns: `repeat(${Math.min(queueStatus.queues.length, 3)}, 1fr)`,
              }}
              data-testid="queue-depths-grid"
            >
              {queueStatus.queues.map((queue) => (
                <QueueDepthIndicator
                  key={queue.name}
                  queue={queue}
                  warningThreshold={warningThreshold}
                  criticalThreshold={criticalThreshold}
                  testId={`queue-${queue.name}`}
                />
              ))}
            </div>
          </div>
        )}

        {/* Queue Depth History Chart */}
        <div className="rounded-lg bg-gray-800/30 p-3">
          <div className="mb-2 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-[#76B900]" />
            <Text className="text-xs font-medium text-gray-400">Queue Depth History</Text>
          </div>
          {queueChartData.length > 1 ? (
            <div data-testid="queue-history-chart">
              <AreaChart
                className="h-24"
                data={queueChartData}
                index="time"
                categories={['total']}
                colors={[overallHealthColor]}
                showLegend={false}
                showGridLines={false}
                showXAxis={false}
                showYAxis={false}
                curveType="monotone"
                valueFormatter={(value) => `${value} items`}
              />
            </div>
          ) : (
            <div
              className="flex h-24 items-center justify-center"
              data-testid="queue-history-empty"
            >
              <div className="flex items-center gap-1 text-gray-500">
                <TrendingUp className="h-4 w-4" />
                <Text className="text-xs">Collecting data...</Text>
              </div>
            </div>
          )}
        </div>

        {/* Throughput Section */}
        <div className="rounded-lg bg-gray-800/30 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-[#76B900]" />
              <Text className="text-xs font-medium text-gray-400">Throughput</Text>
            </div>
            {throughput && (
              <div className="flex items-center gap-4 text-sm" data-testid="throughput-values">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-gray-500">Detections:</span>
                  <span className="font-medium text-white">
                    {formatThroughput(throughput.detections_per_minute)}/min
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-gray-500">Events:</span>
                  <span className="font-medium text-white">
                    {formatThroughput(throughput.events_per_minute)}/min
                  </span>
                </div>
                {throughput.enrichments_per_minute !== undefined && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-gray-500">Enrichments:</span>
                    <span className="font-medium text-white">
                      {formatThroughput(throughput.enrichments_per_minute)}/min
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Throughput History Chart */}
          {throughputChartData.length > 1 ? (
            <div data-testid="throughput-history-chart">
              <AreaChart
                className="h-24"
                data={throughputChartData}
                index="time"
                categories={['detections', 'events']}
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
            <div
              className="flex h-24 items-center justify-center"
              data-testid="throughput-history-empty"
            >
              <div className="flex items-center gap-1 text-gray-500">
                <Zap className="h-4 w-4" />
                <Text className="text-xs">Collecting throughput data...</Text>
              </div>
            </div>
          )}
        </div>

        {/* Warning Banner */}
        {isCritical && (
          <div
            className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2"
            role="alert"
            data-testid="queue-critical-warning"
          >
            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-red-500" />
            <Text className="text-xs text-red-400">
              Queue depth critical. Processing backlog may cause delays.
            </Text>
          </div>
        )}

        {isWarning && !isCritical && (
          <div
            className="flex items-center gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-3 py-2"
            role="alert"
            data-testid="queue-warning-banner"
          >
            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-yellow-500" />
            <Text className="text-xs text-yellow-400">
              Queue depth elevated. Monitoring recommended.
            </Text>
          </div>
        )}

        {/* Timestamp */}
        {lastUpdate && (
          <p className="text-right text-xs text-gray-500" data-testid="queue-metrics-timestamp">
            Updated: {new Date(lastUpdate).toLocaleTimeString()}
          </p>
        )}
      </div>
    </Card>
  );
}
