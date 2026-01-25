/**
 * ErrorState - Reusable error state component with consistent retry functionality.
 *
 * Provides a standardized way to display error states across the application.
 * Supports both full-page error displays and inline error messages.
 *
 * Features:
 * - Consistent styling matching NVIDIA dark theme
 * - Required retry button when onRetry is provided
 * - Support for custom error messages and titles
 * - Compact and full variants for different contexts
 * - Accessible with proper ARIA attributes
 *
 * @example
 * ```tsx
 * // Basic usage with retry
 * <ErrorState
 *   title="Error loading data"
 *   message={error.message}
 *   onRetry={refetch}
 * />
 *
 * // Compact inline variant
 * <ErrorState
 *   title="Failed to load"
 *   message={error.message}
 *   onRetry={refetch}
 *   variant="compact"
 * />
 *
 * // Full page error (no retry possible)
 * <ErrorState
 *   title="Service Unavailable"
 *   message="Please try again later"
 * />
 * ```
 *
 * @see NEM-3529 - Add consistent retry buttons to all error states
 */

import { clsx } from 'clsx';
import { AlertCircle, RefreshCw } from 'lucide-react';

/**
 * Props for the ErrorState component.
 */
export interface ErrorStateProps {
  /** Title of the error message */
  title: string;
  /** Optional detailed error message or Error object */
  message?: string | Error | null;
  /** Callback when retry button is clicked */
  onRetry?: () => void;
  /** Label for the retry button */
  retryLabel?: string;
  /** Whether a retry is currently in progress */
  isRetrying?: boolean;
  /** Display variant: 'default' for full display, 'compact' for inline */
  variant?: 'default' | 'compact';
  /** Additional CSS classes */
  className?: string;
  /** Test ID for testing */
  testId?: string;
}

/**
 * Extract error message from various error types.
 *
 * @param message - The message or Error object
 * @returns The extracted error message string
 */
function extractMessage(message: string | Error | null | undefined): string | null {
  if (!message) return null;
  if (typeof message === 'string') return message;
  if (message instanceof Error) return message.message;
  return null;
}

/**
 * ErrorState provides a consistent error display component with retry functionality.
 *
 * This component should be used throughout the application for displaying
 * error states, ensuring a consistent user experience.
 */
export function ErrorState({
  title,
  message,
  onRetry,
  retryLabel = 'Try again',
  isRetrying = false,
  variant = 'default',
  className,
  testId = 'error-state',
}: ErrorStateProps) {
  const errorMessage = extractMessage(message);

  // Compact variant for inline error displays
  if (variant === 'compact') {
    return (
      <div
        role="alert"
        aria-live="polite"
        className={clsx(
          'rounded-lg border border-red-500/30 bg-red-500/10 p-3',
          className
        )}
        data-testid={testId}
      >
        <div className="flex items-start gap-3">
          <AlertCircle
            className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400"
            aria-hidden="true"
          />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-red-400">{title}</p>
            {errorMessage && (
              <p className="mt-0.5 text-xs text-gray-400 truncate">{errorMessage}</p>
            )}
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                disabled={isRetrying}
                className={clsx(
                  'mt-2 inline-flex items-center gap-1.5 text-xs font-medium transition-colors',
                  'focus:outline-none focus:ring-1 focus:ring-[#76B900]',
                  isRetrying
                    ? 'cursor-not-allowed text-gray-500'
                    : 'text-[#76B900] hover:text-[#8ACE00] hover:underline'
                )}
                data-testid={`${testId}-retry`}
              >
                <RefreshCw
                  className={clsx('h-3 w-3', isRetrying && 'animate-spin')}
                  aria-hidden="true"
                />
                {isRetrying ? 'Retrying...' : retryLabel}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Default variant for full error displays
  return (
    <div
      role="alert"
      aria-live="polite"
      className={clsx(
        'rounded-lg border border-red-500/20 bg-red-500/10 p-4',
        className
      )}
      data-testid={testId}
    >
      <div className="flex items-start gap-3">
        <AlertCircle
          className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500"
          aria-hidden="true"
        />
        <div className="flex-1">
          <h3 className="font-semibold text-red-500">{title}</h3>
          {errorMessage && (
            <p className="mt-1 text-sm text-red-400">{errorMessage}</p>
          )}
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              disabled={isRetrying}
              className={clsx(
                'mt-3 inline-flex items-center gap-2 rounded-md px-3 py-1.5',
                'text-sm font-medium transition-colors',
                'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]',
                isRetrying
                  ? 'cursor-not-allowed bg-gray-700/30 text-gray-500'
                  : 'bg-gray-700/50 text-[#76B900] hover:bg-gray-700'
              )}
              data-testid={`${testId}-retry`}
            >
              <RefreshCw
                className={clsx('h-3.5 w-3.5', isRetrying && 'animate-spin')}
                aria-hidden="true"
              />
              {isRetrying ? 'Retrying...' : retryLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ErrorState;
