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
 * Get the color hex code for a given risk level
 * @param level - Risk level category
 * @returns Hex color code
 */
export function getRiskColor(level: RiskLevel): string {
  const colors: Record<RiskLevel, string> = {
    low: '#76B900', // NVIDIA Green
    medium: '#FFB800', // NVIDIA Yellow
    high: '#E74856', // NVIDIA Red
    critical: '#ef4444', // red-500
  };

  return colors[level];
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
