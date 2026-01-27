/**
 * DateRangePicker - Date range selection with React 19 useTransition.
 *
 * Uses React 19's useTransition hook to prevent UI blocking during
 * expensive refetches triggered by date range changes. The date change
 * is marked as low priority, keeping the UI responsive.
 *
 * @module components/DateRangePicker
 * @see NEM-3749 - React 19 useTransition for non-blocking search/filter
 */

import { clsx } from 'clsx';
import { Calendar, Loader2, X } from 'lucide-react';
import { memo, useCallback, useTransition } from 'react';

/**
 * Date range value.
 */
export interface DateRange {
  /** Start date in ISO format (YYYY-MM-DD) */
  startDate: string;
  /** End date in ISO format (YYYY-MM-DD) */
  endDate: string;
}

/**
 * Preset date range options.
 */
export type DatePreset = 'today' | 'yesterday' | '7d' | '30d' | '90d' | 'custom';

export interface DateRangePickerProps {
  /** Current date range */
  value: DateRange;
  /** Callback when date range changes (wrapped in startTransition) */
  onChange: (range: DateRange) => void;
  /** Optional callback for preset selection */
  onPresetSelect?: (preset: DatePreset) => void;
  /** Show preset quick-select buttons */
  showPresets?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Labels for the date inputs */
  labels?: {
    start?: string;
    end?: string;
  };
}

/**
 * Preset options with calculated date ranges.
 */
const DATE_PRESETS: { value: DatePreset; label: string }[] = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: '90d', label: 'Last 90 days' },
];

/**
 * Calculate date range from preset.
 */
function getDateRangeFromPreset(preset: DatePreset): DateRange {
  const today = new Date();
  const endDate = today.toISOString().split('T')[0];

  let startDate: string;

  switch (preset) {
    case 'today':
      startDate = endDate;
      break;
    case 'yesterday': {
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      startDate = yesterday.toISOString().split('T')[0];
      break;
    }
    case '7d': {
      const weekAgo = new Date(today);
      weekAgo.setDate(weekAgo.getDate() - 7);
      startDate = weekAgo.toISOString().split('T')[0];
      break;
    }
    case '30d': {
      const monthAgo = new Date(today);
      monthAgo.setDate(monthAgo.getDate() - 30);
      startDate = monthAgo.toISOString().split('T')[0];
      break;
    }
    case '90d': {
      const quarterAgo = new Date(today);
      quarterAgo.setDate(quarterAgo.getDate() - 90);
      startDate = quarterAgo.toISOString().split('T')[0];
      break;
    }
    case 'custom':
    default:
      // Return current date as fallback
      startDate = endDate;
  }

  return { startDate, endDate };
}

/**
 * DateRangePicker component with React 19 useTransition for non-blocking updates.
 *
 * Date range changes trigger expensive data refetches. Using useTransition keeps
 * the UI responsive by marking the date change as a low-priority update.
 *
 * @example
 * ```tsx
 * const [dateRange, setDateRange] = useState<DateRange>({
 *   startDate: '2024-01-01',
 *   endDate: '2024-01-31',
 * });
 *
 * <DateRangePicker
 *   value={dateRange}
 *   onChange={setDateRange}
 *   showPresets
 * />
 * ```
 */
const DateRangePicker = memo(function DateRangePicker({
  value,
  onChange,
  onPresetSelect,
  showPresets = true,
  className,
  labels = { start: 'Start Date', end: 'End Date' },
}: DateRangePickerProps) {
  // React 19 useTransition for non-blocking date updates
  const [isPending, startTransition] = useTransition();

  /**
   * Handle start date change.
   * Wrapped in startTransition to prevent UI blocking.
   */
  const handleStartDateChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newStartDate = e.target.value;
      startTransition(() => {
        onChange({
          ...value,
          startDate: newStartDate,
        });
      });
    },
    [value, onChange]
  );

  /**
   * Handle end date change.
   * Wrapped in startTransition to prevent UI blocking.
   */
  const handleEndDateChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newEndDate = e.target.value;
      startTransition(() => {
        onChange({
          ...value,
          endDate: newEndDate,
        });
      });
    },
    [value, onChange]
  );

  /**
   * Handle preset selection.
   * Calculates the date range and applies it via startTransition.
   */
  const handlePresetClick = useCallback(
    (preset: DatePreset) => {
      startTransition(() => {
        const range = getDateRangeFromPreset(preset);
        onChange(range);
        if (onPresetSelect) {
          onPresetSelect(preset);
        }
      });
    },
    [onChange, onPresetSelect]
  );

  /**
   * Clear the date range.
   */
  const handleClear = useCallback(() => {
    startTransition(() => {
      onChange({ startDate: '', endDate: '' });
    });
  }, [onChange]);

  const hasValue = value.startDate || value.endDate;

  return (
    <div className={clsx('space-y-3', className)}>
      {/* Preset buttons */}
      {showPresets && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Date range presets">
          {DATE_PRESETS.map((preset) => (
            <button
              key={preset.value}
              type="button"
              onClick={() => handlePresetClick(preset.value)}
              disabled={isPending}
              className={clsx(
                'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                'border border-gray-700 bg-[#1A1A1A] text-gray-300',
                'hover:border-[#76B900] hover:text-[#76B900]',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
            >
              {preset.label}
            </button>
          ))}
        </div>
      )}

      {/* Date inputs */}
      <div className="flex flex-wrap items-end gap-4">
        {/* Start date */}
        <div className="flex-1 min-w-[140px]">
          <label
            htmlFor="date-range-start"
            className="mb-1 block text-xs font-medium text-gray-400"
          >
            {labels.start}
          </label>
          <div className="relative">
            <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              id="date-range-start"
              type="date"
              value={value.startDate}
              onChange={handleStartDateChange}
              disabled={isPending}
              max={value.endDate || undefined}
              className={clsx(
                'w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-3 text-sm text-white',
                'focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
            />
          </div>
        </div>

        {/* End date */}
        <div className="flex-1 min-w-[140px]">
          <label htmlFor="date-range-end" className="mb-1 block text-xs font-medium text-gray-400">
            {labels.end}
          </label>
          <div className="relative">
            <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              id="date-range-end"
              type="date"
              value={value.endDate}
              onChange={handleEndDateChange}
              disabled={isPending}
              min={value.startDate || undefined}
              className={clsx(
                'w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-3 text-sm text-white',
                'focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
            />
          </div>
        </div>

        {/* Loading indicator and clear button */}
        <div className="flex items-center gap-2 pb-0.5">
          {isPending && (
            <Loader2
              className="h-5 w-5 animate-spin text-[#76B900]"
              data-testid="date-loading-indicator"
              aria-label="Loading"
            />
          )}
          {hasValue && !isPending && (
            <button
              type="button"
              onClick={handleClear}
              className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
              aria-label="Clear date range"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
});

export default DateRangePicker;
