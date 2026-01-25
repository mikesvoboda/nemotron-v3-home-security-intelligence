/**
 * RiskHistoryCard - Display risk level distribution over time
 *
 * Shows a stacked area chart of events by risk level (critical, high, medium, low)
 * over a date range to help identify risk trends and patterns.
 */

import { Card, Title, Text, AreaChart } from '@tremor/react';
import { AlertCircle, Loader2, ShieldAlert } from 'lucide-react';
import { useMemo } from 'react';

import { useRiskHistoryQuery } from '../../hooks/useRiskHistoryQuery';

// ============================================================================
// Types
// ============================================================================

interface RiskHistoryCardProps {
  /** Date range for the risk history query */
  dateRange: {
    startDate: string;
    endDate: string;
  };
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Risk level colors matching the design system.
 */
const RISK_COLORS: [string, string, string, string] = ['red', 'orange', 'yellow', 'emerald'];

/**
 * Risk level categories in display order (highest to lowest).
 */
const RISK_CATEGORIES = ['Critical', 'High', 'Medium', 'Low'] as const;

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
 * RiskHistoryCard displays risk level distribution over time.
 *
 * Fetches risk history data for the specified date range and displays
 * a stacked area chart showing daily counts by risk level.
 *
 * @param props - Component props
 * @returns React element
 */
export default function RiskHistoryCard({ dateRange }: RiskHistoryCardProps) {
  const { dataPoints, isLoading, error } = useRiskHistoryQuery({
    start_date: dateRange.startDate,
    end_date: dateRange.endDate,
  });

  // Transform data points for Tremor AreaChart (stacked)
  const chartData = useMemo(() => {
    return dataPoints.map((point) => ({
      date: formatDate(point.date),
      Critical: point.critical,
      High: point.high,
      Medium: point.medium,
      Low: point.low,
    }));
  }, [dataPoints]);

  // Calculate totals by risk level
  const riskTotals = useMemo(() => {
    return dataPoints.reduce(
      (acc, point) => ({
        critical: acc.critical + point.critical,
        high: acc.high + point.high,
        medium: acc.medium + point.medium,
        low: acc.low + point.low,
      }),
      { critical: 0, high: 0, medium: 0, low: 0 }
    );
  }, [dataPoints]);

  // Format date range for display
  const dateRangeLabel = `${formatDate(dateRange.startDate)} - ${formatDate(dateRange.endDate)}`;

  // Loading state
  if (isLoading) {
    return (
      <Card data-testid="risk-history-loading">
        <Title>Risk History</Title>
        <div className="flex h-48 items-center justify-center">
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
        <div className="flex h-48 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>Failed to load risk history</Text>
        </div>
      </Card>
    );
  }

  // Empty state
  if (dataPoints.length === 0) {
    return (
      <Card data-testid="risk-history-empty">
        <Title>Risk History</Title>
        <div className="flex h-48 flex-col items-center justify-center text-gray-400">
          <ShieldAlert className="mb-2 h-8 w-8" />
          <Text>No risk data available</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="risk-history-card">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-5 w-5 text-[#76B900]" />
          <Title>Risk History</Title>
        </div>
        <Text className="text-gray-400">{dateRangeLabel}</Text>
      </div>

      {/* Risk level summary */}
      <div className="mb-4 grid grid-cols-4 gap-2">
        <div className="text-center">
          <Text className="text-xs text-red-400">Critical</Text>
          <p className="font-semibold text-red-400" data-testid="risk-total-critical">
            {riskTotals.critical}
          </p>
        </div>
        <div className="text-center">
          <Text className="text-xs text-orange-400">High</Text>
          <p className="font-semibold text-orange-400" data-testid="risk-total-high">
            {riskTotals.high}
          </p>
        </div>
        <div className="text-center">
          <Text className="text-xs text-yellow-400">Medium</Text>
          <p className="font-semibold text-yellow-400" data-testid="risk-total-medium">
            {riskTotals.medium}
          </p>
        </div>
        <div className="text-center">
          <Text className="text-xs text-emerald-400">Low</Text>
          <p className="font-semibold text-emerald-400" data-testid="risk-total-low">
            {riskTotals.low}
          </p>
        </div>
      </div>

      {/* Stacked area chart */}
      <AreaChart
        className="h-40"
        data={chartData}
        index="date"
        categories={[...RISK_CATEGORIES]}
        colors={RISK_COLORS}
        stack={true}
        showLegend={false}
        showGridLines={false}
        curveType="monotone"
        data-testid="risk-history-chart"
      />
    </Card>
  );
}
