/**
 * Severity color configuration for event cards.
 *
 * Provides visual distinction between risk levels through:
 * - Background tints (very subtle, WCAG AA compliant)
 * - Left border colors
 * - Glow effects for critical events
 * - Optional pulse animation for critical events
 */

import { getRiskLevel, type RiskLevel } from './risk';

/**
 * Severity level type (alias for RiskLevel for semantic clarity)
 */
export type SeverityLevel = RiskLevel;

/**
 * Configuration for severity-based styling
 */
export interface SeverityConfig {
  /** Severity level */
  level: SeverityLevel;
  /** Background tint color (rgba format for transparency) */
  bgTint: string;
  /** Left border color (hex format) */
  borderColor: string;
  /** Box shadow for glow effect (empty string if none) */
  glowShadow: string;
  /** Whether to apply pulse animation */
  shouldPulse: boolean;
  /** Tailwind CSS class for background */
  bgClass: string;
  /** Tailwind CSS class for border-left color */
  borderClass: string;
  /** Tailwind CSS class for glow effect */
  glowClass: string;
  /** Tailwind CSS class for pulse animation */
  pulseClass: string;
}

/**
 * Severity color constants
 *
 * Background tints are very subtle (4-8% opacity) to maintain WCAG AA contrast.
 * Border colors use standard Tailwind severity colors.
 */
export const SEVERITY_COLORS = {
  critical: {
    bgTint: 'rgba(239, 68, 68, 0.08)', // red-500 at 8% opacity
    borderColor: '#EF4444', // red-500
    glowShadow: '0 0 8px rgba(239, 68, 68, 0.3)',
  },
  high: {
    bgTint: 'rgba(249, 115, 22, 0.06)', // orange-500 at 6% opacity
    borderColor: '#F97316', // orange-500
    glowShadow: '',
  },
  medium: {
    bgTint: 'rgba(234, 179, 8, 0.04)', // yellow-500 at 4% opacity
    borderColor: '#EAB308', // yellow-500
    glowShadow: '',
  },
  low: {
    bgTint: 'transparent',
    borderColor: '#76B900', // NVIDIA green (primary)
    glowShadow: '',
  },
} as const;

/**
 * Severity thresholds (matching risk.ts for consistency)
 * - Critical: >= 80
 * - High: 60-79
 * - Medium: 30-59
 * - Low: < 30
 *
 * Note: These thresholds differ slightly from the backend RISK_THRESHOLDS
 * (which uses 85 for critical) to provide earlier visual warning for
 * events approaching critical status.
 */
export const SEVERITY_THRESHOLDS = {
  CRITICAL_MIN: 80,
  HIGH_MIN: 60,
  MEDIUM_MIN: 30,
} as const;

/**
 * Get the severity level from a risk score.
 *
 * Uses slightly different thresholds than getRiskLevel for visual emphasis:
 * - Critical: >= 80 (vs 85 in risk.ts)
 * - High: 60-79 (same as risk.ts)
 * - Medium: 30-59 (same as risk.ts)
 * - Low: < 30 (same as risk.ts)
 *
 * @param riskScore - Numeric risk score between 0-100
 * @returns Severity level category
 */
export function getSeverityLevel(riskScore: number): SeverityLevel {
  if (riskScore < 0 || riskScore > 100) {
    throw new Error('Risk score must be between 0 and 100');
  }

  if (riskScore >= SEVERITY_THRESHOLDS.CRITICAL_MIN) return 'critical';
  if (riskScore >= SEVERITY_THRESHOLDS.HIGH_MIN) return 'high';
  if (riskScore >= SEVERITY_THRESHOLDS.MEDIUM_MIN) return 'medium';
  return 'low';
}

/**
 * Get the full severity configuration for a given risk score.
 *
 * Returns all styling information needed for severity-tinted event cards:
 * - Background tint colors
 * - Border colors
 * - Glow effects (critical only)
 * - Pulse animation flag (critical only)
 * - Tailwind CSS classes for all effects
 *
 * @param riskScore - Numeric risk score between 0-100
 * @returns Complete severity configuration object
 */
export function getSeverityConfig(riskScore: number): SeverityConfig {
  const level = getSeverityLevel(riskScore);
  const colors = SEVERITY_COLORS[level];

  return {
    level,
    bgTint: colors.bgTint,
    borderColor: colors.borderColor,
    glowShadow: colors.glowShadow,
    shouldPulse: level === 'critical',
    bgClass: getSeverityBgClass(level),
    borderClass: getSeverityBorderClass(level),
    glowClass: level === 'critical' ? 'shadow-[0_0_8px_rgba(239,68,68,0.3)]' : '',
    pulseClass: level === 'critical' ? 'animate-pulse-subtle' : '',
  };
}

/**
 * Get Tailwind CSS background class for severity level.
 *
 * Uses inline styles via arbitrary values for precise opacity control.
 * Background tints are intentionally subtle to maintain readability.
 *
 * @param level - Severity level
 * @returns Tailwind CSS class for background tint
 */
export function getSeverityBgClass(level: SeverityLevel): string {
  const classes: Record<SeverityLevel, string> = {
    critical: 'bg-red-500/[0.08]',
    high: 'bg-orange-500/[0.06]',
    medium: 'bg-yellow-500/[0.04]',
    low: 'bg-transparent',
  };
  return classes[level];
}

/**
 * Get Tailwind CSS border-left class for severity level.
 *
 * @param level - Severity level
 * @returns Tailwind CSS class for left border color
 */
export function getSeverityBorderClass(level: SeverityLevel): string {
  const classes: Record<SeverityLevel, string> = {
    critical: 'border-l-red-500',
    high: 'border-l-orange-500',
    medium: 'border-l-yellow-500',
    low: 'border-l-primary', // NVIDIA green
  };
  return classes[level];
}

/**
 * Get inline style object for severity-based styling.
 *
 * Useful when Tailwind classes don't provide enough specificity
 * or when dynamic values are needed.
 *
 * @param riskScore - Numeric risk score between 0-100
 * @param prefersReducedMotion - Whether user prefers reduced motion
 * @returns CSS style object
 */
export function getSeverityStyle(
  riskScore: number,
  prefersReducedMotion: boolean = false
): React.CSSProperties {
  const config = getSeverityConfig(riskScore);

  return {
    backgroundColor: config.bgTint,
    borderLeftColor: config.borderColor,
    boxShadow: config.glowShadow || undefined,
    animation:
      config.shouldPulse && !prefersReducedMotion
        ? 'pulse-subtle 2s ease-in-out infinite'
        : undefined,
  };
}

/**
 * Check if a risk score represents a critical severity level.
 *
 * @param riskScore - Numeric risk score between 0-100
 * @returns True if the score is at critical severity (>= 80)
 */
export function isCriticalSeverity(riskScore: number): boolean {
  return riskScore >= SEVERITY_THRESHOLDS.CRITICAL_MIN;
}

/**
 * Re-export getRiskLevel for convenience
 * (maintains backward compatibility with existing code)
 */
export { getRiskLevel };
