/**
 * Summary Parser Utility
 *
 * Provides fallback parsing of prose content to extract structured bullet points
 * when the backend doesn't provide pre-structured data.
 *
 * @see NEM-2923
 */

import type { SummaryBulletPoint } from '@/types/summary';

// ============================================================================
// Constants
// ============================================================================

/**
 * Common time patterns in 12-hour and 24-hour formats.
 */
const TIME_PATTERNS = [
  // 12-hour format: "2:15 PM", "12:30 AM", etc.
  /\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))\b/gi,
  // Time ranges: "2:15 PM - 3:00 PM", "14:00-15:00"
  /\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\s*[-\u2013]\s*\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)\b/gi,
  // 24-hour format: "14:30", "09:15"
  /\b(\d{2}:\d{2})\b/g,
];

/**
 * Patterns for camera and location names.
 */
const CAMERA_PATTERNS = [
  // Common camera location names
  /\b(front\s*door|back\s*door|garage|driveway|backyard|porch|entrance|side\s*gate|garden|patio)\s*(?:camera)?\b/gi,
  // Explicit camera references - limit capture to 50 chars max to avoid ReDoS
  /\b(?:camera|cam)\s*[:.]?\s*["']?([^"',.\n]{1,50})["']?/gi,
  // At/in location patterns - specific named locations only
  // eslint-disable-next-line security/detect-unsafe-regex
  /\bat\s+(?:the\s+)?(front|back|side|main|rear)\s*(door|gate|entrance|yard|porch|garage|driveway)/gi,
];

/**
 * Patterns for activity/detection types.
 */
const ACTIVITY_PATTERNS = [
  // People/person detection
  /\b(person|people|individual|visitor|delivery|mail carrier|pedestrian)/gi,
  // Vehicle detection
  /\b(vehicle|car|truck|van|motorcycle|bicycle|bike)/gi,
  // Animal detection
  /\b(animal|dog|cat|bird|wildlife|squirrel|raccoon)/gi,
  // Package/delivery
  /\b(package|parcel|box|delivery)/gi,
  // Motion/activity
  /\b(motion|movement|activity)/gi,
];

/**
 * Weather-related keywords.
 */
const WEATHER_PATTERNS = [
  /\b(sunny|cloudy|rainy|foggy|snowy|clear|overcast|stormy|windy)\b/gi,
  /\b(rain|snow|fog|mist|haze|drizzle)\b/gi,
  /\bweather\s*[:.]?\s*([^,.]+)/gi,
];

/**
 * Severity indicator keywords (for assigning severity scores).
 */
const SEVERITY_KEYWORDS: { pattern: RegExp; severity: number }[] = [
  { pattern: /\b(critical|emergency|intruder|breach|weapon|threat)\b/i, severity: 90 },
  { pattern: /\b(suspicious|masked|loitering|trespassing|high-risk)\b/i, severity: 70 },
  { pattern: /\b(unusual|unexpected|unfamiliar)\b/i, severity: 50 },
  { pattern: /\b(routine|normal|expected|delivery)\b/i, severity: 20 },
];

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Extract all matches from a string using multiple patterns.
 */
function extractMatches(content: string, patterns: RegExp[]): string[] {
  const matches: string[] = [];

  for (const pattern of patterns) {
    // Reset regex state for global patterns
    pattern.lastIndex = 0;
    let match;
    while ((match = pattern.exec(content)) !== null) {
      // Get the first capturing group if it exists, otherwise the full match
      const value = match[1] || match[0];
      if (value && !matches.includes(value.trim())) {
        matches.push(value.trim());
      }
    }
  }

  return matches;
}

/**
 * Determine severity score for a text fragment.
 */
function determineSeverity(text: string): number | undefined {
  for (const { pattern, severity } of SEVERITY_KEYWORDS) {
    if (pattern.test(text)) {
      return severity;
    }
  }
  return undefined;
}

/**
 * Clean and normalize extracted text.
 */
function normalizeText(text: string): string {
  return text
    .replace(/\s+/g, ' ')
    .replace(/^[,.\s]+|[,.\s]+$/g, '')
    .trim();
}

// ============================================================================
// Main Functions
// ============================================================================

/**
 * Extract bullet points from prose content.
 *
 * This function parses natural language summary content and extracts
 * structured bullet points for display.
 *
 * @param content - The prose content to parse
 * @returns Array of SummaryBulletPoint objects
 *
 * @example
 * ```ts
 * const bullets = extractBulletPoints(
 *   'At 2:15 PM, a suspicious person was detected at the front door camera.'
 * );
 * // Returns:
 * // [
 * //   { icon: 'time', text: '2:15 PM' },
 * //   { icon: 'alert', text: 'Suspicious activity detected', severity: 70 },
 * //   { icon: 'location', text: 'Front door' },
 * // ]
 * ```
 */
export function extractBulletPoints(content: string): SummaryBulletPoint[] {
  if (!content || typeof content !== 'string') {
    return [];
  }

  const bullets: SummaryBulletPoint[] = [];
  const normalizedContent = normalizeText(content);

  // Extract time ranges
  const times = extractMatches(normalizedContent, TIME_PATTERNS);
  if (times.length > 0) {
    bullets.push({
      icon: 'time',
      text: times.length === 1 ? times[0] : `${times[0]} - ${times[times.length - 1]}`,
    });
  }

  // Extract locations/cameras
  const locations = extractMatches(normalizedContent, CAMERA_PATTERNS);
  for (const location of locations.slice(0, 2)) {
    // Limit to 2 locations
    bullets.push({
      icon: 'location',
      text: capitalizeFirst(location),
    });
  }

  // Extract activity patterns and determine severity
  const activities = extractMatches(normalizedContent, ACTIVITY_PATTERNS);
  if (activities.length > 0) {
    const activityText = activities.slice(0, 3).join(', ');
    const severity = determineSeverity(normalizedContent);
    bullets.push({
      icon: severity && severity >= 50 ? 'alert' : 'pattern',
      text: `${capitalizeFirst(activityText)} detected`,
      severity,
    });
  }

  // Extract weather conditions
  const weather = extractMatches(normalizedContent, WEATHER_PATTERNS);
  if (weather.length > 0) {
    bullets.push({
      icon: 'weather',
      text: capitalizeFirst(weather[0]),
    });
  }

  // If we couldn't extract structured data, create a summary bullet
  if (bullets.length === 0 && normalizedContent.length > 0) {
    // Truncate long content for the bullet
    const truncated =
      normalizedContent.length > 80 ? `${normalizedContent.slice(0, 77)}...` : normalizedContent;

    bullets.push({
      icon: 'pattern',
      text: truncated,
      severity: determineSeverity(normalizedContent),
    });
  }

  return bullets;
}

/**
 * Extract time range from content as a formatted string.
 *
 * @param content - The content to extract time range from
 * @returns Formatted time range string or undefined
 *
 * @example
 * ```ts
 * extractTimeRange('Activity between 2:15 PM and 3:00 PM')
 * // Returns: '2:15 PM - 3:00 PM'
 * ```
 */
export function extractTimeRange(content: string): string | undefined {
  if (!content) return undefined;

  const times = extractMatches(content, TIME_PATTERNS);
  if (times.length >= 2) {
    return `${times[0]} - ${times[times.length - 1]}`;
  }
  if (times.length === 1) {
    return times[0];
  }
  return undefined;
}

/**
 * Extract camera names from content.
 *
 * @param content - The content to extract camera names from
 * @returns Array of camera/location names
 *
 * @example
 * ```ts
 * extractCameraNames('Activity at the front door and garage cameras')
 * // Returns: ['Front door', 'Garage']
 * ```
 */
export function extractCameraNames(content: string): string[] {
  if (!content) return [];

  const locations = extractMatches(content, CAMERA_PATTERNS);
  return locations.map((loc) => capitalizeFirst(loc));
}

/**
 * Extract detected patterns/object types from content.
 *
 * @param content - The content to extract patterns from
 * @returns Array of detected pattern names
 *
 * @example
 * ```ts
 * extractPatterns('Person and vehicle detected in driveway')
 * // Returns: ['Person', 'Vehicle']
 * ```
 */
export function extractPatterns(content: string): string[] {
  if (!content) return [];

  const activities = extractMatches(content, ACTIVITY_PATTERNS);
  return [...new Set(activities.map((act) => capitalizeFirst(act)))];
}

/**
 * Extract weather conditions from content.
 *
 * @param content - The content to extract weather from
 * @returns Weather condition string or undefined
 *
 * @example
 * ```ts
 * extractWeatherConditions('Cloudy conditions with light rain')
 * // Returns: 'Cloudy'
 * ```
 */
export function extractWeatherConditions(content: string): string | undefined {
  if (!content) return undefined;

  const weather = extractMatches(content, WEATHER_PATTERNS);
  return weather.length > 0 ? capitalizeFirst(weather[0]) : undefined;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Capitalize the first letter of a string.
 */
function capitalizeFirst(str: string): string {
  if (!str) return str;
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}
