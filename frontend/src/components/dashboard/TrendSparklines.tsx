/**
 * TrendSparklines component for dashboard trend visualization.
 *
 * Displays three mini sparklines showing:
 * - Event count trends
 * - Average risk trends
 * - High-risk count trends
 *
 * Each metric includes:
 * - Mini sparkline chart (SVG)
 * - Deviation indicator (e.g., "40% above baseline")
 *
 * @see NEM-5406/5407/5408/5409 - Feature 5: Trend Comparison Sparklines
 */

import { TrendingUp, TrendingDown, Minus, AlertTriangle, RefreshCw } from 'lucide-react';
import { useMemo } from 'react';

import type { TrendSparklinesProps, TrendMetric } from '@/types/trends';

/**
 * Generates an SVG path for a sparkline chart.
 *
 * @param data - Array of data points
 * @param width - Width of the SVG viewBox
 * @param height - Height of the SVG viewBox
 * @returns SVG path string
 */
export function generateSparklinePath(data: number[], width: number, height: number): string {
  if (data.length === 0) return '';

  const maxValue = Math.max(...data, 1); // Avoid division by zero
  const minValue = Math.min(...data, 0);
  const range = maxValue - minValue || 1;
  const padding = 2;
  const availableHeight = height - padding * 2;

  // Calculate points
  const points = data.map((value, index) => {
    const x = data.length === 1 ? width / 2 : (index / (data.length - 1)) * width;
    const normalizedValue = (value - minValue) / range;
    const y = height - padding - normalizedValue * availableHeight;
    return { x, y };
  });

  if (points.length === 0) return '';
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;

  // Build path
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length; i++) {
    path += ` L ${points[i].x} ${points[i].y}`;
  }

  return path;
}

/**
 * Single sparkline metric card.
 */
interface SparklineCardProps {
  label: string;
  metric: TrendMetric;
  testId: string;
  /** Whether higher values are bad (true for risk metrics) */
  invertColors?: boolean;
}

function SparklineCard({ label, metric, testId, invertColors = false }: SparklineCardProps) {
  const { values, deviationPct } = metric;

  // Determine color based on deviation and metric type
  const getDeviationColor = () => {
    if (deviationPct === 0) return 'text-gray-400';
    const isPositive = deviationPct > 0;
    // For risk metrics, higher is bad; for events, higher is neutral/informational
    if (invertColors) {
      return isPositive ? 'text-red-400' : 'text-green-400';
    }
    return isPositive ? 'text-blue-400' : 'text-gray-400';
  };

  // Get deviation icon
  const DeviationIcon = deviationPct > 0 ? TrendingUp : deviationPct < 0 ? TrendingDown : Minus;

  // Format deviation text
  const deviationText = useMemo(() => {
    const absValue = Math.abs(Math.round(deviationPct));
    if (deviationPct === 0) return '0% change';
    return deviationPct > 0 ? `${absValue}% above baseline` : `${absValue}% below baseline`;
  }, [deviationPct]);

  // Generate sparkline path
  const sparklinePath = useMemo(() => generateSparklinePath(values, 80, 24), [values]);

  // Determine sparkline color based on metric type
  const sparklineColor = invertColors
    ? deviationPct > 0
      ? '#f87171'
      : '#4ade80'
    : '#60a5fa';

  return (
    <div
      className="flex flex-col gap-1 rounded-lg border border-gray-800 bg-[#1A1A1A] p-3"
      data-testid={testId}
    >
      {/* Label */}
      <span className="text-xs font-medium text-gray-400">{label}</span>

      {/* Sparkline and deviation */}
      <div className="flex items-center justify-between gap-2">
        {/* Sparkline SVG */}
        <svg
          width="80"
          height="24"
          viewBox="0 0 80 24"
          preserveAspectRatio="none"
          className="flex-shrink-0"
          aria-hidden="true"
          data-testid={`sparkline-${testId.replace('trend-', '')}`}
        >
          {sparklinePath && (
            <path
              d={sparklinePath}
              fill="none"
              stroke={sparklineColor}
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
        </svg>

        {/* Deviation indicator */}
        <div
          className={`flex items-center gap-1 text-xs ${getDeviationColor()}`}
          data-testid={`deviation-${testId.replace('trend-', '')}`}
        >
          <DeviationIcon className="h-3 w-3" aria-hidden="true" />
          <span>{deviationText}</span>
        </div>
      </div>
    </div>
  );
}

/**
 * Loading skeleton for trend sparklines.
 */
function TrendSparklinesSkeleton() {
  return (
    <div
      className="grid grid-cols-1 gap-3 sm:grid-cols-3"
      data-testid="trend-sparklines-loading"
    >
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="flex flex-col gap-2 rounded-lg border border-gray-800 bg-[#1A1A1A] p-3"
          data-testid={`skeleton-${i}`}
        >
          <div className="h-3 w-16 animate-pulse rounded bg-gray-700" />
          <div className="flex items-center justify-between gap-2">
            <div className="h-6 w-20 animate-pulse rounded bg-gray-700" />
            <div className="h-4 w-24 animate-pulse rounded bg-gray-700" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Error state for trend sparklines.
 */
interface TrendSparklinesErrorProps {
  onRetry?: () => void;
}

function TrendSparklinesError({ onRetry }: TrendSparklinesErrorProps) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-2 rounded-lg border border-red-800/30 bg-red-900/10 p-4"
      data-testid="trend-sparklines-error"
    >
      <AlertTriangle className="h-5 w-5 text-red-400" aria-hidden="true" />
      <span className="text-sm text-red-400">Failed to load trend data</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="flex items-center gap-1 text-xs text-red-300 hover:text-red-200"
        >
          <RefreshCw className="h-3 w-3" />
          Retry
        </button>
      )}
    </div>
  );
}

/**
 * Empty state for trend sparklines.
 */
function TrendSparklinesEmpty() {
  return (
    <div
      className="flex flex-col items-center justify-center gap-2 rounded-lg border border-gray-800 bg-[#1A1A1A] p-4"
      data-testid="trend-sparklines-empty"
    >
      <TrendingUp className="h-5 w-5 text-gray-500" aria-hidden="true" />
      <span className="text-sm text-gray-400">No trend data available</span>
      <span className="text-xs text-gray-500">Data will appear as events are recorded</span>
    </div>
  );
}

/**
 * TrendSparklines component displays three mini sparklines for trend comparison.
 *
 * Shows event count, average risk, and high-risk count with baseline
 * deviation indicators for quick trend analysis.
 *
 * @example
 * ```tsx
 * function Dashboard() {
 *   const { data, isLoading, error, refetch } = useTrends('hourly');
 *   return (
 *     <TrendSparklines
 *       data={data}
 *       isLoading={isLoading}
 *       error={error}
 *       onRetry={refetch}
 *     />
 *   );
 * }
 * ```
 */
export default function TrendSparklines({
  data,
  isLoading,
  error,
  onRetry,
  className = '',
  compact = false,
}: TrendSparklinesProps) {
  // Loading state
  if (isLoading) {
    return <TrendSparklinesSkeleton />;
  }

  // Error state
  if (error) {
    return <TrendSparklinesError onRetry={onRetry} />;
  }

  // Empty state
  if (!data) {
    return <TrendSparklinesEmpty />;
  }

  const gridClass = compact ? 'grid grid-cols-3 gap-2' : 'grid grid-cols-1 gap-3 sm:grid-cols-3';

  return (
    <div
      className={`${gridClass} ${className}`}
      data-testid="trend-sparklines"
      aria-label="Trend comparison sparklines"
    >
      <SparklineCard
        label="Event Count"
        metric={data.eventCount}
        testId="trend-event-count"
        invertColors={false}
      />
      <SparklineCard
        label="Avg Risk"
        metric={data.avgRisk}
        testId="trend-avg-risk"
        invertColors={true}
      />
      <SparklineCard
        label="High Risk"
        metric={data.highRiskCount}
        testId="trend-high-risk"
        invertColors={true}
      />
    </div>
  );
}
