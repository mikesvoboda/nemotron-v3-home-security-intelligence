/**
 * SummaryCardError - Error state component for summary cards.
 *
 * Displays when summary data fails to load due to network issues,
 * server errors, or other problems. Provides user-friendly error messages
 * and a retry mechanism.
 *
 * @see SummaryCards.tsx - Parent component that uses this error state
 * @see NEM-2928
 */

import { Card, Flex, Text, Title } from '@tremor/react';
import { clsx } from 'clsx';
import { AlertTriangle, Calendar, Clock, RefreshCw } from 'lucide-react';

import type { SummaryType } from '@/types/summary';

/**
 * Props for the SummaryCardError component.
 */
export interface SummaryCardErrorProps {
  /** Type of summary: 'hourly' or 'daily' - determines icon and title */
  type: SummaryType;
  /** Error message or Error object */
  error: string | Error;
  /** Callback when retry button is clicked */
  onRetry: () => void;
  /** Whether a retry is currently in progress */
  isRetrying?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Maps technical error messages to user-friendly descriptions.
 * @param error - The error message or Error object
 * @returns User-friendly error message
 */
function getUserFriendlyMessage(error: string | Error): string {
  const errorMessage = error instanceof Error ? error.message : error;
  const lowerMessage = errorMessage.toLowerCase();

  // Network errors
  if (
    lowerMessage.includes('network') ||
    lowerMessage.includes('fetch') ||
    lowerMessage.includes('connection') ||
    lowerMessage.includes('offline')
  ) {
    return 'Unable to connect to the server. Please check your network connection.';
  }

  // Timeout errors
  if (lowerMessage.includes('timeout') || lowerMessage.includes('timed out')) {
    return 'The request took too long. Please try again.';
  }

  // Server errors (5xx)
  if (
    lowerMessage.includes('500') ||
    lowerMessage.includes('502') ||
    lowerMessage.includes('503') ||
    lowerMessage.includes('server error')
  ) {
    return 'The server encountered an error. Please try again in a moment.';
  }

  // Not found (404)
  if (lowerMessage.includes('404') || lowerMessage.includes('not found')) {
    return 'Summary data is not available at this time.';
  }

  // Authentication errors
  if (
    lowerMessage.includes('401') ||
    lowerMessage.includes('403') ||
    lowerMessage.includes('unauthorized') ||
    lowerMessage.includes('forbidden')
  ) {
    return 'Unable to access summary data. Please refresh the page.';
  }

  // Rate limiting
  if (lowerMessage.includes('429') || lowerMessage.includes('rate limit')) {
    return 'Too many requests. Please wait a moment and try again.';
  }

  // Default fallback
  return 'Unable to load summary data. Please try again.';
}

/**
 * SummaryCardError provides an error state display when summary data
 * fails to load, with retry functionality.
 *
 * Features:
 * - User-friendly error message translation
 * - Retry button with loading state
 * - Alert styling with red color scheme
 * - Accessible with role="alert"
 * - Dark theme styling consistent with NVIDIA design system
 *
 * @example
 * ```tsx
 * // Basic usage with string error
 * <SummaryCardError
 *   type="hourly"
 *   error="Failed to fetch"
 *   onRetry={handleRetry}
 * />
 *
 * // With Error object and retrying state
 * <SummaryCardError
 *   type="daily"
 *   error={new Error('Network error')}
 *   onRetry={handleRetry}
 *   isRetrying={isLoading}
 * />
 * ```
 */
export function SummaryCardError({
  type,
  error,
  onRetry,
  isRetrying = false,
  className,
}: SummaryCardErrorProps) {
  const isHourly = type === 'hourly';
  const title = isHourly ? 'Hourly Summary' : 'Daily Summary';
  const Icon = isHourly ? Clock : Calendar;
  const userMessage = getUserFriendlyMessage(error);

  return (
    <Card
      className={clsx('mb-4 border-l-4 border-gray-800 bg-[#1A1A1A]', className)}
      style={{ borderLeftColor: '#ef4444' }} // red-500 - error state
      data-testid={`summary-card-error-${type}`}
      role="alert"
      aria-live="polite"
    >
      {/* Header */}
      <Flex justifyContent="start" className="mb-3 gap-2">
        <Icon className="h-5 w-5 text-gray-500" aria-hidden="true" />
        <Title className="text-white">{title}</Title>
      </Flex>

      {/* Error content */}
      <div
        className="rounded-lg border border-red-500/30 bg-red-900/20 p-4"
        data-testid={`summary-card-error-content-${type}`}
      >
        <Flex justifyContent="start" alignItems="start" className="gap-3">
          <AlertTriangle
            className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-400"
            aria-hidden="true"
          />
          <div className="flex-1">
            <Text className="font-medium text-red-400">
              Failed to load summary
            </Text>
            <Text className="mt-1 text-sm text-gray-400">
              {userMessage}
            </Text>

            {/* Retry button */}
            <button
              type="button"
              onClick={onRetry}
              disabled={isRetrying}
              className={clsx(
                'mt-3 inline-flex items-center gap-2 rounded-md px-3 py-1.5',
                'text-sm font-medium transition-colors',
                'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
                isRetrying
                  ? 'cursor-not-allowed bg-gray-700/30 text-gray-500'
                  : 'bg-gray-700/50 text-[#76B900] hover:bg-gray-700'
              )}
              data-testid={`summary-card-error-retry-${type}`}
              aria-label={isRetrying ? 'Retrying...' : 'Retry loading summary'}
            >
              <RefreshCw
                className={clsx('h-3.5 w-3.5', isRetrying && 'animate-spin')}
                aria-hidden="true"
              />
              {isRetrying ? 'Retrying...' : 'Try again'}
            </button>
          </div>
        </Flex>
      </div>
    </Card>
  );
}

export default SummaryCardError;
