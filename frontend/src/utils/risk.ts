/**
 * Risk level type definition
 */
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

/**
 * Risk score thresholds matching backend SeverityService defaults.
 *
 * These thresholds are configurable on the backend via environment variables:
 * - SEVERITY_LOW_MAX (default: 29)
 * - SEVERITY_MEDIUM_MAX (default: 59)
 * - SEVERITY_HIGH_MAX (default: 84)
 *
 * For dynamic threshold configuration, fetch from: GET /api/system/severity
 * The API returns current thresholds and all severity level definitions.
 */
export const RISK_THRESHOLDS = {
  LOW_MAX: 29, // 0-29 = Low
  MEDIUM_MAX: 59, // 30-59 = Medium
  HIGH_MAX: 84, // 60-84 = High
  // 85-100 = Critical
} as const;

/**
 * Convert a numeric risk score (0-100) to a categorical risk level
 * @param score - Numeric risk score between 0-100
 * @returns Risk level category
 *
 * Note: Uses default thresholds. For dynamic threshold support,
 * fetch thresholds from GET /api/system/severity and use getRiskLevelWithThresholds.
 */
export function getRiskLevel(score: number): RiskLevel {
  if (score < 0 || score > 100) {
    throw new Error('Risk score must be between 0 and 100');
  }

  // Thresholds match backend defaults (see backend/core/config.py):
  // LOW: 0-29, MEDIUM: 30-59, HIGH: 60-84, CRITICAL: 85-100
  if (score <= RISK_THRESHOLDS.LOW_MAX) return 'low';
  if (score <= RISK_THRESHOLDS.MEDIUM_MAX) return 'medium';
  if (score <= RISK_THRESHOLDS.HIGH_MAX) return 'high';
  return 'critical';
}

/**
 * Convert a numeric risk score to a categorical risk level using custom thresholds.
 * Use this when you've fetched dynamic thresholds from the backend API.
 *
 * @param score - Numeric risk score between 0-100
 * @param thresholds - Custom thresholds object with low_max, medium_max, high_max
 * @returns Risk level category
 */
export function getRiskLevelWithThresholds(
  score: number,
  thresholds: { low_max: number; medium_max: number; high_max: number }
): RiskLevel {
  if (score < 0 || score > 100) {
    throw new Error('Risk score must be between 0 and 100');
  }

  if (score <= thresholds.low_max) return 'low';
  if (score <= thresholds.medium_max) return 'medium';
  if (score <= thresholds.high_max) return 'high';
  return 'critical';
}

/**
 * Get the color hex code for a given risk level using Tailwind CSS standard severity colors.
 * These colors provide clear visual differentiation between severity levels and work
 * well in both light and dark themes.
 *
 * @param level - Risk level category
 * @returns Hex color code matching Tailwind CSS color palette
 *
 * Color mapping:
 * - Critical (85-100): Red (#ef4444 / red-500)
 * - High (60-84): Orange (#f97316 / orange-500)
 * - Medium (30-59): Yellow (#eab308 / yellow-500)
 * - Low (0-29): Green (#22c55e / green-500)
 */
export function getRiskColor(level: RiskLevel): string {
  const colors: Record<RiskLevel, string> = {
    low: '#22c55e', // green-500 - Safe/Normal
    medium: '#eab308', // yellow-500 - Warning/Caution
    high: '#f97316', // orange-500 - Elevated risk
    critical: '#ef4444', // red-500 - Critical/Emergency
  };

  return colors[level];
}

/**
 * Get the Tailwind CSS background color class for a given risk level.
 * Useful for applying consistent severity-based styling using Tailwind classes.
 *
 * @param level - Risk level category
 * @returns Tailwind CSS background color class
 */
export function getRiskBgClass(level: RiskLevel): string {
  const classes: Record<RiskLevel, string> = {
    low: 'bg-green-500',
    medium: 'bg-yellow-500',
    high: 'bg-orange-500',
    critical: 'bg-red-500',
  };

  return classes[level];
}

/**
 * Get the Tailwind CSS text color class for a given risk level.
 * Useful for applying consistent severity-based text styling using Tailwind classes.
 *
 * @param level - Risk level category
 * @returns Tailwind CSS text color class
 */
export function getRiskTextClass(level: RiskLevel): string {
  const classes: Record<RiskLevel, string> = {
    low: 'text-green-500',
    medium: 'text-yellow-500',
    high: 'text-orange-500',
    critical: 'text-red-500',
  };

  return classes[level];
}

/**
 * Get a human-readable label for a risk level
 * @param level - Risk level category
 * @returns Capitalized label string
 */
export function getRiskLabel(level: RiskLevel): string {
  const labels: Record<RiskLevel, string> = {
    low: 'Low',
    medium: 'Medium',
    high: 'High',
    critical: 'Critical',
  };

  return labels[level];
}
