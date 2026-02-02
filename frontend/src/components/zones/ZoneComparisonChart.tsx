/**
 * ZoneComparisonChart - Bar chart for zone comparison visualization (NEM-4714)
 *
 * Displays a horizontal bar chart comparing zones by a selected metric:
 * - Color-coded bars by zone type
 * - Hover tooltips with details
 * - Responsive design
 *
 * Part of Phase 4B: Frontend Comparison Tab Content.
 *
 * @module components/zones/ZoneComparisonChart
 */

import { Card, Title, BarChart, Text } from '@tremor/react';
import { clsx } from 'clsx';
import { BarChart3 } from 'lucide-react';
import { memo, useMemo } from 'react';

import type { ComparisonMetric, ZoneComparisonData } from '../../hooks/useZoneComparison';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the ZoneComparisonChart component.
 */
export interface ZoneComparisonChartProps {
  /** Comparison data for zones */
  zones: ZoneComparisonData[];
  /** The metric being compared */
  metric: ComparisonMetric;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get a human-readable label for a metric.
 */
function getMetricLabel(metric: ComparisonMetric): string {
  switch (metric) {
    case 'crossings':
      return 'Crossings';
    case 'dwell_time':
      return 'Avg Dwell Time (seconds)';
    case 'anomalies':
      return 'Anomalies';
    case 'occupancy':
      return 'Occupancy';
    default:
      return 'Value';
  }
}

// ============================================================================
// Subcomponents
// ============================================================================

/**
 * Loading skeleton for the chart.
 */
function ChartSkeleton() {
  return (
    <div className="flex h-64 items-center justify-center" data-testid="chart-skeleton">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#76B900] border-t-transparent" />
    </div>
  );
}

/**
 * Empty state when no data is available.
 */
function EmptyState() {
  return (
    <div className="flex h-64 items-center justify-center" data-testid="chart-empty">
      <Text className="text-gray-400">Select zones to compare</Text>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneComparisonChart component.
 *
 * Displays a bar chart comparing zone metrics.
 *
 * @param props - Component props
 * @returns Rendered component
 */
function ZoneComparisonChartComponent({
  zones,
  metric,
  isLoading = false,
  className,
}: ZoneComparisonChartProps) {
  // Transform data for the chart
  const chartData = useMemo(() => {
    if (zones.length === 0) return [];

    return zones.map((zone) => ({
      name: zone.zone_name,
      [getMetricLabel(metric)]: zone.value,
      zoneType: zone.zone_type,
    }));
  }, [zones, metric]);

  // Get the dominant zone type for chart color
  // For simplicity, we use a single color - green (primary brand color)
  const chartCategories = [getMetricLabel(metric)];

  // Loading state
  if (isLoading) {
    return (
      <Card
        className={clsx('border-gray-700 bg-gray-800/50', className)}
        data-testid="zone-comparison-chart-loading"
      >
        <Title className="flex items-center gap-2 text-white">
          <BarChart3 className="h-5 w-5 text-[#76B900]" aria-hidden="true" />
          Zone Comparison
        </Title>
        <ChartSkeleton />
      </Card>
    );
  }

  // Empty state
  if (zones.length === 0) {
    return (
      <Card
        className={clsx('border-gray-700 bg-gray-800/50', className)}
        data-testid="zone-comparison-chart-empty"
      >
        <Title className="flex items-center gap-2 text-white">
          <BarChart3 className="h-5 w-5 text-[#76B900]" aria-hidden="true" />
          Zone Comparison
        </Title>
        <EmptyState />
      </Card>
    );
  }

  // Calculate summary stats
  const totalValue = zones.reduce((sum, z) => sum + z.value, 0);
  const avgValue = totalValue / zones.length;
  const maxZone = zones.reduce((max, z) => (z.value > max.value ? z : max), zones[0]);

  return (
    <Card
      className={clsx('border-gray-700 bg-gray-800/50', className)}
      data-testid="zone-comparison-chart"
    >
      {/* Header */}
      <Title className="mb-2 flex items-center gap-2 text-white">
        <BarChart3 className="h-5 w-5 text-[#76B900]" aria-hidden="true" />
        Zone Comparison - {getMetricLabel(metric)}
      </Title>

      {/* Summary statistics */}
      <div className="mb-4 flex gap-4 text-sm">
        <div>
          <span className="text-gray-400">Zones: </span>
          <span className="font-medium text-white" data-testid="zone-count">
            {zones.length}
          </span>
        </div>
        <div>
          <span className="text-gray-400">Avg: </span>
          <span className="font-medium text-white" data-testid="avg-value">
            {metric === 'dwell_time'
              ? avgValue < 60
                ? `${Math.round(avgValue)}s`
                : `${Math.round(avgValue / 60)}m`
              : Math.round(avgValue).toLocaleString()}
          </span>
        </div>
        <div>
          <span className="text-gray-400">Highest: </span>
          <span className="font-medium text-[#76B900]" data-testid="max-zone">
            {maxZone.zone_name}
          </span>
        </div>
      </div>

      {/* Bar Chart */}
      <BarChart
        className="h-64"
        data={chartData}
        index="name"
        categories={chartCategories}
        colors={['emerald']}
        showAnimation
        showLegend={false}
        showGridLines={false}
        layout="vertical"
        yAxisWidth={120}
        data-testid="comparison-bar-chart"
        aria-label="Zone comparison chart showing metric values across different zones"
      />
    </Card>
  );
}

/**
 * Memoized ZoneComparisonChart for performance.
 */
export const ZoneComparisonChart = memo(ZoneComparisonChartComponent);

export default ZoneComparisonChart;
