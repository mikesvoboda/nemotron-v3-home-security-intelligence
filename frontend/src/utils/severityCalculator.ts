/**
 * Severity Calculator for Summary Cards
 *
 * Calculates severity level for summary cards based on multiple signals:
 * 1. maxRiskScore if available (highest priority)
 * 2. Keyword detection in content (fallback)
 * 3. Event count (lowest priority fallback)
 *
 * @see NEM-2924
 */

// ============================================================================
// Types
// ============================================================================

/**
 * Severity levels for summary cards.
 * Ordered from least to most severe.
 */
export type SeverityLevel = 'clear' | 'low' | 'medium' | 'high' | 'critical';

/**
 * Result of severity calculation with styling information.
 */
export interface SeverityResult {
  /** The calculated severity level */
  level: SeverityLevel;
  /** Human-readable label for display */
  label: string;
  /** Tremor color name for Badge component */
  color: 'emerald' | 'green' | 'yellow' | 'orange' | 'red';
  /** CSS border color for card styling */
  borderColor: string;
}

/**
 * Input data for severity calculation.
 */
export interface SeverityInput {
  /** The summary content text */
  content: string;
  /** Number of events in the summary */
  eventCount: number;
  /** Maximum risk score from events (optional) */
  maxRiskScore?: number;
}

// ============================================================================
// Keywords for Detection
// ============================================================================

/**
 * Keywords that indicate critical severity.
 * Case-insensitive matching.
 */
const CRITICAL_KEYWORDS = [
  'critical',
  'emergency',
  'intruder',
  'breach',
  'weapon',
  'threat',
] as const;

/**
 * Keywords that indicate high severity.
 * Case-insensitive matching.
 */
const HIGH_KEYWORDS = [
  'high-risk',
  'suspicious',
  'masked',
  'obscured face',
  'loitering',
  'trespassing',
] as const;

/**
 * Keywords that indicate medium severity.
 * Case-insensitive matching.
 */
const MEDIUM_KEYWORDS = ['unusual', 'unexpected', 'unfamiliar', 'monitoring'] as const;

/**
 * Keywords that indicate low severity.
 * Case-insensitive matching.
 */
const LOW_KEYWORDS = ['routine', 'normal', 'expected', 'delivery'] as const;

// ============================================================================
// Severity Thresholds
// ============================================================================

/**
 * Risk score thresholds for severity levels.
 * These are adjusted from the standard risk thresholds to better suit
 * summary card display where we want earlier visual escalation.
 */
const SEVERITY_THRESHOLDS = {
  CRITICAL: 80, // >=80 = critical
  HIGH: 60, // >=60 = high
  MEDIUM: 40, // >=40 = medium
  LOW: 20, // >=20 = low
  // <20 with events = low, without events = clear
} as const;

// ============================================================================
// Severity Result Configurations
// ============================================================================

/**
 * Pre-configured severity results for each level.
 */
const SEVERITY_CONFIGS: Record<SeverityLevel, SeverityResult> = {
  clear: {
    level: 'clear',
    label: 'All clear',
    color: 'emerald',
    borderColor: '#10b981', // emerald-500
  },
  low: {
    level: 'low',
    label: 'Low activity',
    color: 'green',
    borderColor: '#22c55e', // green-500
  },
  medium: {
    level: 'medium',
    label: 'Moderate activity',
    color: 'yellow',
    borderColor: '#eab308', // yellow-500
  },
  high: {
    level: 'high',
    label: 'High activity',
    color: 'orange',
    borderColor: '#f97316', // orange-500
  },
  critical: {
    level: 'critical',
    label: 'Critical',
    color: 'red',
    borderColor: '#ef4444', // red-500
  },
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Check if content contains any keywords from the given list.
 * Case-insensitive matching.
 *
 * @param content - Text content to search
 * @param keywords - Array of keywords to look for
 * @returns true if any keyword is found
 */
function containsKeyword(content: string, keywords: readonly string[]): boolean {
  const lowerContent = content.toLowerCase();
  return keywords.some((keyword) => lowerContent.includes(keyword.toLowerCase()));
}

/**
 * Detect severity level from content using keyword analysis.
 *
 * @param content - The summary content text
 * @returns Detected severity level, or null if no keywords matched
 */
function detectSeverityFromKeywords(content: string): SeverityLevel | null {
  if (containsKeyword(content, CRITICAL_KEYWORDS)) {
    return 'critical';
  }
  if (containsKeyword(content, HIGH_KEYWORDS)) {
    return 'high';
  }
  if (containsKeyword(content, MEDIUM_KEYWORDS)) {
    return 'medium';
  }
  if (containsKeyword(content, LOW_KEYWORDS)) {
    return 'low';
  }
  return null;
}

/**
 * Calculate severity level from a risk score.
 *
 * @param score - Risk score (0-100)
 * @returns Severity level based on thresholds
 */
function getSeverityFromScore(score: number): SeverityLevel {
  if (score >= SEVERITY_THRESHOLDS.CRITICAL) return 'critical';
  if (score >= SEVERITY_THRESHOLDS.HIGH) return 'high';
  if (score >= SEVERITY_THRESHOLDS.MEDIUM) return 'medium';
  if (score >= SEVERITY_THRESHOLDS.LOW) return 'low';
  return 'clear';
}

// ============================================================================
// Main Function
// ============================================================================

/**
 * Calculate severity for a summary based on available data.
 *
 * Priority order:
 * 1. maxRiskScore - if available, use score-based thresholds
 * 2. Keywords - analyze content for severity-indicating words
 * 3. Event count - use as final fallback
 *
 * @param input - Summary data for severity calculation
 * @returns SeverityResult with level, label, and styling information
 *
 * @example
 * ```ts
 * // Using maxRiskScore
 * const result = calculateSeverity({
 *   content: 'Some content',
 *   eventCount: 5,
 *   maxRiskScore: 85
 * });
 * // result.level === 'critical'
 *
 * // Using keyword detection
 * const result = calculateSeverity({
 *   content: 'Intruder detected in backyard',
 *   eventCount: 1
 * });
 * // result.level === 'critical'
 *
 * // Using event count fallback
 * const result = calculateSeverity({
 *   content: 'Activity recorded',
 *   eventCount: 3
 * });
 * // result.level === 'low' (has events but no keywords)
 * ```
 */
export function calculateSeverity(input: SeverityInput): SeverityResult {
  const { content, eventCount, maxRiskScore } = input;

  // Priority 1: Use maxRiskScore if available and valid
  if (maxRiskScore !== undefined && maxRiskScore >= 0 && maxRiskScore <= 100) {
    const level = getSeverityFromScore(maxRiskScore);
    return SEVERITY_CONFIGS[level];
  }

  // Priority 2: Detect from keywords in content
  const keywordLevel = detectSeverityFromKeywords(content);
  if (keywordLevel !== null) {
    return SEVERITY_CONFIGS[keywordLevel];
  }

  // Priority 3: Fall back to event count
  if (eventCount > 0) {
    // Events exist but no keywords matched - default to low
    return SEVERITY_CONFIGS.low;
  }

  // No events, no keywords - all clear
  return SEVERITY_CONFIGS.clear;
}

/**
 * Get severity configuration for a specific level.
 * Useful for testing or direct level styling.
 *
 * @param level - The severity level
 * @returns SeverityResult for the given level
 */
export function getSeverityConfig(level: SeverityLevel): SeverityResult {
  return SEVERITY_CONFIGS[level];
}

/**
 * Check if a severity level should show the pulse-critical animation.
 *
 * @param level - The severity level
 * @returns true if the level is critical
 */
export function shouldShowCriticalAnimation(level: SeverityLevel): boolean {
  return level === 'critical';
}
