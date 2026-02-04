/**
 * RiskDistributionChart - Donut chart showing event distribution by risk level.
 *
 * Displays a Tremor DonutChart with segments for Critical, High, Medium, and Low risk levels.
 * Clicking a segment filters the timeline to show only events of that risk level.
 * Clicking the same segment again clears the filter (toggle behavior).
 *
 * Features:
 * - Donut chart with custom risk level colors (red, orange, yellow, green)
 * - Click-to-filter interaction with toggle behavior
 * - Optional legend with clickable items
 * - Empty state when no events exist
 * - Loading skeleton state
 * - Accessible with proper ARIA labels
 *
 * @see NEM-5400, NEM-5401, NEM-5402, NEM-5403
 * @module components/dashboard/RiskDistributionChart
 */

import { Card, DonutChart, Text } from '@tremor/react';
import { clsx } from 'clsx';
import { PieChart } from 'lucide-react';
import { useMemo, useCallback } from 'react';

import { RISK_HEX_COLORS } from '../../constants/chartColors';
import { ChartLoadingState } from '../common/ChartLoadingState';

import type { RiskLevel } from '../../utils/risk';

/**
 * Risk distribution data structure.
 */
export interface RiskDistribution {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

/**
 * Props for the RiskDistributionChart component.
 */
export interface RiskDistributionChartProps {
  /** Distribution of events by risk level */
  distribution?: RiskDistribution;
  /** Currently selected risk level filter */
  selectedRiskLevel?: RiskLevel | null;
  /** Callback when a risk level is selected/deselected */
  onRiskLevelSelect?: (riskLevel: RiskLevel | null) => void;
  /** Whether to show the legend below the chart */
  showLegend?: boolean;
  /** Whether the data is loading */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Chart data item for Tremor DonutChart.
 */
interface ChartDataItem {
  name: string;
  value: number;
  color: string;
  riskLevel: RiskLevel;
}

/**
 * Risk level display labels.
 */
const RISK_LABELS: Record<RiskLevel, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

/**
 * Tremor color names for risk levels.
 */
const RISK_TREMOR_COLORS: Record<RiskLevel, string> = {
  critical: 'red',
  high: 'orange',
  medium: 'yellow',
  low: 'green',
};

/**
 * Order for displaying risk levels (highest severity first).
 */
const RISK_ORDER: RiskLevel[] = ['critical', 'high', 'medium', 'low'];

/**
 * Transform distribution data to chart format, filtering out zero values.
 */
function transformDistributionToChartData(
  distribution: RiskDistribution | undefined
): ChartDataItem[] {
  if (!distribution) return [];

  return RISK_ORDER.filter((level) => distribution[level] > 0).map((level) => ({
    name: RISK_LABELS[level],
    value: distribution[level],
    color: RISK_TREMOR_COLORS[level],
    riskLevel: level,
  }));
}

/**
 * Calculate total events from distribution.
 */
function calculateTotal(distribution: RiskDistribution | undefined): number {
  if (!distribution) return 0;
  return distribution.critical + distribution.high + distribution.medium + distribution.low;
}

/**
 * Format large numbers for display.
 */
function formatCount(count: number): string {
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
  return count.toString();
}

/**
 * RiskDistributionChart displays a donut chart of events by risk level.
 *
 * Clicking a segment filters the timeline to that risk level.
 * Clicking the same segment again clears the filter.
 *
 * @example
 * ```tsx
 * const [selectedRisk, setSelectedRisk] = useState<RiskLevel | null>(null);
 *
 * <RiskDistributionChart
 *   distribution={{ critical: 5, high: 10, medium: 25, low: 60 }}
 *   selectedRiskLevel={selectedRisk}
 *   onRiskLevelSelect={setSelectedRisk}
 *   showLegend
 * />
 * ```
 */
export default function RiskDistributionChart({
  distribution,
  selectedRiskLevel,
  onRiskLevelSelect,
  showLegend = true,
  isLoading = false,
  className,
}: RiskDistributionChartProps) {
  // Transform distribution to chart data
  const chartData = useMemo(() => transformDistributionToChartData(distribution), [distribution]);

  // Calculate total events
  const totalEvents = useMemo(() => calculateTotal(distribution), [distribution]);

  // Get Tremor colors array for chart
  const chartColors = useMemo(() => chartData.map((item) => item.color), [chartData]);

  // Handle segment click - toggle filter on/off
  const handleValueChange = useCallback(
    (value: { name: string; value: number } | null) => {
      if (!onRiskLevelSelect) return;

      if (value === null) {
        // Clear selection
        onRiskLevelSelect(null);
        return;
      }

      // Find the risk level from the display name
      const riskLevel = chartData.find((item) => item.name === value.name)?.riskLevel;

      if (!riskLevel) return;

      // Toggle: if already selected, clear; otherwise select
      if (selectedRiskLevel === riskLevel) {
        onRiskLevelSelect(null);
      } else {
        onRiskLevelSelect(riskLevel);
      }
    },
    [chartData, selectedRiskLevel, onRiskLevelSelect]
  );

  // Handle legend item click
  const handleLegendClick = useCallback(
    (riskLevel: RiskLevel) => {
      if (!onRiskLevelSelect) return;

      // Toggle: if already selected, clear; otherwise select
      if (selectedRiskLevel === riskLevel) {
        onRiskLevelSelect(null);
      } else {
        onRiskLevelSelect(riskLevel);
      }
    },
    [selectedRiskLevel, onRiskLevelSelect]
  );

  // Loading state
  if (isLoading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A]', className)}
        data-testid="risk-distribution-loading"
      >
        <div className="mb-3 flex items-center gap-2">
          <PieChart className="h-5 w-5 text-gray-500" />
          <Text className="font-medium text-gray-300">Risk Distribution</Text>
        </div>
        <ChartLoadingState height="h-40" data-testid="risk-distribution-loading-spinner" />
      </Card>
    );
  }

  // Empty state - no events
  if (chartData.length === 0) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A]', className)}
        data-testid="risk-distribution-empty"
      >
        <div className="mb-3 flex items-center gap-2">
          <PieChart className="h-5 w-5 text-gray-500" />
          <Text className="font-medium text-gray-300">Risk Distribution</Text>
        </div>
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <PieChart className="mb-2 h-10 w-10 text-gray-600" />
          <Text className="text-sm text-gray-500">No events recorded</Text>
          <Text className="text-xs text-gray-600">Events will appear here once detected</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A]', className)}
      data-testid="risk-distribution-chart"
      data-selected={selectedRiskLevel || undefined}
    >
      {/* Header */}
      <div className="mb-3 flex items-center gap-2">
        <PieChart className="h-5 w-5 text-[#76B900]" />
        <Text className="font-medium text-gray-300">Risk Distribution</Text>
      </div>

      {/* Donut Chart */}
      <div
        className="flex items-center justify-center"
        role="img"
        aria-label="Risk distribution donut chart showing events by severity level"
      >
        <div className="relative">
          <DonutChart
            className="h-32 w-32"
            data={chartData}
            category="value"
            index="name"
            colors={chartColors}
            showAnimation
            showTooltip
            valueFormatter={(value) => `${formatCount(value)} events`}
            onValueChange={handleValueChange}
            data-testid="donut-chart"
          />
          {/* Center label showing total */}
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span
              className="text-2xl font-bold text-white"
              data-testid="total-events"
            >
              {formatCount(totalEvents)}
            </span>
            <span className="text-xs text-gray-400">events</span>
          </div>
        </div>
      </div>

      {/* Legend */}
      {showLegend && (
        <div className="mt-4 grid grid-cols-2 gap-2">
          {RISK_ORDER.filter((level) => distribution && distribution[level] > 0).map((level) => (
            <button
              key={level}
              type="button"
              onClick={() => handleLegendClick(level)}
              className={clsx(
                'flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors',
                'hover:bg-gray-800/50 focus:outline-none focus:ring-2 focus:ring-[#76B900]',
                selectedRiskLevel === level && 'bg-gray-800/70 ring-1 ring-gray-600'
              )}
              data-testid={`legend-${level}`}
              aria-pressed={selectedRiskLevel === level}
              title={`Click to filter by ${RISK_LABELS[level]} risk events`}
            >
              <div
                className="h-3 w-3 flex-shrink-0 rounded-full"
                style={{ backgroundColor: RISK_HEX_COLORS[level] }}
                data-color={level}
              />
              <span className="truncate text-gray-300">{RISK_LABELS[level]}</span>
              <span className="ml-auto font-medium text-gray-400">
                {formatCount(distribution?.[level] ?? 0)}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Selected filter indicator */}
      {selectedRiskLevel && (
        <div className="mt-3 flex items-center justify-center">
          <button
            type="button"
            onClick={() => onRiskLevelSelect?.(null)}
            className="flex items-center gap-1 rounded-full bg-gray-800 px-3 py-1 text-xs text-gray-300 transition-colors hover:bg-gray-700"
            aria-label="Clear risk level filter"
          >
            <span>Filtering: {RISK_LABELS[selectedRiskLevel]}</span>
            <span className="ml-1 text-gray-500">&times;</span>
          </button>
        </div>
      )}
    </Card>
  );
}
