/**
 * DateRangeDropdown - Dropdown selector for date range presets and custom ranges.
 *
 * Provides a user interface for selecting:
 * - Preset date ranges (Last 7 days, Last 30 days, Last 90 days)
 * - Custom date range with inline date pickers
 *
 * @module components/analytics/DateRangeDropdown
 * @see NEM-2702
 */

import { Menu, Transition } from '@headlessui/react';
import clsx from 'clsx';
import { Calendar, ChevronDown, Check } from 'lucide-react';
import { useState, useCallback, Fragment } from 'react';

import CustomDateRangePicker from './CustomDateRangePicker';

import type { DateRange, DateRangePreset } from '../../hooks/useDateRangeState';

/**
 * Props for DateRangeDropdown component.
 */
interface DateRangeDropdownProps {
  /** Current preset value */
  preset: DateRangePreset;
  /** Display label for current preset */
  presetLabel: string;
  /** Whether custom range is selected */
  isCustom: boolean;
  /** Current date range */
  range: DateRange;
  /** Set a preset date range */
  setPreset: (preset: DateRangePreset) => void;
  /** Set a custom date range */
  setCustomRange: (start: Date, end: Date) => void;
  /** Optional additional CSS classes */
  className?: string;
}

/**
 * Preset option configuration.
 */
interface PresetOption {
  value: DateRangePreset;
  label: string;
  isCustom?: boolean;
}

/**
 * Available preset options.
 */
const PRESET_OPTIONS: PresetOption[] = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: '90d', label: 'Last 90 days' },
  { value: 'custom', label: 'Custom range...', isCustom: true },
];

/**
 * Format date to display string (e.g., "Jan 17").
 */
function formatDateShort(date: Date): string {
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

/**
 * DateRangeDropdown - A dropdown for selecting date ranges.
 *
 * @example Basic usage
 * ```tsx
 * const { preset, presetLabel, isCustom, range, setPreset, setCustomRange } = useDateRangeState();
 *
 * <DateRangeDropdown
 *   preset={preset}
 *   presetLabel={presetLabel}
 *   isCustom={isCustom}
 *   range={range}
 *   setPreset={setPreset}
 *   setCustomRange={setCustomRange}
 * />
 * ```
 */
export default function DateRangeDropdown({
  preset,
  presetLabel,
  isCustom,
  range,
  setPreset,
  setCustomRange,
  className,
}: DateRangeDropdownProps) {
  // State for showing custom date picker
  const [showCustomPicker, setShowCustomPicker] = useState(false);

  // Get display text for the dropdown button
  const getDisplayText = useCallback(() => {
    if (isCustom && range.startDate && range.endDate) {
      return `${formatDateShort(range.startDate)} - ${formatDateShort(range.endDate)}`;
    }
    return presetLabel;
  }, [isCustom, range, presetLabel]);

  // Handle preset selection
  const handlePresetClick = useCallback(
    (option: PresetOption, close: () => void) => {
      if (option.isCustom) {
        // Open custom date picker instead of closing
        setShowCustomPicker(true);
      } else {
        setPreset(option.value);
        close();
      }
    },
    [setPreset]
  );

  // Handle custom range apply
  const handleCustomApply = useCallback(
    (startDate: Date, endDate: Date) => {
      setCustomRange(startDate, endDate);
      setShowCustomPicker(false);
    },
    [setCustomRange]
  );

  // Handle custom range cancel
  const handleCustomCancel = useCallback(() => {
    setShowCustomPicker(false);
  }, []);

  return (
    <div className={clsx('relative', className)}>
      <Menu as="div" className="relative inline-block text-left">
        {({ open, close }) => (
          <>
            <Menu.Button
              className={clsx(
                'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
                'border-gray-700 bg-gray-800 text-gray-200',
                'hover:border-gray-600 hover:bg-gray-700',
                'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900'
              )}
              data-testid="date-range-dropdown"
              aria-expanded={open}
            >
              <Calendar className="h-4 w-4 text-gray-400" />
              <span>{getDisplayText()}</span>
              <ChevronDown
                className={clsx('h-4 w-4 text-gray-400 transition-transform', open && 'rotate-180')}
              />
            </Menu.Button>

            <Transition
              as={Fragment}
              enter="transition ease-out duration-100"
              enterFrom="transform opacity-0 scale-95"
              enterTo="transform opacity-100 scale-100"
              leave="transition ease-in duration-75"
              leaveFrom="transform opacity-100 scale-100"
              leaveTo="transform opacity-0 scale-95"
            >
              <Menu.Items
                className={clsx(
                  'absolute right-0 z-50 mt-2 w-56 origin-top-right',
                  'rounded-lg border border-gray-700 bg-gray-800 shadow-lg',
                  'focus:outline-none'
                )}
              >
                <div className="py-1">
                  {PRESET_OPTIONS.map((option, index) => {
                    const isSelected = !option.isCustom && preset === option.value;
                    const isCustomSelected = option.isCustom && isCustom;

                    // Add separator before "Custom range" option
                    const showDivider =
                      index > 0 && option.isCustom && !PRESET_OPTIONS[index - 1].isCustom;

                    return (
                      <Fragment key={option.value}>
                        {showDivider && <div className="my-1 border-t border-gray-700" />}
                        <Menu.Item>
                          {({ active }) => (
                            <button
                              type="button"
                              data-selected={isSelected || isCustomSelected}
                              onClick={() => handlePresetClick(option, close)}
                              className={clsx(
                                'flex w-full items-center justify-between px-4 py-2 text-left text-sm',
                                active ? 'bg-gray-700 text-white' : 'text-gray-300',
                                (isSelected || isCustomSelected) && 'text-[#76B900]'
                              )}
                            >
                              <span>{option.label}</span>
                              {(isSelected || isCustomSelected) && (
                                <Check className="h-4 w-4 text-[#76B900]" />
                              )}
                            </button>
                          )}
                        </Menu.Item>
                      </Fragment>
                    );
                  })}
                </div>
              </Menu.Items>
            </Transition>
          </>
        )}
      </Menu>

      {/* Custom Date Range Picker Modal */}
      {showCustomPicker && (
        <CustomDateRangePicker
          initialStartDate={range.startDate}
          initialEndDate={range.endDate}
          onApply={handleCustomApply}
          onCancel={handleCustomCancel}
        />
      )}
    </div>
  );
}
