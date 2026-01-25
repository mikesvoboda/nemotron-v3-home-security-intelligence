/**
 * BatchClosureReasonChart - Pie/bar chart for batch closure reasons
 *
 * Displays distribution of batch closure reasons:
 * - timeout: Batch window expired
 * - idle: No activity for idle timeout period
 * - max_size: Maximum batch size reached
 *
 * @module components/batch/BatchClosureReasonChart
 */

import { Text, DonutChart } from '@tremor/react';
import { clsx } from 'clsx';

import type { ClosureReasonStats, ClosureReasonPercentages } from '../../hooks/useBatchStatistics';

// ============================================================================
// Types
// ============================================================================

export interface BatchClosureReasonChartProps {
  /** Closure reason counts */
  closureReasonStats: ClosureReasonStats;
  /** Closure reason percentages */
  closureReasonPercentages: ClosureReasonPercentages;
  /** Total number of closed batches */
  totalBatches: number;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

const CLOSURE_REASON_LABELS: Record<string, string> = {
  timeout: 'Timeout',
  idle: 'Idle',
  max_size: 'Max Size',
  unknown: 'Unknown',
};

const CLOSURE_REASON_COLORS: string[] = ['amber', 'blue', 'emerald', 'gray'];

const CLOSURE_REASON_HEX: Record<string, string> = {
  timeout: '#f59e0b', // amber
  idle: '#3b82f6', // blue
  max_size: '#10b981', // emerald
  unknown: '#6b7280', // gray
};

// ============================================================================
// Component
// ============================================================================

/**
 * BatchClosureReasonChart - Visual chart of batch closure reasons
 */
export default function BatchClosureReasonChart({
  closureReasonStats,
  closureReasonPercentages,
  totalBatches,
  className,
}: BatchClosureReasonChartProps) {
  // Transform data for donut chart
  const chartData = Object.entries(closureReasonStats)
    .filter(([, count]) => count > 0)
    .map(([reason, count]) => ({
      name: CLOSURE_REASON_LABELS[reason] || reason,
      count,
      percentage: closureReasonPercentages[reason] || 0,
    }));

  // Empty state
  if (totalBatches === 0) {
    return (
      <div
        className={clsx('rounded-lg border border-gray-700 bg-gray-800/30 p-4', className)}
        data-testid="closure-reason-chart"
      >
        <Text className="mb-4 text-sm font-medium text-gray-300">Closure Reasons</Text>
        <Text className="text-center text-gray-400">
          No closed batches yet. Statistics will appear as batches complete.
        </Text>
      </div>
    );
  }

  return (
    <div
      className={clsx('rounded-lg border border-gray-700 bg-gray-800/30 p-4', className)}
      data-testid="closure-reason-chart"
    >
      <Text className="mb-4 text-sm font-medium text-gray-300">Closure Reasons</Text>

      <div className="flex flex-col items-center gap-4 md:flex-row md:items-start">
        {/* Donut Chart */}
        <DonutChart
          className="h-32 w-32"
          data={chartData}
          category="count"
          index="name"
          colors={CLOSURE_REASON_COLORS.slice(0, chartData.length)}
          showAnimation
          showTooltip
          valueFormatter={(value) => String(value)}
        />

        {/* Legend with percentages */}
        <div className="flex-1 space-y-2">
          {chartData.map((item) => {
            const reason = Object.entries(CLOSURE_REASON_LABELS).find(
              ([, label]) => label === item.name
            )?.[0] ?? 'unknown';
            const color = CLOSURE_REASON_HEX[reason] || CLOSURE_REASON_HEX.unknown;

            return (
              <div
                key={item.name}
                className="flex items-center justify-between"
              >
                <div className="flex items-center gap-2">
                  <div
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: color }}
                  />
                  <Text className="text-sm text-gray-300">{item.name}</Text>
                </div>
                <div className="flex items-center gap-2">
                  <Text className="text-sm font-medium text-white">
                    {item.count}
                  </Text>
                  <Text className="text-xs text-gray-500">
                    ({item.percentage.toFixed(1)}%)
                  </Text>
                </div>
              </div>
            );
          })}

          {/* Total */}
          <div className="mt-2 border-t border-gray-700 pt-2">
            <div className="flex items-center justify-between">
              <Text className="text-sm text-gray-400">Total</Text>
              <Text className="text-sm font-medium text-white">{totalBatches}</Text>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
