/**
 * ThresholdPreview - Component showing real-time preview of event matches.
 *
 * Displays how many historical events would trigger at the selected threshold,
 * with loading and error states.
 *
 * @see NEM-3604 Alert Threshold Configuration
 */

import { clsx } from 'clsx';
import { AlertCircle, Loader2, RefreshCw, TrendingUp } from 'lucide-react';

import type { UseThresholdPreviewResult } from '../../hooks/useThresholdPreview';

// =============================================================================
// Types
// =============================================================================

export interface ThresholdPreviewProps {
  /** Preview state from useThresholdPreview hook */
  previewState: UseThresholdPreviewResult;
  /** Whether to show the refresh button */
  showRefresh?: boolean;
  /** Optional className for the container */
  className?: string;
  /** Label prefix (default: "Events that would trigger:") */
  label?: string;
  /** Test ID for testing */
  testId?: string;
}

// =============================================================================
// Component
// =============================================================================

/**
 * Displays real-time preview of how many events would trigger at the current threshold.
 */
export default function ThresholdPreview({
  previewState,
  showRefresh = true,
  className,
  label = 'Events that would trigger:',
  testId = 'threshold-preview',
}: ThresholdPreviewProps) {
  const {
    isLoading,
    error,
    eventsMatched,
    eventsTested,
    matchRate,
    refresh,
  } = previewState;

  // Loading state
  if (isLoading) {
    return (
      <div
        className={clsx(
          'flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800/50 px-3 py-2',
          className
        )}
        data-testid={testId}
      >
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        <span className="text-sm text-text-secondary">Calculating preview...</span>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className={clsx(
          'flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2',
          className
        )}
        data-testid={testId}
        role="alert"
      >
        <AlertCircle className="h-4 w-4 shrink-0 text-red-500" />
        <span className="flex-1 text-sm text-red-400">Preview unavailable</span>
        {showRefresh && (
          <button
            type="button"
            onClick={refresh}
            className="text-red-400 hover:text-red-300"
            aria-label="Retry preview"
            data-testid={`${testId}-retry`}
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        )}
      </div>
    );
  }

  // No data state (rule not saved yet)
  if (eventsMatched === null || eventsTested === null) {
    return (
      <div
        className={clsx(
          'flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800/50 px-3 py-2',
          className
        )}
        data-testid={testId}
      >
        <TrendingUp className="h-4 w-4 text-gray-500" />
        <span className="text-sm text-text-secondary">
          Save rule to see threshold preview
        </span>
      </div>
    );
  }

  // Determine the color based on match rate
  const getMatchRateColor = (rate: number | null): string => {
    if (rate === null) return 'text-gray-400';
    if (rate === 0) return 'text-green-400';
    if (rate <= 25) return 'text-yellow-400';
    if (rate <= 50) return 'text-orange-400';
    return 'text-red-400';
  };

  const rateColor = getMatchRateColor(matchRate);

  // Success state with data
  return (
    <div
      className={clsx(
        'flex items-center justify-between rounded-lg border border-gray-700 bg-gray-800/50 px-3 py-2',
        className
      )}
      data-testid={testId}
    >
      <div className="flex items-center gap-2">
        <TrendingUp className={clsx('h-4 w-4', rateColor)} />
        <span className="text-sm text-text-secondary">{label}</span>
        <span className={clsx('text-sm font-semibold', rateColor)} data-testid={`${testId}-count`}>
          {eventsMatched} / {eventsTested}
        </span>
        {matchRate !== null && (
          <span className="text-xs text-gray-500">
            ({matchRate.toFixed(1)}%)
          </span>
        )}
      </div>

      {showRefresh && (
        <button
          type="button"
          onClick={refresh}
          className="text-gray-400 hover:text-gray-300"
          aria-label="Refresh preview"
          data-testid={`${testId}-refresh`}
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
