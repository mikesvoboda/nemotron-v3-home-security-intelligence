/**
 * Rate Limit Countdown Hook
 *
 * Provides a live countdown timer for rate limit reset.
 * Updates every second when rate limited for accurate UI display.
 */

import { useEffect, useState } from 'react';

import { useRateLimitStore } from '../stores/rate-limit-store';

// ============================================================================
// Types
// ============================================================================

/**
 * Return type for the useRateLimitCountdown hook.
 */
export interface UseRateLimitCountdownReturn {
  /** Whether the client is currently rate limited */
  isLimited: boolean;
  /** Seconds remaining until rate limit resets (updates every second) */
  secondsRemaining: number;
  /** Formatted countdown string (e.g., "1:30" or "0:05") */
  formattedCountdown: string;
  /** Current rate limit info, null if not set */
  current: {
    limit: number;
    remaining: number;
    reset: number;
    retryAfter?: number;
  } | null;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Formats seconds into MM:SS or M:SS format.
 *
 * @param seconds - Number of seconds to format
 * @returns Formatted string like "1:30" or "0:05"
 */
export function formatCountdown(seconds: number): string {
  if (seconds <= 0) {
    return '0:00';
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook that provides a live countdown for rate limit reset.
 *
 * When rate limited, this hook updates every second to provide an accurate
 * countdown for UI display. When not rate limited, it returns static values
 * without the interval overhead.
 *
 * @returns Object containing isLimited, secondsRemaining, formattedCountdown, and current rate limit info
 *
 * @example
 * ```tsx
 * import { useRateLimitCountdown } from '@/hooks/useRateLimitCountdown';
 *
 * function RateLimitBanner() {
 *   const { isLimited, formattedCountdown } = useRateLimitCountdown();
 *
 *   if (!isLimited) return null;
 *
 *   return (
 *     <div className="bg-yellow-500 p-2 text-center">
 *       Rate limited. Retry in {formattedCountdown}
 *     </div>
 *   );
 * }
 * ```
 */
export function useRateLimitCountdown(): UseRateLimitCountdownReturn {
  const { current, isLimited } = useRateLimitStore();

  // Local state for live countdown
  const [secondsRemaining, setSecondsRemaining] = useState<number>(() => {
    if (!current) return 0;
    const now = Math.floor(Date.now() / 1000);
    return Math.max(0, current.reset - now);
  });

  // Update countdown every second when rate limited
  useEffect(() => {
    if (!isLimited || !current) {
      setSecondsRemaining(0);
      return;
    }

    // Calculate initial value
    const now = Math.floor(Date.now() / 1000);
    const initialSeconds = Math.max(0, current.reset - now);
    setSecondsRemaining(initialSeconds);

    // If already past reset time, don't start interval
    if (initialSeconds <= 0) {
      return;
    }

    // Update every second
    const intervalId = setInterval(() => {
      const currentNow = Math.floor(Date.now() / 1000);
      const remaining = Math.max(0, current.reset - currentNow);
      setSecondsRemaining(remaining);

      // Stop interval when countdown reaches 0
      if (remaining <= 0) {
        clearInterval(intervalId);
      }
    }, 1000);

    return () => {
      clearInterval(intervalId);
    };
  }, [isLimited, current]);

  return {
    isLimited,
    secondsRemaining,
    formattedCountdown: formatCountdown(secondsRemaining),
    current,
  };
}
