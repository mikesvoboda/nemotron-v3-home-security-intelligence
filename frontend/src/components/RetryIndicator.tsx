/**
 * RetryIndicator - Shows retry status with countdown and cancel button.
 *
 * Displays when requests are being automatically retried after a 429 rate limit response.
 * Shows:
 * - User-friendly message about rate limiting
 * - Countdown until next retry attempt
 * - Current attempt number out of maximum
 * - Cancel button to abort pending retries
 *
 * @see NEM-2297
 *
 * @example
 * ```tsx
 * // Add to App.tsx layout
 * <RetryIndicator />
 * ```
 */
import { clsx } from 'clsx';

import { useActiveRetries, useRetryStore, formatRetryCountdown } from '../hooks/useRetry';

// ============================================================================
// Types
// ============================================================================

export interface RetryIndicatorProps {
  /** Optional class name for additional styling */
  className?: string;
  /** Position of the indicator (default: 'bottom-right') */
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
}

// ============================================================================
// Position Styles
// ============================================================================

const positionStyles: Record<NonNullable<RetryIndicatorProps['position']>, string> = {
  'top-left': 'top-4 left-4',
  'top-right': 'top-4 right-4',
  'bottom-left': 'bottom-20 left-4',
  'bottom-right': 'bottom-20 right-4',
};

// ============================================================================
// Component
// ============================================================================

/**
 * RetryIndicator shows when automatic retry is in progress due to rate limiting.
 *
 * Features:
 * - Shows countdown until next retry
 * - Displays attempt number (e.g., "Attempt 1 of 3")
 * - Cancel button to abort all pending retries
 * - Accessible with role="status" and aria-live="polite"
 */
export default function RetryIndicator({
  className,
  position = 'bottom-right',
}: RetryIndicatorProps) {
  const activeRetries = useActiveRetries();
  const cancelRetry = useRetryStore((state) => {
    // Return a function that cancels a specific retry
    return (id: string) => {
      state.cancelRetry(id);
    };
  });

  // Don't render if no active retries
  if (activeRetries.length === 0) {
    return null;
  }

  // Get the first (most recent) retry for display
  const primaryRetry = activeRetries[0];
  const hasMultiple = activeRetries.length > 1;

  const handleCancelAll = () => {
    // Cancel all active retries
    for (const retry of activeRetries) {
      cancelRetry(retry.id);
    }
  };

  const handleCancelOne = (id: string) => {
    cancelRetry(id);
  };

  return (
    <div
      className={clsx(
        'fixed z-50 flex flex-col gap-2 rounded-lg border border-amber-300 bg-amber-50 p-4 shadow-lg dark:border-amber-700 dark:bg-amber-900/90',
        positionStyles[position],
        className
      )}
      data-testid="retry-indicator"
      role="status"
      aria-live="polite"
    >
      {/* Header with title and close button */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <div
            className="h-5 w-5 animate-spin rounded-full border-2 border-amber-500 border-t-transparent dark:border-amber-400"
            data-testid="retry-spinner"
            aria-hidden="true"
          />
          <span className="font-medium text-amber-800 dark:text-amber-200">
            Request limit reached
          </span>
        </div>
        {activeRetries.length === 1 && (
          <button
            type="button"
            onClick={() => handleCancelOne(primaryRetry.id)}
            className="text-amber-600 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-200"
            aria-label="Cancel retry"
            data-testid="retry-cancel-single"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Primary retry countdown */}
      <div className="text-sm text-amber-700 dark:text-amber-300">
        <p data-testid="retry-message">
          Retrying in{' '}
          <span className="font-semibold" data-testid="retry-countdown">
            {formatRetryCountdown(primaryRetry.secondsRemaining * 1000)}
          </span>
        </p>
        <p className="mt-1 text-xs text-amber-600 dark:text-amber-400" data-testid="retry-attempt">
          Attempt {primaryRetry.attempt} of {primaryRetry.maxAttempts}
        </p>
      </div>

      {/* Multiple retries indicator */}
      {hasMultiple && (
        <div className="mt-1 text-xs text-amber-600 dark:text-amber-400">
          <p data-testid="retry-multiple">
            +{activeRetries.length - 1} more request
            {activeRetries.length > 2 ? 's' : ''} queued
          </p>
        </div>
      )}

      {/* Cancel all button for multiple retries */}
      {hasMultiple && (
        <button
          type="button"
          onClick={handleCancelAll}
          className="mt-2 w-full rounded-md border border-amber-400 bg-amber-100 px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-200 dark:border-amber-600 dark:bg-amber-800 dark:text-amber-200 dark:hover:bg-amber-700"
          data-testid="retry-cancel-all"
        >
          Cancel all retries
        </button>
      )}

      {/* Single retry cancel button (more prominent) */}
      {!hasMultiple && (
        <button
          type="button"
          onClick={() => handleCancelOne(primaryRetry.id)}
          className="mt-2 w-full rounded-md border border-amber-400 bg-amber-100 px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-200 dark:border-amber-600 dark:bg-amber-800 dark:text-amber-200 dark:hover:bg-amber-700"
          data-testid="retry-cancel-button"
        >
          Cancel retry
        </button>
      )}
    </div>
  );
}

// ============================================================================
// Compact Variant
// ============================================================================

export interface RetryIndicatorCompactProps {
  /** Optional class name for additional styling */
  className?: string;
}

/**
 * Compact version of the retry indicator for inline use.
 * Shows just the countdown without cancel button.
 */
export function RetryIndicatorCompact({ className }: RetryIndicatorCompactProps) {
  const activeRetries = useActiveRetries();

  if (activeRetries.length === 0) {
    return null;
  }

  const primaryRetry = activeRetries[0];

  return (
    <div
      className={clsx(
        'inline-flex items-center gap-2 rounded-md bg-amber-100 px-2 py-1 text-sm text-amber-800 dark:bg-amber-900 dark:text-amber-200',
        className
      )}
      data-testid="retry-indicator-compact"
      role="status"
      aria-live="polite"
    >
      <div
        className="h-3 w-3 animate-spin rounded-full border-2 border-amber-500 border-t-transparent"
        aria-hidden="true"
      />
      <span>Retrying in {formatRetryCountdown(primaryRetry.secondsRemaining * 1000)}</span>
    </div>
  );
}
