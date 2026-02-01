/**
 * PipelineLatencyHistoryPanel - Historical pipeline latency metrics chart
 *
 * Displays latency for each pipeline stage (watch_to_detect, detect_to_batch,
 * batch_to_analyze, total_pipeline) over time using Tremor's AreaChart.
 */

import { Card, Title, Text, AreaChart } from '@tremor/react';
import { AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { useMemo } from 'react';

import { usePipelineLatencyHistory } from '../../hooks/usePipelineLatencyHistory';

/**
 * Props for PipelineLatencyHistoryPanel component.
 */
export interface PipelineLatencyHistoryPanelProps {
  /** Time window in minutes (default: 60) */
  since?: number;
  /** Bucket size in seconds (default: 60) */
  bucketSeconds?: number;
  /** Additional CSS classes */
  className?: string;
  /** Test ID for testing */
  'data-testid'?: string;
}

/**
 * Chart data point format for Tremor AreaChart.
 */
interface ChartDataPoint {
  time: string;
  'Watch to Detect': number;
  'Detect to Batch': number;
  'Batch to Analyze': number;
  'Total Pipeline': number;
}

/**
 * Transform API data to chart format.
 */
function transformChartData(
  chartData: ReturnType<typeof usePipelineLatencyHistory>['chartData']
): ChartDataPoint[] {
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
 * PipelineLatencyHistoryPanel - Displays historical pipeline latency metrics
 *
 * Shows latency for each pipeline stage over time:
 * - Watch to Detect: Time from file watch to detection start
 * - Detect to Batch: Time from detection to batching
 * - Batch to Analyze: Time from batching to analysis
 * - Total Pipeline: End-to-end latency
 *
 * @example
 * ```tsx
 * <PipelineLatencyHistoryPanel
 *   since={60}
 *   bucketSeconds={60}
 *   data-testid="pipeline-latency-history"
 * />
 * ```
 */
export default function PipelineLatencyHistoryPanel({
  since = 60,
  bucketSeconds = 60,
  className,
  'data-testid': testId = 'pipeline-latency-history-panel',
}: PipelineLatencyHistoryPanelProps) {
  const { chartData, isLoading, error, refetch, data } = usePipelineLatencyHistory({
    since,
    bucket_seconds: bucketSeconds,
  });

  // Transform data for chart
  const transformedData: ChartDataPoint[] = useMemo(
    () => transformChartData(chartData),
    [chartData]
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
  if (transformedData.length === 0) {
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
        {isLoading && (
          <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
        )}
      </div>

      <AreaChart
        className="h-48"
        data={transformedData}
        index="time"
        categories={['Watch to Detect', 'Detect to Batch', 'Batch to Analyze', 'Total Pipeline']}
        colors={['emerald', 'blue', 'amber', 'violet']}
        showLegend={true}
        showGridLines={false}
        curveType="monotone"
        valueFormatter={(value) => `${value}ms`}
        data-testid={`${testId}-chart`}
        aria-label="Pipeline latency history chart"
      />
    </Card>
  );
}
