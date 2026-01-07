import { clsx } from 'clsx';

import type { TimeRange } from '../../types/performance';

export interface TimeRangeSelectorProps {
  /** Currently selected time range */
  selectedRange: TimeRange;
  /** Callback when time range changes */
  onRangeChange: (range: TimeRange) => void;
  /** Additional CSS classes */
  className?: string;
}

/** Available time range options with labels */
const TIME_RANGES: { value: TimeRange; label: string }[] = [
  { value: '5m', label: '5m' },
  { value: '15m', label: '15m' },
  { value: '60m', label: '60m' },
];

/**
 * TimeRangeSelector - A toggle button group for selecting time ranges.
 *
 * Allows users to switch between 5-minute, 15-minute, and 60-minute
 * time windows for historical metrics visualization.
 *
 * Time range resolutions:
 * - 5m: 5-second resolution (60 data points)
 * - 15m: 15-second resolution (60 data points)
 * - 60m: 1-minute resolution (60 data points)
 *
 * @example
 * ```tsx
 * <TimeRangeSelector
 *   selectedRange="5m"
 *   onRangeChange={(range) => setTimeRange(range)}
 * />
 * ```
 */
export default function TimeRangeSelector({
  selectedRange,
  onRangeChange,
  className,
}: TimeRangeSelectorProps) {
  return (
    <div
      role="group"
      aria-label="Time range selection"
      className={clsx('flex items-center gap-1 rounded-lg bg-gray-800/50 p-1', className)}
      data-testid="time-range-selector"
    >
      {TIME_RANGES.map(({ value, label }) => {
        const isSelected = selectedRange === value;
        return (
          <button
            key={value}
            type="button"
            onClick={() => onRangeChange(value)}
            aria-pressed={isSelected}
            className={clsx(
              'rounded-md px-3 py-1.5 text-sm font-medium transition-all duration-150',
              isSelected
                ? 'bg-[#76B900] text-gray-950 shadow-sm' // WCAG 2.1 AA: dark text on green for 4.5:1+ contrast
                : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-200'
            )}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
