/**
 * RouteLoadingFallback - Loading indicator for lazy-loaded routes
 *
 * This component is displayed as the Suspense fallback while route components
 * are being dynamically loaded. It provides visual feedback to users during
 * code splitting chunk fetches.
 *
 * @example
 * <Suspense fallback={<RouteLoadingFallback />}>
 *   <LazyDashboardPage />
 * </Suspense>
 */

import { Loader2 } from 'lucide-react';

export interface RouteLoadingFallbackProps {
  /** Optional message to display below the spinner */
  message?: string;
}

/**
 * Displays a centered loading spinner with accessible status message.
 * Used as the fallback UI for Suspense boundaries wrapping lazy-loaded routes.
 */
export default function RouteLoadingFallback({
  message = 'Loading...',
}: RouteLoadingFallbackProps) {
  return (
    <div className="flex min-h-[400px] w-full items-center justify-center">
      <div
        role="status"
        aria-busy="true"
        aria-live="polite"
        className="flex flex-col items-center gap-4"
      >
        <Loader2
          className="h-10 w-10 animate-spin text-primary-500"
          aria-hidden="true"
        />
        <span className="text-sm text-text-secondary">{message}</span>
      </div>
    </div>
  );
}
