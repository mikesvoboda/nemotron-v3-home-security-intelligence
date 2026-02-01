/**
 * ZoneComparisonTable - Table displaying zone comparison data (NEM-4714)
 *
 * Displays a sortable table comparing zones by a selected metric:
 * - Zone name with type badge
 * - Metric value
 * - Trend indicator with color-coded up/down arrows
 *
 * Part of Phase 4B: Frontend Comparison Tab Content.
 *
 * @module components/zones/ZoneComparisonTable
 */

import { clsx } from 'clsx';
import { ArrowDown, ArrowUp, Minus } from 'lucide-react';
import { memo, useCallback, useMemo, useState } from 'react';

import type { ComparisonMetric, ZoneComparisonData } from '../../hooks/useZoneComparison';

// ============================================================================
// Types
// ============================================================================

/**
 * Sort direction options.
 */
type SortDirection = 'asc' | 'desc';

/**
 * Sortable column identifiers.
 */
type SortColumn = 'zone_name' | 'value' | 'trend_percent';

/**
 * Props for the ZoneComparisonTable component.
 */
export interface ZoneComparisonTableProps {
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
 * Format a metric value based on the metric type.
 */
function formatMetricValue(value: number, metric: ComparisonMetric): string {
  switch (metric) {
    case 'dwell_time':
      // Convert seconds to human-readable format
      if (value < 60) {
        return `${Math.round(value)}s`;
      } else if (value < 3600) {
        return `${Math.round(value / 60)}m`;
      }
      return `${(value / 3600).toFixed(1)}h`;
    case 'crossings':
    case 'anomalies':
    case 'occupancy':
    default:
      return value.toLocaleString();
  }
}

/**
 * Get a human-readable label for a metric.
 */
function getMetricLabel(metric: ComparisonMetric): string {
  switch (metric) {
    case 'crossings':
      return 'Crossings';
    case 'dwell_time':
      return 'Avg Dwell Time';
    case 'anomalies':
      return 'Anomalies';
    case 'occupancy':
      return 'Occupancy';
    default:
      return 'Value';
  }
}

/**
 * Get badge styling for zone type.
 */
function getZoneTypeBadgeStyle(zoneType: string): { bg: string; text: string } {
  switch (zoneType) {
    case 'entry_point':
      return { bg: 'bg-blue-500/20', text: 'text-blue-400' };
    case 'driveway':
      return { bg: 'bg-purple-500/20', text: 'text-purple-400' };
    case 'sidewalk':
      return { bg: 'bg-orange-500/20', text: 'text-orange-400' };
    case 'yard':
      return { bg: 'bg-green-500/20', text: 'text-green-400' };
    default:
      return { bg: 'bg-gray-500/20', text: 'text-gray-400' };
  }
}

/**
 * Format zone type for display.
 */
function formatZoneType(zoneType: string): string {
  return zoneType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

// ============================================================================
// Subcomponents
// ============================================================================

/**
 * Trend indicator component.
 */
interface TrendIndicatorProps {
  value: number | null;
}

function TrendIndicator({ value }: TrendIndicatorProps) {
  if (value === null) {
    return <span className="text-gray-500" data-testid="trend-no-data">-</span>;
  }

  const isPositive = value > 0;
  const isNegative = value < 0;
  const isNeutral = value === 0;

  return (
    <div
      className={clsx(
        'flex items-center gap-1 font-medium',
        isPositive && 'text-green-400',
        isNegative && 'text-red-400',
        isNeutral && 'text-gray-400'
      )}
      data-testid="trend-indicator"
    >
      {isPositive && <ArrowUp className="h-4 w-4" aria-hidden="true" />}
      {isNegative && <ArrowDown className="h-4 w-4" aria-hidden="true" />}
      {isNeutral && <Minus className="h-4 w-4" aria-hidden="true" />}
      <span>{isPositive ? '+' : ''}{value.toFixed(1)}%</span>
    </div>
  );
}

/**
 * Sortable column header.
 */
interface SortableHeaderProps {
  label: string;
  column: SortColumn;
  currentSort: SortColumn;
  direction: SortDirection;
  onSort: (column: SortColumn) => void;
  align?: 'left' | 'right';
}

function SortableHeader({
  label,
  column,
  currentSort,
  direction,
  onSort,
  align = 'left',
}: SortableHeaderProps) {
  const isActive = currentSort === column;

  return (
    <th
      className={clsx(
        'px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-400',
        'cursor-pointer select-none hover:text-gray-200 transition-colors',
        align === 'right' && 'text-right'
      )}
      onClick={() => onSort(column)}
      role="columnheader"
      aria-sort={isActive ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <div className={clsx('flex items-center gap-1', align === 'right' && 'justify-end')}>
        <span>{label}</span>
        {isActive && (
          <span className="text-[#76B900]">
            {direction === 'asc' ? (
              <ArrowUp className="h-3 w-3" aria-hidden="true" />
            ) : (
              <ArrowDown className="h-3 w-3" aria-hidden="true" />
            )}
          </span>
        )}
      </div>
    </th>
  );
}

/**
 * Loading skeleton row.
 */
function SkeletonRow() {
  return (
    <tr className="border-b border-gray-700/50">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="h-4 w-24 animate-pulse rounded bg-gray-700" />
          <div className="h-4 w-16 animate-pulse rounded bg-gray-700" />
        </div>
      </td>
      <td className="px-4 py-3 text-right">
        <div className="ml-auto h-4 w-12 animate-pulse rounded bg-gray-700" />
      </td>
      <td className="px-4 py-3 text-right">
        <div className="ml-auto h-4 w-16 animate-pulse rounded bg-gray-700" />
      </td>
    </tr>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneComparisonTable component.
 *
 * Displays a sortable table of zone comparison data.
 *
 * @param props - Component props
 * @returns Rendered component
 */
function ZoneComparisonTableComponent({
  zones,
  metric,
  isLoading = false,
  className,
}: ZoneComparisonTableProps) {
  const [sortColumn, setSortColumn] = useState<SortColumn>('value');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  // Handle sort column click
  const handleSort = useCallback((column: SortColumn) => {
    setSortColumn((currentColumn) => {
      if (currentColumn === column) {
        // Toggle direction if clicking same column
        setSortDirection((dir) => (dir === 'asc' ? 'desc' : 'asc'));
        return column;
      }
      // Reset to descending when switching columns
      setSortDirection('desc');
      return column;
    });
  }, []);

  // Sort zones based on current sort state
  const sortedZones = useMemo(() => {
    if (zones.length === 0) return [];

    return [...zones].sort((a, b) => {
      let comparison = 0;

      switch (sortColumn) {
        case 'zone_name':
          comparison = a.zone_name.localeCompare(b.zone_name);
          break;
        case 'value':
          comparison = a.value - b.value;
          break;
        case 'trend_percent':
          // Handle null values - always put them at the end regardless of sort direction
          if (a.trend_percent === null && b.trend_percent === null) {
            return 0;
          } else if (a.trend_percent === null) {
            return 1; // a (null) goes after b (always at end)
          } else if (b.trend_percent === null) {
            return -1; // b (null) goes after a (always at end)
          } else {
            comparison = a.trend_percent - b.trend_percent;
          }
          break;
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [zones, sortColumn, sortDirection]);

  // Loading state
  if (isLoading) {
    return (
      <div
        className={clsx('overflow-hidden rounded-lg border border-gray-700 bg-gray-800/50', className)}
        data-testid="zone-comparison-table-loading"
      >
        <table className="w-full">
          <thead className="border-b border-gray-700 bg-gray-800">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
                Zone
              </th>
              <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-400">
                {getMetricLabel(metric)}
              </th>
              <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-400">
                Trend
              </th>
            </tr>
          </thead>
          <tbody>
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </tbody>
        </table>
      </div>
    );
  }

  // Empty state
  if (zones.length === 0) {
    return (
      <div
        className={clsx(
          'flex min-h-[200px] items-center justify-center rounded-lg border border-gray-700 bg-gray-800/50 p-6',
          className
        )}
        data-testid="zone-comparison-table-empty"
      >
        <p className="text-gray-400">No zones selected for comparison</p>
      </div>
    );
  }

  return (
    <div
      className={clsx('overflow-hidden rounded-lg border border-gray-700 bg-gray-800/50', className)}
      data-testid="zone-comparison-table"
    >
      <table className="w-full">
        <thead className="border-b border-gray-700 bg-gray-800">
          <tr>
            <SortableHeader
              label="Zone"
              column="zone_name"
              currentSort={sortColumn}
              direction={sortDirection}
              onSort={handleSort}
              align="left"
            />
            <SortableHeader
              label={getMetricLabel(metric)}
              column="value"
              currentSort={sortColumn}
              direction={sortDirection}
              onSort={handleSort}
              align="right"
            />
            <SortableHeader
              label="Trend"
              column="trend_percent"
              currentSort={sortColumn}
              direction={sortDirection}
              onSort={handleSort}
              align="right"
            />
          </tr>
        </thead>
        <tbody>
          {sortedZones.map((zone) => {
            const badgeStyle = getZoneTypeBadgeStyle(zone.zone_type);
            return (
              <tr
                key={zone.zone_id}
                className="border-b border-gray-700/50 transition-colors hover:bg-gray-700/30"
                data-testid={`zone-row-${zone.zone_id}`}
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-white">{zone.zone_name}</span>
                    <span
                      className={clsx(
                        'rounded-full px-2 py-0.5 text-xs font-medium',
                        badgeStyle.bg,
                        badgeStyle.text
                      )}
                    >
                      {formatZoneType(zone.zone_type)}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <span className="font-medium text-white" data-testid={`zone-value-${zone.zone_id}`}>
                    {formatMetricValue(zone.value, metric)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <TrendIndicator value={zone.trend_percent} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Memoized ZoneComparisonTable for performance.
 */
export const ZoneComparisonTable = memo(ZoneComparisonTableComponent);

export default ZoneComparisonTable;
