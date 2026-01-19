/**
 * useSummaryExpansion - Hook for persisting summary expansion state
 *
 * Provides a useState-like API with automatic persistence to sessionStorage.
 * This allows expansion state to survive page refreshes within the same session,
 * but resets when the browser tab is closed (appropriate for UI state).
 *
 * @see NEM-2925
 */

import { useState, useEffect, useCallback, useMemo } from 'react';

/** Storage key prefix for summary expansion state */
const STORAGE_KEY_PREFIX = 'summary-expansion-';

/**
 * Options for useSummaryExpansion hook
 */
export interface UseSummaryExpansionOptions {
  /** Unique identifier for this summary (e.g., 'hourly-123' or 'daily-456') */
  summaryId: string;
  /** Default expanded state if no stored value exists */
  defaultExpanded?: boolean;
}

/**
 * Return type for useSummaryExpansion hook
 */
export interface UseSummaryExpansionReturn {
  /** Whether the summary is currently expanded */
  isExpanded: boolean;
  /** Toggle the expansion state */
  toggle: () => void;
  /** Set expansion state directly */
  setExpanded: (expanded: boolean) => void;
  /** Clear stored state (useful for testing) */
  clearStorage: () => void;
}

/**
 * Custom hook that persists summary expansion state in sessionStorage
 *
 * @param options - Configuration options
 * @returns Object with expansion state and control methods
 *
 * @example
 * ```tsx
 * function ExpandableSummary({ summary }: Props) {
 *   const { isExpanded, toggle } = useSummaryExpansion({
 *     summaryId: `${summary.type}-${summary.id}`,
 *     defaultExpanded: false,
 *   });
 *
 *   return (
 *     <button onClick={toggle} aria-expanded={isExpanded}>
 *       {isExpanded ? 'Hide' : 'Show'} Details
 *     </button>
 *   );
 * }
 * ```
 */
export function useSummaryExpansion(
  options: UseSummaryExpansionOptions
): UseSummaryExpansionReturn {
  const { summaryId, defaultExpanded = false } = options;

  // Memoize storage key to prevent unnecessary recalculations
  const storageKey = useMemo(
    () => `${STORAGE_KEY_PREFIX}${summaryId}`,
    [summaryId]
  );

  // Read stored value or use default
  const readStoredValue = useCallback((): boolean => {
    // Check if we're in a browser environment
    if (typeof window === 'undefined') {
      return defaultExpanded;
    }

    try {
      const item = window.sessionStorage.getItem(storageKey);
      if (item === null) {
        return defaultExpanded;
      }
      return item === 'true';
    } catch (error) {
      // sessionStorage may be disabled or quota exceeded
      console.warn(`Error reading sessionStorage key "${storageKey}":`, error);
      return defaultExpanded;
    }
  }, [storageKey, defaultExpanded]);

  // Initialize state from storage
  const [isExpanded, setIsExpanded] = useState<boolean>(readStoredValue);

  // Sync state with storage when summaryId changes
  useEffect(() => {
    setIsExpanded(readStoredValue());
  }, [readStoredValue]);

  // Persist state to sessionStorage whenever it changes
  const persistToStorage = useCallback(
    (value: boolean): void => {
      if (typeof window === 'undefined') {
        return;
      }

      try {
        window.sessionStorage.setItem(storageKey, String(value));
      } catch (error) {
        // sessionStorage may be disabled or quota exceeded
        console.warn(`Error writing sessionStorage key "${storageKey}":`, error);
      }
    },
    [storageKey]
  );

  // Set expanded state and persist
  const setExpanded = useCallback(
    (expanded: boolean): void => {
      setIsExpanded(expanded);
      persistToStorage(expanded);
    },
    [persistToStorage]
  );

  // Toggle expansion state
  const toggle = useCallback((): void => {
    setIsExpanded((prev) => {
      const next = !prev;
      persistToStorage(next);
      return next;
    });
  }, [persistToStorage]);

  // Clear storage (for testing or reset)
  const clearStorage = useCallback((): void => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      window.sessionStorage.removeItem(storageKey);
    } catch (error) {
      console.warn(`Error removing sessionStorage key "${storageKey}":`, error);
    }
  }, [storageKey]);

  return {
    isExpanded,
    toggle,
    setExpanded,
    clearStorage,
  };
}

export default useSummaryExpansion;
