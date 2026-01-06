/**
 * Const Assertions and Literal Types for Type-Safe Constants
 *
 * This module provides type-safe constants using `as const` assertions,
 * ensuring that enum values are inferred as literal types rather than
 * their base types (string, number).
 *
 * Benefits:
 * - Compile-time exhaustiveness checking in switch statements
 * - Auto-completion for valid values
 * - No runtime overhead (constants are inlined)
 * - Prevents accidental typos in string literals
 *
 * @example
 * ```ts
 * // TypeScript will error if you forget to handle a risk level
 * function getRiskEmoji(level: RiskLevel): string {
 *   switch (level) {
 *     case 'low': return '[]';
 *     case 'medium': return '[]';
 *     case 'high': return '[]';
 *     case 'critical': return '[]';
 *     // TypeScript ensures all cases are handled
 *   }
 * }
 * ```
 */

// ============================================================================
// Risk Level Constants
// ============================================================================

/**
 * All valid risk level values.
 * Uses `as const` for literal type inference.
 */
export const RISK_LEVELS = ['low', 'medium', 'high', 'critical'] as const;

/**
 * Risk level type derived from the RISK_LEVELS constant.
 * This ensures the type and values are always in sync.
 */
export type RiskLevel = (typeof RISK_LEVELS)[number];

/**
 * Risk level configuration with thresholds and display properties.
 */
export const RISK_LEVEL_CONFIG = {
  low: {
    label: 'Low',
    color: '#76B900', // NVIDIA Green
    tailwindBg: 'bg-risk-low',
    tailwindText: 'text-risk-low',
    minScore: 0,
    maxScore: 29,
  },
  medium: {
    label: 'Medium',
    color: '#FFB800', // NVIDIA Yellow
    tailwindBg: 'bg-risk-medium',
    tailwindText: 'text-risk-medium',
    minScore: 30,
    maxScore: 59,
  },
  high: {
    label: 'High',
    color: '#E74856', // NVIDIA Red
    tailwindBg: 'bg-risk-high',
    tailwindText: 'text-risk-high',
    minScore: 60,
    maxScore: 84,
  },
  critical: {
    label: 'Critical',
    color: '#ef4444', // red-500
    tailwindBg: 'bg-red-500',
    tailwindText: 'text-red-500',
    minScore: 85,
    maxScore: 100,
  },
} as const;

/**
 * Type for risk level configuration.
 */
export type RiskLevelConfig = (typeof RISK_LEVEL_CONFIG)[RiskLevel];

// ============================================================================
// Health Status Constants
// ============================================================================

/**
 * All valid health status values.
 */
export const HEALTH_STATUSES = ['healthy', 'degraded', 'unhealthy'] as const;

/**
 * Health status type.
 */
export type HealthStatus = (typeof HEALTH_STATUSES)[number];

/**
 * Health status configuration with display properties.
 */
export const HEALTH_STATUS_CONFIG = {
  healthy: {
    label: 'Healthy',
    color: '#76B900',
    tailwindBg: 'bg-primary-500',
    tailwindText: 'text-primary-500',
    icon: 'check-circle',
  },
  degraded: {
    label: 'Degraded',
    color: '#FFB800',
    tailwindBg: 'bg-yellow-500',
    tailwindText: 'text-yellow-500',
    icon: 'alert-triangle',
  },
  unhealthy: {
    label: 'Unhealthy',
    color: '#E74856',
    tailwindBg: 'bg-red-500',
    tailwindText: 'text-red-500',
    icon: 'x-circle',
  },
} as const;

/**
 * Type for health status configuration.
 */
export type HealthStatusConfig = (typeof HEALTH_STATUS_CONFIG)[HealthStatus];

// ============================================================================
// Container Status Constants
// ============================================================================

/**
 * All valid container/service status values.
 */
export const CONTAINER_STATUSES = [
  'running',
  'starting',
  'unhealthy',
  'stopped',
  'error',
  'unknown',
] as const;

/**
 * Container status type.
 */
export type ContainerStatus = (typeof CONTAINER_STATUSES)[number];

/**
 * Container status configuration with display properties.
 */
export const CONTAINER_STATUS_CONFIG = {
  running: {
    label: 'Running',
    color: '#76B900',
    tailwindBg: 'bg-primary-500',
    tailwindDot: 'status-online',
  },
  starting: {
    label: 'Starting',
    color: '#FFB800',
    tailwindBg: 'bg-yellow-500',
    tailwindDot: 'status-warning',
  },
  unhealthy: {
    label: 'Unhealthy',
    color: '#E74856',
    tailwindBg: 'bg-red-500',
    tailwindDot: 'status-error',
  },
  stopped: {
    label: 'Stopped',
    color: '#707070',
    tailwindBg: 'bg-gray-500',
    tailwindDot: 'status-offline',
  },
  error: {
    label: 'Error',
    color: '#E74856',
    tailwindBg: 'bg-red-500',
    tailwindDot: 'status-error',
  },
  unknown: {
    label: 'Unknown',
    color: '#707070',
    tailwindBg: 'bg-gray-500',
    tailwindDot: 'status-offline',
  },
} as const;

/**
 * Type for container status configuration.
 */
export type ContainerStatusConfig = (typeof CONTAINER_STATUS_CONFIG)[ContainerStatus];

// ============================================================================
// Object Type Constants (Detection Classes)
// ============================================================================

/**
 * Primary object types detected by the AI models.
 */
export const OBJECT_TYPES = ['person', 'vehicle', 'animal', 'package'] as const;

/**
 * Object type.
 */
export type ObjectType = (typeof OBJECT_TYPES)[number];

/**
 * Object type configuration with display properties.
 */
export const OBJECT_TYPE_CONFIG = {
  person: {
    label: 'Person',
    icon: 'user',
    tailwindBg: 'bg-blue-500',
    tailwindText: 'text-blue-500',
  },
  vehicle: {
    label: 'Vehicle',
    icon: 'car',
    tailwindBg: 'bg-purple-500',
    tailwindText: 'text-purple-500',
  },
  animal: {
    label: 'Animal',
    icon: 'paw-print',
    tailwindBg: 'bg-amber-500',
    tailwindText: 'text-amber-500',
  },
  package: {
    label: 'Package',
    icon: 'package',
    tailwindBg: 'bg-teal-500',
    tailwindText: 'text-teal-500',
  },
} as const;

/**
 * Type for object type configuration.
 */
export type ObjectTypeConfig = (typeof OBJECT_TYPE_CONFIG)[ObjectType];

// ============================================================================
// Confidence Level Constants
// ============================================================================

/**
 * Confidence level classifications.
 */
export const CONFIDENCE_LEVELS = ['low', 'medium', 'high'] as const;

/**
 * Confidence level type.
 */
export type ConfidenceLevel = (typeof CONFIDENCE_LEVELS)[number];

/**
 * Confidence level thresholds.
 */
export const CONFIDENCE_THRESHOLDS = {
  low: { min: 0, max: 0.5 },
  medium: { min: 0.5, max: 0.8 },
  high: { min: 0.8, max: 1.0 },
} as const;

/**
 * Confidence level configuration.
 */
export const CONFIDENCE_LEVEL_CONFIG = {
  low: {
    label: 'Low',
    tailwindBg: 'bg-red-500/20',
    tailwindText: 'text-red-400',
  },
  medium: {
    label: 'Medium',
    tailwindBg: 'bg-yellow-500/20',
    tailwindText: 'text-yellow-400',
  },
  high: {
    label: 'High',
    tailwindBg: 'bg-primary-500/20',
    tailwindText: 'text-primary-400',
  },
} as const;

// ============================================================================
// WebSocket Message Type Constants
// ============================================================================

/**
 * All valid WebSocket message types.
 */
export const WS_MESSAGE_TYPES = [
  'event',
  'system_status',
  'service_status',
  'ping',
  'pong',
  'error',
] as const;

/**
 * WebSocket message type.
 */
export type WsMessageType = (typeof WS_MESSAGE_TYPES)[number];

// ============================================================================
// Day of Week Constants
// ============================================================================

/**
 * Days of the week for alert schedule configuration.
 */
export const DAYS_OF_WEEK = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
] as const;

/**
 * Day of week type.
 */
export type DayOfWeek = (typeof DAYS_OF_WEEK)[number];

/**
 * Day of week display labels.
 */
export const DAY_OF_WEEK_LABELS = {
  monday: 'Monday',
  tuesday: 'Tuesday',
  wednesday: 'Wednesday',
  thursday: 'Thursday',
  friday: 'Friday',
  saturday: 'Saturday',
  sunday: 'Sunday',
} as const satisfies Record<DayOfWeek, string>;

/**
 * Short day labels (3 letters).
 */
export const DAY_OF_WEEK_SHORT = {
  monday: 'Mon',
  tuesday: 'Tue',
  wednesday: 'Wed',
  thursday: 'Thu',
  friday: 'Fri',
  saturday: 'Sat',
  sunday: 'Sun',
} as const satisfies Record<DayOfWeek, string>;

// ============================================================================
// Alert Severity Constants
// ============================================================================

/**
 * Alert severity levels.
 */
export const ALERT_SEVERITIES = ['info', 'warning', 'critical'] as const;

/**
 * Alert severity type.
 */
export type AlertSeverity = (typeof ALERT_SEVERITIES)[number];

/**
 * Alert severity configuration.
 */
export const ALERT_SEVERITY_CONFIG = {
  info: {
    label: 'Info',
    color: '#3b82f6', // blue-500
    tailwindBg: 'bg-blue-500',
    tailwindText: 'text-blue-500',
    icon: 'info',
  },
  warning: {
    label: 'Warning',
    color: '#FFB800',
    tailwindBg: 'bg-yellow-500',
    tailwindText: 'text-yellow-500',
    icon: 'alert-triangle',
  },
  critical: {
    label: 'Critical',
    color: '#E74856',
    tailwindBg: 'bg-red-500',
    tailwindText: 'text-red-500',
    icon: 'alert-circle',
  },
} as const;

// ============================================================================
// Model Status Constants
// ============================================================================

/**
 * AI model status values from the Model Zoo.
 */
export const MODEL_STATUSES = ['loaded', 'unloaded', 'loading', 'error', 'disabled'] as const;

/**
 * Model status type.
 */
export type ModelStatus = (typeof MODEL_STATUSES)[number];

/**
 * Model status configuration.
 */
export const MODEL_STATUS_CONFIG = {
  loaded: {
    label: 'Loaded',
    color: '#76B900',
    tailwindBg: 'bg-primary-500',
    tailwindDot: 'status-online',
  },
  unloaded: {
    label: 'Unloaded',
    color: '#707070',
    tailwindBg: 'bg-gray-500',
    tailwindDot: 'status-offline',
  },
  loading: {
    label: 'Loading',
    color: '#FFB800',
    tailwindBg: 'bg-yellow-500',
    tailwindDot: 'status-warning',
  },
  error: {
    label: 'Error',
    color: '#E74856',
    tailwindBg: 'bg-red-500',
    tailwindDot: 'status-error',
  },
  disabled: {
    label: 'Disabled',
    color: '#707070',
    tailwindBg: 'bg-gray-600',
    tailwindDot: 'status-offline',
  },
} as const;

// ============================================================================
// Time Range Constants
// ============================================================================

/**
 * Time range options for historical data queries.
 */
export const TIME_RANGES = ['5m', '15m', '60m', '24h', '7d'] as const;

/**
 * Time range type.
 */
export type TimeRange = (typeof TIME_RANGES)[number];

/**
 * Time range configuration with duration in milliseconds.
 */
export const TIME_RANGE_CONFIG = {
  '5m': { label: '5 Minutes', durationMs: 5 * 60 * 1000 },
  '15m': { label: '15 Minutes', durationMs: 15 * 60 * 1000 },
  '60m': { label: '1 Hour', durationMs: 60 * 60 * 1000 },
  '24h': { label: '24 Hours', durationMs: 24 * 60 * 60 * 1000 },
  '7d': { label: '7 Days', durationMs: 7 * 24 * 60 * 60 * 1000 },
} as const;

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Type guard to check if a value is a valid risk level.
 */
export function isRiskLevel(value: unknown): value is RiskLevel {
  return typeof value === 'string' && RISK_LEVELS.includes(value as RiskLevel);
}

/**
 * Type guard to check if a value is a valid health status.
 */
export function isHealthStatus(value: unknown): value is HealthStatus {
  return typeof value === 'string' && HEALTH_STATUSES.includes(value as HealthStatus);
}

/**
 * Type guard to check if a value is a valid container status.
 */
export function isContainerStatus(value: unknown): value is ContainerStatus {
  return typeof value === 'string' && CONTAINER_STATUSES.includes(value as ContainerStatus);
}

/**
 * Type guard to check if a value is a valid object type.
 */
export function isObjectType(value: unknown): value is ObjectType {
  return typeof value === 'string' && OBJECT_TYPES.includes(value as ObjectType);
}

/**
 * Type guard to check if a value is a valid model status.
 */
export function isModelStatus(value: unknown): value is ModelStatus {
  return typeof value === 'string' && MODEL_STATUSES.includes(value as ModelStatus);
}

/**
 * Type guard to check if a value is a valid day of week.
 */
export function isDayOfWeek(value: unknown): value is DayOfWeek {
  return typeof value === 'string' && DAYS_OF_WEEK.includes(value as DayOfWeek);
}

/**
 * Get risk level from a numeric score.
 */
export function getRiskLevelFromScore(score: number): RiskLevel {
  if (score <= RISK_LEVEL_CONFIG.low.maxScore) return 'low';
  if (score <= RISK_LEVEL_CONFIG.medium.maxScore) return 'medium';
  if (score <= RISK_LEVEL_CONFIG.high.maxScore) return 'high';
  return 'critical';
}

/**
 * Get confidence level from a numeric score (0-1).
 */
export function getConfidenceLevelFromScore(score: number): ConfidenceLevel {
  if (score < CONFIDENCE_THRESHOLDS.medium.min) return 'low';
  if (score < CONFIDENCE_THRESHOLDS.high.min) return 'medium';
  return 'high';
}

// ============================================================================
// Exhaustiveness Checking Helper
// ============================================================================

/**
 * Helper for exhaustiveness checking in switch statements.
 * If all cases are handled, this function should never be called.
 * If a case is missing, TypeScript will error.
 *
 * @example
 * ```ts
 * function handleRiskLevel(level: RiskLevel): string {
 *   switch (level) {
 *     case 'low': return 'Safe';
 *     case 'medium': return 'Caution';
 *     case 'high': return 'Warning';
 *     case 'critical': return 'Danger';
 *     default:
 *       return assertNever(level);
 *   }
 * }
 * ```
 */
export function assertNever(value: never, message?: string): never {
  throw new Error(message ?? `Unexpected value: ${value as string}`);
}
