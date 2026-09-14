/**
 * Confidence level type definition
 */
export type ConfidenceLevel = 'low' | 'medium' | 'high';

/**
 * Convert a numeric confidence score (0.0-1.0) to a categorical confidence level
 * @param confidence - Numeric confidence score between 0.0-1.0
 * @returns Confidence level category
 */
export function getConfidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence < 0 || confidence > 1) {
    throw new Error('Confidence score must be between 0.0 and 1.0');
  }

  if (confidence < 0.7) return 'low';
  if (confidence < 0.85) return 'medium';
  return 'high';
}

/**
 * Get the color hex code for a given confidence level
 * @param level - Confidence level category
 * @returns Hex color code
 */
export function getConfidenceColor(level: ConfidenceLevel): string {
  const colors: Record<ConfidenceLevel, string> = {
    low: '#E74856', // Red - low confidence detections need attention
    medium: '#FFB800', // Yellow - medium confidence
    high: '#76B900', // NVIDIA Green - high confidence
  };

  return colors[level];
}

/**
 * Get Tailwind CSS classes for a given confidence level
 * @param level - Confidence level category
 * @returns Tailwind CSS class string for text color
 */
export function getConfidenceTextColorClass(level: ConfidenceLevel): string {
  const classes: Record<ConfidenceLevel, string> = {
    low: 'text-red-400',
    medium: 'text-yellow-400',
    high: 'text-green-400',
  };

  return classes[level];
}

/**
 * Get Tailwind CSS classes for background color based on confidence level
 * @param level - Confidence level category
 * @returns Tailwind CSS class string for background color
 */
export function getConfidenceBgColorClass(level: ConfidenceLevel): string {
  const classes: Record<ConfidenceLevel, string> = {
    low: 'bg-red-500/20',
    medium: 'bg-yellow-500/20',
    high: 'bg-green-500/20',
  };

  return classes[level];
}

/**
 * Get Tailwind CSS classes for border color based on confidence level
 * @param level - Confidence level category
 * @returns Tailwind CSS class string for border color
 */
export function getConfidenceBorderColorClass(level: ConfidenceLevel): string {
  const classes: Record<ConfidenceLevel, string> = {
    low: 'border-red-500/40',
    medium: 'border-yellow-500/40',
    high: 'border-green-500/40',
  };

  return classes[level];
}

/**
 * Get a human-readable label for a confidence level
 * @param level - Confidence level category
 * @returns Capitalized label string
 */
export function getConfidenceLabel(level: ConfidenceLevel): string {
  const labels: Record<ConfidenceLevel, string> = {
    low: 'Low Confidence',
    medium: 'Medium Confidence',
    high: 'High Confidence',
  };

  return labels[level];
}

/**
 * Format confidence as a percentage string
 * @param confidence - Numeric confidence score between 0.0-1.0
 * @returns Formatted percentage string (e.g., "95%")
 */
export function formatConfidencePercent(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

/**
 * Calculate the average confidence from an array of detections
 * @param detections - Array of objects with confidence property
 * @returns Average confidence value, or null if array is empty
 */
export function calculateAverageConfidence(
  detections: Array<{ confidence: number }>
): number | null {
  if (detections.length === 0) return null;

  const sum = detections.reduce((acc, d) => acc + d.confidence, 0);
  return sum / detections.length;
}

/**
 * Calculate the maximum confidence from an array of detections
 * @param detections - Array of objects with confidence property
 * @returns Maximum confidence value, or null if array is empty
 */
export function calculateMaxConfidence(detections: Array<{ confidence: number }>): number | null {
  if (detections.length === 0) return null;

  return Math.max(...detections.map((d) => d.confidence));
}

/**
 * Sort detections by confidence in descending order (highest first)
 * @param detections - Array of objects with confidence property
 * @returns New array sorted by confidence descending
 */
export function sortDetectionsByConfidence<T extends { confidence: number }>(detections: T[]): T[] {
  return [...detections].sort((a, b) => b.confidence - a.confidence);
}

/**
 * Filter detections by minimum confidence threshold
 * @param detections - Array of objects with confidence property
 * @param minConfidence - Minimum confidence threshold (0.0-1.0)
 * @returns Filtered array of detections
 */
export function filterDetectionsByConfidence<T extends { confidence: number }>(
  detections: T[],
  minConfidence: number
): T[] {
  return detections.filter((d) => d.confidence >= minConfidence);
}
