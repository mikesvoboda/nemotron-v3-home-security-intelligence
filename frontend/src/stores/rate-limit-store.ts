/**
 * Rate Limit State Management Store
 *
 * Provides central state management for rate limit information across frontend components.
 * Uses Zustand for reactive state management with auto-clear behavior when rate limit resets.
 *
 * Enhancements (NEM-3399, NEM-3400):
 * - DevTools middleware for debugging
 * - useShallow hooks for selective subscriptions
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { useShallow } from 'zustand/shallow';

// ============================================================================
// Types
// ============================================================================

/**
 * Rate limit information from API response headers.
 */
export interface RateLimitInfo {
  /** Maximum requests allowed per window */
  limit: number;
  /** Remaining requests in current window */
  remaining: number;
  /** Unix timestamp (seconds) when rate limit resets */
  reset: number;
  /** Optional retry-after value in seconds */
  retryAfter?: number;
}

/**
 * Rate limit store state and actions.
 */
export interface RateLimitState {
  /** Current rate limit information, null if not set */
  current: RateLimitInfo | null;
  /** Whether the client is currently rate limited (remaining = 0) */
  isLimited: boolean;
  /** Seconds until rate limit resets, 0 if not limited */
  secondsUntilReset: number;
  /** Update rate limit state with new information */
  update: (info: RateLimitInfo) => void;
  /** Clear all rate limit state */
  clear: () => void;
  /** Internal: Timer ID for auto-clear */
  _timerId: ReturnType<typeof setTimeout> | null;
}

// ============================================================================
// Store (NEM-3400: DevTools middleware)
// ============================================================================

/**
 * Zustand store for rate limit state management.
 *
 * Features:
 * - Tracks current rate limit info from API responses
 * - Provides `isLimited` flag when remaining = 0
 * - Calculates `secondsUntilReset` from reset timestamp
 * - Auto-clears `isLimited` when reset time passes
 * - DevTools integration for debugging (NEM-3400)
 *
 * @example
 * ```tsx
 * import { useRateLimitStore } from '@/stores/rate-limit-store';
 *
 * // In a component
 * const { isLimited, secondsUntilReset, update } = useRateLimitStore();
 *
 * // Update from API response headers
 * update({
 *   limit: 100,
 *   remaining: 0,
 *   reset: Math.floor(Date.now() / 1000) + 60,
 * });
 *
 * if (isLimited) {
 *   return <div>Rate limited. Retry in {secondsUntilReset}s</div>;
 * }
 * ```
 */
export const useRateLimitStore = create<RateLimitState>()(
  devtools(
    (set, get) => ({
      current: null,
      isLimited: false,
      secondsUntilReset: 0,
      _timerId: null,

      update: (info: RateLimitInfo) => {
        // Clear any existing timer
        const existingTimerId = get()._timerId;
        if (existingTimerId !== null) {
          clearTimeout(existingTimerId);
        }

        const now = Math.floor(Date.now() / 1000);
        const secondsUntilReset = Math.max(0, info.reset - now);
        const isLimited = info.remaining === 0;

        // If rate limited and reset time is in the future, schedule auto-clear
        let timerId: ReturnType<typeof setTimeout> | null = null;
        if (isLimited && secondsUntilReset > 0) {
          timerId = setTimeout(() => {
            set(
              {
                isLimited: false,
                secondsUntilReset: 0,
                _timerId: null,
              },
              undefined,
              'update/auto-clear'
            );
          }, secondsUntilReset * 1000);
        }

        set(
          {
            current: info,
            isLimited,
            secondsUntilReset,
            _timerId: timerId,
          },
          undefined,
          'update'
        );
      },

      clear: () => {
        // Clear any existing timer
        const existingTimerId = get()._timerId;
        if (existingTimerId !== null) {
          clearTimeout(existingTimerId);
        }

        set(
          {
            current: null,
            isLimited: false,
            secondsUntilReset: 0,
            _timerId: null,
          },
          undefined,
          'clear'
        );
      },
    }),
    { name: 'rate-limit-store', enabled: import.meta.env.DEV }
  )
);

// ============================================================================
// Selectors
// ============================================================================

/**
 * Selector for rate limit percentage used.
 * Returns a value between 0 and 100.
 */
export const selectRateLimitUsagePercent = (state: RateLimitState): number => {
  if (!state.current || state.current.limit === 0) {
    return 0;
  }
  const used = state.current.limit - state.current.remaining;
  return Math.round((used / state.current.limit) * 100);
};

/**
 * Selector for whether rate limit usage is high (>= 80%).
 */
export const selectIsHighUsage = (state: RateLimitState): boolean => {
  return selectRateLimitUsagePercent(state) >= 80;
};

// ============================================================================
// Shallow Hooks for Selective Subscriptions (NEM-3399)
// ============================================================================

/**
 * Hook to select rate limit status flags with shallow equality.
 * Prevents re-renders when only detailed info changes but status stays the same.
 *
 * @example
 * ```tsx
 * const { isLimited, secondsUntilReset } = useRateLimitStatus();
 * ```
 */
export function useRateLimitStatus() {
  return useRateLimitStore(
    useShallow((state) => ({
      isLimited: state.isLimited,
      secondsUntilReset: state.secondsUntilReset,
    }))
  );
}

/**
 * Hook to select the current rate limit info.
 *
 * @example
 * ```tsx
 * const current = useRateLimitCurrent();
 * ```
 */
export function useRateLimitCurrent() {
  return useRateLimitStore((state) => state.current);
}

/**
 * Hook to select rate limit actions only.
 * Actions are stable references and don't cause re-renders.
 *
 * @example
 * ```tsx
 * const { update, clear } = useRateLimitActions();
 * ```
 */
export function useRateLimitActions() {
  return useRateLimitStore(
    useShallow((state) => ({
      update: state.update,
      clear: state.clear,
    }))
  );
}
