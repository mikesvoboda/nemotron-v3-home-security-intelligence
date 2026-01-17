/**
 * CustomDateRangePicker - Inline date pickers for selecting a custom date range.
 *
 * Provides start and end date inputs with validation and Apply/Cancel buttons.
 *
 * @module components/analytics/CustomDateRangePicker
 * @see NEM-2702
 */

import clsx from 'clsx';
import { useState, useCallback, useMemo } from 'react';

/**
 * Props for CustomDateRangePicker component.
 */
interface CustomDateRangePickerProps {
  /** Initial start date */
  initialStartDate: Date | null;
  /** Initial end date */
  initialEndDate: Date | null;
  /** Callback when user applies the custom range */
  onApply: (startDate: Date, endDate: Date) => void;
  /** Callback when user cancels */
  onCancel: () => void;
}

/**
 * Format Date to YYYY-MM-DD for date input value.
 */
function formatDateForInput(date: Date | null): string {
  if (!date) return '';
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Parse YYYY-MM-DD string to Date.
 */
function parseDateFromInput(value: string): Date | null {
  if (!value) return null;
  const date = new Date(value + 'T00:00:00.000Z');
  if (isNaN(date.getTime())) return null;
  return date;
}

/**
 * CustomDateRangePicker - A panel with date inputs for custom range selection.
 *
 * @example Usage within DateRangeDropdown
 * ```tsx
 * <CustomDateRangePicker
 *   initialStartDate={range.startDate}
 *   initialEndDate={range.endDate}
 *   onApply={(start, end) => setCustomRange(start, end)}
 *   onCancel={() => setShowPicker(false)}
 * />
 * ```
 */
export default function CustomDateRangePicker({
  initialStartDate,
  initialEndDate,
  onApply,
  onCancel,
}: CustomDateRangePickerProps) {
  // Local state for date inputs
  const [startDateStr, setStartDateStr] = useState(() =>
    formatDateForInput(initialStartDate)
  );
  const [endDateStr, setEndDateStr] = useState(() =>
    formatDateForInput(initialEndDate)
  );
  const [error, setError] = useState<string | null>(null);

  // Parse dates from strings
  const startDate = useMemo(() => parseDateFromInput(startDateStr), [startDateStr]);
  const endDate = useMemo(() => parseDateFromInput(endDateStr), [endDateStr]);

  // Check if inputs are filled
  const hasValidInput = useMemo(() => {
    return !!startDateStr && !!endDateStr && !!startDate && !!endDate;
  }, [startDateStr, endDateStr, startDate, endDate]);

  // Handle Apply button click
  const handleApply = useCallback(() => {
    if (!startDate || !endDate) {
      setError('Please select both start and end dates');
      return;
    }

    if (startDate > endDate) {
      setError('Start date must be before end date');
      return;
    }

    setError(null);
    onApply(startDate, endDate);
  }, [startDate, endDate, onApply]);

  // Handle start date change
  const handleStartDateChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setStartDateStr(e.target.value);
      setError(null);
    },
    []
  );

  // Handle end date change
  const handleEndDateChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setEndDateStr(e.target.value);
      setError(null);
    },
    []
  );

  return (
    <div
      data-testid="custom-date-picker"
      className={clsx(
        'absolute right-0 z-50 mt-2 w-72',
        'rounded-lg border border-gray-700 bg-gray-800 p-4 shadow-lg'
      )}
    >
      {/* Date Inputs */}
      <div className="space-y-4">
        <div>
          <label
            htmlFor="custom-start-date"
            className="block text-sm font-medium text-gray-300"
          >
            Start Date
          </label>
          <input
            id="custom-start-date"
            type="date"
            value={startDateStr}
            onChange={handleStartDateChange}
            className={clsx(
              'mt-1 w-full rounded-md border px-3 py-2 text-sm',
              'border-gray-600 bg-gray-700 text-white',
              'focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]'
            )}
          />
        </div>

        <div>
          <label
            htmlFor="custom-end-date"
            className="block text-sm font-medium text-gray-300"
          >
            End Date
          </label>
          <input
            id="custom-end-date"
            type="date"
            value={endDateStr}
            onChange={handleEndDateChange}
            className={clsx(
              'mt-1 w-full rounded-md border px-3 py-2 text-sm',
              'border-gray-600 bg-gray-700 text-white',
              'focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]'
            )}
          />
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div
          role="alert"
          className="mt-3 rounded bg-red-500/10 px-3 py-2 text-sm text-red-400"
        >
          {error}
        </div>
      )}

      {/* Action Buttons */}
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className={clsx(
            'rounded-md px-3 py-1.5 text-sm font-medium',
            'border border-gray-600 bg-transparent text-gray-300',
            'hover:bg-gray-700',
            'focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-800'
          )}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleApply}
          disabled={!hasValidInput}
          className={clsx(
            'rounded-md px-3 py-1.5 text-sm font-medium',
            'bg-[#76B900] text-white',
            'hover:bg-[#5f9600]',
            'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-800',
            'disabled:cursor-not-allowed disabled:opacity-50'
          )}
        >
          Apply
        </button>
      </div>
    </div>
  );
}
