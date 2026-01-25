/**
 * useThresholdPreview - Hook for real-time threshold preview.
 *
 * Provides debounced preview of how many events would trigger at a given threshold.
 * Uses the existing testAlertRule API when a rule ID is available.
 *
 * @see NEM-3604 Alert Threshold Configuration
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { testAlertRule } from '../services/api';

import type { RuleTestResponse } from '../services/api';

// =============================================================================
// Types
// =============================================================================

export interface ThresholdPreviewState {
  /** Whether preview data is loading */
  isLoading: boolean;
  /** Error message if preview fetch failed */
  error: string | null;
  /** Number of events that would trigger at current threshold */
  eventsMatched: number | null;
  /** Total events tested */
  eventsTested: number | null;
  /** Match rate as percentage (0-100) */
  matchRate: number | null;
  /** Full test response for detailed results */
  testResponse: RuleTestResponse | null;
}

export interface UseThresholdPreviewOptions {
  /** Alert rule ID (required for preview to work) */
  ruleId?: string | null;
  /** Current threshold value being configured */
  threshold: number | null;
  /** Debounce delay in milliseconds (default: 500ms) */
  debounceMs?: number;
  /** Maximum events to test against (default: 100) */
  testLimit?: number;
  /** Whether preview is enabled (default: true when ruleId is set) */
  enabled?: boolean;
}

export interface UseThresholdPreviewResult extends ThresholdPreviewState {
  /** Manually trigger a preview refresh */
  refresh: () => void;
  /** Clear the current preview data */
  clear: () => void;
}

// =============================================================================
// Constants
// =============================================================================

const DEFAULT_DEBOUNCE_MS = 500;
const DEFAULT_TEST_LIMIT = 100;

// =============================================================================
// Hook
// =============================================================================

/**
 * Hook for fetching and caching threshold preview data.
 *
 * Features:
 * - Debounced API calls to prevent excessive requests
 * - Loading and error state management
 * - Manual refresh capability
 * - Automatic cleanup on unmount
 *
 * @example
 * ```tsx
 * const { isLoading, eventsMatched, eventsTested, matchRate } = useThresholdPreview({
 *   ruleId: 'abc-123',
 *   threshold: 70,
 * });
 *
 * return (
 *   <div>
 *     {isLoading ? 'Loading...' : `${eventsMatched}/${eventsTested} events would trigger`}
 *   </div>
 * );
 * ```
 */
export function useThresholdPreview({
  ruleId,
  threshold,
  debounceMs = DEFAULT_DEBOUNCE_MS,
  testLimit = DEFAULT_TEST_LIMIT,
  enabled = true,
}: UseThresholdPreviewOptions): UseThresholdPreviewResult {
  const [state, setState] = useState<ThresholdPreviewState>({
    isLoading: false,
    error: null,
    eventsMatched: null,
    eventsTested: null,
    matchRate: null,
    testResponse: null,
  });

  // Track the latest request to handle race conditions
  const latestRequestRef = useRef<number>(0);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch preview data
  const fetchPreview = useCallback(
    async (requestId: number) => {
      if (!ruleId || !enabled) {
        return;
      }

      setState((prev) => ({ ...prev, isLoading: true, error: null }));

      try {
        const response = await testAlertRule(ruleId, { limit: testLimit });

        // Only update if this is still the latest request
        if (requestId === latestRequestRef.current) {
          setState({
            isLoading: false,
            error: null,
            eventsMatched: response.events_matched,
            eventsTested: response.events_tested,
            matchRate: response.match_rate,
            testResponse: response,
          });
        }
      } catch (err) {
        // Only update if this is still the latest request
        if (requestId === latestRequestRef.current) {
          setState((prev) => ({
            ...prev,
            isLoading: false,
            error: err instanceof Error ? err.message : 'Failed to fetch preview',
          }));
        }
      }
    },
    [ruleId, testLimit, enabled]
  );

  // Debounced fetch effect
  useEffect(() => {
    // Skip if no rule ID or not enabled
    if (!ruleId || !enabled) {
      return;
    }

    // Clear any pending debounce timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Increment request ID to track latest
    const requestId = ++latestRequestRef.current;

    // Set up debounced fetch
    debounceTimerRef.current = setTimeout(() => {
      void fetchPreview(requestId);
    }, debounceMs);

    // Cleanup on unmount or dependency change
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [ruleId, threshold, debounceMs, enabled, fetchPreview]);

  // Manual refresh function
  const refresh = useCallback(() => {
    if (!ruleId || !enabled) return;

    // Clear any pending debounce
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Fetch immediately
    const requestId = ++latestRequestRef.current;
    void fetchPreview(requestId);
  }, [ruleId, enabled, fetchPreview]);

  // Clear function
  const clear = useCallback(() => {
    // Cancel any pending request
    latestRequestRef.current++;

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    setState({
      isLoading: false,
      error: null,
      eventsMatched: null,
      eventsTested: null,
      matchRate: null,
      testResponse: null,
    });
  }, []);

  return {
    ...state,
    refresh,
    clear,
  };
}

export default useThresholdPreview;
