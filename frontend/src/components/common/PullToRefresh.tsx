/**
 * PullToRefresh Component
 *
 * Provides pull-to-refresh functionality for mobile devices with visual feedback.
 * Wraps content and detects pull-down gestures at the top of the container.
 *
 * Features:
 * - Pull indicator that rotates based on pull progress
 * - Loading spinner during refresh
 * - Configurable threshold and visual styles
 * - Accessibility support with ARIA attributes
 *
 * @see NEM-2970
 *
 * @example
 * ```tsx
 * <PullToRefresh onRefresh={async () => await refetch()} isRefreshing={isFetching}>
 *   <EventList events={events} />
 * </PullToRefresh>
 * ```
 */

import { RefreshCw } from 'lucide-react';

import { usePullToRefresh } from '../../hooks/usePullToRefresh';

import type { ReactNode } from 'react';

export interface PullToRefreshProps {
  /**
   * Content to wrap with pull-to-refresh functionality.
   */
  children: ReactNode;

  /**
   * Callback function when refresh is triggered.
   * Should return a Promise that resolves when refresh is complete.
   */
  onRefresh: () => Promise<void>;

  /**
   * External control of refreshing state.
   * Useful when refresh state is managed externally (e.g., by React Query).
   */
  isRefreshing?: boolean;

  /**
   * Whether pull-to-refresh is disabled.
   * @default false
   */
  disabled?: boolean;

  /**
   * Minimum pull distance in pixels to trigger refresh.
   * @default 80
   */
  threshold?: number;

  /**
   * Additional CSS classes for the container.
   */
  className?: string;
}

/**
 * PullToRefresh component that wraps content with pull-to-refresh functionality.
 */
export function PullToRefresh({
  children,
  onRefresh,
  isRefreshing: externalIsRefreshing,
  disabled = false,
  threshold = 80,
  className = '',
}: PullToRefreshProps) {
  const {
    containerRef,
    isPulling,
    isRefreshing: internalIsRefreshing,
    pullDistance,
    pullProgress,
  } = usePullToRefresh({
    onRefresh,
    threshold,
    disabled,
    isRefreshing: externalIsRefreshing,
  });

  // Use external isRefreshing if provided, otherwise use internal
  const isRefreshing = externalIsRefreshing ?? internalIsRefreshing;

  // Calculate rotation based on pull progress (0-180 degrees)
  const rotation = pullProgress * 180;

  // Calculate indicator height (capped at threshold)
  const indicatorHeight = Math.min(pullDistance, threshold);

  return (
    <div
      ref={containerRef}
      data-testid="pull-to-refresh-container"
      className={`touch-pan-y overflow-auto ${className}`}
      role="region"
      aria-label="Pull to refresh content"
    >
      {/* Pull indicator */}
      <div
        data-testid="pull-indicator"
        className="flex items-center justify-center overflow-hidden transition-[height] duration-75"
        style={{ height: `${isPulling ? indicatorHeight : 0}px` }}
        aria-hidden="true"
      >
        <div
          className="text-[#76B900] transition-transform"
          style={{ transform: `rotate(${rotation}deg)` }}
        >
          <RefreshCw className="h-6 w-6" />
        </div>
      </div>

      {/* Refresh spinner (fixed at top while refreshing) */}
      {isRefreshing && (
        <div data-testid="refresh-spinner" className="flex items-center justify-center py-4">
          <RefreshCw className="h-6 w-6 animate-spin text-[#76B900]" />
        </div>
      )}

      {/* Screen reader status for accessibility */}
      <div role="status" className="sr-only" aria-live="polite">
        {isRefreshing ? 'Refreshing content...' : ''}
      </div>

      {/* Main content */}
      <div>{children}</div>
    </div>
  );
}

export default PullToRefresh;
