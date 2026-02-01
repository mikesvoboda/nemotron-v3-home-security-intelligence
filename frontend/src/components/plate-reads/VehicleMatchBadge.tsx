/**
 * VehicleMatchBadge - Badge indicating known/unknown vehicle status
 *
 * Displays a badge showing whether a detected license plate matches a registered
 * household vehicle. Shows "Known" (green) for matched vehicles or "Unknown"
 * (amber) for unregistered vehicles.
 *
 * Phase 3: RegisteredVehicle matching integration for LPR UI (NEM-4865)
 *
 * @module components/plate-reads/VehicleMatchBadge
 * @see frontend/src/hooks/useVehicleMatchQuery.ts - Vehicle matching hook
 */

import { clsx } from 'clsx';
import { Car, AlertTriangle, Loader2 } from 'lucide-react';
import { memo, useMemo } from 'react';

import { useVehicleMatchQuery, type VehicleMatch } from '../../hooks/useVehicleMatchQuery';

import type { TrustLevel } from '../../hooks/useHouseholdApi';

// ============================================================================
// Types
// ============================================================================

export interface VehicleMatchBadgeProps {
  /** The license plate text to check for matches */
  plateText: string;
  /** Size variant for the badge */
  size?: 'sm' | 'md';
  /** Whether to show detailed info in tooltip (owner name, trust level) */
  showDetails?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get size-specific CSS classes.
 */
function getSizeClasses(size: 'sm' | 'md') {
  switch (size) {
    case 'sm':
      return {
        badge: 'px-1.5 py-0.5 text-xs gap-1',
        icon: 'h-3 w-3',
      };
    case 'md':
    default:
      return {
        badge: 'px-2 py-1 text-sm gap-1.5',
        icon: 'h-4 w-4',
      };
  }
}

/**
 * Format trust level for display.
 */
function formatTrustLevel(trusted: boolean, ownerTrustLevel?: TrustLevel): string {
  if (!trusted) {
    return 'Untrusted';
  }
  if (ownerTrustLevel) {
    switch (ownerTrustLevel) {
      case 'full':
        return 'Fully Trusted';
      case 'partial':
        return 'Partially Trusted';
      case 'monitor':
        return 'Monitored';
      default:
        return 'Trusted';
    }
  }
  return 'Trusted';
}

/**
 * Build tooltip text for the badge.
 */
function buildTooltipText(match: VehicleMatch | null, showDetails: boolean): string {
  if (!match) {
    return showDetails
      ? 'Not registered in household vehicles'
      : 'Unknown vehicle';
  }

  const parts: string[] = [];
  parts.push(match.vehicle.description);

  if (showDetails) {
    if (match.owner) {
      parts.push(`Owner: ${match.owner.name}`);
    }
    const trustLabel = formatTrustLevel(match.vehicle.trusted, match.owner?.trusted_level);
    parts.push(trustLabel);
  }

  return parts.join(' | ');
}

// ============================================================================
// Component
// ============================================================================

/**
 * VehicleMatchBadge displays whether a plate matches a registered vehicle.
 *
 * @example
 * ```tsx
 * // Basic usage - shows Known/Unknown badge
 * <VehicleMatchBadge plateText="ABC123" />
 *
 * // With details in tooltip
 * <VehicleMatchBadge plateText="ABC123" showDetails />
 *
 * // Small size for table cells
 * <VehicleMatchBadge plateText="ABC123" size="sm" />
 * ```
 */
function VehicleMatchBadgeComponent({
  plateText,
  size = 'md',
  showDetails = false,
  className,
}: VehicleMatchBadgeProps): React.ReactElement {
  const { match, isLoading } = useVehicleMatchQuery(plateText);

  const sizeClasses = useMemo(() => getSizeClasses(size), [size]);
  const tooltipText = useMemo(
    () => buildTooltipText(match, showDetails),
    [match, showDetails]
  );

  const isKnown = match !== null;

  // Determine badge styling based on match status
  const badgeColors = isKnown
    ? 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/30'
    : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30';

  const Icon = isKnown ? Car : AlertTriangle;
  const label = isKnown ? 'Known' : 'Unknown';
  const ariaLabel = isKnown
    ? `Known vehicle: ${match?.vehicle.description || plateText}`
    : `Unknown vehicle: ${plateText}`;

  // Loading state
  if (isLoading) {
    return (
      <span
        className={clsx(
          'inline-flex items-center rounded-full border font-medium',
          'bg-gray-500/10 text-gray-500 dark:text-gray-400 border-gray-500/30',
          sizeClasses.badge,
          className
        )}
        data-testid="vehicle-match-loading"
        aria-label="Loading vehicle match status"
      >
        <Loader2 className={clsx(sizeClasses.icon, 'animate-spin')} aria-hidden="true" />
      </span>
    );
  }

  return (
    <span
      role="status"
      aria-label={ariaLabel}
      title={tooltipText}
      className={clsx(
        'inline-flex items-center rounded-full border font-medium',
        badgeColors,
        sizeClasses.badge,
        className
      )}
      data-testid="vehicle-match-badge"
      data-known={isKnown}
    >
      <Icon className={sizeClasses.icon} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

/**
 * Memoized VehicleMatchBadge for performance.
 */
export const VehicleMatchBadge = memo(VehicleMatchBadgeComponent);

export default VehicleMatchBadge;
