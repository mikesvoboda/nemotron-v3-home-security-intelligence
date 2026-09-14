/**
 * Severity Types
 *
 * TypeScript types for severity configuration fetched from the backend API.
 * These types mirror the backend SeverityService and API schemas.
 *
 * @module types/severity
 */

/**
 * Severity level enumeration matching backend SeverityEnum.
 */
export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';

/**
 * Definition for a single severity level.
 * Contains metadata about the severity including its display properties
 * and score boundaries.
 */
export interface SeverityDefinition {
  /** The severity level identifier */
  severity: SeverityLevel;
  /** Human-readable label (e.g., "Low", "Medium", "High", "Critical") */
  label: string;
  /** Description of what this severity level means */
  description: string;
  /** Hex color code for UI styling (e.g., "#22c55e" for green) */
  color: string;
  /** Priority order (1 = lowest, 4 = highest) */
  priority: number;
  /** Minimum score for this severity level (inclusive) */
  min_score: number;
  /** Maximum score for this severity level (inclusive) */
  max_score: number;
}

/**
 * Threshold configuration for severity levels.
 * These values define the boundaries between severity levels:
 * - Scores 0 to low_max are "low"
 * - Scores low_max+1 to medium_max are "medium"
 * - Scores medium_max+1 to high_max are "high"
 * - Scores high_max+1 to 100 are "critical"
 */
export interface SeverityThresholds {
  /** Maximum score for "low" severity (default: 29) */
  low_max: number;
  /** Maximum score for "medium" severity (default: 59) */
  medium_max: number;
  /** Maximum score for "high" severity (default: 84) */
  high_max: number;
}

/**
 * Complete severity metadata response from GET /api/system/severity.
 * Contains both the severity definitions and current threshold configuration.
 */
export interface SeverityMetadata {
  /** Array of all severity level definitions */
  definitions: SeverityDefinition[];
  /** Current threshold configuration */
  thresholds: SeverityThresholds;
}

/**
 * Default thresholds matching backend SeverityService defaults.
 * Used as fallback when API is not available or during loading.
 */
export const DEFAULT_SEVERITY_THRESHOLDS: SeverityThresholds = {
  low_max: 29,
  medium_max: 59,
  high_max: 84,
};

/**
 * Default severity definitions matching backend defaults.
 * Used as fallback when API is not available.
 */
export const DEFAULT_SEVERITY_DEFINITIONS: SeverityDefinition[] = [
  {
    severity: 'low',
    label: 'Low',
    description: 'Minimal risk, routine activity',
    color: '#22c55e',
    priority: 1,
    min_score: 0,
    max_score: 29,
  },
  {
    severity: 'medium',
    label: 'Medium',
    description: 'Moderate risk, requires attention',
    color: '#eab308',
    priority: 2,
    min_score: 30,
    max_score: 59,
  },
  {
    severity: 'high',
    label: 'High',
    description: 'Elevated risk, urgent attention needed',
    color: '#f97316',
    priority: 3,
    min_score: 60,
    max_score: 84,
  },
  {
    severity: 'critical',
    label: 'Critical',
    description: 'Critical risk, immediate action required',
    color: '#ef4444',
    priority: 4,
    min_score: 85,
    max_score: 100,
  },
];
