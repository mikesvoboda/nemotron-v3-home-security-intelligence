import { Clock, TrendingUp, AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { useState, useEffect, useCallback, useMemo } from 'react';

import {
  fetchPipelineLatency,
  fetchPipelineLatencyHistory,
  type PipelineLatencyResponse,
  type PipelineLatencyHistoryResponse,
  type PipelineStageLatency,
} from '../../services/api';

interface PipelineLatencyPanelProps {
  /** Auto-refresh interval in milliseconds (0 to disable) */
  refreshInterval?: number;
}

// Stage display names and colors
const STAGE_CONFIG: Record<string, { label: string; color: string; shortLabel: string }> = {
  watch_to_detect: {
    label: 'File Watcher → RT-DETR',
    shortLabel: 'Watch→Detect',
    color: '#76B900',
  },
  detect_to_batch: {
    label: 'RT-DETR → Batch Aggregator',
    shortLabel: 'Detect→Batch',
    color: '#F59E0B',
  },
  batch_to_analyze: {
    label: 'Batch Aggregator → Nemotron',
    shortLabel: 'Batch→Analyze',
    color: '#8B5CF6',
  },
  total_pipeline: {
    label: 'Total End-to-End',
    shortLabel: 'Total',
    color: '#3B82F6',
  },
};

// Time range options
type TimeRange = {
  label: string;
  value: number;
  bucketSeconds: number;
};

const TIME_RANGES: TimeRange[] = [
  { label: '1 hour', value: 60, bucketSeconds: 60 },
  { label: '6 hours', value: 360, bucketSeconds: 300 },
  { label: '24 hours', value: 1440, bucketSeconds: 900 },
];

/**
 * PipelineLatencyPanel displays pipeline processing latency breakdown.
 *
 * Shows:
 * - Latency breakdown by pipeline stage (file_watcher → rtdetr → nemotron → database)
 * - Timing percentiles (p50, p95, p99)
 * - Historical trend over time (last 24h, 7d, 30d)
 * - Highlights bottlenecks (stages with highest latency)
 */
export default function PipelineLatencyPanel({ refreshInterval = 0 }: PipelineLatencyPanelProps) {
  // State
  const [latencyData, setLatencyData] = useState<PipelineLatencyResponse | null>(null);
  const [historyData, setHistoryData] = useState<PipelineLatencyHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedTimeRange, setSelectedTimeRange] = useState(TIME_RANGES[0]);

  // Load data
  const loadData = useCallback(async () => {
    try {
      const [latency, history] = await Promise.all([
        fetchPipelineLatency(selectedTimeRange.value),
        fetchPipelineLatencyHistory(selectedTimeRange.value, selectedTimeRange.bucketSeconds),
      ]);

      setLatencyData(latency);
      setHistoryData(history);
      setError(null);
    } catch (err) {
      setError('Failed to load pipeline latency data');
      console.error('Failed to load pipeline latency:', err);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [selectedTimeRange]);

  // Initial load and refresh interval
  useEffect(() => {
    void loadData();

    if (refreshInterval > 0) {
      const interval = setInterval(() => {
        void loadData();
      }, refreshInterval);

      return () => clearInterval(interval);
    }
  }, [loadData, refreshInterval]);

  // Handle manual refresh
  const handleRefresh = useCallback(async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    await loadData();
  }, [isRefreshing, loadData]);

  // Find bottleneck stage (highest p95 latency)
  const bottleneckStage = useMemo(() => {
    if (!latencyData) return null;

    let maxP95 = 0;
    let maxStage = '';

    const stages: Array<[string, PipelineStageLatency | null | undefined]> = [
      ['watch_to_detect', latencyData.watch_to_detect],
      ['detect_to_batch', latencyData.detect_to_batch],
      ['batch_to_analyze', latencyData.batch_to_analyze],
    ];

    stages.forEach(([key, value]) => {
      if (value && typeof value === 'object' && 'p95_ms' in value) {
        const p95 = value.p95_ms ?? 0;
        if (p95 > maxP95) {
          maxP95 = p95;
          maxStage = key;
        }
      }
    });

    return maxStage || null;
  }, [latencyData]);

  // Calculate percentage of total for each stage
  const calculatePercentage = useCallback(
    (stageLatency: PipelineStageLatency | null | undefined): number => {
      if (!stageLatency?.avg_ms || !latencyData?.total_pipeline?.avg_ms) return 0;
      return (stageLatency.avg_ms / latencyData.total_pipeline.avg_ms) * 100;
    },
    [latencyData]
  );

  // Format latency in ms
  const formatLatency = (ms: number | null | undefined): string => {
    if (ms === null || ms === undefined) return 'N/A';
    if (ms < 1) return '<1ms';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  // Render stage bar
  const renderStageBar = (stageKey: string, stageData: PipelineStageLatency | null | undefined) => {
    if (!stageData) return null;

    const config = STAGE_CONFIG[stageKey];
    if (!config) return null;

    const percentage = calculatePercentage(stageData);
    const isBottleneck = stageKey === bottleneckStage;

    return (
      <div key={stageKey} className="group" data-testid={`stage-bar-${stageKey}`}>
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-sm" style={{ backgroundColor: config.color }} />
            <span className="text-sm font-medium text-gray-300">{config.label}</span>
            {isBottleneck && (
              <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs text-red-400">
                Bottleneck
              </span>
            )}
          </div>
          <span className="text-sm text-gray-500">{percentage.toFixed(1)}% of total</span>
        </div>

        {/* Bar chart */}
        <div className="mb-2 h-8 overflow-hidden rounded bg-gray-800">
          <div
            className="h-full transition-all duration-300 group-hover:brightness-110"
            style={{
              width: `${percentage}%`,
              backgroundColor: config.color,
            }}
          />
        </div>

        {/* Stats */}
        <div className="grid grid-cols-5 gap-2 text-xs">
          <div>
            <span className="text-gray-500">Avg:</span>
            <span className="ml-1 text-white">{formatLatency(stageData.avg_ms)}</span>
          </div>
          <div>
            <span className="text-gray-500">P50:</span>
            <span className="ml-1 text-white">{formatLatency(stageData.p50_ms)}</span>
          </div>
          <div>
            <span className="text-gray-500">P95:</span>
            <span className="ml-1 text-white">{formatLatency(stageData.p95_ms)}</span>
          </div>
          <div>
            <span className="text-gray-500">P99:</span>
            <span className="ml-1 text-white">{formatLatency(stageData.p99_ms)}</span>
          </div>
          <div>
            <span className="text-gray-500">Samples:</span>
            <span className="ml-1 text-white">{stageData.sample_count ?? 0}</span>
          </div>
        </div>
      </div>
    );
  };

  // Render historical trend chart (simple sparkline-style)
  const renderTrendChart = () => {
    if (!historyData || historyData.snapshots.length === 0) {
      return (
        <div className="flex h-48 items-center justify-center text-gray-400">
          No historical data available yet
        </div>
      );
    }

    const maxP95 = Math.max(
      ...historyData.snapshots.flatMap((snapshot) =>
        Object.values(snapshot.stages)
          .filter(
            (stage): stage is NonNullable<typeof stage> =>
              stage !== null && stage !== undefined && typeof stage === 'object'
          )
          .map((stage) => ('p95_ms' in stage ? (stage.p95_ms ?? 0) : 0))
      ),
      1
    );

    return (
      <div className="space-y-4">
        {Object.entries(STAGE_CONFIG).map(([stageKey, config]) => {
          const stageData = historyData.snapshots.map((snapshot) => {
            const stage = snapshot.stages[stageKey];
            return {
              timestamp: snapshot.timestamp,
              p95:
                stage && typeof stage === 'object' && 'p95_ms' in stage
                  ? (stage.p95_ms ?? null)
                  : null,
            };
          });

          const hasData = stageData.some((d) => d.p95 !== null);
          if (!hasData) return null;

          return (
            <div key={stageKey} data-testid={`trend-${stageKey}`}>
              <div className="mb-1 flex items-center gap-2 text-sm">
                <div className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: config.color }} />
                <span className="text-gray-300">{config.shortLabel}</span>
              </div>
              <div className="flex h-12 items-end gap-0.5">
                {stageData.map((point, idx) => {
                  const height = point.p95 ? (point.p95 / maxP95) * 100 : 0;
                  return (
                    <div
                      key={idx}
                      className="flex-1 rounded-t transition-all hover:brightness-110"
                      style={{
                        height: `${height}%`,
                        backgroundColor: config.color,
                        minHeight: height > 0 ? '2px' : '0',
                      }}
                      title={`${new Date(point.timestamp).toLocaleTimeString()}: ${formatLatency(point.p95)}`}
                    />
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6">
      {/* Header */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Clock className="h-6 w-6 text-[#76B900]" />
          <div>
            <h3 className="text-lg font-semibold text-white">Pipeline Latency Breakdown</h3>
            <p className="text-sm text-gray-400">Processing time by pipeline stage</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Time range selector */}
          <select
            value={selectedTimeRange.value}
            onChange={(e) => {
              const range = TIME_RANGES.find((r) => r.value === Number(e.target.value));
              if (range) setSelectedTimeRange(range);
            }}
            className="rounded border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-[#76B900] focus:outline-none"
            data-testid="time-range-selector"
          >
            {TIME_RANGES.map((range) => (
              <option key={range.value} value={range.value}>
                {range.label}
              </option>
            ))}
          </select>

          {/* Refresh button */}
          <button
            onClick={() => void handleRefresh()}
            disabled={isRefreshing}
            className="flex items-center gap-2 rounded border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-300 transition-colors hover:bg-gray-700 disabled:opacity-50"
            data-testid="pipeline-latency-refresh-button"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="mb-6 flex items-center gap-2 rounded bg-red-500/10 px-4 py-3 text-red-400">
          <AlertCircle className="h-5 w-5" />
          {error}
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
          <span className="ml-3 text-gray-400">Loading latency data...</span>
        </div>
      )}

      {/* Content */}
      {!isLoading && !error && latencyData && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Stage Breakdown */}
          <div>
            <div className="mb-4 flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-gray-400" />
              <h4 className="font-semibold text-white">Stage Breakdown</h4>
            </div>
            <div className="space-y-6">
              {renderStageBar('watch_to_detect', latencyData.watch_to_detect)}
              {renderStageBar('detect_to_batch', latencyData.detect_to_batch)}
              {renderStageBar('batch_to_analyze', latencyData.batch_to_analyze)}
              {latencyData.total_pipeline && (
                <div className="border-t border-gray-700 pt-4">
                  {renderStageBar('total_pipeline', latencyData.total_pipeline)}
                </div>
              )}
            </div>
          </div>

          {/* Historical Trend */}
          <div>
            <div className="mb-4 flex items-center gap-2">
              <Clock className="h-5 w-5 text-gray-400" />
              <h4 className="font-semibold text-white">Historical Trend (P95)</h4>
            </div>
            {renderTrendChart()}
          </div>
        </div>
      )}

      {/* No Data State */}
      {!isLoading && !error && !latencyData && (
        <div className="flex h-48 items-center justify-center text-gray-400">
          No pipeline latency data available yet
        </div>
      )}
    </div>
  );
}
