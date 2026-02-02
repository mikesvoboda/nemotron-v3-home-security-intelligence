/**
 * CrossingTrendsChart - Area chart showing line zone crossing trends (NEM-4714)
 *
 * Displays a time-series visualization of line zone crossings:
 * - Entry counts over time
 * - Exit counts over time
 * - Total summary statistics
 *
 * Part of Phase 1C: Frontend Line Zone Crossing Display.
 *
 * @module components/zones/CrossingTrendsChart
 */

import { Card, Title, AreaChart, Text } from '@tremor/react';
import { clsx } from 'clsx';
import { TrendingUp } from 'lucide-react';
import { memo, useMemo } from 'react';

import type { CrossingTrendsResponse } from '../../types/zoneAnalytics';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the CrossingTrendsChart component.
 */
export interface CrossingTrendsChartProps {
  /** Crossing trends data from API */
  data: CrossingTrendsResponse | undefined;
  /** Whether data is being loaded */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Subcomponents
// ============================================================================

/**
 * Loading skeleton for the chart.
 */
function ChartSkeleton() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#76B900] border-t-transparent" />
    </div>
  );
}

/**
 * Empty state when no data is available.
 */
function EmptyState() {
  return (
    <div className="flex h-64 items-center justify-center">
      <Text className="text-gray-400">No crossing data available</Text>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * CrossingTrendsChart component.
 *
 * Displays an area chart showing line zone crossing trends over time.
 *
 * @param props - Component props
 * @returns Rendered component
 */
function CrossingTrendsChartComponent({
  data,
  isLoading = false,
  className,
}: CrossingTrendsChartProps) {
  // Transform data for the chart
  const chartData = useMemo(() => {
    if (!data?.trends) return [];

    return data.trends.map((point) => ({
      time: new Date(point.timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
      }),
      In: point.in_count,
      Out: point.out_count,
    }));
  }, [data?.trends]);

  // Loading state
  if (isLoading) {
    return (
      <Card
        className={clsx('border-gray-700 bg-gray-800/50', className)}
        data-testid="crossing-trends-chart-loading"
      >
        <Title className="flex items-center gap-2 text-white">
          <TrendingUp className="h-5 w-5 text-[#76B900]" aria-hidden="true" />
          Crossing Trends
        </Title>
        <ChartSkeleton />
      </Card>
    );
  }

  // Empty state
  if (!data || chartData.length === 0) {
    return (
      <Card
        className={clsx('border-gray-700 bg-gray-800/50', className)}
        data-testid="crossing-trends-chart-empty"
      >
        <Title className="flex items-center gap-2 text-white">
          <TrendingUp className="h-5 w-5 text-[#76B900]" aria-hidden="true" />
          Crossing Trends
        </Title>
        <EmptyState />
      </Card>
    );
  }

  return (
    <Card
      className={clsx('border-gray-700 bg-gray-800/50', className)}
      data-testid="crossing-trends-chart"
    >
      {/* Header */}
      <Title className="mb-2 flex items-center gap-2 text-white">
        <TrendingUp className="h-5 w-5 text-[#76B900]" aria-hidden="true" />
        Crossing Trends - {data.zone_name}
      </Title>

      {/* Summary statistics */}
      <div className="mb-4 flex gap-4 text-sm">
        <div>
          <span className="text-gray-400">Total In: </span>
          <span className="font-medium text-green-400" data-testid="total-in">
            {data.total_in}
          </span>
        </div>
        <div>
          <span className="text-gray-400">Total Out: </span>
          <span className="font-medium text-red-400" data-testid="total-out">
            {data.total_out}
          </span>
        </div>
      </div>

      {/* Area Chart */}
      <AreaChart
        className="h-64"
        data={chartData}
        index="time"
        categories={['In', 'Out']}
        colors={['green', 'red']}
        showAnimation
        showLegend
        showGridLines={false}
        data-testid="crossing-area-chart"
        aria-label="Crossing trends chart showing zone entry and exit counts over time"
      />
    </Card>
  );
}

/**
 * Memoized CrossingTrendsChart for performance.
 */
export const CrossingTrendsChart = memo(CrossingTrendsChartComponent);

export default CrossingTrendsChart;
