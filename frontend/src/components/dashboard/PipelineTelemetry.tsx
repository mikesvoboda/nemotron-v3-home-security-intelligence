import { Card, Title, Text, Badge, BarList, TabGroup, TabList, Tab, TabPanels, TabPanel } from '@tremor/react';
import { clsx } from 'clsx';
import { Activity, Clock, Zap, TrendingUp, AlertTriangle, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { fetchPipelineLatency, fetchTelemetry } from '../../services/api';

import type { PipelineLatencyResponse, PipelineStageLatency, TelemetryResponse } from '../../services/api';

export interface PipelineTelemetryProps {
  /** Window in minutes for latency statistics (default: 60) */
  windowMinutes?: number;
  /** Polling interval in milliseconds (default: 30000, 0 to disable) */
  pollingInterval?: number;
  /** Additional CSS classes */
  className?: string;
}

/** Stage configuration for display */
interface StageConfig {
  key: string;
  label: string;
  description: string;
  icon: React.ReactNode;
}

const STAGE_CONFIGS: StageConfig[] = [
  {
    key: 'watch_to_detect',
    label: 'File to Detection',
    description: 'Time from file watcher to RT-DETR',
    icon: <Activity className="h-4 w-4" />,
  },
  {
    key: 'detect_to_batch',
    label: 'Detection to Batch',
    description: 'Time from detection to batch aggregation',
    icon: <Zap className="h-4 w-4" />,
  },
  {
    key: 'batch_to_analyze',
    label: 'Batch to Analysis',
    description: 'Time from batch to Nemotron LLM',
    icon: <TrendingUp className="h-4 w-4" />,
  },
  {
    key: 'total_pipeline',
    label: 'End-to-End',
    description: 'Total pipeline processing time',
    icon: <Clock className="h-4 w-4" />,
  },
];

/**
 * Format milliseconds to human-readable string
 */
function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return 'N/A';
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

/**
 * Get color for latency value based on thresholds
 */
function getLatencyColor(ms: number | null | undefined, stage: string): 'gray' | 'green' | 'yellow' | 'red' {
  if (ms === null || ms === undefined) return 'gray';

  // Different thresholds for different stages
  const thresholds: Record<string, { warn: number; critical: number }> = {
    watch_to_detect: { warn: 100, critical: 500 },
    detect_to_batch: { warn: 500, critical: 2000 },
    batch_to_analyze: { warn: 10000, critical: 30000 },
    total_pipeline: { warn: 30000, critical: 90000 },
  };

  const threshold = thresholds[stage] || { warn: 1000, critical: 5000 };

  if (ms < threshold.warn) return 'green';
  if (ms < threshold.critical) return 'yellow';
  return 'red';
}

/**
 * StageLatencyCard displays latency stats for a single pipeline stage
 */
function StageLatencyCard({
  config,
  latency,
}: {
  config: StageConfig;
  latency: PipelineStageLatency | null | undefined;
}) {
  const avgColor = getLatencyColor(latency?.avg_ms, config.key);
  const p95Color = getLatencyColor(latency?.p95_ms, config.key);

  const barData = latency ? [
    { name: 'Min', value: latency.min_ms ?? 0 },
    { name: 'P50', value: latency.p50_ms ?? 0 },
    { name: 'Avg', value: latency.avg_ms ?? 0 },
    { name: 'P95', value: latency.p95_ms ?? 0 },
    { name: 'P99', value: latency.p99_ms ?? 0 },
    { name: 'Max', value: latency.max_ms ?? 0 },
  ] : [];

  return (
    <div
      className="rounded-lg border border-gray-800 bg-gray-900/50 p-4"
      data-testid={`stage-card-${config.key}`}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[#76B900]">{config.icon}</span>
          <div>
            <Text className="font-medium text-white">{config.label}</Text>
            <Text className="text-xs text-gray-500">{config.description}</Text>
          </div>
        </div>
        {latency && (
          <Badge color={avgColor} size="sm">
            avg {formatLatency(latency.avg_ms)}
          </Badge>
        )}
      </div>

      {latency ? (
        <>
          <div className="mb-3 grid grid-cols-3 gap-2 text-center">
            <div className="rounded bg-gray-800/50 p-2">
              <Text className="text-xs text-gray-500">P50</Text>
              <Text className="text-sm font-semibold text-white">
                {formatLatency(latency.p50_ms)}
              </Text>
            </div>
            <div className="rounded bg-gray-800/50 p-2">
              <Text className="text-xs text-gray-500">P95</Text>
              <Text className={clsx(
                'text-sm font-semibold',
                p95Color === 'green' && 'text-green-400',
                p95Color === 'yellow' && 'text-yellow-400',
                p95Color === 'red' && 'text-red-400',
                p95Color === 'gray' && 'text-gray-400'
              )}>
                {formatLatency(latency.p95_ms)}
              </Text>
            </div>
            <div className="rounded bg-gray-800/50 p-2">
              <Text className="text-xs text-gray-500">P99</Text>
              <Text className="text-sm font-semibold text-white">
                {formatLatency(latency.p99_ms)}
              </Text>
            </div>
          </div>

          <div className="space-y-1">
            <BarList
              data={barData}
              valueFormatter={(v: number) => formatLatency(v)}
              color="emerald"
              className="text-xs"
            />
          </div>

          <div className="mt-2 text-right">
            <Text className="text-xs text-gray-500">
              {latency.sample_count} samples
            </Text>
          </div>
        </>
      ) : (
        <div className="flex h-24 items-center justify-center">
          <Text className="text-gray-500">No data available</Text>
        </div>
      )}
    </div>
  );
}

/**
 * QueueDepthsDisplay shows current queue depths
 */
function QueueDepthsDisplay({
  telemetry,
}: {
  telemetry: TelemetryResponse | null;
}) {
  const detectionDepth = telemetry?.queues?.detection_queue ?? 0;
  const analysisDepth = telemetry?.queues?.analysis_queue ?? 0;

  const getDepthColor = (depth: number): 'gray' | 'green' | 'yellow' | 'red' => {
    if (depth === 0) return 'gray';
    if (depth <= 5) return 'green';
    if (depth <= 10) return 'yellow';
    return 'red';
  };

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4" data-testid="detection-queue-depth">
        <div className="flex items-center justify-between">
          <div>
            <Text className="text-sm text-gray-400">Detection Queue</Text>
            <Text className="text-xs text-gray-600">RT-DETR processing</Text>
          </div>
          <Badge color={getDepthColor(detectionDepth)} size="lg">
            {detectionDepth}
          </Badge>
        </div>
      </div>

      <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4" data-testid="analysis-queue-depth">
        <div className="flex items-center justify-between">
          <div>
            <Text className="text-sm text-gray-400">Analysis Queue</Text>
            <Text className="text-xs text-gray-600">Nemotron LLM</Text>
          </div>
          <Badge color={getDepthColor(analysisDepth)} size="lg">
            {analysisDepth}
          </Badge>
        </div>
      </div>
    </div>
  );
}

/**
 * PipelineTelemetry displays rich pipeline telemetry including:
 * - Queue depths for detection and analysis queues
 * - Stage latencies with detailed percentiles (avg, min, max, p50, p95, p99)
 * - Sample counts for data quality indication
 */
export default function PipelineTelemetry({
  windowMinutes = 60,
  pollingInterval = 30000,
  className,
}: PipelineTelemetryProps) {
  const [latencyData, setLatencyData] = useState<PipelineLatencyResponse | null>(null);
  const [telemetryData, setTelemetryData] = useState<TelemetryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [latency, telemetry] = await Promise.all([
        fetchPipelineLatency(windowMinutes),
        fetchTelemetry(),
      ]);
      setLatencyData(latency);
      setTelemetryData(telemetry);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch telemetry');
    } finally {
      setLoading(false);
    }
  }, [windowMinutes]);

  // Initial fetch and polling
  useEffect(() => {
    void fetchData();

    if (pollingInterval > 0) {
      const intervalId = setInterval(() => {
        void fetchData();
      }, pollingInterval);

      return () => clearInterval(intervalId);
    }
  }, [fetchData, pollingInterval]);

  const handleRefresh = () => {
    setLoading(true);
    void fetchData();
  };

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="pipeline-telemetry"
    >
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Activity className="h-5 w-5 text-[#76B900]" />
          Pipeline Telemetry
        </Title>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <Text className="text-xs text-gray-500">
              Updated {lastUpdated.toLocaleTimeString()}
            </Text>
          )}
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-400 transition-colors hover:bg-gray-800 hover:text-white disabled:opacity-50"
            aria-label="Refresh telemetry"
          >
            <RefreshCw className={clsx('h-3 w-3', loading && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {error ? (
        <div
          className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4"
          role="alert"
          data-testid="telemetry-error"
        >
          <AlertTriangle className="h-5 w-5 text-red-500" />
          <Text className="text-red-400">{error}</Text>
        </div>
      ) : loading && !latencyData ? (
        <div className="flex h-48 items-center justify-center" data-testid="telemetry-loading">
          <div className="text-center">
            <div className="mx-auto mb-2 h-8 w-8 animate-spin rounded-full border-2 border-gray-700 border-t-[#76B900]" />
            <Text className="text-gray-500">Loading telemetry...</Text>
          </div>
        </div>
      ) : (
        <TabGroup>
          <TabList variant="solid" className="mb-4 bg-gray-800/50">
            <Tab className="text-sm">Queue Depths</Tab>
            <Tab className="text-sm">Stage Latencies</Tab>
          </TabList>

          <TabPanels>
            {/* Queue Depths Tab */}
            <TabPanel>
              <QueueDepthsDisplay telemetry={telemetryData} />

              {/* Basic stage latencies inline */}
              {telemetryData?.latencies && (
                <div className="mt-4">
                  <Text className="mb-2 text-sm font-medium text-gray-400">
                    Stage Latencies (Simple View)
                  </Text>
                  <div className="space-y-2">
                    {['watch', 'detect', 'batch', 'analyze'].map((stage) => {
                      const latency = telemetryData.latencies?.[stage as keyof typeof telemetryData.latencies];
                      return (
                        <div
                          key={stage}
                          className="flex items-center justify-between rounded bg-gray-800/30 px-3 py-2"
                        >
                          <Text className="text-sm capitalize text-gray-300">{stage}</Text>
                          <Text className="text-sm font-medium text-white">
                            {latency?.avg_ms ? formatLatency(latency.avg_ms) : 'N/A'}
                          </Text>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </TabPanel>

            {/* Stage Latencies Tab (Detailed) */}
            <TabPanel>
              <div className="mb-3 flex items-center justify-between">
                <Text className="text-sm text-gray-400">
                  Statistics from last {windowMinutes} minutes
                </Text>
                {latencyData?.timestamp && (
                  <Text className="text-xs text-gray-500">
                    Snapshot: {new Date(latencyData.timestamp).toLocaleString()}
                  </Text>
                )}
              </div>

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {STAGE_CONFIGS.map((config) => (
                  <StageLatencyCard
                    key={config.key}
                    config={config}
                    latency={
                      latencyData?.[config.key as keyof PipelineLatencyResponse] as
                        | PipelineStageLatency
                        | null
                        | undefined
                    }
                  />
                ))}
              </div>
            </TabPanel>
          </TabPanels>
        </TabGroup>
      )}
    </Card>
  );
}
