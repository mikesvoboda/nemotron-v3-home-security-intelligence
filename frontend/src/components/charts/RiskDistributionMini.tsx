/**
 * RiskDistributionMini component displays a mini horizontal bar chart
 * showing the distribution of events by risk level.
 *
 * Used in EventStatsPanel for a compact visual representation.
 */

import { clsx } from 'clsx';

import type { RiskDistributionItem } from '../../types/generated';

/**
 * Props for the RiskDistributionMini component.
 */
export interface RiskDistributionMiniProps {
  /** Risk distribution data from the API */
  distribution?: RiskDistributionItem[];
  /** Additional CSS classes */
  className?: string;
}

/**
 * Color mapping for risk levels in the bar chart.
 */
const riskBarColors: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-green-500',
};

/**
 * Order for displaying risk levels (highest severity first).
 */
const riskOrder = ['critical', 'high', 'medium', 'low'];

/**
 * RiskDistributionMini displays a compact horizontal stacked bar chart
 * showing the distribution of events by risk level.
 *
 * The bars are proportional to the count for each risk level.
 *
 * @param props - Component props
 * @returns JSX element
 *
 * @example
 * ```tsx
 * <RiskDistributionMini
 *   distribution={[
 *     { risk_level: 'critical', count: 2 },
 *     { risk_level: 'high', count: 5 },
 *     { risk_level: 'medium', count: 12 },
 *     { risk_level: 'low', count: 25 },
 *   ]}
 * />
 * ```
 */
export default function RiskDistributionMini({
  distribution,
  className,
}: RiskDistributionMiniProps) {
  // Build a map of risk level to count
  const countMap = new Map<string, number>();
  if (distribution) {
    for (const item of distribution) {
      countMap.set(item.risk_level, item.count);
    }
  }

  // Calculate total for proportional widths
  const total = distribution?.reduce((sum, item) => sum + item.count, 0) ?? 0;

  // Get items in order, filtering out zero counts
  const orderedItems = riskOrder
    .map((level) => ({
      level,
      count: countMap.get(level) ?? 0,
    }))
    .filter((item) => countMap.has(item.level));

  return (
    <div
      className={clsx('flex flex-col gap-2', className)}
      data-testid="risk-distribution-mini"
      aria-label="Risk distribution chart"
      role="img"
    >
      {/* Label */}
      <span className="text-xs font-medium text-gray-400">Risk Distribution</span>

      {/* Bar container */}
      <div className="flex h-6 w-full overflow-hidden rounded-lg bg-gray-800">
        {orderedItems.map(({ level, count }) => {
          // Calculate flex value based on count proportion
          const flexValue = total > 0 ? count / total : 0;

          // Format label for accessibility
          const label = `${level.charAt(0).toUpperCase() + level.slice(1)}: ${count} event${count !== 1 ? 's' : ''}`;

          return (
            <div
              key={level}
              className={clsx(
                'h-full transition-all duration-300',
                riskBarColors[level]
              )}
              style={{ flex: flexValue }}
              data-testid={`risk-bar-${level}`}
              aria-label={label}
              title={label}
            />
          );
        })}

        {/* Empty state - when no data */}
        {orderedItems.length === 0 && (
          <div className="flex h-full w-full items-center justify-center">
            <span className="text-xs text-gray-500">No data</span>
          </div>
        )}
      </div>
    </div>
  );
}
