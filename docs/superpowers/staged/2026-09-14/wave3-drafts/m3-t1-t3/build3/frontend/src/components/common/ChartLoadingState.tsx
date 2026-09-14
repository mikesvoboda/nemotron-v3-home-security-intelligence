/**
 * ChartLoadingState Component
 *
 * A standardized loading state for chart components across the application.
 * Provides a consistent spinner with optional loading text.
 *
 * Features:
 * - Configurable height to match different chart containers
 * - Optional loading message
 * - Uses NVIDIA brand color (#76B900) or neutral gray
 * - Respects prefers-reduced-motion via Tailwind's motion-safe
 * - Accessible with appropriate test IDs
 *
 * Usage:
 * ```tsx
 * if (isLoading) {
 *   return <ChartLoadingState height="h-48" message="Loading chart data..." />;
 * }
 * ```
 *
 * @module components/common/ChartLoadingState
 */

import { clsx } from 'clsx';
import { Loader2 } from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

export interface ChartLoadingStateProps {
  /** Height class for the container (e.g., 'h-32', 'h-48', 'h-64') */
  height?: string;
  /** Optional loading message to display below the spinner */
  message?: string;
  /** Use brand color (#76B900) instead of gray */
  useBrandColor?: boolean;
  /** Additional CSS classes for the container */
  className?: string;
  /** Test ID for testing */
  'data-testid'?: string;
}

// ============================================================================
// Component
// ============================================================================

/**
 * ChartLoadingState displays a consistent loading spinner for charts.
 *
 * Standardizes the loading state pattern across all chart components
 * in the application, ensuring visual consistency and accessibility.
 *
 * @param props - Component props
 * @returns React element
 */
export default function ChartLoadingState({
  height = 'h-48',
  message,
  useBrandColor = false,
  className,
  'data-testid': testId = 'chart-loading-state',
}: ChartLoadingStateProps) {
  const spinnerColorClass = useBrandColor ? 'text-[#76B900]' : 'text-gray-400';

  return (
    <div
      className={clsx('flex items-center justify-center', height, className)}
      data-testid={testId}
    >
      <div className="flex flex-col items-center gap-2">
        <Loader2
          className={clsx('h-8 w-8 motion-safe:animate-spin', spinnerColorClass)}
          aria-hidden="true"
        />
        {message && (
          <span className="text-sm text-gray-500" data-testid={`${testId}-message`}>
            {message}
          </span>
        )}
        <span className="sr-only">Loading chart data</span>
      </div>
    </div>
  );
}

export { ChartLoadingState };
