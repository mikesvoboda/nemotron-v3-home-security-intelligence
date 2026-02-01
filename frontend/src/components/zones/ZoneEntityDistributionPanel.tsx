/**
 * ZoneEntityDistributionPanel - Panel showing entity distribution across zones (NEM-4937)
 *
 * Displays entity distribution visualization for all polygon zones:
 * - Grid of zone distribution cards
 * - Grand total summary
 * - Real-time updates via polling
 *
 * Part of Zone Entity Distribution Visualization feature.
 *
 * @module components/zones/ZoneEntityDistributionPanel
 */

import { clsx } from 'clsx';
import { PieChart, RefreshCw } from 'lucide-react';
import { memo, useCallback, useState } from 'react';

import { ZoneEntityDistributionCard } from './ZoneEntityDistributionCard';
import { useAllZonesEntityDistribution } from '../../hooks/useZoneEntityDistribution';
import Button from '../common/Button';
import EmptyState from '../common/EmptyState';
import LoadingSpinner from '../common/LoadingSpinner';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the ZoneEntityDistributionPanel component.
 */
export interface ZoneEntityDistributionPanelProps {
  /** Optional camera ID filter */
  cameraId?: string;
  /** Callback when a zone card is clicked */
  onZoneSelect?: (zoneId: number) => void;
  /** Currently selected zone ID */
  selectedZoneId?: number;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Summary header showing grand total.
 */
interface SummaryHeaderProps {
  grandTotal: number;
  zoneCount: number;
  isRefetching: boolean;
  onRefresh: () => void;
}

function SummaryHeader({ grandTotal, zoneCount, isRefetching, onRefresh }: SummaryHeaderProps) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <PieChart className="h-5 w-5 text-[#76B900]" aria-hidden="true" />
          <h3 className="font-semibold text-white">Entity Distribution by Zone</h3>
        </div>
        <span className="rounded-full bg-gray-700 px-3 py-1 text-sm text-gray-300">
          <span className="font-medium text-white">{grandTotal.toLocaleString()}</span> entities in{' '}
          <span className="font-medium text-white">{zoneCount}</span> zone
          {zoneCount !== 1 ? 's' : ''}
        </span>
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={onRefresh}
        disabled={isRefetching}
        leftIcon={<RefreshCw className={clsx('h-4 w-4', isRefetching && 'animate-spin')} />}
        data-testid="refresh-button"
      >
        Refresh
      </Button>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneEntityDistributionPanel component.
 *
 * Displays entity distribution across all polygon zones with cards.
 *
 * @param props - Component props
 * @returns Rendered component
 */
function ZoneEntityDistributionPanelComponent({
  cameraId,
  onZoneSelect,
  selectedZoneId,
  className,
}: ZoneEntityDistributionPanelProps) {
  const [isRefetching, setIsRefetching] = useState(false);

  const { data, isLoading, error, refetch } = useAllZonesEntityDistribution({
    cameraId,
    enabled: true,
  });

  const handleRefresh = useCallback(() => {
    setIsRefetching(true);
    void Promise.resolve(refetch()).finally(() => {
      setIsRefetching(false);
    });
  }, [refetch]);

  // Loading state
  if (isLoading) {
    return (
      <div
        className={clsx('rounded-lg border border-gray-700 bg-gray-800/50 p-6', className)}
        data-testid="entity-distribution-panel-loading"
      >
        <div className="flex items-center justify-center min-h-[200px]">
          <LoadingSpinner />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className={clsx('rounded-lg border border-gray-700 bg-gray-800/50 p-6', className)}
        data-testid="entity-distribution-panel-error"
      >
        <div className="text-center">
          <p className="text-red-400 mb-4">Failed to load entity distribution: {error.message}</p>
          <Button variant="outline-primary" size="sm" onClick={handleRefresh}>
            Try Again
          </Button>
        </div>
      </div>
    );
  }

  // Empty state - no zones
  if (!data || data.zones.length === 0) {
    return (
      <div
        className={clsx('rounded-lg border border-gray-700 bg-gray-800/50 p-6', className)}
        data-testid="entity-distribution-panel-empty"
      >
        <EmptyState
          icon={PieChart}
          title="No polygon zones configured"
          description="Create polygon zones to visualize entity distribution across monitored areas."
          variant="muted"
        />
      </div>
    );
  }

  return (
    <div
      className={clsx('rounded-lg border border-gray-700 bg-gray-800/50 p-4', className)}
      data-testid="entity-distribution-panel"
    >
      {/* Summary Header */}
      <SummaryHeader
        grandTotal={data.grand_total}
        zoneCount={data.zones.length}
        isRefetching={isRefetching}
        onRefresh={handleRefresh}
      />

      {/* Zone Cards Grid */}
      <div
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        data-testid="zone-distribution-grid"
      >
        {data.zones.map((zone) => (
          <ZoneEntityDistributionCard
            key={zone.zone_id}
            distribution={zone}
            onClick={onZoneSelect}
            isSelected={selectedZoneId === zone.zone_id}
          />
        ))}
      </div>

      {/* No entities message if grand total is 0 */}
      {data.grand_total === 0 && (
        <div className="mt-4 rounded-lg bg-gray-700/50 p-4 text-center">
          <p className="text-sm text-gray-400">
            No entity activity detected in the last 24 hours.
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Memoized ZoneEntityDistributionPanel for performance.
 */
export const ZoneEntityDistributionPanel = memo(ZoneEntityDistributionPanelComponent);

export default ZoneEntityDistributionPanel;
