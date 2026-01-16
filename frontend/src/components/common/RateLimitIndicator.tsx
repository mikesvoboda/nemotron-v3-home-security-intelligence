/**
 * RateLimitIndicator - Displays rate limit status with countdown timer.
 *
 * Shows a fixed-position indicator when API rate limit quota is low or exhausted.
 * - Yellow warning when quota < 50%
 * - Red alert when quota < 20% or rate limited (remaining = 0)
 * - Live countdown showing seconds until reset
 * - Toast notification when quota drops below 20%
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
import { useEffect, useRef } from 'react';
import { toast } from 'sonner';

import { useRateLimitCountdown } from '../../hooks/useRateLimitCountdown';

// ============================================================================
// Types
// ============================================================================

export interface RateLimitIndicatorProps {
  /** Optional class name for additional styling */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

/** Threshold below which the quota is considered "very low" and toast notification is shown */
const VERY_LOW_QUOTA_THRESHOLD = 20;

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
export default function RateLimitIndicator({ className }: RateLimitIndicatorProps) {
  const { isLimited, formattedCountdown, current } = useRateLimitCountdown();

  // Track if we've already shown a toast for the current low quota state
  // This prevents showing multiple toasts for the same low quota event
  const hasShownToastRef = useRef(false);

  // Calculate remaining percentage for the component
  const remainingPercentage = current
    ? calculateRemainingPercentage(current.remaining, current.limit)
    : 100;

  // Determine if quota is very low (< 20%)
  const isVeryLow = remainingPercentage < VERY_LOW_QUOTA_THRESHOLD;

  // Show toast notification when quota drops below 20%
  useEffect(() => {
    if (!current) {
      // Reset toast flag when rate limit info is cleared
      hasShownToastRef.current = false;
      return;
    }

    // Check if quota is very low and we haven't shown a toast yet
    if (isVeryLow && !hasShownToastRef.current) {
      toast.warning('API quota running low', {
        description: `Only ${current.remaining} of ${current.limit} requests remaining. Consider reducing request frequency.`,
        duration: 6000,
      });
      hasShownToastRef.current = true;
    }

    // Reset the flag when quota recovers above 20%
    if (!isVeryLow && hasShownToastRef.current) {
      hasShownToastRef.current = false;
    }
  }, [current, isVeryLow]);

  // Don't render if no rate limit info
  if (!current) {
    return null;
  }

  // Don't render if quota is above 50% and not rate limited
  if (remainingPercentage > 50 && !isLimited) {
    return null;
  }

  // Determine styling based on state
  const isRateLimited = isLimited || current.remaining === 0;

  // Build ARIA label
  const ariaLabel = isRateLimited
    ? `Rate limited. Retry in ${formattedCountdown}`
    : `API quota low: ${current.remaining} of ${current.limit} requests remaining`;

  return (
    <div
      className={clsx(
        'fixed bottom-4 right-4 z-50 min-w-[200px] rounded-lg border p-4 shadow-lg',
        isRateLimited ? 'border-red-300 bg-red-100' : 'border-yellow-300 bg-yellow-100',
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
