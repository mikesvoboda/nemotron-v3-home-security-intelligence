/**
 * SeverityBadge Component
 *
 * Displays a severity indicator badge with icon, label, and optional count.
 * Uses severity colors from severityCalculator for visual consistency.
 *
 * @see NEM-2926
 */

import { AlertCircle, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';

import type { SeverityLevel } from '@/utils/severityCalculator';

import { getSeverityConfig } from '@/utils/severityCalculator';

// ============================================================================
// Types
// ============================================================================

export interface SeverityBadgeProps {
  /** Severity level to display */
  level: SeverityLevel;
  /** Event count to show (optional) */
  count?: number;
  /** Whether to show pulsing animation (for critical alerts) */
  pulsing?: boolean;
  /** Size variant */
  size?: 'sm' | 'md';
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Icon Mapping
// ============================================================================

/**
 * Get the appropriate icon component for a severity level.
 * - clear/low: CheckCircle (positive indicator)
 * - medium: AlertCircle (attention needed)
 * - high: AlertTriangle (warning)
 * - critical: XCircle (urgent action required)
 */
function getSeverityIcon(level: SeverityLevel) {
  switch (level) {
    case 'clear':
    case 'low':
      return CheckCircle;
    case 'medium':
      return AlertCircle;
    case 'high':
      return AlertTriangle;
    case 'critical':
      return XCircle;
    default:
      return CheckCircle;
  }
}

// ============================================================================
// Color Mapping
// ============================================================================

/**
 * Get CSS color classes for severity level.
 * Returns background and text color classes.
 */
function getSeverityColorClasses(level: SeverityLevel): {
  bg: string;
  text: string;
  border: string;
} {
  switch (level) {
    case 'clear':
      return {
        bg: 'bg-emerald-500/10',
        text: 'text-emerald-400',
        border: 'border-emerald-500/30',
      };
    case 'low':
      return {
        bg: 'bg-green-500/10',
        text: 'text-green-400',
        border: 'border-green-500/30',
      };
    case 'medium':
      return {
        bg: 'bg-yellow-500/10',
        text: 'text-yellow-400',
        border: 'border-yellow-500/30',
      };
    case 'high':
      return {
        bg: 'bg-orange-500/10',
        text: 'text-orange-400',
        border: 'border-orange-500/30',
      };
    case 'critical':
      return {
        bg: 'bg-red-500/10',
        text: 'text-red-400',
        border: 'border-red-500/30',
      };
    default:
      return {
        bg: 'bg-gray-500/10',
        text: 'text-gray-400',
        border: 'border-gray-500/30',
      };
  }
}

// ============================================================================
// Size Configuration
// ============================================================================

/**
 * Get size-specific classes for the badge.
 */
function getSizeClasses(size: 'sm' | 'md'): {
  badge: string;
  icon: string;
  text: string;
} {
  if (size === 'sm') {
    return {
      badge: 'px-2 py-0.5 gap-1',
      icon: 'h-3 w-3',
      text: 'text-xs',
    };
  }
  // md (default)
  return {
    badge: 'px-2.5 py-1 gap-1.5',
    icon: 'h-4 w-4',
    text: 'text-sm',
  };
}

// ============================================================================
// Component
// ============================================================================

/**
 * SeverityBadge displays a visual indicator for severity levels.
 *
 * Features:
 * - Appropriate icons for each severity level
 * - Color-coded backgrounds and text
 * - Optional event count display
 * - Optional pulsing animation for critical alerts
 * - Two size variants (sm, md)
 * - Uppercase label with letter-spacing
 *
 * @example
 * ```tsx
 * // Basic usage
 * <SeverityBadge level="high" />
 *
 * // With count
 * <SeverityBadge level="critical" count={5} />
 *
 * // With pulsing animation
 * <SeverityBadge level="critical" count={3} pulsing />
 *
 * // Small size
 * <SeverityBadge level="medium" size="sm" />
 * ```
 */
export function SeverityBadge({
  level,
  count,
  pulsing = false,
  size = 'md',
  className = '',
}: SeverityBadgeProps) {
  const Icon = getSeverityIcon(level);
  const colors = getSeverityColorClasses(level);
  const sizes = getSizeClasses(size);
  const config = getSeverityConfig(level);

  // Build label text
  const labelText = config.label.toUpperCase();

  // Determine if animation should apply
  const shouldPulse = pulsing && level === 'critical';

  // Build class string
  const badgeClasses = [
    'inline-flex items-center rounded-full border font-medium tracking-wide',
    colors.bg,
    colors.text,
    colors.border,
    sizes.badge,
    sizes.text,
    shouldPulse ? 'animate-pulse-critical' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <span
      className={badgeClasses}
      role="status"
      aria-label={
        count !== undefined
          ? `Severity: ${config.label}, ${count} ${count === 1 ? 'event' : 'events'}`
          : `Severity: ${config.label}`
      }
      data-testid="severity-badge"
      data-severity={level}
    >
      <Icon className={sizes.icon} aria-hidden="true" />
      <span>{labelText}</span>
      {count !== undefined && (
        <span className="ml-0.5 font-semibold" data-testid="severity-badge-count">
          ({count})
        </span>
      )}
    </span>
  );
}

export default SeverityBadge;
