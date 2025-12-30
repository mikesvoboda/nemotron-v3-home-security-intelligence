import {
  Card,
  Title,
  Text,
  Badge,
  AreaChart,
  TabGroup,
  TabList,
  Tab,
} from '@tremor/react';
import { clsx } from 'clsx';
import {
  Activity,
  TrendingUp,
  Clock,
  AlertTriangle,
  Layers,
  Zap,
  BarChart3,
} from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';

import { fetchTelemetry, type TelemetryResponse, type StageLatency } from '../../services/api';

export interface PipelineTelemetryProps {
  /** Polling interval in milliseconds (default: 5000) */
  pollingInterval?: number;
  /** Warning threshold for queue depth (default: 10) */
  queueWarningThreshold?: number;
  /** Warning threshold for latency in ms (default: 10000) */
  latencyWarningThreshold?: number;
  /** Additional CSS classes */
  className?: string;
}

/**
 * History data point for latency charts
 */
interface LatencyHistoryPoint {
  time: string;
  detect: number | null;
  batch: number | null;
  analyze: number | null;
}

/**
 * Throughput data point
 */
interface ThroughputPoint {
  time: string;
  detections: number;
  analyses: number;
}

/**
 * Tab index for chart selection
 */
type ChartTab = 0 | 1 | 2;

/**
 * Formats latency value in milliseconds to human-readable format
 */
function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return 'N/A';
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
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
 * Gets badge color based on queue depth
 */
function getQueueBadgeColor(
  depth: number,
  threshold: number
): 'gray' | 'green' | 'yellow' | 'red' {
  if (depth === 0) return 'gray';
  if (depth <= threshold / 2) return 'green';
  if (depth <= threshold) return 'yellow';
  return 'red';
}

/**
 * Gets error rate color based on percentage
 */
function getErrorRateColor(rate: number): 'gray' | 'green' | 'yellow' | 'red' {
  if (rate === 0) return 'gray';
  if (rate < 1) return 'green';
  if (rate < 5) return 'yellow';
  return 'red';
}

/**
 * PipelineTelemetry displays real-time AI pipeline metrics including:
 * - Detection and analysis queue depths
 * - Processing latency (avg, p95, p99) for each pipeline stage
 * - Throughput metrics (detections/min, analyses/min)
 * - Error rates
 *
 * Uses the /api/system/telemetry endpoint for data.
 */
export default function PipelineTelemetry({
  pollingInterval = 5000,
  queueWarningThreshold = 10,
  latencyWarningThreshold = 10000,
  className,
}: PipelineTelemetryProps) {
  // Current telemetry data
  const [telemetry, setTelemetry] = useState<TelemetryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // History data for charts
  const [latencyHistory, setLatencyHistory] = useState<LatencyHistoryPoint[]>([]);
  const [throughputHistory, setThroughputHistory] = useState<ThroughputPoint[]>([]);

  // Track previous telemetry for throughput calculation
  const [prevTelemetry, setPrevTelemetry] = useState<TelemetryResponse | null>(null);
  const [prevTimestamp, setPrevTimestamp] = useState<number | null>(null);

  // Tab selection
  const [selectedTab, setSelectedTab] = useState<ChartTab>(0);

  // Simulated error count for demo (in real app, this would come from backend)
  const [errorCount] = useState(0);
  const [totalProcessed] = useState(0);

  // Fetch telemetry data
  const fetchData = useCallback(async () => {
    try {
      const data = await fetchTelemetry();
      const now = Date.now();

      setTelemetry(data);
      setError(null);

      // Add to latency history
      const timeStr = new Date(data.timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });

      setLatencyHistory((prev) => {
        const newPoint: LatencyHistoryPoint = {
          time: timeStr,
          detect: data.latencies?.detect?.avg_ms ?? null,
          batch: data.latencies?.batch?.avg_ms ?? null,
          analyze: data.latencies?.analyze?.avg_ms ?? null,
        };

        // Keep last 30 data points (2.5 minutes at 5s interval)
        const updated = [...prev, newPoint];
        return updated.slice(-30);
      });

      // Calculate throughput if we have previous data
      if (prevTelemetry && prevTimestamp) {
        const timeDiffMs = now - prevTimestamp;
        const timeDiffMin = timeDiffMs / 60000;

        if (timeDiffMin > 0) {
          // Calculate throughput based on queue changes (rough approximation)
          // In a real implementation, this would come from the backend
          const detectionsPerMin = Math.max(
            0,
            ((prevTelemetry.queues.detection_queue - data.queues.detection_queue) / timeDiffMin) * 60
          );
          const analysesPerMin = Math.max(
            0,
            ((prevTelemetry.queues.analysis_queue - data.queues.analysis_queue) / timeDiffMin) * 60
          );

          setThroughputHistory((prev) => {
            const newPoint: ThroughputPoint = {
              time: timeStr,
              detections: Math.round(detectionsPerMin),
              analyses: Math.round(analysesPerMin),
            };

            // Keep last 30 data points
            const updated = [...prev, newPoint];
            return updated.slice(-30);
          });
        }
      }

      setPrevTelemetry(data);
      setPrevTimestamp(now);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch telemetry');
    } finally {
      setIsLoading(false);
    }
  }, [prevTelemetry, prevTimestamp]);

  // Initial fetch and polling
  useEffect(() => {
    void fetchData();

    const interval = setInterval(() => {
      void fetchData();
    }, pollingInterval);

    return () => clearInterval(interval);
  }, [fetchData, pollingInterval]);

  // Extract values from telemetry
  const detectionQueue = telemetry?.queues.detection_queue ?? 0;
  const analysisQueue = telemetry?.queues.analysis_queue ?? 0;
  const detectLatency = telemetry?.latencies?.detect;
  const batchLatency = telemetry?.latencies?.batch;
  const analyzeLatency = telemetry?.latencies?.analyze;

  // Check for warnings
  const detectionBackingUp = detectionQueue > queueWarningThreshold;
  const analysisBackingUp = analysisQueue > queueWarningThreshold;
  const anyQueueWarning = detectionBackingUp || analysisBackingUp;
  const anyLatencyWarning =
    (detectLatency?.avg_ms ?? 0) > latencyWarningThreshold ||
    (analyzeLatency?.avg_ms ?? 0) > latencyWarningThreshold;

  // Calculate error rate
  const errorRate = totalProcessed > 0 ? (errorCount / totalProcessed) * 100 : 0;

  // Get chart data based on selected tab
  const getChartData = () => {
    switch (selectedTab) {
      case 0:
        return latencyHistory.map((p) => ({
          time: p.time,
          value: p.detect ?? 0,
        }));
      case 1:
        return latencyHistory.map((p) => ({
          time: p.time,
          value: p.analyze ?? 0,
        }));
      case 2:
        return throughputHistory;
      default:
        return [];
    }
  };

  // Get chart color based on tab
  const getChartColor = (): ('emerald' | 'amber' | 'blue')[] => {
    switch (selectedTab) {
      case 0:
        return ['emerald'];
      case 1:
        return ['amber'];
      case 2:
        return ['emerald', 'blue'];
      default:
        return ['emerald'];
    }
  };

  // Get chart categories based on tab
  const getChartCategories = (): string[] => {
    switch (selectedTab) {
      case 0:
      case 1:
        return ['value'];
      case 2:
        return ['detections', 'analyses'];
      default:
        return ['value'];
    }
  };

  // Get value formatter based on tab
  const getValueFormatter = () => {
    switch (selectedTab) {
      case 0:
      case 1:
        return (value: number) => `${value.toFixed(0)}ms`;
      case 2:
        return (value: number) => `${value}/min`;
      default:
        return (value: number) => `${value}`;
    }
  };

  const chartData = getChartData();

  /**
   * Renders a latency stat row
   */
  const renderLatencyRow = (label: string, stage: StageLatency | null | undefined) => (
    <div
      className="flex items-center justify-between rounded-lg bg-gray-800/50 p-3"
      data-testid={`latency-row-${label.toLowerCase().replace(' ', '-')}`}
    >
      <div className="flex flex-col">
        <Text className="text-sm font-medium text-gray-300">{label}</Text>
        <Text className="text-xs text-gray-500">
          {stage?.sample_count ?? 0} samples
        </Text>
      </div>
      <div className="flex items-center gap-3">
        <div className="text-right">
          <Text className="text-xs text-gray-500">avg / p95 / p99</Text>
          <Text className="text-sm font-medium text-white">
            {formatLatency(stage?.avg_ms)} / {formatLatency(stage?.p95_ms)} /{' '}
            {formatLatency(stage?.p99_ms)}
          </Text>
        </div>
        <Badge
          color={getLatencyColor(stage?.avg_ms, latencyWarningThreshold)}
          size="sm"
          data-testid={`latency-badge-${label.toLowerCase().replace(' ', '-')}`}
        >
          {formatLatency(stage?.avg_ms)}
        </Badge>
      </div>
    </div>
  );

  // Loading state
  if (isLoading && !telemetry) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="pipeline-telemetry"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Activity className="h-5 w-5 text-[#76B900]" />
          Pipeline Telemetry
        </Title>
        <div
          className="flex h-64 items-center justify-center text-gray-500"
          data-testid="telemetry-loading"
        >
          <Text>Loading telemetry...</Text>
        </div>
      </Card>
    );
  }

  // Error state
  if (error && !telemetry) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="pipeline-telemetry"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Activity className="h-5 w-5 text-[#76B900]" />
          Pipeline Telemetry
        </Title>
        <div
          className="flex h-64 items-center justify-center text-red-400"
          data-testid="telemetry-error"
        >
          <Text>{error}</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="pipeline-telemetry"
    >
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Activity className="h-5 w-5 text-[#76B900]" />
        Pipeline Telemetry
        {(anyQueueWarning || anyLatencyWarning) && (
          <AlertTriangle
            className="h-5 w-5 animate-pulse text-yellow-500"
            data-testid="telemetry-warning-icon"
            aria-label="Pipeline warning"
          />
        )}
      </Title>

      <div className="space-y-6">
        {/* Queue Depths Section */}
        <div>
          <div className="mb-3 flex items-center gap-2">
            <Layers className="h-4 w-4 text-[#76B900]" />
            <Text className="text-sm font-medium text-gray-300">Queue Depths</Text>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div
              className={clsx(
                'flex flex-col items-center rounded-lg p-4',
                detectionBackingUp
                  ? 'border border-red-500/30 bg-red-500/10'
                  : 'bg-gray-800/50'
              )}
              data-testid="detection-queue-card"
            >
              <Text className="mb-1 text-xs text-gray-500">Detection</Text>
              <Badge
                color={getQueueBadgeColor(detectionQueue, queueWarningThreshold)}
                size="lg"
                data-testid="detection-queue-depth"
              >
                {detectionQueue}
              </Badge>
              {detectionBackingUp && (
                <AlertTriangle
                  className="mt-1 h-4 w-4 text-red-500"
                  data-testid="detection-queue-warning"
                />
              )}
            </div>
            <div
              className={clsx(
                'flex flex-col items-center rounded-lg p-4',
                analysisBackingUp
                  ? 'border border-red-500/30 bg-red-500/10'
                  : 'bg-gray-800/50'
              )}
              data-testid="analysis-queue-card"
            >
              <Text className="mb-1 text-xs text-gray-500">Analysis</Text>
              <Badge
                color={getQueueBadgeColor(analysisQueue, queueWarningThreshold)}
                size="lg"
                data-testid="analysis-queue-depth"
              >
                {analysisQueue}
              </Badge>
              {analysisBackingUp && (
                <AlertTriangle
                  className="mt-1 h-4 w-4 text-red-500"
                  data-testid="analysis-queue-warning"
                />
              )}
            </div>
          </div>
        </div>

        {/* Processing Latency Section */}
        <div>
          <div className="mb-3 flex items-center gap-2">
            <Clock className="h-4 w-4 text-[#76B900]" />
            <Text className="text-sm font-medium text-gray-300">Processing Latency</Text>
          </div>
          <div className="space-y-2">
            {renderLatencyRow('Detection', detectLatency)}
            {renderLatencyRow('Batch Agg', batchLatency)}
            {renderLatencyRow('Analysis', analyzeLatency)}
          </div>
        </div>

        {/* Throughput & Error Rate Section */}
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-lg bg-gray-800/50 p-4">
            <div className="mb-2 flex items-center gap-2">
              <Zap className="h-4 w-4 text-[#76B900]" />
              <Text className="text-xs text-gray-500">Throughput</Text>
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <Text className="text-xs text-gray-400">Detections</Text>
                <Text
                  className="text-sm font-medium text-white"
                  data-testid="detections-throughput"
                >
                  {throughputHistory.length > 0
                    ? `${throughputHistory[throughputHistory.length - 1].detections}/min`
                    : 'N/A'}
                </Text>
              </div>
              <div className="flex items-center justify-between">
                <Text className="text-xs text-gray-400">Analyses</Text>
                <Text
                  className="text-sm font-medium text-white"
                  data-testid="analyses-throughput"
                >
                  {throughputHistory.length > 0
                    ? `${throughputHistory[throughputHistory.length - 1].analyses}/min`
                    : 'N/A'}
                </Text>
              </div>
            </div>
          </div>
          <div className="rounded-lg bg-gray-800/50 p-4">
            <div className="mb-2 flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-[#76B900]" />
              <Text className="text-xs text-gray-500">Error Rate</Text>
            </div>
            <div className="flex items-center justify-center">
              <Badge
                color={getErrorRateColor(errorRate)}
                size="lg"
                data-testid="error-rate-badge"
              >
                {errorRate.toFixed(1)}%
              </Badge>
            </div>
          </div>
        </div>

        {/* Metrics Chart */}
        <div className="border-t border-gray-800 pt-4">
          <div className="mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-[#76B900]" />
            <Text className="text-sm font-medium text-gray-300">Metrics History</Text>
          </div>

          <TabGroup
            index={selectedTab}
            onIndexChange={(index) => setSelectedTab(index as ChartTab)}
            className="mb-3"
          >
            <TabList variant="solid" className="bg-gray-800/50">
              <Tab className="text-xs" data-testid="tab-detection-latency">
                Detection
              </Tab>
              <Tab className="text-xs" data-testid="tab-analysis-latency">
                Analysis
              </Tab>
              <Tab className="text-xs" data-testid="tab-throughput">
                Throughput
              </Tab>
            </TabList>
          </TabGroup>

          {chartData.length > 0 ? (
            <AreaChart
              className="h-32"
              data={chartData}
              index="time"
              categories={getChartCategories()}
              colors={getChartColor()}
              valueFormatter={getValueFormatter()}
              showLegend={selectedTab === 2}
              showGridLines={false}
              curveType="monotone"
              data-testid="telemetry-chart"
            />
          ) : (
            <div
              className="flex h-32 items-center justify-center text-gray-500"
              data-testid="telemetry-chart-empty"
            >
              <Text>Collecting data...</Text>
            </div>
          )}

          {/* Data point count */}
          {chartData.length > 0 && (
            <div className="mt-2 text-right">
              <span className="text-xs text-gray-500" data-testid="telemetry-data-count">
                {chartData.length} data point{chartData.length !== 1 ? 's' : ''}
              </span>
            </div>
          )}
        </div>

        {/* Timestamp */}
        {telemetry && (
          <div className="border-t border-gray-800 pt-2 text-right">
            <Text className="text-xs text-gray-500" data-testid="telemetry-timestamp">
              Updated: {new Date(telemetry.timestamp).toLocaleTimeString()}
            </Text>
          </div>
        )}
      </div>
    </Card>
  );
}
