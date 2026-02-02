/**
 * Centralized chart color constants for Recharts and Tremor components.
 *
 * This file provides a single source of truth for all chart-related colors,
 * enabling consistent styling across the application and easy theme updates.
 *
 * Color Categories:
 * - SEVERITY_COLORS: Risk level colors (critical, high, medium, low)
 * - CHART_COLORS: General chart palette (primary, secondary, etc.)
 * - TREMOR_COLORS: Tremor-specific color name arrays
 * - DETECTION_COLORS: Object type detection colors
 *
 * @module constants/chartColors
 */

// ============================================================================
// Severity/Risk Colors
// ============================================================================

/**
 * Hex color values for risk/severity levels.
 * Used for legends, custom SVG elements, and inline styles.
 */
export const SEVERITY_COLORS = {
  critical: '#EF4444', // red-500
  high: '#F97316', // orange-500
  medium: '#EAB308', // yellow-500 (note: some components use #F59E0B amber-500)
  low: '#10B981', // emerald-500
  info: '#3B82F6', // blue-500
} as const;

/**
 * Alternative severity colors using amber instead of yellow for medium.
 * Used in some analytics components.
 */
export const SEVERITY_COLORS_ALT = {
  critical: '#EF4444', // red-500
  high: '#F97316', // orange-500
  medium: '#F59E0B', // amber-500
  low: '#10B981', // emerald-500
  info: '#3B82F6', // blue-500
} as const;

/**
 * Tremor color names for severity levels.
 * Use with Tremor's AreaChart, LineChart, etc.
 */
export const SEVERITY_TREMOR_COLORS = ['emerald', 'amber', 'orange', 'red'] as const;

/**
 * Risk level Tremor color mapping.
 */
export const RISK_TREMOR_COLORS = {
  low: 'green',
  medium: 'yellow',
  high: 'orange',
  critical: 'red',
} as const;

/**
 * Risk level hex color mapping.
 */
export const RISK_HEX_COLORS = {
  low: '#22C55E', // green-500
  medium: '#EAB308', // yellow-500
  high: '#F97316', // orange-500
  critical: '#EF4444', // red-500
} as const;

// ============================================================================
// General Chart Colors
// ============================================================================

/**
 * Primary chart color palette for general use.
 * These are semantic colors for different chart purposes.
 */
export const CHART_COLORS = {
  primary: '#76B900', // NVIDIA green - brand primary
  secondary: '#3B82F6', // blue-500
  tertiary: '#8B5CF6', // violet-500
  success: '#22C55E', // green-500
  warning: '#EAB308', // yellow-500
  danger: '#EF4444', // red-500
  info: '#06B6D4', // cyan-500
  neutral: '#6B7280', // gray-500
} as const;

/**
 * Extended color palette for multi-series charts.
 * Provides good visual distinction between series.
 */
export const CHART_PALETTE = [
  '#10B981', // emerald-500
  '#3B82F6', // blue-500
  '#F59E0B', // amber-500
  '#8B5CF6', // violet-500
  '#F43F5E', // rose-500
  '#06B6D4', // cyan-500
  '#F97316', // orange-500
  '#6366F1', // indigo-500
  '#84CC16', // lime-500
  '#EC4899', // pink-500
] as const;

/**
 * Tremor color names for multi-series charts.
 * Matches CHART_PALETTE order for consistency.
 */
export const TREMOR_PALETTE = [
  'emerald',
  'blue',
  'amber',
  'violet',
  'rose',
  'cyan',
  'orange',
  'indigo',
  'lime',
  'pink',
] as const;

// ============================================================================
// Detection/Object Type Colors
// ============================================================================

/**
 * Default colors for object detection types.
 * Used in bounding box overlays and detection charts.
 * Note: Uses lowercase hex values to maintain backward compatibility with existing snapshots.
 */
export const DETECTION_OBJECT_COLORS: Record<string, string> = {
  person: '#ef4444', // red-500
  car: '#3b82f6', // blue-500
  dog: '#f59e0b', // amber-500
  cat: '#8b5cf6', // violet-500
  package: '#10b981', // emerald-500
  default: '#6b7280', // gray-500
};

/**
 * Tremor color names for detection class charts.
 */
export const DETECTION_TREMOR_COLORS = [
  'emerald',
  'blue',
  'amber',
  'violet',
  'rose',
  'cyan',
] as const;

/**
 * Hex colors for detection classes (matching DETECTION_TREMOR_COLORS).
 */
export const DETECTION_HEX_COLORS: Record<string, string> = {
  emerald: '#10B981',
  blue: '#3B82F6',
  amber: '#F59E0B',
  violet: '#8B5CF6',
  rose: '#F43F5E',
  cyan: '#06B6D4',
};

// ============================================================================
// Performance/System Chart Colors
// ============================================================================

/**
 * Colors for GPU and system performance charts.
 */
export const PERFORMANCE_COLORS = {
  gpu: '#10B981', // emerald-500 - GPU utilization
  vram: '#3B82F6', // blue-500 - VRAM usage
  cpu: '#3B82F6', // blue-500 - CPU usage
  ram: '#F59E0B', // amber-500 - RAM usage
  disk: '#F43F5E', // rose-500 - Disk usage
  temperature: '#F59E0B', // amber-500 - Temperature
  temperatureWarning: '#EAB308', // yellow-500 - Warning threshold
  temperatureCritical: '#EF4444', // red-500 - Critical threshold
} as const;

/**
 * Tremor colors for performance charts.
 */
export const PERFORMANCE_TREMOR_COLORS = {
  gpuUtilization: ['emerald', 'blue'] as const,
  temperature: ['amber', 'yellow', 'red'] as const,
  latency: ['cyan', 'violet', 'emerald'] as const,
  resources: ['blue', 'amber', 'rose'] as const,
} as const;

// ============================================================================
// Body Part Colors (Pose Detection)
// ============================================================================

/**
 * Colors for pose skeleton body parts.
 * Note: Uses lowercase hex values to maintain backward compatibility with existing snapshots.
 */
export const BODY_PART_COLORS = {
  head: '#22c55e', // green-500
  torso: '#eab308', // yellow-500
  left_arm: '#3b82f6', // blue-500
  right_arm: '#8b5cf6', // violet-500
  left_leg: '#ef4444', // red-500
  right_leg: '#f97316', // orange-500
} as const;

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get hex color value from a Tremor color name.
 *
 * @param colorName - Tremor color name (e.g., 'emerald', 'blue')
 * @returns Hex color value, or gray as fallback
 */
export function getTremorHexColor(colorName: string): string {
  const colorMap: Record<string, string> = {
    emerald: '#10B981',
    green: '#22C55E',
    blue: '#3B82F6',
    amber: '#F59E0B',
    yellow: '#EAB308',
    violet: '#8B5CF6',
    rose: '#F43F5E',
    cyan: '#06B6D4',
    orange: '#F97316',
    indigo: '#6366F1',
    lime: '#84CC16',
    pink: '#EC4899',
    red: '#EF4444',
  };
  return colorMap[colorName] || '#6B7280';
}

/**
 * Get color for a detection object type.
 *
 * @param objectType - Object type (e.g., 'person', 'car')
 * @returns Hex color value
 */
export function getDetectionColor(objectType: string): string {
  const key = objectType.toLowerCase();
  return DETECTION_OBJECT_COLORS[key] || DETECTION_OBJECT_COLORS.default;
}

/**
 * Get a color from the chart palette by index.
 * Wraps around if index exceeds palette length.
 *
 * @param index - Index in the palette
 * @returns Hex color value
 */
export function getChartPaletteColor(index: number): string {
  return CHART_PALETTE[index % CHART_PALETTE.length];
}

/**
 * Get a Tremor color name from the palette by index.
 * Wraps around if index exceeds palette length.
 *
 * @param index - Index in the palette
 * @returns Tremor color name
 */
export function getTremorPaletteColor(index: number): string {
  return TREMOR_PALETTE[index % TREMOR_PALETTE.length];
}

// ============================================================================
// Type Exports
// ============================================================================

export type SeverityLevel = keyof typeof SEVERITY_COLORS;
export type ChartColorKey = keyof typeof CHART_COLORS;
export type TremorColorName = (typeof TREMOR_PALETTE)[number];
