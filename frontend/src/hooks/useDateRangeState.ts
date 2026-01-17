/**
 * Hook for date range state management with URL persistence.
 *
 * Supports both preset ranges (1h, 24h, today, 7d, 30d, 90d, all)
 * and custom date ranges, syncing state to URL query parameters
 * for shareable links.
 *
 * @module hooks/useDateRangeState
 * @see NEM-2701
 */

import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

// ============================================================================
// Types
// ============================================================================

/**
 * Available date range presets.
 * - '1h': Last hour (now - 1 hour to now)
 * - '24h': Last 24 hours (now - 24 hours to now)
 * - 'today': Start of today to now
 * - '7d': Last 7 days (start of today - 6 days to end of today)
 * - '30d': Last 30 days (start of today - 29 days to end of today)
 * - '90d': Last 90 days (start of today - 89 days to end of today)
 * - 'all': No date filter (returns all data)
 * - 'custom': User-specified start and end dates
 */
export type DateRangePreset = '1h' | '24h' | 'today' | '7d' | '30d' | '90d' | 'all' | 'custom';

/**
 * Date range with start and end dates.
 */
export interface DateRange {
  startDate: Date;
  endDate: Date;
}

/**
 * Options for configuring the date range state hook.
 */
export interface UseDateRangeStateOptions {
  /**
   * Default preset to use when no URL param is present.
   * @default '7d'
   */
  defaultPreset?: DateRangePreset;

  /**
   * URL parameter name for the date range.
   * @default 'range'
   */
  urlParam?: string;

  /**
   * Whether to persist the date range to URL.
   * @default true
   */
  persistToUrl?: boolean;
}

/**
 * API parameters for date filtering.
 * Dates are formatted as YYYY-MM-DD strings.
 * Empty strings indicate no filtering.
 */
export interface DateRangeApiParams {
  /** Start date in YYYY-MM-DD format, or empty string for no filter */
  start_date: string;
  /** End date in YYYY-MM-DD format, or empty string for no filter */
  end_date: string;
}

/**
 * Return type for the useDateRangeState hook.
 */
export interface UseDateRangeStateReturn {
  /** Current preset or 'custom' for custom ranges */
  preset: DateRangePreset;
  /** Current date range (start and end dates) */
  range: DateRange;
  /** Set a preset date range */
  setPreset: (preset: DateRangePreset) => void;
  /** Set a custom date range */
  setCustomRange: (start: Date, end: Date) => void;
  /** API-ready parameters with dates in YYYY-MM-DD format */
  apiParams: DateRangeApiParams;
  /** Whether the current range is a custom range */
  isCustom: boolean;
  /** Human-readable label for the current preset */
  presetLabel: string;
  /** Reset to default preset */
  reset: () => void;
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Human-readable labels for each preset.
 */
export const PRESET_LABELS: Record<DateRangePreset, string> = {
  '1h': 'Last hour',
  '24h': 'Last 24 hours',
  today: 'Today',
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
  '90d': 'Last 90 days',
  all: 'All time',
  custom: 'Custom',
};

/**
 * Valid preset values for validation.
 */
const VALID_PRESETS = new Set<string>(['1h', '24h', 'today', '7d', '30d', '90d', 'all', 'custom']);

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Formats a Date to YYYY-MM-DD string in UTC.
 */
function formatDateToYYYYMMDD(date: Date): string {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Parses a YYYY-MM-DD string to a Date object in UTC.
 * Returns null if the string is invalid.
 */
function parseDateFromYYYYMMDD(dateStr: string | null): Date | null {
  if (!dateStr || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    return null;
  }
  const date = new Date(dateStr + 'T00:00:00.000Z');
  if (isNaN(date.getTime())) {
    return null;
  }
  return date;
}

/**
 * Gets the start of a day in UTC.
 */
function getStartOfDayUTC(date: Date): Date {
  const result = new Date(date);
  result.setUTCHours(0, 0, 0, 0);
  return result;
}

/**
 * Gets the end of a day in UTC (23:59:59.999).
 */
function getEndOfDayUTC(date: Date): Date {
  const result = new Date(date);
  result.setUTCHours(23, 59, 59, 999);
  return result;
}

/**
 * Validates a preset string from URL params.
 */
function isValidPreset(value: string | null): value is DateRangePreset {
  return value !== null && value !== '' && VALID_PRESETS.has(value);
}

/**
 * Calculates the date range for a given preset.
 * Uses the provided 'now' date for testability.
 */
export function calculatePresetRange(preset: DateRangePreset, now: Date): DateRange {
  switch (preset) {
    case '1h': {
      // Now - 1 hour to Now
      const startDate = new Date(now.getTime() - 60 * 60 * 1000);
      return { startDate, endDate: new Date(now) };
    }
    case '24h': {
      // Now - 24 hours to Now
      const startDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      return { startDate, endDate: new Date(now) };
    }
    case 'today': {
      // Start of today to Now
      const startDate = getStartOfDayUTC(now);
      return { startDate, endDate: new Date(now) };
    }
    case '7d': {
      // Start of (today - 6 days) to End of today
      const startDate = getStartOfDayUTC(now);
      startDate.setUTCDate(startDate.getUTCDate() - 6);
      const endDate = getEndOfDayUTC(now);
      return { startDate, endDate };
    }
    case '30d': {
      // Start of (today - 29 days) to End of today
      const startDate = getStartOfDayUTC(now);
      startDate.setUTCDate(startDate.getUTCDate() - 29);
      const endDate = getEndOfDayUTC(now);
      return { startDate, endDate };
    }
    case '90d': {
      // Start of (today - 89 days) to End of today
      const startDate = getStartOfDayUTC(now);
      startDate.setUTCDate(startDate.getUTCDate() - 89);
      const endDate = getEndOfDayUTC(now);
      return { startDate, endDate };
    }
    case 'all':
    case 'custom':
    default: {
      // For 'all' and 'custom', return current date as placeholder
      // Custom will be overridden by actual custom values
      // The apiParams will return empty strings for 'all'
      return { startDate: new Date(now), endDate: new Date(now) };
    }
  }
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for managing date range state with URL persistence.
 *
 * @example Basic usage with default preset
 * ```tsx
 * function AnalyticsPage() {
 *   const { preset, range, setPreset, apiParams } = useDateRangeState();
 *
 *   const { data } = useAnalyticsQuery({
 *     start_date: apiParams.start_date,
 *     end_date: apiParams.end_date,
 *   });
 *
 *   return (
 *     <div>
 *       <DateRangeSelector
 *         value={preset}
 *         onChange={setPreset}
 *       />
 *       <AnalyticsChart data={data} />
 *     </div>
 *   );
 * }
 * ```
 *
 * @example Custom date range
 * ```tsx
 * function EventsPage() {
 *   const { preset, range, setPreset, setCustomRange, isCustom } = useDateRangeState();
 *
 *   const handleDatePickerChange = (start: Date, end: Date) => {
 *     setCustomRange(start, end);
 *   };
 *
 *   return (
 *     <div>
 *       <PresetButtons value={preset} onChange={setPreset} />
 *       <DatePicker
 *         startDate={range.startDate}
 *         endDate={range.endDate}
 *         onChange={handleDatePickerChange}
 *       />
 *     </div>
 *   );
 * }
 * ```
 *
 * @example Multiple date ranges on same page
 * ```tsx
 * function Dashboard() {
 *   const eventsDateRange = useDateRangeState({ urlParam: 'events_range' });
 *   const alertsDateRange = useDateRangeState({ urlParam: 'alerts_range' });
 *
 *   // Use independently...
 * }
 * ```
 *
 * @example Without URL persistence (for modals)
 * ```tsx
 * function ExportModal() {
 *   const { setCustomRange, apiParams } = useDateRangeState({
 *     persistToUrl: false,
 *     defaultPreset: 'today',
 *   });
 *
 *   // Modal won't affect URL
 * }
 * ```
 */
export function useDateRangeState(options: UseDateRangeStateOptions = {}): UseDateRangeStateReturn {
  const { defaultPreset = '7d', urlParam = 'range', persistToUrl = true } = options;

  const [searchParams, setSearchParams] = useSearchParams();

  // Parse preset from URL
  const presetFromUrl = useMemo((): DateRangePreset | null => {
    if (!persistToUrl) return null;

    const rangeParam = searchParams.get(urlParam);
    if (isValidPreset(rangeParam)) {
      return rangeParam;
    }

    return null;
  }, [searchParams, urlParam, persistToUrl]);

  // Parse custom dates from URL
  const customDatesFromUrl = useMemo((): DateRange | null => {
    if (!persistToUrl) return null;
    if (presetFromUrl !== 'custom') return null;

    const startParam = searchParams.get('start');
    const endParam = searchParams.get('end');

    if (!startParam || !endParam) return null;

    const startDate = parseDateFromYYYYMMDD(startParam);
    const endDate = parseDateFromYYYYMMDD(endParam);

    if (!startDate || !endDate) return null;

    // Set end date to end of day
    return {
      startDate,
      endDate: getEndOfDayUTC(endDate),
    };
  }, [searchParams, presetFromUrl, persistToUrl]);

  // Determine current preset (from URL or default)
  const preset = useMemo((): DateRangePreset => {
    if (presetFromUrl === 'custom' && !customDatesFromUrl) {
      // Invalid custom range (missing or invalid dates), fall back to default
      return defaultPreset;
    }
    return presetFromUrl ?? defaultPreset;
  }, [presetFromUrl, customDatesFromUrl, defaultPreset]);

  // Calculate current range
  const range = useMemo((): DateRange => {
    if (preset === 'custom' && customDatesFromUrl) {
      return customDatesFromUrl;
    }
    return calculatePresetRange(preset, new Date());
  }, [preset, customDatesFromUrl]);

  // Calculate API params
  const apiParams = useMemo((): DateRangeApiParams => {
    if (preset === 'all') {
      return { start_date: '', end_date: '' };
    }
    return {
      start_date: formatDateToYYYYMMDD(range.startDate),
      end_date: formatDateToYYYYMMDD(range.endDate),
    };
  }, [preset, range]);

  // Helper to update search params while preserving other params
  const updateParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      if (!persistToUrl) return;

      setSearchParams(
        (prev) => {
          const newParams = new URLSearchParams(prev);
          Object.entries(updates).forEach(([key, value]) => {
            if (value === undefined || value === '') {
              newParams.delete(key);
            } else {
              newParams.set(key, value);
            }
          });
          return newParams;
        },
        { replace: true }
      );
    },
    [setSearchParams, persistToUrl]
  );

  // Set preset
  const setPreset = useCallback(
    (newPreset: DateRangePreset) => {
      if (newPreset === 'custom') {
        // Don't switch to custom without dates - use setCustomRange instead
        return;
      }

      updateParams({
        [urlParam]: newPreset,
        start: undefined,
        end: undefined,
      });
    },
    [updateParams, urlParam]
  );

  // Set custom range
  const setCustomRange = useCallback(
    (start: Date, end: Date) => {
      updateParams({
        [urlParam]: 'custom',
        start: formatDateToYYYYMMDD(start),
        end: formatDateToYYYYMMDD(end),
      });
    },
    [updateParams, urlParam]
  );

  // Reset to default preset
  const reset = useCallback(() => {
    updateParams({
      [urlParam]: undefined,
      start: undefined,
      end: undefined,
    });
  }, [updateParams, urlParam]);

  // Derived values
  const isCustom = preset === 'custom';
  const presetLabel = PRESET_LABELS[preset];

  return {
    preset,
    range,
    setPreset,
    setCustomRange,
    apiParams,
    isCustom,
    presetLabel,
    reset,
  };
}

export default useDateRangeState;
