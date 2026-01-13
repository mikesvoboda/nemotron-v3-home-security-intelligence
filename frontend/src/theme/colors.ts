/**
 * Centralized Color Constants for WCAG 2.1 AA Compliance
 *
 * This module defines all semantic color constants used throughout the application.
 * Colors are designed to meet WCAG 2.1 AA contrast ratio requirements:
 * - 4.5:1 for normal text
 * - 3:1 for large text (18pt+ or 14pt+ bold)
 *
 * Usage:
 * 1. Import constants directly: `import { STATUS_COLORS } from '@/theme/colors'`
 * 2. Use utility functions: `getStatusColor('healthy')` returns Tremor color name
 * 3. Use Tailwind classes: `bg-status-healthy`, `text-status-warning`, etc.
 *
 * @see https://www.w3.org/WAI/WCAG21/quickref/#contrast-minimum
 */

// =============================================================================
// STATUS COLORS - For service/system status indicators
// =============================================================================

/**
 * Status color names for Tremor Badge components.
 * These map to Tremor's built-in color palette which has been audited for accessibility.
 *
 * - healthy/online: emerald (chosen over 'green' for better WCAG 4.5:1 contrast)
 * - warning/degraded: yellow
 * - error/offline: red
 * - inactive/unknown: gray
 */
export const STATUS_COLORS = {
  healthy: 'emerald',
  online: 'emerald',
  warning: 'yellow',
  degraded: 'yellow',
  error: 'red',
  offline: 'red',
  unhealthy: 'red',
  inactive: 'gray',
  unknown: 'gray',
} as const;

/**
 * Type for valid status color keys
 */
export type StatusColorKey = keyof typeof STATUS_COLORS;

/**
 * Type for Tremor color values used in status indicators
 */
export type TremorStatusColor = (typeof STATUS_COLORS)[StatusColorKey];

// =============================================================================
// STATUS TAILWIND CLASSES - For direct Tailwind CSS usage
// =============================================================================

/**
 * Background color classes for status indicators.
 * Uses 500 shade for solid backgrounds with sufficient contrast.
 */
export const STATUS_BG_CLASSES = {
  healthy: 'bg-emerald-500',
  online: 'bg-emerald-500',
  warning: 'bg-yellow-500',
  degraded: 'bg-yellow-500',
  error: 'bg-red-500',
  offline: 'bg-red-500',
  unhealthy: 'bg-red-500',
  inactive: 'bg-gray-500',
  unknown: 'bg-gray-500',
} as const;

/**
 * Light background color classes for status cards/containers.
 * Uses 10% opacity for subtle backgrounds while maintaining text contrast.
 */
export const STATUS_BG_LIGHT_CLASSES = {
  healthy: 'bg-emerald-500/10',
  online: 'bg-emerald-500/10',
  warning: 'bg-yellow-500/10',
  degraded: 'bg-yellow-500/10',
  error: 'bg-red-500/10',
  offline: 'bg-red-500/10',
  unhealthy: 'bg-red-500/10',
  inactive: 'bg-gray-500/10',
  unknown: 'bg-gray-500/10',
} as const;

/**
 * Text color classes for status indicators.
 * Uses 400 shade on dark backgrounds for WCAG 4.5:1 contrast.
 */
export const STATUS_TEXT_CLASSES = {
  healthy: 'text-emerald-400',
  online: 'text-emerald-400',
  warning: 'text-yellow-400',
  degraded: 'text-yellow-400',
  error: 'text-red-400',
  offline: 'text-red-400',
  unhealthy: 'text-red-400',
  inactive: 'text-gray-400',
  unknown: 'text-gray-400',
} as const;

/**
 * Border color classes for status indicators.
 * Uses 30% opacity for subtle borders that complement the status.
 */
export const STATUS_BORDER_CLASSES = {
  healthy: 'border-emerald-500/30',
  online: 'border-emerald-500/30',
  warning: 'border-yellow-500/30',
  degraded: 'border-yellow-500/30',
  error: 'border-red-500/30',
  offline: 'border-red-500/30',
  unhealthy: 'border-red-500/30',
  inactive: 'border-gray-500/30',
  unknown: 'border-gray-500/30',
} as const;

// =============================================================================
// HEX COLOR VALUES - For programmatic usage (charts, canvas, etc.)
// =============================================================================

/**
 * Status colors as hex values for use in charts, Canvas APIs, etc.
 * These colors meet WCAG 4.5:1 contrast requirements on dark backgrounds (#1A1A1A).
 */
export const STATUS_HEX_COLORS = {
  healthy: '#10B981', // emerald-500
  online: '#10B981',
  warning: '#F59E0B', // yellow-500 (amber)
  degraded: '#F59E0B',
  error: '#EF4444', // red-500
  offline: '#EF4444',
  unhealthy: '#EF4444',
  inactive: '#6B7280', // gray-500
  unknown: '#6B7280',
} as const;

// =============================================================================
// QUEUE/PIPELINE COLORS - For monitoring dashboards
// =============================================================================

/**
 * Queue depth status colors based on threshold percentage.
 * - empty (0): gray - no items in queue
 * - normal (0-50% of threshold): emerald - healthy processing
 * - elevated (50-100% of threshold): yellow - approaching capacity
 * - critical (>100% of threshold): red - queue backing up
 */
export const QUEUE_STATUS_COLORS = {
  empty: 'gray',
  normal: 'emerald',
  elevated: 'yellow',
  critical: 'red',
} as const;

export type QueueStatusKey = keyof typeof QUEUE_STATUS_COLORS;

/**
 * Latency status colors based on threshold percentage.
 * - fast (0-50% of threshold): emerald - excellent performance
 * - normal (50-100% of threshold): yellow - acceptable performance
 * - slow (>100% of threshold): red - performance degradation
 * - unknown: gray - no data available
 */
export const LATENCY_STATUS_COLORS = {
  fast: 'emerald',
  normal: 'yellow',
  slow: 'red',
  unknown: 'gray',
} as const;

export type LatencyStatusKey = keyof typeof LATENCY_STATUS_COLORS;

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Get Tremor Badge color for a status value.
 * Supports common status strings and normalizes them to Tremor color names.
 *
 * @param status - Status string (healthy, online, warning, etc.)
 * @returns Tremor color name for use in Badge components
 *
 * @example
 * ```tsx
 * <Badge color={getStatusColor('healthy')}>Healthy</Badge>
 * <Badge color={getStatusColor('degraded')}>Degraded</Badge>
 * ```
 */
export function getStatusColor(status: string): TremorStatusColor {
  const normalizedStatus = status.toLowerCase().trim();

  // Direct mapping
  if (normalizedStatus in STATUS_COLORS) {
    return STATUS_COLORS[normalizedStatus as StatusColorKey];
  }

  // Common aliases
  const aliases: Record<string, StatusColorKey> = {
    ok: 'healthy',
    success: 'healthy',
    active: 'online',
    running: 'online',
    warn: 'warning',
    caution: 'warning',
    restarting: 'degraded',
    fail: 'error',
    failed: 'error',
    critical: 'error',
    down: 'offline',
    stopped: 'inactive',
    disabled: 'inactive',
    pending: 'unknown',
  };

  if (normalizedStatus in aliases) {
    return STATUS_COLORS[aliases[normalizedStatus]];
  }

  // Default to gray for unknown statuses
  return 'gray';
}

/**
 * Get Tailwind CSS classes for a status value.
 * Returns an object with bg, text, and border classes.
 *
 * @param status - Status string (healthy, online, warning, etc.)
 * @returns Object with bgClass, bgLightClass, textClass, and borderClass
 *
 * @example
 * ```tsx
 * const classes = getStatusClasses('healthy');
 * <div className={`${classes.bgLightClass} ${classes.borderClass} border`}>
 *   <span className={classes.textClass}>Healthy</span>
 * </div>
 * ```
 */
export function getStatusClasses(status: string): {
  bgClass: string;
  bgLightClass: string;
  textClass: string;
  borderClass: string;
} {
  const normalizedStatus = status.toLowerCase().trim();

  // Find the canonical status key
  let statusKey: StatusColorKey = 'unknown';

  if (normalizedStatus in STATUS_COLORS) {
    statusKey = normalizedStatus as StatusColorKey;
  } else {
    // Check aliases
    const aliases: Record<string, StatusColorKey> = {
      ok: 'healthy',
      success: 'healthy',
      active: 'online',
      running: 'online',
      warn: 'warning',
      caution: 'warning',
      restarting: 'degraded',
      fail: 'error',
      failed: 'error',
      critical: 'error',
      down: 'offline',
      stopped: 'inactive',
      disabled: 'inactive',
      pending: 'unknown',
    };

    if (normalizedStatus in aliases) {
      statusKey = aliases[normalizedStatus];
    }
  }

  return {
    bgClass: STATUS_BG_CLASSES[statusKey],
    bgLightClass: STATUS_BG_LIGHT_CLASSES[statusKey],
    textClass: STATUS_TEXT_CLASSES[statusKey],
    borderClass: STATUS_BORDER_CLASSES[statusKey],
  };
}

/**
 * Get hex color value for a status.
 *
 * @param status - Status string
 * @returns Hex color string
 *
 * @example
 * ```tsx
 * // For use in charts or Canvas
 * const color = getStatusHexColor('healthy'); // '#10B981'
 * ```
 */
export function getStatusHexColor(status: string): string {
  const normalizedStatus = status.toLowerCase().trim();

  if (normalizedStatus in STATUS_HEX_COLORS) {
    return STATUS_HEX_COLORS[normalizedStatus as StatusColorKey];
  }

  // Check aliases
  const aliases: Record<string, StatusColorKey> = {
    ok: 'healthy',
    success: 'healthy',
    active: 'online',
    running: 'online',
    warn: 'warning',
    caution: 'warning',
    restarting: 'degraded',
    fail: 'error',
    failed: 'error',
    critical: 'error',
    down: 'offline',
    stopped: 'inactive',
    disabled: 'inactive',
    pending: 'unknown',
  };

  if (normalizedStatus in aliases) {
    return STATUS_HEX_COLORS[aliases[normalizedStatus]];
  }

  return STATUS_HEX_COLORS.unknown;
}

/**
 * Get queue status color based on depth relative to threshold.
 *
 * @param depth - Current queue depth
 * @param threshold - Warning threshold
 * @returns Tremor color name
 *
 * @example
 * ```tsx
 * <Badge color={getQueueStatusColor(5, 10)}>5 items</Badge>
 * ```
 */
export function getQueueStatusColor(
  depth: number,
  threshold: number
): (typeof QUEUE_STATUS_COLORS)[QueueStatusKey] {
  if (depth === 0) return QUEUE_STATUS_COLORS.empty;
  if (depth <= threshold / 2) return QUEUE_STATUS_COLORS.normal;
  if (depth <= threshold) return QUEUE_STATUS_COLORS.elevated;
  return QUEUE_STATUS_COLORS.critical;
}

/**
 * Get latency status color based on value relative to threshold.
 *
 * @param ms - Latency in milliseconds (null/undefined = unknown)
 * @param threshold - Warning threshold in milliseconds
 * @returns Tremor color name
 *
 * @example
 * ```tsx
 * <Badge color={getLatencyStatusColor(500, 1000)}>500ms</Badge>
 * ```
 */
export function getLatencyStatusColor(
  ms: number | null | undefined,
  threshold: number
): (typeof LATENCY_STATUS_COLORS)[LatencyStatusKey] {
  if (ms === null || ms === undefined) return LATENCY_STATUS_COLORS.unknown;
  if (ms < threshold / 2) return LATENCY_STATUS_COLORS.fast;
  if (ms < threshold) return LATENCY_STATUS_COLORS.normal;
  return LATENCY_STATUS_COLORS.slow;
}
