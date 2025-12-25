/**
 * Risk level type definition
 */
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

/**
 * Convert a numeric risk score (0-100) to a categorical risk level
 * @param score - Numeric risk score between 0-100
 * @returns Risk level category
 */
export function getRiskLevel(score: number): RiskLevel {
  if (score < 0 || score > 100) {
    throw new Error('Risk score must be between 0 and 100');
  }

  if (score <= 25) return 'low';
  if (score <= 50) return 'medium';
  if (score <= 75) return 'high';
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
