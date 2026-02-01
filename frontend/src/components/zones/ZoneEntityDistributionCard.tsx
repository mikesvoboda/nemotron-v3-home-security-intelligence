/**
 * ZoneEntityDistributionCard - Card displaying entity type distribution (NEM-4937)
 *
 * Displays a summary of entity type distribution for a polygon zone including:
 * - Zone name and total entity count
 * - Entity type breakdown with counts and percentages
 * - Visual bar chart representation
 *
 * Part of Zone Entity Distribution Visualization feature.
 *
 * @module components/zones/ZoneEntityDistributionCard
 */

import { clsx } from 'clsx';
import { PieChart, Users } from 'lucide-react';
import { memo } from 'react';

import {
  getEntityTypeColor,
  getEntityTypeLabel,
} from '../../hooks/useZoneEntityDistribution';

import type { ZoneEntityDistribution } from '../../hooks/useZoneEntityDistribution';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the ZoneEntityDistributionCard component.
 */
export interface ZoneEntityDistributionCardProps {
  /** Entity distribution data for the zone */
  distribution: ZoneEntityDistribution;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Callback when card is clicked */
  onClick?: (zoneId: number) => void;
  /** Whether this card is selected */
  isSelected?: boolean;
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Entity type row with bar visualization.
 */
interface EntityTypeRowProps {
  entityType: string;
  count: number;
  percentage: number;
}

function EntityTypeRow({ entityType, count, percentage }: EntityTypeRowProps) {
  const color = getEntityTypeColor(entityType);
  const label = getEntityTypeLabel(entityType);

  return (
    <div className="space-y-1" data-testid={`entity-type-${entityType}`}>
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-300">{label}</span>
        <span className="text-white font-medium">
          {count} <span className="text-gray-500">({percentage.toFixed(1)}%)</span>
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-gray-700">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: `${percentage}%`,
            backgroundColor: color,
          }}
          data-testid={`entity-bar-${entityType}`}
        />
      </div>
    </div>
  );
}

/**
 * Loading skeleton for the card.
 */
function LoadingSkeleton() {
  return (
    <div className="animate-pulse space-y-4" data-testid="loading-skeleton">
      <div className="flex items-center justify-between">
        <div className="h-5 w-32 rounded bg-gray-700" />
        <div className="h-5 w-16 rounded bg-gray-700" />
      </div>
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-1">
            <div className="flex justify-between">
              <div className="h-4 w-20 rounded bg-gray-700" />
              <div className="h-4 w-12 rounded bg-gray-700" />
            </div>
            <div className="h-2 w-full rounded bg-gray-700" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Empty state when no entities.
 */
function EmptyState() {
  return (
    <div
      className="flex flex-col items-center justify-center py-6 text-gray-400"
      data-testid="empty-state"
    >
      <Users className="h-8 w-8 mb-2 opacity-50" />
      <p className="text-sm">No entities detected</p>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneEntityDistributionCard component.
 *
 * Displays entity type distribution for a polygon zone with visual bars.
 *
 * @param props - Component props
 * @returns Rendered component
 */
function ZoneEntityDistributionCardComponent({
  distribution,
  isLoading = false,
  className,
  onClick,
  isSelected = false,
}: ZoneEntityDistributionCardProps) {
  const hasEntities = distribution.total_entities > 0;

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- Accessibility properly handled: role, tabIndex, and keyboard support are conditionally applied when onClick is provided
    <div
      className={clsx(
        'rounded-lg border bg-gray-800/50 p-4 transition-all',
        isSelected
          ? 'border-[#76B900] ring-2 ring-[#76B900] ring-offset-2 ring-offset-[#121212]'
          : 'border-gray-700 hover:border-gray-600',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick ? () => onClick(distribution.zone_id) : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick(distribution.zone_id);
              }
            }
          : undefined
      }
      tabIndex={onClick ? 0 : undefined}
      role={onClick ? 'button' : undefined}
      aria-pressed={onClick ? isSelected : undefined}
      data-testid={`entity-distribution-card-${distribution.zone_id}`}
    >
      {isLoading ? (
        <LoadingSkeleton />
      ) : (
        <>
          {/* Header */}
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <PieChart className="h-4 w-4 text-[#76B900]" aria-hidden="true" />
              <h3 className="font-medium text-white truncate" title={distribution.zone_name}>
                {distribution.zone_name}
              </h3>
            </div>
            <span
              className="rounded-full bg-gray-700 px-2 py-0.5 text-xs font-medium text-gray-300"
              data-testid="total-count"
            >
              {distribution.total_entities.toLocaleString()} total
            </span>
          </div>

          {/* Entity Type Breakdown */}
          {hasEntities ? (
            <div className="space-y-3">
              {distribution.entity_types.map((et) => (
                <EntityTypeRow
                  key={et.entity_type}
                  entityType={et.entity_type}
                  count={et.count}
                  percentage={et.percentage}
                />
              ))}
            </div>
          ) : (
            <EmptyState />
          )}
        </>
      )}
    </div>
  );
}

/**
 * Memoized ZoneEntityDistributionCard for performance.
 */
export const ZoneEntityDistributionCard = memo(ZoneEntityDistributionCardComponent);

export default ZoneEntityDistributionCard;
