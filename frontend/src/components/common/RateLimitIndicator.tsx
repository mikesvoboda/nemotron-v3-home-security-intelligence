/**
 * RateLimitIndicator - Displays rate limit status with countdown timer.
 *
 * Shows a fixed-position indicator when API rate limit quota is low or exhausted.
 * - Yellow warning when quota < 50%
 * - Red alert when rate limited (remaining = 0)
 * - Live countdown showing seconds until reset
 * - Auto-hides when quota replenishes above 50%
 *
 * @example
 * ```tsx
 * // Add to App.tsx layout
 * <RateLimitIndicator />
 * ```
 */
import { clsx } from 'clsx';
import { AlertTriangle } from 'lucide-react';

import { useRateLimitCountdown } from '../../hooks/useRateLimitCountdown';

// ============================================================================
// Types
// ============================================================================

export interface RateLimitIndicatorProps {
  /** Optional class name for additional styling */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Calculate the percentage of quota remaining.
 * Returns a value between 0 and 100.
 */
function calculateRemainingPercentage(remaining: number, limit: number): number {
  if (limit === 0) return 0;
  return Math.round((remaining / limit) * 100);
}

// ============================================================================
// Component
// ============================================================================

/**
 * RateLimitIndicator displays rate limit status with visual feedback.
 *
 * Features:
 * - Fixed position at bottom-right corner
 * - Yellow warning when quota drops below 50%
 * - Red alert when rate limited (remaining = 0)
 * - Live countdown timer until rate limit resets
 * - Auto-hides when quota replenishes above 50%
 * - Accessible with ARIA attributes
 */
export default function RateLimitIndicator({
  className,
}: RateLimitIndicatorProps) {
  const { isLimited, formattedCountdown, current } = useRateLimitCountdown();

  // Don't render if no rate limit info
  if (!current) {
    return null;
  }

  const remainingPercentage = calculateRemainingPercentage(
    current.remaining,
    current.limit
  );

  // Don't render if quota is above 50% and not rate limited
  if (remainingPercentage > 50 && !isLimited) {
    return null;
  }

  // Determine styling based on state
  const isRateLimited = isLimited || current.remaining === 0;
  const isVeryLow = remainingPercentage < 20;

  // Build ARIA label
  const ariaLabel = isRateLimited
    ? `Rate limited. Retry in ${formattedCountdown}`
    : `API quota low: ${current.remaining} of ${current.limit} requests remaining`;

  return (
    <div
      className={clsx(
        'fixed bottom-4 right-4 z-50 min-w-[200px] rounded-lg border p-4 shadow-lg',
        isRateLimited
          ? 'border-red-300 bg-red-100'
          : 'border-yellow-300 bg-yellow-100',
        className
      )}
      data-testid="rate-limit-indicator"
      role="status"
      aria-live="polite"
      aria-label={ariaLabel}
    >
      {isRateLimited ? (
        // Rate limited state - show alert with countdown
        <div className="flex items-center gap-2">
          <AlertTriangle
            className="h-5 w-5 flex-shrink-0 text-red-600"
            data-testid="rate-limit-icon"
            aria-hidden="true"
          />
          <div>
            <p className="font-medium text-red-800">Rate Limited</p>
            <p className="text-sm text-red-600">Retry in {formattedCountdown}</p>
          </div>
        </div>
      ) : (
        // Low quota warning state - show progress bar
        <div>
          <div className="mb-1 flex justify-between text-sm">
            <span className="font-medium text-yellow-800">API Quota</span>
            <span className="text-yellow-700">
              {current.remaining}/{current.limit}
            </span>
          </div>
          {/* Custom progress bar */}
          <div
            className={clsx(
              'h-2 w-full overflow-hidden rounded-full',
              isVeryLow ? 'bg-red-200' : 'bg-yellow-200'
            )}
            data-testid="rate-limit-progress-container"
          >
            <div
              className={clsx(
                'h-full rounded-full transition-all duration-300',
                isVeryLow ? 'bg-red-500' : 'bg-yellow-500'
              )}
              style={{ width: `${remainingPercentage}%` }}
              data-testid="rate-limit-progress"
              role="progressbar"
              aria-valuenow={remainingPercentage}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${remainingPercentage}% of API quota remaining`}
            />
          </div>
        </div>
      )}
    </div>
  );
}
