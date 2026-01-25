/**
 * RiskScoreTrendCard - Display average risk score trends over time
 *
 * Shows a line chart of average risk scores by day to help identify
 * trends and patterns in overall risk levels.
 */

import { Card, Title, Text, LineChart } from '@tremor/react';
import { AlertCircle, Loader2, TrendingUp } from 'lucide-react';
import { useMemo } from 'react';

import { useRiskScoreTrends } from '../../hooks/useRiskScoreTrends';

// ============================================================================
// Types
// ============================================================================

interface RiskScoreTrendCardProps {
  /** Date range for the trends query */
  dateRange: {
    startDate: string;
    endDate: string;
  };
}

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

// ============================================================================
// Component
// ============================================================================

/**
 * RiskScoreTrendCard displays average risk score trends over time.
 *
 * Fetches risk score trend data for the specified date range and displays
 * a line chart showing the average risk score per day.
 *
 * @param props - Component props
 * @returns React element
 */
export default function RiskScoreTrendCard({ dateRange }: RiskScoreTrendCardProps) {
  const { dataPoints, isLoading, error } = useRiskScoreTrends({
    start_date: dateRange.startDate,
    end_date: dateRange.endDate,
  });

  // Transform data points for Tremor LineChart
  const chartData = useMemo(() => {
    return dataPoints.map((point) => ({
      date: formatDate(point.date),
      'Avg Risk Score': point.avg_score,
      Events: point.count,
    }));
  }, [dataPoints]);

  // Calculate overall average and trend
  const { overallAverage, trend } = useMemo(() => {
    if (dataPoints.length === 0) {
      return { overallAverage: 0, trend: 0 };
    }

    const pointsWithData = dataPoints.filter((p) => p.count > 0);
    if (pointsWithData.length === 0) {
      return { overallAverage: 0, trend: 0 };
    }

    // Calculate weighted average (weighted by event count)
    const totalEvents = pointsWithData.reduce((sum, p) => sum + p.count, 0);
    const weightedSum = pointsWithData.reduce((sum, p) => sum + p.avg_score * p.count, 0);
    const avg = totalEvents > 0 ? weightedSum / totalEvents : 0;

    // Calculate trend (difference between last and first non-zero points)
    const firstPoint = pointsWithData[0];
    const lastPoint = pointsWithData[pointsWithData.length - 1];
    const trendValue = lastPoint.avg_score - firstPoint.avg_score;

    return {
      overallAverage: Math.round(avg * 10) / 10,
      trend: Math.round(trendValue * 10) / 10,
    };
  }, [dataPoints]);

  // Format date range for display
  const dateRangeLabel = `${formatDate(dateRange.startDate)} - ${formatDate(dateRange.endDate)}`;

  // Loading state
  if (isLoading) {
    return (
      <Card data-testid="risk-score-trend-loading">
        <Title>Risk Score Trends</Title>
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card data-testid="risk-score-trend-error">
        <Title>Risk Score Trends</Title>
        <div className="flex h-48 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>Failed to load risk score trends</Text>
        </div>
      </Card>
    );
  }

  // Empty state (no events at all)
  const hasAnyData = dataPoints.some((p) => p.count > 0);
  if (!hasAnyData) {
    return (
      <Card data-testid="risk-score-trend-empty">
        <Title>Risk Score Trends</Title>
        <div className="flex h-48 flex-col items-center justify-center text-gray-400">
          <TrendingUp className="mb-2 h-8 w-8" />
          <Text>No risk score data available</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="risk-score-trend-card">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-[#76B900]" />
          <Title>Risk Score Trends</Title>
        </div>
        <Text className="text-gray-400">{dateRangeLabel}</Text>
      </div>

      {/* Summary stats */}
      <div className="mb-4 grid grid-cols-2 gap-4">
        <div>
          <Text className="text-gray-400">Average Score</Text>
          <p className="text-2xl font-bold text-white" data-testid="risk-score-trend-average">
            {overallAverage}
          </p>
        </div>
        <div>
          <Text className="text-gray-400">Trend</Text>
          <p
            className={`text-2xl font-bold ${
              trend > 0 ? 'text-red-400' : trend < 0 ? 'text-emerald-400' : 'text-gray-400'
            }`}
            data-testid="risk-score-trend-direction"
          >
            {trend > 0 ? '+' : ''}
            {trend}
          </p>
        </div>
      </div>

      {/* Line chart */}
      <LineChart
        className="h-40"
        data={chartData}
        index="date"
        categories={['Avg Risk Score']}
        colors={['amber']}
        showLegend={false}
        showGridLines={false}
        curveType="monotone"
        yAxisWidth={40}
        minValue={0}
        maxValue={100}
        data-testid="risk-score-trend-chart"
      />
    </Card>
  );
}
