/**
 * ApproachVectorIndicator - Display approach vector on detection cards (NEM-5024 Phase 6)
 *
 * This component displays approach vector information on detection/event cards:
 * - Directional arrow showing the approach direction
 * - Zone name being approached
 * - ETA countdown
 * - Urgency-based color coding (red/yellow/green)
 *
 * Used to surface existing backend approach vector calculations in the UI.
 *
 * @module components/common/ApproachVectorIndicator
 * @see NEM-5024 Hidden Backend Exposure Epic
 *
 * @example
 * ```tsx
 * <ApproachVectorIndicator
 *   isApproaching={true}
 *   directionDegrees={45}
 *   speedNormalized={0.05}
 *   estimatedArrivalSeconds={5}
 *   zoneName="Front Door"
 *   urgency="imminent"
 * />
 * ```
 */

import { clsx } from 'clsx';
import { ArrowUp } from 'lucide-react';
import { memo } from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Urgency levels based on ETA to zone.
 * Matches backend ApproachUrgency enum.
 */
export type ApproachUrgency = 'imminent' | 'approaching' | 'distant' | 'not_approaching';

/**
 * Size variants for the indicator.
 */
export type ApproachVectorSize = 'sm' | 'md' | 'lg';

/**
 * Props for the ApproachVectorIndicator component.
 */
export interface ApproachVectorIndicatorProps {
  /** Whether the entity is moving toward the zone */
  isApproaching: boolean;
  /** Direction of movement in degrees (0=up, 90=right, 180=down, 270=left) */
  directionDegrees: number;
  /** Speed of movement in normalized units per second */
  speedNormalized: number;
  /** Estimated time to reach zone in seconds (null if not approaching) */
  estimatedArrivalSeconds: number | null;
  /** Name of the zone being approached */
  zoneName: string;
  /** Urgency level based on ETA */
  urgency: ApproachUrgency;
  /** Size variant */
  size?: ApproachVectorSize;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format ETA as a human-readable countdown.
 *
 * @param seconds - ETA in seconds (or null)
 * @returns Formatted string like "5s", "Now", "<1s", or null
 */
function formatETA(seconds: number | null): string | null {
  if (seconds === null) return null;
  if (seconds === 0) return 'Now';
  if (seconds < 1) return '<1s';
  return `${Math.round(seconds)}s`;
}

/**
 * Get urgency-based border color class.
 *
 * @param urgency - Urgency level
 * @returns Tailwind border color class
 */
function getUrgencyBorderClass(urgency: ApproachUrgency): string {
  switch (urgency) {
    case 'imminent':
      return 'border-red-500';
    case 'approaching':
      return 'border-amber-500';
    case 'distant':
      return 'border-green-500';
    case 'not_approaching':
    default:
      return 'border-gray-500';
  }
}

/**
 * Get urgency-based background color class.
 *
 * @param urgency - Urgency level
 * @returns Tailwind background color class
 */
function getUrgencyBgClass(urgency: ApproachUrgency): string {
  switch (urgency) {
    case 'imminent':
      return 'bg-red-500/10';
    case 'approaching':
      return 'bg-amber-500/10';
    case 'distant':
      return 'bg-green-500/10';
    case 'not_approaching':
    default:
      return 'bg-gray-500/10';
  }
}

/**
 * Get urgency-based text color class.
 *
 * @param urgency - Urgency level
 * @returns Tailwind text color class
 */
function getUrgencyTextClass(urgency: ApproachUrgency): string {
  switch (urgency) {
    case 'imminent':
      return 'text-red-400';
    case 'approaching':
      return 'text-amber-400';
    case 'distant':
      return 'text-green-400';
    case 'not_approaching':
    default:
      return 'text-gray-400';
  }
}

/**
 * Get urgency-based icon color class.
 *
 * @param urgency - Urgency level
 * @returns Tailwind text color class for icon
 */
function getUrgencyIconClass(urgency: ApproachUrgency): string {
  switch (urgency) {
    case 'imminent':
      return 'text-red-500';
    case 'approaching':
      return 'text-amber-500';
    case 'distant':
      return 'text-green-500';
    case 'not_approaching':
    default:
      return 'text-gray-500';
  }
}

/**
 * Get size-based classes.
 *
 * @param size - Size variant
 * @returns Object with Tailwind classes for different elements
 */
function getSizeClasses(size: ApproachVectorSize): {
  container: string;
  icon: string;
  text: string;
} {
  switch (size) {
    case 'sm':
      return {
        container: 'px-2 py-1 gap-1.5',
        icon: 'h-3 w-3',
        text: 'text-xs',
      };
    case 'lg':
      return {
        container: 'px-4 py-2.5 gap-3',
        icon: 'h-5 w-5',
        text: 'text-base',
      };
    case 'md':
    default:
      return {
        container: 'px-3 py-1.5 gap-2',
        icon: 'h-4 w-4',
        text: 'text-sm',
      };
  }
}

// ============================================================================
// Component
// ============================================================================

/**
 * ApproachVectorIndicator component.
 *
 * Displays approach vector information with directional arrow, zone name,
 * and ETA countdown. Uses urgency-based color coding.
 *
 * @param props - Component props
 * @returns Rendered indicator or null if not approaching
 */
function ApproachVectorIndicatorComponent({
  isApproaching,
  directionDegrees,
  speedNormalized: _speedNormalized,
  estimatedArrivalSeconds,
  zoneName,
  urgency,
  size = 'md',
  className,
}: ApproachVectorIndicatorProps) {
  // Don't render if not approaching
  if (!isApproaching) {
    return null;
  }

  const etaText = formatETA(estimatedArrivalSeconds);
  const sizeClasses = getSizeClasses(size);

  // Build aria-label for accessibility
  const ariaLabel = etaText
    ? `Approaching ${zoneName}, estimated arrival in ${estimatedArrivalSeconds === 0 ? 'now' : `${Math.round(estimatedArrivalSeconds ?? 0)} seconds`}`
    : `Approaching ${zoneName}`;

  return (
    <div
      data-testid="approach-vector-indicator"
      className={clsx(
        // Base styles
        'inline-flex items-center rounded-lg border',
        // Urgency-based styles
        getUrgencyBorderClass(urgency),
        getUrgencyBgClass(urgency),
        // Size-based styles
        sizeClasses.container,
        sizeClasses.text,
        // Animation for imminent
        urgency === 'imminent' && 'animate-pulse',
        // Custom className
        className
      )}
      aria-label={ariaLabel}
      role="status"
    >
      {/* Directional Arrow */}
      <span
        data-testid="direction-arrow"
        className={clsx('flex-shrink-0', getUrgencyIconClass(urgency))}
        style={{ transform: `rotate(${directionDegrees}deg)` }}
        aria-hidden="true"
      >
        <ArrowUp className={sizeClasses.icon} />
      </span>

      {/* Text Content */}
      <span className={clsx('flex items-center gap-1.5', getUrgencyTextClass(urgency))}>
        <span className="font-medium">
          Approaching <span className="truncate max-w-[120px] inline-block align-bottom">{zoneName}</span>
        </span>
        {etaText && (
          <>
            <span className="text-gray-500">-</span>
            <span className="font-semibold whitespace-nowrap">ETA: {etaText}</span>
          </>
        )}
      </span>
    </div>
  );
}

/**
 * Memoized ApproachVectorIndicator for performance.
 */
export const ApproachVectorIndicator = memo(ApproachVectorIndicatorComponent);

export default ApproachVectorIndicator;
