/**
 * DetectionTrendsCard - Display detection trend analytics
 *
 * Shows daily detection counts over a date range using an area chart.
 * Visualizes detection patterns to help identify anomalies and trends.
 */

import { Card, Title, Text, AreaChart } from '@tremor/react';
import { AlertCircle, Loader2, TrendingUp } from 'lucide-react';
import { useMemo } from 'react';

import { useDetectionTrendsQuery } from '../../hooks/useDetectionTrendsQuery';

// ============================================================================
// Types
// ============================================================================

interface DetectionTrendsCardProps {
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

/**
 * Format a number with thousands separator.
 *
 * @param num - Number to format
 * @returns Formatted number string
 */
function formatNumber(num: number): string {
  return num.toLocaleString();
}

// ============================================================================
// Component
// ============================================================================

/**
 * DetectionTrendsCard displays detection count trends over time.
 *
 * Fetches detection trend data for the specified date range and displays
 * an area chart showing daily detection counts with total summary.
 *
 * @param props - Component props
 * @returns React element
 */
export default function DetectionTrendsCard({ dateRange }: DetectionTrendsCardProps) {
  const { dataPoints, totalDetections, isLoading, error } = useDetectionTrendsQuery({
    start_date: dateRange.startDate,
    end_date: dateRange.endDate,
  });

  // Transform data points for Tremor AreaChart
  const chartData = useMemo(() => {
    return dataPoints.map((point) => ({
      date: formatDate(point.date),
      Detections: point.count,
    }));
  }, [dataPoints]);

  // Format date range for display
  const dateRangeLabel = `${formatDate(dateRange.startDate)} - ${formatDate(dateRange.endDate)}`;

  // Loading state
  if (isLoading) {
    return (
      <Card data-testid="detection-trends-loading">
        <Title>Detection Trends</Title>
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card data-testid="detection-trends-error">
        <Title>Detection Trends</Title>
        <div className="flex h-48 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>Failed to load detection trends</Text>
        </div>
      </Card>
    );
  }

  // Empty state
  if (dataPoints.length === 0) {
    return (
      <Card data-testid="detection-trends-empty">
        <Title>Detection Trends</Title>
        <div className="flex h-48 flex-col items-center justify-center text-gray-400">
          <TrendingUp className="mb-2 h-8 w-8" />
          <Text>No detection data available</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="detection-trends-card">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-[#76B900]" />
          <Title>Detection Trends</Title>
        </div>
        <Text className="text-gray-400">{dateRangeLabel}</Text>
      </div>

      {/* Summary stat */}
      <div className="mb-4">
        <Text className="text-gray-400">Total Detections</Text>
        <p
          className="text-2xl font-bold text-white"
          data-testid="detection-trends-total"
        >
          {formatNumber(totalDetections)}
        </p>
      </div>

      {/* Area chart */}
      <AreaChart
        className="h-40"
        data={chartData}
        index="date"
        categories={['Detections']}
        colors={['emerald']}
        showLegend={false}
        showGridLines={false}
        curveType="monotone"
        data-testid="detection-trends-chart"
      />
    </Card>
  );
}
