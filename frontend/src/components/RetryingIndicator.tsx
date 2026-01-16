/**
 * RetryingIndicator - Shows when requests are being automatically retried.
 *
 * This component displays a small indicator when the client is rate limited
 * AND has active queries/mutations being retried.
 *
 * @example
 * ```tsx
 * // Add to App.tsx layout
 * <RetryingIndicator />
 * ```
 */
import { useIsFetching, useIsMutating } from '@tanstack/react-query';
import { clsx } from 'clsx';

import { useRateLimitStore } from '../stores/rate-limit-store';

// ============================================================================
// Types
// ============================================================================

export interface RetryingIndicatorProps {
  /** Optional class name for additional styling */
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

/**
 * RetryingIndicator shows when automatic retry is in progress.
 *
 * Only visible when:
 * 1. Client is rate limited (remaining = 0)
 * 2. AND there are active queries or mutations
 */
export default function RetryingIndicator({ className }: RetryingIndicatorProps) {
  const { isLimited } = useRateLimitStore();
  const fetchingCount = useIsFetching();
  const mutatingCount = useIsMutating();

  // Only show if rate limited AND there are active requests
  const hasActiveRequests = fetchingCount > 0 || mutatingCount > 0;
  if (!isLimited || !hasActiveRequests) {
    return null;
  }

  return (
    <div
      className={clsx(
        'fixed bottom-20 right-4 z-50 flex items-center gap-2 rounded-lg border border-blue-300 bg-blue-100 px-3 py-2 shadow-lg',
        className
      )}
      data-testid="retrying-indicator"
      role="status"
      aria-live="polite"
    >
      <div
        className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"
        data-testid="retrying-spinner"
        aria-hidden="true"
      />
      <span className="text-sm font-medium text-blue-800">Retrying request...</span>
    </div>
  );
}
