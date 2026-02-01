/**
 * GPUHistoryPanel - Historical GPU metrics chart
 *
 * Displays GPU utilization, temperature, and memory usage over time
 * using Tremor's AreaChart component. Fetches data from the GPU history API.
 */

import { Card, Title, Text, AreaChart } from '@tremor/react';
import { AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { useMemo } from 'react';

import { useGPUMetricsHistory } from '../../hooks/useGPUMetricsHistory';

/**
 * Props for GPUHistoryPanel component.
 */
export interface GPUHistoryPanelProps {
  /** Number of data points to fetch (default: 300) */
  limit?: number;
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
  'Utilization %': number;
  'Temperature C': number;
  'Memory %': number;
}

/**
 * Transform API data to chart format.
 */
function transformChartData(
  chartData: ReturnType<typeof useGPUMetricsHistory>['chartData']
): ChartDataPoint[] {
  if (!chartData) return [];

  return chartData.map((point) => ({
    time: point.timestamp,
    'Utilization %': point.utilization,
    'Temperature C': point.temperature,
    'Memory %': Math.round(point.memory_percent * 10) / 10,
  }));
}

/**
 * GPUHistoryPanel - Displays historical GPU metrics
 *
 * Shows GPU utilization, temperature, and memory usage percentage
 * over time. Fetches the last 300 data points by default.
 *
 * @example
 * ```tsx
 * <GPUHistoryPanel limit={300} data-testid="gpu-history" />
 * ```
 */
export default function GPUHistoryPanel({
  limit = 300,
  className,
  'data-testid': testId = 'gpu-history-panel',
}: GPUHistoryPanelProps) {
  const { chartData, isLoading, error, refetch, data } = useGPUMetricsHistory({ limit });

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
        <Title className="mb-4 text-white">GPU History</Title>
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
        <Title className="mb-4 text-white">GPU History</Title>
        <div
          className="flex h-48 flex-col items-center justify-center text-red-400"
          data-testid={`${testId}-error`}
        >
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text className="mb-2">Failed to load GPU history</Text>
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
        <Title className="mb-4 text-white">GPU History</Title>
        <div
          className="flex h-48 flex-col items-center justify-center text-gray-400"
          data-testid={`${testId}-empty`}
        >
          <Text>No GPU data available</Text>
        </div>
      </Card>
    );
  }

  // Get GPU name from the data if available
  const gpuName = data?.items[0]?.gpu_name ?? 'GPU';

  return (
    <Card
      className={className}
      data-testid={testId}
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <Title className="text-white">GPU History</Title>
          <Text className="text-gray-400 text-xs">{gpuName}</Text>
        </div>
        {isLoading && (
          <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
        )}
      </div>

      <AreaChart
        className="h-48"
        data={transformedData}
        index="time"
        categories={['Utilization %', 'Temperature C', 'Memory %']}
        colors={['emerald', 'red', 'blue']}
        showLegend={true}
        showGridLines={false}
        curveType="monotone"
        data-testid={`${testId}-chart`}
        aria-label="GPU utilization history chart"
      />
    </Card>
  );
}
