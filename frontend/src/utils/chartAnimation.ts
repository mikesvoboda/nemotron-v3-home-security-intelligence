/**
 * Chart Animation Utilities - Performance optimization for large datasets (NEM-5045)
 *
 * Provides utilities to conditionally disable animations in chart components
 * when rendering large datasets. Animations can cause performance issues
 * (jank, dropped frames, high CPU usage) when the dataset exceeds a threshold.
 *
 * @module utils/chartAnimation
 */

// ============================================================================
// Constants
// ============================================================================

/**
 * Animation threshold - disable animations for datasets larger than this.
 *
 * Based on performance testing, 100 data points is the threshold where
 * animation overhead becomes noticeable on typical hardware.
 */
export const CHART_ANIMATION_THRESHOLD = 100;

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Determines whether chart animations should be enabled based on data size.
 *
 * Returns true (animate) for small datasets, false (no animation) for large datasets.
 *
 * @param dataLength - The number of data points in the chart dataset
 * @returns Whether animations should be enabled
 *
 * @example
 * ```tsx
 * import { shouldAnimateChart } from '../utils/chartAnimation';
 *
 * // In a Tremor chart component:
 * <AreaChart
 *   data={chartData}
 *   showAnimation={shouldAnimateChart(chartData.length)}
 *   // ... other props
 * />
 *
 * // In a Recharts component:
 * <BarChart data={chartData}>
 *   <Bar isAnimationActive={shouldAnimateChart(chartData.length)} />
 * </BarChart>
 * ```
 */
export function shouldAnimateChart(dataLength: number): boolean {
  return dataLength <= CHART_ANIMATION_THRESHOLD;
}

/**
 * Gets the animation configuration for a chart based on data size.
 *
 * Returns an object with animation-related props that can be spread
 * onto chart components.
 *
 * @param dataLength - The number of data points in the chart dataset
 * @returns Animation configuration object
 *
 * @example
 * ```tsx
 * import { getChartAnimationConfig } from '../utils/chartAnimation';
 *
 * // In a Tremor chart:
 * const animationConfig = getChartAnimationConfig(data.length);
 * <AreaChart data={data} {...animationConfig} />
 * ```
 */
export function getChartAnimationConfig(dataLength: number): { showAnimation: boolean } {
  return {
    showAnimation: shouldAnimateChart(dataLength),
  };
}
