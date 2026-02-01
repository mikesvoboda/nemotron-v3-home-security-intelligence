import { useMemo } from 'react';

import type { CurrentDeviation, DeviationInterpretation } from '../../services/api';

interface BaselineDeviationCardProps {
  /** Current deviation from baseline, null if no data */
  deviation: (CurrentDeviation & { last_updated?: string }) | null;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Color configuration for each interpretation level.
 */
const INTERPRETATION_COLORS: Record<
  DeviationInterpretation,
  { bg: string; border: string; text: string }
> = {
  far_below_normal: {
    bg: 'bg-blue-500/20',
    border: 'border-blue-500',
    text: 'text-blue-400',
  },
  below_normal: {
    bg: 'bg-blue-100/10',
    border: 'border-blue-300',
    text: 'text-blue-300',
  },
  normal: {
    bg: 'bg-green-500/20',
    border: 'border-green-500',
    text: 'text-green-400',
  },
  slightly_above_normal: {
    bg: 'bg-yellow-500/20',
    border: 'border-yellow-500',
    text: 'text-yellow-400',
  },
  above_normal: {
    bg: 'bg-orange-500/20',
    border: 'border-orange-500',
    text: 'text-orange-400',
  },
  far_above_normal: {
    bg: 'bg-red-500/20',
    border: 'border-red-500',
    text: 'text-red-400',
  },
};

/**
 * Human-readable labels for interpretation levels.
 */
const INTERPRETATION_LABELS: Record<DeviationInterpretation, string> = {
  far_below_normal: 'Far Below Normal',
  below_normal: 'Below Normal',
  normal: 'Normal',
  slightly_above_normal: 'Slightly Above Normal',
  above_normal: 'Above Normal',
  far_above_normal: 'Far Above Normal',
};

/**
 * Icon types for each interpretation level.
 */
type IconType = 'check' | 'arrow-up' | 'arrow-down' | 'alert';
const INTERPRETATION_ICONS: Record<DeviationInterpretation, IconType> = {
  far_below_normal: 'arrow-down',
  below_normal: 'arrow-down',
  normal: 'check',
  slightly_above_normal: 'arrow-up',
  above_normal: 'arrow-up',
  far_above_normal: 'alert',
};

/**
 * SVG path data for each icon type.
 */
const ICON_PATHS: Record<IconType, string> = {
  check: 'M5 13l4 4L19 7',
  'arrow-up': 'M5 15l7-7 7 7',
  'arrow-down': 'M19 9l-7 7-7-7',
  alert: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
};

/**
 * Fixed icon colors for specific icon types (overrides dynamic color).
 */
const FIXED_ICON_COLORS: Partial<Record<IconType, string>> = {
  check: 'text-green-400',
  alert: 'text-red-400',
};

/**
 * Format a factor name from snake_case to human-readable.
 */
function formatFactorName(factor: string): string {
  return factor
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Format the deviation score with +/- sign.
 */
function formatScore(score: number): string {
  if (score === 0) {
    return '0.0';
  }
  const rounded = Math.round(score * 10) / 10;
  const formatted = rounded.toFixed(1);
  return score >= 0 ? `+${formatted}` : formatted;
}

/**
 * BaselineDeviationCard displays the current deviation from baseline.
 *
 * Features:
 * - Color-coded by interpretation level
 * - Score display with +/- sign
 * - Interpretation text
 * - Contributing factors as badges
 * - Null state for no data
 */
export default function BaselineDeviationCard({
  deviation,
  className = '',
}: BaselineDeviationCardProps) {
  // Compute all deviation-dependent values in a single memo
  const displayData = useMemo(() => {
    if (!deviation) {
      return {
        colors: null,
        iconClass: null as IconType | null,
        label: '',
        ariaLabel: 'No deviation data available',
      };
    }
    const label = INTERPRETATION_LABELS[deviation.interpretation];
    return {
      colors: INTERPRETATION_COLORS[deviation.interpretation],
      iconClass: INTERPRETATION_ICONS[deviation.interpretation],
      label,
      ariaLabel: `Current activity status: ${label}, ${formatScore(deviation.score)} standard deviations`,
    };
  }, [deviation]);

  const { colors, iconClass, label, ariaLabel } = displayData;

  // No data state
  if (!deviation) {
    return (
      <div
        className={`flex-col rounded-lg border border-gray-700 bg-gray-800/50 p-4 ${className}`}
        data-testid="deviation-no-data"
      >
        <h3 className="mb-2 text-lg font-semibold text-white">Current Activity Status</h3>
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <div className="mb-2 text-gray-400">No deviation data available</div>
          <div className="text-sm text-gray-500">
            Baseline data is still being collected. Check back later.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`flex flex-col rounded-lg border ${colors?.border} ${colors?.bg} p-4 ${className}`}
      data-testid="baseline-deviation-card"
      aria-label={ariaLabel}
    >
      <h3 className="mb-4 text-lg font-semibold text-white">Current Activity Status</h3>

      {/* Main content row */}
      <div className="flex flex-col items-start gap-4">
        {/* Icon and score */}
        <div className="flex items-center gap-3">
          <div
            className={`flex h-12 w-12 items-center justify-center rounded-full ${colors?.bg} ${iconClass}`}
            data-testid="deviation-icon"
          >
            {iconClass && (
              <svg
                className={`h-6 w-6 ${FIXED_ICON_COLORS[iconClass] ?? colors?.text}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d={ICON_PATHS[iconClass]}
                />
              </svg>
            )}
          </div>
          <div>
            <div
              className={`text-3xl font-bold ${colors?.text}`}
              data-testid="deviation-score"
            >
              {formatScore(deviation.score)}
            </div>
            <div className="text-sm text-gray-400">standard deviations</div>
          </div>
        </div>

        {/* Interpretation */}
        <div
          className={`text-xl font-semibold ${colors?.text}`}
          data-testid="deviation-interpretation"
          aria-live="polite"
        >
          {label}
        </div>

        {/* Explanation */}
        <div className="text-sm text-gray-400">
          This score measures how far current activity differs from typical patterns.
        </div>

        {/* Last updated timestamp */}
        {deviation.last_updated && (
          <div className="text-xs text-gray-500">
            Last updated: {new Date(deviation.last_updated).toLocaleString()}
          </div>
        )}
      </div>

      {/* Contributing factors */}
      {deviation.contributing_factors.length > 0 && (
        <div className="mt-4 border-t border-gray-700 pt-4">
          <div className="mb-2 text-sm font-medium text-gray-300">Contributing Factors</div>
          <div
            className="grid grid-cols-1 gap-2 sm:grid-cols-2"
            data-testid="contributing-factors"
            role="list"
          >
            {deviation.contributing_factors.map((factor, index) => (
              <div
                key={factor}
                className="truncate rounded-full bg-gray-700/50 px-3 py-1 text-sm text-gray-300"
                data-testid={`factor-badge-${index}`}
                role="listitem"
              >
                <span className="sr-only">{factor}</span>
                <span aria-hidden="true">{formatFactorName(factor)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
