/**
 * PipelineLatencyHistoryPanel - Historical pipeline latency metrics chart
 *
 * Displays latency for each pipeline stage (watch_to_detect, detect_to_batch,
 * batch_to_analyze, total_pipeline) over time using Tremor's AreaChart.
 * Supports two views: Stage Averages and Percentiles (P50/P95/P99).
 */

import { Card, Title, Text, AreaChart } from '@tremor/react';
import { AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { useMemo, useState } from 'react';

import { usePipelineLatencyHistory } from '../../hooks/usePipelineLatencyHistory';

import type { PipelinePercentileChartDataPoint } from '../../hooks/usePipelineLatencyHistory';

/**
 * View mode for the chart display.
 */
export type LatencyViewMode = 'stages' | 'percentiles';

/**
 * Props for PipelineLatencyHistoryPanel component.
 */
export interface PipelineLatencyHistoryPanelProps {
  /** Time window in minutes (default: 60) */
  since?: number;
  /** Bucket size in seconds (default: 60) */
  bucketSeconds?: number;
  /** Initial view mode (default: 'stages') */
  initialViewMode?: LatencyViewMode;
  /** Additional CSS classes */
  className?: string;
  /** Test ID for testing */
  'data-testid'?: string;
}

/**
 * Chart data point format for Tremor AreaChart (stages view).
 */
interface StageChartDataPoint {
  time: string;
  'Watch to Detect': number;
  'Detect to Batch': number;
  'Batch to Analyze': number;
  'Total Pipeline': number;
}

/**
 * Chart data point format for Tremor AreaChart (percentiles view).
 */
interface PercentileChartDataPoint {
  time: string;
  P50: number;
  P95: number;
  P99: number;
}

/**
 * Transform API data to stage chart format.
 */
function transformStageChartData(
  chartData: ReturnType<typeof usePipelineLatencyHistory>['chartData']
): StageChartDataPoint[] {
  if (!chartData) return [];

  return chartData.map((point) => ({
    time: point.timestamp,
    'Watch to Detect': Math.round(point.watch_to_detect),
    'Detect to Batch': Math.round(point.detect_to_batch),
    'Batch to Analyze': Math.round(point.batch_to_analyze),
    'Total Pipeline': Math.round(point.total_pipeline),
  }));
}

/**
 * Transform API data to percentile chart format.
 */
function transformPercentileChartData(
  percentileData: PipelinePercentileChartDataPoint[] | undefined
): PercentileChartDataPoint[] {
  if (!percentileData) return [];

  return percentileData.map((point) => ({
    time: point.timestamp,
    P50: Math.round(point.P50),
    P95: Math.round(point.P95),
    P99: Math.round(point.P99),
  }));
}

/**
 * View mode toggle button component.
 */
function ViewModeToggle({
  viewMode,
  onViewModeChange,
  testId,
}: {
  viewMode: LatencyViewMode;
  onViewModeChange: (mode: LatencyViewMode) => void;
  testId: string;
}) {
  return (
    <div
      className="flex rounded-md bg-gray-800 p-0.5"
      data-testid={`${testId}-view-toggle`}
    >
      <button
        className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
          viewMode === 'stages'
            ? 'bg-[#76B900] text-black'
            : 'text-gray-400 hover:text-white'
        }`}
        onClick={() => onViewModeChange('stages')}
        data-testid={`${testId}-view-stages`}
        aria-pressed={viewMode === 'stages'}
      >
        Stages
      </button>
      <button
        className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
          viewMode === 'percentiles'
            ? 'bg-[#76B900] text-black'
            : 'text-gray-400 hover:text-white'
        }`}
        onClick={() => onViewModeChange('percentiles')}
        data-testid={`${testId}-view-percentiles`}
        aria-pressed={viewMode === 'percentiles'}
      >
        Percentiles
      </button>
    </div>
  );
}

/**
 * PipelineLatencyHistoryPanel - Displays historical pipeline latency metrics
 *
 * Shows latency for each pipeline stage over time:
 * - Watch to Detect: Time from file watch to detection start
 * - Detect to Batch: Time from detection to batching
 * - Batch to Analyze: Time from batching to analysis
 * - Total Pipeline: End-to-end latency
 *
 * Also supports Percentiles view showing P50/P95/P99 for total pipeline latency.
 *
 * @example
 * ```tsx
 * <PipelineLatencyHistoryPanel
 *   since={60}
 *   bucketSeconds={60}
 *   initialViewMode="stages"
 *   data-testid="pipeline-latency-history"
 * />
 * ```
 */
export default function PipelineLatencyHistoryPanel({
  since = 60,
  bucketSeconds = 60,
  initialViewMode = 'stages',
  className,
  'data-testid': testId = 'pipeline-latency-history-panel',
}: PipelineLatencyHistoryPanelProps) {
  const [viewMode, setViewMode] = useState<LatencyViewMode>(initialViewMode);

  const { chartData, percentileChartData, isLoading, error, refetch, data } = usePipelineLatencyHistory({
    since,
    bucket_seconds: bucketSeconds,
  });

  // Transform data for stage chart
  const stageData: StageChartDataPoint[] = useMemo(
    () => transformStageChartData(chartData),
    [chartData]
  );

  // Transform data for percentile chart
  const percentileData: PercentileChartDataPoint[] = useMemo(
    () => transformPercentileChartData(percentileChartData),
    [percentileChartData]
  );

  // Loading state
  if (isLoading && !data) {
    return (
      <Card
        className={className}
        data-testid={testId}
      >
        <Title className="mb-4 text-white">Pipeline Latency History</Title>
        <div
          className="flex h-48 items-center justify-center"
          data-testid={`${testId}-loading`}
        >
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card
        className={className}
        data-testid={testId}
      >
        <Title className="mb-4 text-white">Pipeline Latency History</Title>
        <div
          className="flex h-48 flex-col items-center justify-center text-red-400"
          data-testid={`${testId}-error`}
        >
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text className="mb-2">Failed to load pipeline latency history</Text>
          <button
            onClick={refetch}
            className="flex items-center gap-2 rounded-md bg-red-500/10 px-4 py-2 text-sm text-red-400 hover:bg-red-500/20 transition-colors"
            data-testid={`${testId}-retry`}
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      </Card>
    );
  }

  // Empty state
  if (stageData.length === 0) {
    return (
      <Card
        className={className}
        data-testid={testId}
      >
        <Title className="mb-4 text-white">Pipeline Latency History</Title>
        <div
          className="flex h-48 flex-col items-center justify-center text-gray-400"
          data-testid={`${testId}-empty`}
        >
          <Text>No pipeline latency data available</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className={className}
      data-testid={testId}
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <Title className="text-white">Pipeline Latency History</Title>
          <Text className="text-gray-400 text-xs">
            Last {data?.window_minutes ?? since} minutes, {data?.bucket_seconds ?? bucketSeconds}s buckets
          </Text>
        </div>
        <div className="flex items-center gap-3">
          {isLoading && (
            <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
          )}
          <ViewModeToggle
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            testId={testId}
          />
        </div>
      </div>

      {viewMode === 'stages' ? (
        <AreaChart
          className="h-48"
          data={stageData}
          index="time"
          categories={['Watch to Detect', 'Detect to Batch', 'Batch to Analyze', 'Total Pipeline']}
          colors={['emerald', 'blue', 'amber', 'violet']}
          showLegend={true}
          showGridLines={false}
          curveType="monotone"
          valueFormatter={(value) => `${value}ms`}
          data-testid={`${testId}-chart-stages`}
          aria-label="Pipeline latency history chart showing stage averages"
        />
      ) : (
        <AreaChart
          className="h-48"
          data={percentileData}
          index="time"
          categories={['P50', 'P95', 'P99']}
          colors={['emerald', 'amber', 'rose']}
          showLegend={true}
          showGridLines={false}
          curveType="monotone"
          valueFormatter={(value) => `${value}ms`}
          data-testid={`${testId}-chart-percentiles`}
          aria-label="Pipeline latency history chart showing P50, P95, and P99 percentiles"
        />
      )}
    </Card>
  );
}
