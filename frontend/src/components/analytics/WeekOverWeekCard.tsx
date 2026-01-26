/**
 * WeekOverWeekCard - Display week-over-week comparison metrics
 *
 * Shows this week vs last week comparison for key security metrics:
 * - Total detections: more data collection is good (green for increase)
 * - High-risk events: more high-risk is bad (red for increase)
 * - Average risk score: higher risk is bad (red for increase)
 *
 * Features:
 * - Automatic date range calculation (last 7 days vs 7-14 days ago)
 * - Percentage change with visual indicators
 * - Color-coded arrows (green = good change, red = bad change)
 * - Loading skeleton and error states
 */

import { Card, Title, Text } from '@tremor/react';
import { AlertCircle, ArrowUp, ArrowDown, Minus, Loader2, TrendingUp } from 'lucide-react';
import { useMemo } from 'react';

import { useDetectionTrendsQuery } from '../../hooks/useDetectionTrendsQuery';
import { useRiskHistoryQuery } from '../../hooks/useRiskHistoryQuery';
import { useRiskScoreTrends } from '../../hooks/useRiskScoreTrends';

// ============================================================================
// Types
// ============================================================================

/**
 * Direction of change indicator
 */
type ChangeDirection = 'increase' | 'decrease' | 'stable';

/**
 * Props for a single comparison metric row
 */
interface MetricRowProps {
  /** Label for the metric */
  label: string;
  /** This week's value */
  thisWeek: number;
  /** Last week's value */
  lastWeek: number;
  /** Percentage change */
  percentChange: number;
  /** Direction of change */
  direction: ChangeDirection;
  /** Whether an increase is considered good (true) or bad (false) */
  increaseIsGood: boolean;
  /** Test ID prefix for this metric */
  testIdPrefix: string;
  /** Format function for the value display */
  formatValue?: (value: number) => string;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Calculate percentage change between two values.
 * Returns 0 if previous value is 0 to avoid division by zero.
 *
 * @param current - Current period value
 * @param previous - Previous period value
 * @returns Percentage change
 */
function calculatePercentChange(current: number, previous: number): number {
  if (previous === 0) return current > 0 ? 100 : 0;
  return ((current - previous) / previous) * 100;
}

/**
 * Determine change direction based on values.
 *
 * @param current - Current period value
 * @param previous - Previous period value
 * @returns Change direction
 */
function getChangeDirection(current: number, previous: number): ChangeDirection {
  if (Math.abs(current - previous) < 0.01) return 'stable';
  return current > previous ? 'increase' : 'decrease';
}

/**
 * Format a number with locale-aware thousands separators.
 *
 * @param value - Number to format
 * @returns Formatted string
 */
function formatNumber(value: number): string {
  return value.toLocaleString();
}

/**
 * Format a decimal number with one decimal place.
 *
 * @param value - Number to format
 * @returns Formatted string
 */
function formatDecimal(value: number): string {
  return value.toFixed(1);
}

/**
 * Get ISO date string (YYYY-MM-DD) for a Date object.
 *
 * @param date - Date object
 * @returns ISO date string
 */
function toISODateString(date: Date): string {
  return date.toISOString().split('T')[0];
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * MetricRow displays a single comparison metric with visual indicators.
 */
function MetricRow({
  label,
  thisWeek,
  lastWeek,
  percentChange,
  direction,
  increaseIsGood,
  testIdPrefix,
  formatValue = formatNumber,
}: MetricRowProps) {
  // Determine if the change is good or bad based on direction and whether increase is good
  const isGoodChange =
    direction === 'stable' ||
    (direction === 'increase' && increaseIsGood) ||
    (direction === 'decrease' && !increaseIsGood);

  // Color class based on whether change is good or bad
  const colorClass = direction === 'stable' ? 'text-gray-400' : isGoodChange ? 'text-emerald-400' : 'text-red-400';

  // Arrow icon based on direction
  const ArrowIcon = direction === 'increase' ? ArrowUp : direction === 'decrease' ? ArrowDown : Minus;

  return (
    <div className="flex items-center justify-between rounded-lg bg-gray-800/50 p-4">
      <div className="flex-1">
        <Text className="text-gray-400">{label}</Text>
        <div className="mt-1 flex items-baseline gap-4">
          <div>
            <span
              className="text-2xl font-bold text-white"
              data-testid={`${testIdPrefix}-this-week`}
            >
              {formatValue(thisWeek)}
            </span>
            <span className="ml-1 text-xs text-gray-500">this week</span>
          </div>
          <div className="text-gray-500">vs</div>
          <div>
            <span
              className="text-lg text-gray-400"
              data-testid={`${testIdPrefix}-last-week`}
            >
              {formatValue(lastWeek)}
            </span>
            <span className="ml-1 text-xs text-gray-500">last week</span>
          </div>
        </div>
      </div>

      {/* Change indicator */}
      <div
        className={`flex items-center gap-1 ${colorClass}`}
        data-testid={`${testIdPrefix}-indicator`}
      >
        <ArrowIcon className="h-5 w-5" />
        <span
          className="text-lg font-semibold"
          data-testid={`${testIdPrefix}-change`}
        >
          {Math.abs(percentChange).toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * WeekOverWeekCard displays week-over-week comparison metrics.
 *
 * Automatically calculates date ranges:
 * - This week: last 7 days ending today
 * - Last week: 7-14 days ago
 *
 * @returns React element
 */
export default function WeekOverWeekCard() {
  // Calculate date ranges
  const { thisWeekRange, lastWeekRange } = useMemo(() => {
    const today = new Date();
    const thisWeekEnd = new Date(today);
    const thisWeekStart = new Date(today);
    thisWeekStart.setDate(thisWeekStart.getDate() - 6); // Last 7 days including today

    const lastWeekEnd = new Date(thisWeekStart);
    lastWeekEnd.setDate(lastWeekEnd.getDate() - 1); // Day before this week starts
    const lastWeekStart = new Date(lastWeekEnd);
    lastWeekStart.setDate(lastWeekStart.getDate() - 6); // 7 days before last week end

    return {
      thisWeekRange: {
        start_date: toISODateString(thisWeekStart),
        end_date: toISODateString(thisWeekEnd),
      },
      lastWeekRange: {
        start_date: toISODateString(lastWeekStart),
        end_date: toISODateString(lastWeekEnd),
      },
    };
  }, []);

  // Fetch detection trends for both weeks
  const thisWeekDetections = useDetectionTrendsQuery(thisWeekRange);
  const lastWeekDetections = useDetectionTrendsQuery(lastWeekRange);

  // Fetch risk history for both weeks
  const thisWeekRisk = useRiskHistoryQuery(thisWeekRange);
  const lastWeekRisk = useRiskHistoryQuery(lastWeekRange);

  // Fetch risk score trends for both weeks
  const thisWeekRiskScore = useRiskScoreTrends(thisWeekRange);
  const lastWeekRiskScore = useRiskScoreTrends(lastWeekRange);

  // Check loading state
  const isLoading =
    thisWeekDetections.isLoading ||
    lastWeekDetections.isLoading ||
    thisWeekRisk.isLoading ||
    lastWeekRisk.isLoading ||
    thisWeekRiskScore.isLoading ||
    lastWeekRiskScore.isLoading;

  // Check error state
  const hasError =
    thisWeekDetections.error ||
    lastWeekDetections.error ||
    thisWeekRisk.error ||
    lastWeekRisk.error ||
    thisWeekRiskScore.error ||
    lastWeekRiskScore.error;

  // Calculate high-risk events (high + critical)
  const { thisWeekHighRisk, lastWeekHighRisk } = useMemo(() => {
    const sumHighRisk = (dataPoints: Array<{ high: number; critical: number }>) =>
      dataPoints.reduce((sum, point) => sum + point.high + point.critical, 0);

    return {
      thisWeekHighRisk: sumHighRisk(thisWeekRisk.dataPoints),
      lastWeekHighRisk: sumHighRisk(lastWeekRisk.dataPoints),
    };
  }, [thisWeekRisk.dataPoints, lastWeekRisk.dataPoints]);

  // Calculate average risk score (weighted by count)
  const { thisWeekAvgRisk, lastWeekAvgRisk } = useMemo(() => {
    const calcWeightedAvg = (dataPoints: Array<{ avg_score: number; count: number }>) => {
      const totalCount = dataPoints.reduce((sum, p) => sum + p.count, 0);
      if (totalCount === 0) return 0;
      const weightedSum = dataPoints.reduce((sum, p) => sum + p.avg_score * p.count, 0);
      return weightedSum / totalCount;
    };

    return {
      thisWeekAvgRisk: calcWeightedAvg(thisWeekRiskScore.dataPoints),
      lastWeekAvgRisk: calcWeightedAvg(lastWeekRiskScore.dataPoints),
    };
  }, [thisWeekRiskScore.dataPoints, lastWeekRiskScore.dataPoints]);

  // Get total detections
  const thisWeekTotalDetections = thisWeekDetections.totalDetections;
  const lastWeekTotalDetections = lastWeekDetections.totalDetections;

  // Calculate metrics for display
  const detectionsChange = calculatePercentChange(thisWeekTotalDetections, lastWeekTotalDetections);
  const detectionsDirection = getChangeDirection(thisWeekTotalDetections, lastWeekTotalDetections);

  const highRiskChange = calculatePercentChange(thisWeekHighRisk, lastWeekHighRisk);
  const highRiskDirection = getChangeDirection(thisWeekHighRisk, lastWeekHighRisk);

  const avgRiskChange = calculatePercentChange(thisWeekAvgRisk, lastWeekAvgRisk);
  const avgRiskDirection = getChangeDirection(thisWeekAvgRisk, lastWeekAvgRisk);

  // Loading state
  if (isLoading) {
    return (
      <Card data-testid="week-over-week-loading">
        <Title>Week over Week</Title>
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  // Error state
  if (hasError) {
    return (
      <Card data-testid="week-over-week-error">
        <Title>Week over Week</Title>
        <div className="flex h-64 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>Failed to load comparison data</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="week-over-week-card">
      {/* Header */}
      <div className="mb-4 flex items-center gap-2">
        <TrendingUp className="h-5 w-5 text-[#76B900]" />
        <Title>Week over Week</Title>
      </div>

      {/* Comparison metrics */}
      <div className="space-y-4">
        {/* Total Detections - more is good (better coverage/detection) */}
        <MetricRow
          label="Total Detections"
          thisWeek={thisWeekTotalDetections}
          lastWeek={lastWeekTotalDetections}
          percentChange={detectionsChange}
          direction={detectionsDirection}
          increaseIsGood={true}
          testIdPrefix="detections"
        />

        {/* High-Risk Events - more is bad */}
        <MetricRow
          label="High-Risk Events"
          thisWeek={thisWeekHighRisk}
          lastWeek={lastWeekHighRisk}
          percentChange={highRiskChange}
          direction={highRiskDirection}
          increaseIsGood={false}
          testIdPrefix="high-risk"
        />

        {/* Average Risk Score - higher is bad */}
        <MetricRow
          label="Avg Risk Score"
          thisWeek={thisWeekAvgRisk}
          lastWeek={lastWeekAvgRisk}
          percentChange={avgRiskChange}
          direction={avgRiskDirection}
          increaseIsGood={false}
          testIdPrefix="avg-risk"
          formatValue={formatDecimal}
        />
      </div>
    </Card>
  );
}
