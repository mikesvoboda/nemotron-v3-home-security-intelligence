/**
 * PerformanceHistoryPanel - Historical performance metrics chart
 *
 * Displays GPU utilization, CPU percentage, and RAM usage over time
 * using Tremor's AreaChart component. Supports time range selection.
 */

import { Card, Title, Text, AreaChart } from '@tremor/react';
import { AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { useState, useMemo } from 'react';

import TimeRangeSelector from './TimeRangeSelector';
import { usePerformanceHistory } from '../../hooks/usePerformanceHistory';

import type { TimeRange } from '../../types/performance';

/**
 * Props for PerformanceHistoryPanel component.
 */
export interface PerformanceHistoryPanelProps {
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
  'GPU %': number;
  'CPU %': number;
  'RAM GB': number;
}

/**
 * Format timestamp for chart display.
 *
 * @param isoString - ISO 8601 timestamp
 * @returns Formatted time string (e.g., "10:00:05")
 */
function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return isoString;
  }
}

/**
 * PerformanceHistoryPanel - Displays historical performance metrics
 *
 * Shows GPU utilization, CPU percentage, and RAM usage over the selected
 * time range. Uses Tremor AreaChart for visualization.
 *
 * @example
 * ```tsx
 * <PerformanceHistoryPanel data-testid="performance-history" />
 * ```
 */
export default function PerformanceHistoryPanel({
  className,
  'data-testid': testId = 'performance-history-panel',
}: PerformanceHistoryPanelProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>('5m');
  const { snapshots, isLoading, error, refetch } = usePerformanceHistory(timeRange);

  // Transform snapshots to chart data format
  const chartData: ChartDataPoint[] = useMemo(() => {
    return snapshots.map((s) => ({
      time: formatTime(s.timestamp),
      'GPU %': s.gpu?.utilization ?? 0,
      'CPU %': s.host?.cpu_percent ?? 0,
      'RAM GB': s.host?.ram_used_gb ?? 0,
    }));
  }, [snapshots]);

  // Loading state
  if (isLoading && snapshots.length === 0) {
    return (
      <Card
        className={className}
        data-testid={testId}
      >
        <div className="flex items-center justify-between mb-4">
          <Title className="text-white">Performance History</Title>
          <TimeRangeSelector
            selectedRange={timeRange}
            onRangeChange={setTimeRange}
            data-testid={`${testId}-time-selector`}
          />
        </div>
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
        <div className="flex items-center justify-between mb-4">
          <Title className="text-white">Performance History</Title>
          <TimeRangeSelector
            selectedRange={timeRange}
            onRangeChange={setTimeRange}
            data-testid={`${testId}-time-selector`}
          />
        </div>
        <div
          className="flex h-48 flex-col items-center justify-center text-red-400"
          data-testid={`${testId}-error`}
        >
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text className="mb-2">Failed to load performance history</Text>
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
  if (snapshots.length === 0) {
    return (
      <Card
        className={className}
        data-testid={testId}
      >
        <div className="flex items-center justify-between mb-4">
          <Title className="text-white">Performance History</Title>
          <TimeRangeSelector
            selectedRange={timeRange}
            onRangeChange={setTimeRange}
            data-testid={`${testId}-time-selector`}
          />
        </div>
        <div
          className="flex h-48 flex-col items-center justify-center text-gray-400"
          data-testid={`${testId}-empty`}
        >
          <Text>No performance data available</Text>
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
        <Title className="text-white">Performance History</Title>
        <div className="flex items-center gap-2">
          {isLoading && (
            <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
          )}
          <TimeRangeSelector
            selectedRange={timeRange}
            onRangeChange={setTimeRange}
            data-testid={`${testId}-time-selector`}
          />
        </div>
      </div>

      <AreaChart
        className="h-48"
        data={chartData}
        index="time"
        categories={['GPU %', 'CPU %', 'RAM GB']}
        colors={['emerald', 'blue', 'amber']}
        showLegend={true}
        showGridLines={false}
        curveType="monotone"
        data-testid={`${testId}-chart`}
      />
    </Card>
  );
}
