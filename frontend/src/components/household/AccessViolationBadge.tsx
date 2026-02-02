/**
 * AccessViolationBadge - Badge indicating schedule violation
 *
 * Displays a visual warning badge when a detection occurs outside
 * of the member's allowed schedule hours.
 *
 * @module components/household/AccessViolationBadge
 * @see NEM-4863 Phase 3 - Access Violations
 */

import { AlertTriangle, Clock } from 'lucide-react';

import type { WeeklySchedule, DayOfWeek } from '../../hooks/useHouseholdApi';

// ============================================================================
// Constants
// ============================================================================

const DAY_MAPPING: Record<number, DayOfWeek> = {
  0: 'sunday',
  1: 'monday',
  2: 'tuesday',
  3: 'wednesday',
  4: 'thursday',
  5: 'friday',
  6: 'saturday',
};

// ============================================================================
// Types
// ============================================================================

interface AccessViolationBadgeProps {
  /** Detection timestamp */
  detectedAt: string | Date;
  /** Member's allowed schedule */
  schedule: WeeklySchedule | null | undefined;
  /** Whether to show detailed tooltip */
  showTooltip?: boolean;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Check if a timestamp is within the allowed schedule.
 */

export function isWithinSchedule(
  timestamp: string | Date,
  schedule: WeeklySchedule | null | undefined
): boolean {
  if (!schedule) return true; // No schedule means always allowed

  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
  const dayIndex = date.getDay();
  const hour = date.getHours();
  const day = DAY_MAPPING[dayIndex];

  return schedule[day].includes(hour);
}

/**
 * Format a date for display in violation tooltip.
 */
function formatViolationTime(timestamp: string | Date): string {
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
  const dayName = date.toLocaleDateString('en-US', { weekday: 'long' });
  const hour = date.getHours();
  const ampm = hour >= 12 ? 'pm' : 'am';
  const hour12 = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
  return `${dayName} at ${hour12}${ampm}`;
}

// ============================================================================
// Component
// ============================================================================

export default function AccessViolationBadge({
  detectedAt,
  schedule,
  showTooltip = true,
  size = 'sm',
}: AccessViolationBadgeProps) {
  // Check if this is a violation
  const isViolation = !isWithinSchedule(detectedAt, schedule);

  // Don't render if not a violation
  if (!isViolation) {
    return null;
  }

  // Size classes
  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-xs',
    md: 'px-2 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  };

  const iconSizes = {
    sm: 'h-3 w-3',
    md: 'h-4 w-4',
    lg: 'h-5 w-5',
  };

  const tooltipText = showTooltip
    ? `Schedule violation: Detected ${formatViolationTime(detectedAt)}`
    : undefined;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 ${sizeClasses[size]}`}
      title={tooltipText}
      role="status"
      aria-label="Schedule violation"
    >
      <AlertTriangle className={iconSizes[size]} aria-hidden="true" />
      <span>Outside Schedule</span>
    </span>
  );
}

/**
 * Compact badge variant showing just an icon.
 */
export function AccessViolationIcon({
  detectedAt,
  schedule,
}: {
  detectedAt: string | Date;
  schedule: WeeklySchedule | null | undefined;
}) {
  const isViolation = !isWithinSchedule(detectedAt, schedule);

  if (!isViolation) {
    return null;
  }

  return (
    <span
      className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-yellow-500/20 text-yellow-400"
      title={`Schedule violation: Detected ${formatViolationTime(detectedAt)}`}
      role="status"
      aria-label="Schedule violation"
    >
      <Clock className="h-3 w-3" aria-hidden="true" />
    </span>
  );
}
