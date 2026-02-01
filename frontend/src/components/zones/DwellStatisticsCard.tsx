/**
 * DwellStatisticsCard - Card displaying dwell time statistics (NEM-4714)
 *
 * Displays a summary of dwell time statistics for a polygon zone including:
 * - Zone name and status
 * - Average, min, max dwell times
 * - Total records count
 * - Alerts triggered badge
 * - Configure threshold button (for future modal integration)
 *
 * Part of Phase 2B: Frontend Dwell Time Statistics Display.
 *
 * @module components/zones/DwellStatisticsCard
 */

import { clsx } from 'clsx';
import { AlertTriangle, Clock, Settings } from 'lucide-react';
import { memo } from 'react';

import { formatDuration } from '../../hooks/useDwellTimeAnalytics';
import Button from '../common/Button';

import type { DwellStatistics, PolygonZone } from '../../hooks/useDwellTimeAnalytics';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the DwellStatisticsCard component.
 */
export interface DwellStatisticsCardProps {
  /** Polygon zone data */
  zone: PolygonZone;
  /** Dwell statistics for the zone (optional - may still be loading) */
  statistics?: DwellStatistics;
  /** Whether statistics are loading */
  isLoading?: boolean;
  /** Callback when configure button is clicked */
  onConfigure?: (zoneId: number) => void;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Stat item displaying a label and value.
 */
interface StatItemProps {
  label: string;
  value: string;
  testId: string;
}

function StatItem({ label, value, testId }: StatItemProps) {
  return (
    <div className="text-center">
      <div className="text-xl font-bold text-white" data-testid={testId}>
        {value}
      </div>
      <span className="text-xs text-gray-400">{label}</span>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * DwellStatisticsCard component.
 *
 * Displays dwell time statistics for a polygon zone with configuration button.
 *
 * @param props - Component props
 * @returns Rendered component
 */
function DwellStatisticsCardComponent({
  zone,
  statistics,
  isLoading = false,
  onConfigure,
  className,
}: DwellStatisticsCardProps) {
  const hasStats = statistics !== undefined;
  const hasRecords = hasStats && statistics.total_records > 0;
  const hasAlerts = hasStats && statistics.alerts_triggered > 0;

  return (
    <div
      className={clsx('rounded-lg border border-gray-700 bg-gray-800/50 p-4', className)}
      data-testid={`dwell-stats-card-${zone.id}`}
    >
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-blue-400" aria-hidden="true" />
          <h3 className="font-medium text-white">{zone.name}</h3>
        </div>
        <div className="flex items-center gap-2">
          {/* Alerts Badge */}
          {hasAlerts && (
            <span
              className="flex items-center gap-1 rounded-full bg-yellow-500/20 px-2 py-0.5 text-xs font-medium text-yellow-400"
              data-testid="alerts-badge"
            >
              <AlertTriangle className="h-3 w-3" aria-hidden="true" />
              {statistics.alerts_triggered}
            </span>
          )}
          {/* Status Badge */}
          <span
            className={clsx(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              zone.is_active ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'
            )}
            data-testid="zone-status-badge"
          >
            {zone.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>
      </div>

      {/* Statistics */}
      {isLoading ? (
        <div className="flex min-h-[80px] items-center justify-center" data-testid="loading-state">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-400 border-t-transparent" />
        </div>
      ) : hasStats ? (
        <>
          {/* Dwell Time Stats */}
          <div className="mb-4 grid grid-cols-3 gap-3">
            <StatItem
              label="Avg"
              value={formatDuration(statistics.avg_dwell_seconds)}
              testId="avg-dwell"
            />
            <StatItem
              label="Min"
              value={formatDuration(statistics.min_dwell_seconds)}
              testId="min-dwell"
            />
            <StatItem
              label="Max"
              value={formatDuration(statistics.max_dwell_seconds)}
              testId="max-dwell"
            />
          </div>

          {/* Records Count */}
          <div className="mb-4 rounded bg-gray-700/50 px-3 py-2 text-center">
            <span className="text-sm text-gray-400">
              {hasRecords ? (
                <>
                  <span className="font-medium text-white" data-testid="total-records">
                    {statistics.total_records.toLocaleString()}
                  </span>{' '}
                  total records
                </>
              ) : (
                <span data-testid="no-records">No dwell records in time range</span>
              )}
            </span>
          </div>
        </>
      ) : (
        <div className="mb-4 flex min-h-[80px] items-center justify-center" data-testid="no-data-state">
          <span className="text-sm text-gray-400">No statistics available</span>
        </div>
      )}

      {/* Configure Button */}
      <Button
        variant="outline-primary"
        size="sm"
        onClick={() => onConfigure?.(zone.id)}
        leftIcon={<Settings className="h-4 w-4" />}
        fullWidth
        data-testid="configure-button"
      >
        Configure Threshold
      </Button>
    </div>
  );
}

/**
 * Memoized DwellStatisticsCard for performance.
 */
export const DwellStatisticsCard = memo(DwellStatisticsCardComponent);

export default DwellStatisticsCard;
