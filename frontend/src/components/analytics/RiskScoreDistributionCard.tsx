/**
 * RiskScoreDistributionCard - Display risk score distribution histogram
 *
 * Shows a bar chart of events grouped by risk score buckets (0-10, 10-20, etc.)
 * to visualize the distribution of risk scores across events.
 */

import { Card, Title, Text, BarChart } from '@tremor/react';
import { AlertCircle, BarChart3, Loader2 } from 'lucide-react';
import { useMemo } from 'react';

import { useRiskScoreDistribution } from '../../hooks/useRiskScoreDistribution';

// ============================================================================
// Types
// ============================================================================

interface RiskScoreDistributionCardProps {
  /** Date range for the distribution query */
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

/**
 * Get color for a risk score bucket based on score range.
 *
 * @param minScore - Minimum score of the bucket
 * @returns Tremor color name
 */
function getBucketColor(minScore: number): string {
  if (minScore < 30) return 'emerald';
  if (minScore < 60) return 'yellow';
  if (minScore < 85) return 'orange';
  return 'red';
}

// ============================================================================
// Component
// ============================================================================

/**
 * RiskScoreDistributionCard displays risk score distribution as a histogram.
 *
 * Fetches risk score distribution data for the specified date range and displays
 * a bar chart showing the count of events in each score bucket.
 *
 * @param props - Component props
 * @returns React element
 */
export default function RiskScoreDistributionCard({ dateRange }: RiskScoreDistributionCardProps) {
  const { buckets, totalEvents, isLoading, error } = useRiskScoreDistribution({
    start_date: dateRange.startDate,
    end_date: dateRange.endDate,
  });

  // Transform data points for Tremor BarChart
  const chartData = useMemo(() => {
    return buckets.map((bucket) => ({
      range: `${bucket.min_score}-${bucket.max_score}`,
      Events: bucket.count,
      color: getBucketColor(bucket.min_score),
    }));
  }, [buckets]);

  // Format date range for display
  const dateRangeLabel = `${formatDate(dateRange.startDate)} - ${formatDate(dateRange.endDate)}`;

  // Loading state
  if (isLoading) {
    return (
      <Card data-testid="risk-score-distribution-loading">
        <Title>Risk Score Distribution</Title>
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card data-testid="risk-score-distribution-error">
        <Title>Risk Score Distribution</Title>
        <div className="flex h-48 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>Failed to load risk score distribution</Text>
        </div>
      </Card>
    );
  }

  // Empty state
  if (totalEvents === 0) {
    return (
      <Card data-testid="risk-score-distribution-empty">
        <Title>Risk Score Distribution</Title>
        <div className="flex h-48 flex-col items-center justify-center text-gray-400">
          <BarChart3 className="mb-2 h-8 w-8" />
          <Text>No risk score data available</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="risk-score-distribution-card">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-[#76B900]" />
          <Title>Risk Score Distribution</Title>
        </div>
        <Text className="text-gray-400">{dateRangeLabel}</Text>
      </div>

      {/* Summary stat */}
      <div className="mb-4">
        <Text className="text-gray-400">Total Events</Text>
        <p className="text-2xl font-bold text-white" data-testid="risk-score-distribution-total">
          {formatNumber(totalEvents)}
        </p>
      </div>

      {/* Bar chart */}
      <BarChart
        className="h-40"
        data={chartData}
        index="range"
        categories={['Events']}
        colors={['emerald']}
        showLegend={false}
        showGridLines={false}
        data-testid="risk-score-distribution-chart"
      />

      {/* Risk level legend */}
      <div className="mt-4 flex justify-between text-xs">
        <div className="flex items-center gap-1">
          <div className="h-2 w-2 rounded-full bg-emerald-500" />
          <span className="text-gray-400">Low (0-29)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-2 w-2 rounded-full bg-yellow-500" />
          <span className="text-gray-400">Medium (30-59)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-2 w-2 rounded-full bg-orange-500" />
          <span className="text-gray-400">High (60-84)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-2 w-2 rounded-full bg-red-500" />
          <span className="text-gray-400">Critical (85+)</span>
        </div>
      </div>
    </Card>
  );
}
