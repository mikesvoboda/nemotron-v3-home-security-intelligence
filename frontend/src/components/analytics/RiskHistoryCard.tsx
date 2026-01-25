/**
 * RiskHistoryCard - Display risk event history as a stacked area chart
 *
 * Shows the distribution of events by risk level (low, medium, high, critical)
 * over time, with summary metrics and trend indicators.
 *
 * Features:
 * - Stacked area chart visualization
 * - Summary metrics: total events, critical count, high count, avg/day
 * - Trend indicator showing if high-risk events are increasing/decreasing
 * - Loading skeleton and error states
 * - Colors matching severity (green/yellow/orange/red)
 */

import { Card, Title, Text, AreaChart } from '@tremor/react';
import { AlertCircle, Loader2, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useMemo } from 'react';

import { useRiskHistoryQuery } from '../../hooks/useRiskHistoryQuery';

// ============================================================================
// Types
// ============================================================================

interface RiskHistoryCardProps {
  /** Date range for risk history */
  dateRange: {
    startDate: string;
    endDate: string;
  };
}

/** Trend direction for high-risk events */
type TrendDirection = 'increasing' | 'decreasing' | 'stable';

// ============================================================================
// Constants
// ============================================================================

/**
 * Color mapping for risk severity levels.
 * Green for low, yellow for medium, orange for high, red for critical.
 */
const SEVERITY_COLORS: Record<string, string> = {
  low: '#10B981', // emerald-500
  medium: '#F59E0B', // amber-500
  high: '#F97316', // orange-500
  critical: '#EF4444', // red-500
};

/**
 * Tremor color names for the AreaChart.
 */
const TREMOR_COLORS = ['emerald', 'amber', 'orange', 'red'] as const;

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Format a date string for display (e.g., "Jan 10").
 *
 * @param dateStr - ISO date string (YYYY-MM-DD)
 * @returns Formatted date string
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00');
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Calculate the trend direction based on high-risk events (high + critical).
 * Compares the first half of the data to the second half.
 *
 * @param dataPoints - Array of risk history data points
 * @returns TrendDirection indicating if high-risk events are increasing, decreasing, or stable
 */
function calculateTrend(dataPoints: Array<{ high: number; critical: number }>): TrendDirection {
  if (dataPoints.length < 2) return 'stable';

  const midpoint = Math.floor(dataPoints.length / 2);
  const firstHalf = dataPoints.slice(0, midpoint);
  const secondHalf = dataPoints.slice(midpoint);

  const firstHalfAvg =
    firstHalf.reduce((sum, d) => sum + d.high + d.critical, 0) / firstHalf.length;
  const secondHalfAvg =
    secondHalf.reduce((sum, d) => sum + d.high + d.critical, 0) / secondHalf.length;

  const threshold = 0.1; // 10% change threshold for trend
  const changeRatio = (secondHalfAvg - firstHalfAvg) / (firstHalfAvg || 1);

  if (changeRatio > threshold) return 'increasing';
  if (changeRatio < -threshold) return 'decreasing';
  return 'stable';
}

// ============================================================================
// Component
// ============================================================================

/**
 * RiskHistoryCard displays risk event history in a stacked area chart.
 *
 * Fetches risk history data for the specified date range and displays:
 * - Stacked area chart with low/medium/high/critical events by day
 * - Summary metrics: total events, critical count, high count, avg/day
 * - Trend indicator showing if high-risk events are increasing/decreasing
 *
 * @param props - Component props
 * @returns React element
 */
export default function RiskHistoryCard({ dateRange }: RiskHistoryCardProps) {
  const { dataPoints, isLoading, error } = useRiskHistoryQuery({
    start_date: dateRange.startDate,
    end_date: dateRange.endDate,
  });

  // Calculate summary metrics
  const metrics = useMemo(() => {
    if (dataPoints.length === 0) {
      return { total: 0, critical: 0, high: 0, avgPerDay: 0 };
    }

    let total = 0;
    let critical = 0;
    let high = 0;

    dataPoints.forEach((point) => {
      total += point.low + point.medium + point.high + point.critical;
      critical += point.critical;
      high += point.high;
    });

    const avgPerDay = total / dataPoints.length;

    return { total, critical, high, avgPerDay };
  }, [dataPoints]);

  // Calculate trend direction
  const trend = useMemo(() => calculateTrend(dataPoints), [dataPoints]);

  // Format chart data for Tremor AreaChart
  const chartData = useMemo(() => {
    return dataPoints.map((point) => ({
      date: formatDate(point.date),
      Low: point.low,
      Medium: point.medium,
      High: point.high,
      Critical: point.critical,
    }));
  }, [dataPoints]);

  // Format date range for display
  const dateRangeLabel = `${formatDate(dateRange.startDate)} - ${formatDate(dateRange.endDate)}`;

  // Trend icon and color
  const TrendIcon =
    trend === 'increasing' ? TrendingUp : trend === 'decreasing' ? TrendingDown : Minus;
  const trendColor =
    trend === 'increasing'
      ? 'text-red-400'
      : trend === 'decreasing'
        ? 'text-emerald-400'
        : 'text-gray-400';
  const trendLabel =
    trend === 'increasing'
      ? 'High-risk events increasing'
      : trend === 'decreasing'
        ? 'High-risk events decreasing'
        : 'High-risk events stable';

  // Loading state
  if (isLoading) {
    return (
      <Card data-testid="risk-history-loading">
        <Title>Risk History</Title>
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card data-testid="risk-history-error">
        <Title>Risk History</Title>
        <div className="flex h-64 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>Failed to load risk history data</Text>
        </div>
      </Card>
    );
  }

  // Empty state
  if (dataPoints.length === 0) {
    return (
      <Card data-testid="risk-history-empty">
        <Title>Risk History</Title>
        <div className="flex h-64 flex-col items-center justify-center text-gray-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>No risk data available for the selected period</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="risk-history-card">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title>Risk History</Title>
        <div className="flex items-center gap-4">
          {/* Trend Indicator */}
          <div
            className={`flex items-center gap-1.5 ${trendColor}`}
            data-testid="risk-trend-indicator"
            data-trend={trend}
            title={trendLabel}
          >
            <TrendIcon className="h-4 w-4" />
            <span className="text-xs">{trendLabel}</span>
          </div>
          <Text className="text-gray-400">{dateRangeLabel}</Text>
        </div>
      </div>

      {/* Summary Metrics */}
      <div
        className="mb-4 grid grid-cols-4 gap-4 rounded-lg bg-gray-800/50 p-4"
        data-testid="risk-history-metrics"
      >
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{metrics.total}</div>
          <div className="text-xs text-gray-400">Total Events</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-red-400">{metrics.critical}</div>
          <div className="text-xs text-gray-400">Critical</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-orange-400">{metrics.high}</div>
          <div className="text-xs text-gray-400">High</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{metrics.avgPerDay.toFixed(1)}</div>
          <div className="text-xs text-gray-400">Avg/Day</div>
        </div>
      </div>

      {/* Stacked Area Chart */}
      <div data-testid="risk-history-chart">
        <AreaChart
          className="h-48"
          data={chartData}
          index="date"
          categories={['Low', 'Medium', 'High', 'Critical']}
          colors={[...TREMOR_COLORS]}
          stack={true}
          showLegend={false}
          showGridLines={false}
          showAnimation={true}
          curveType="monotone"
        />
      </div>

      {/* Legend */}
      <div
        className="mt-4 flex flex-wrap gap-4 border-t border-gray-800 pt-4 text-xs text-gray-400"
        data-testid="risk-history-legend"
      >
        <div className="flex items-center gap-1.5" data-testid="legend-low">
          <div
            className="h-2.5 w-2.5 rounded-sm"
            style={{ backgroundColor: SEVERITY_COLORS.low }}
          />
          <span>Low</span>
        </div>
        <div className="flex items-center gap-1.5" data-testid="legend-medium">
          <div
            className="h-2.5 w-2.5 rounded-sm"
            style={{ backgroundColor: SEVERITY_COLORS.medium }}
          />
          <span>Medium</span>
        </div>
        <div className="flex items-center gap-1.5" data-testid="legend-high">
          <div
            className="h-2.5 w-2.5 rounded-sm"
            style={{ backgroundColor: SEVERITY_COLORS.high }}
          />
          <span>High</span>
        </div>
        <div className="flex items-center gap-1.5" data-testid="legend-critical">
          <div
            className="h-2.5 w-2.5 rounded-sm"
            style={{ backgroundColor: SEVERITY_COLORS.critical }}
          />
          <span>Critical</span>
        </div>
      </div>
    </Card>
  );
}
