/**
 * DateRangePickerModal component (NEM-3585)
 * Modal for selecting custom date ranges in the timeline scrubber.
 *
 * Features:
 * - Start and end date inputs with validation
 * - Preset ranges (Today, Last 7 days, Last 30 days)
 * - End date cannot be before start date validation
 * - Dark theme consistent with existing UI
 * - Keyboard accessible (Escape to close, Tab navigation)
 */

import { Calendar, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

export interface DateRangePreset {
  label: string;
  getRange: () => { startDate: string; endDate: string };
}

export interface DateRangePickerModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when the modal is closed */
  onClose: () => void;
  /** Initial start date in YYYY-MM-DD format */
  initialStartDate?: string;
  /** Initial end date in YYYY-MM-DD format */
  initialEndDate?: string;
  /** Callback when a date range is applied */
  onApply: (startDate: string, endDate: string) => void;
}

/**
 * Get today's date in YYYY-MM-DD format
 */
function getTodayDate(): string {
  return new Date().toISOString().split('T')[0];
}

/**
 * Get a date N days ago in YYYY-MM-DD format
 */
function getDaysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().split('T')[0];
}

/**
 * Default preset ranges for quick selection
 */
const DEFAULT_PRESETS: DateRangePreset[] = [
  {
    label: 'Today',
    getRange: () => ({ startDate: getTodayDate(), endDate: getTodayDate() }),
  },
  {
    label: 'Last 7 days',
    getRange: () => ({ startDate: getDaysAgo(7), endDate: getTodayDate() }),
  },
  {
    label: 'Last 30 days',
    getRange: () => ({ startDate: getDaysAgo(30), endDate: getTodayDate() }),
  },
];

/**
 * DateRangePickerModal provides a modal interface for selecting custom date ranges.
 * Includes preset options and custom date inputs with validation.
 */
export default function DateRangePickerModal({
  isOpen,
  onClose,
  initialStartDate,
  initialEndDate,
  onApply,
}: DateRangePickerModalProps) {
  const [startDate, setStartDate] = useState<string>(initialStartDate || '');
  const [endDate, setEndDate] = useState<string>(initialEndDate || '');
  const [error, setError] = useState<string | null>(null);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setStartDate(initialStartDate || '');
      setEndDate(initialEndDate || '');
      setError(null);
    }
  }, [isOpen, initialStartDate, initialEndDate]);

  // Handle escape key to close modal
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Validate date range
  const validationError = useMemo(() => {
    if (!startDate || !endDate) return null;
    if (new Date(endDate) < new Date(startDate)) {
      return 'End date cannot be before start date';
    }
    return null;
  }, [startDate, endDate]);

  // Check if form is valid
  const isValid = useMemo(() => {
    return startDate && endDate && !validationError;
  }, [startDate, endDate, validationError]);

  // Handle preset selection
  const handlePresetClick = useCallback((preset: DateRangePreset) => {
    const { startDate: start, endDate: end } = preset.getRange();
    setStartDate(start);
    setEndDate(end);
    setError(null);
  }, []);

  // Handle apply
  const handleApply = useCallback(() => {
    if (!isValid) {
      setError(validationError || 'Please select both start and end dates');
      return;
    }
    onApply(startDate, endDate);
    onClose();
  }, [isValid, validationError, startDate, endDate, onApply, onClose]);

  // Handle backdrop click
  const handleBackdropClick = useCallback(
    (event: React.MouseEvent) => {
      if (event.target === event.currentTarget) {
        onClose();
      }
    },
    [onClose]
  );

  if (!isOpen) return null;

  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <div
      data-testid="date-range-picker-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="date-range-picker-title"
    >
      <div className="mx-4 w-full max-w-md rounded-lg border border-gray-700 bg-[#1F1F1F] p-6 shadow-xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <h2
            id="date-range-picker-title"
            className="flex items-center gap-2 text-lg font-semibold text-white"
          >
            <Calendar className="h-5 w-5 text-[#76B900]" />
            Select Date Range
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
            aria-label="Close date range picker"
            data-testid="date-range-picker-close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Preset Buttons */}
        <div className="mb-6">
          <span className="mb-2 block text-sm font-medium text-gray-300">
            Quick Select
          </span>
          <div className="flex flex-wrap gap-2">
            {DEFAULT_PRESETS.map((preset) => (
              <button
                key={preset.label}
                onClick={() => handlePresetClick(preset)}
                className="rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-1.5 text-sm text-gray-300 transition-colors hover:border-[#76B900] hover:bg-[#76B900]/10 hover:text-white"
                data-testid={`preset-${preset.label.toLowerCase().replace(/\s+/g, '-')}`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        {/* Custom Date Inputs */}
        <div className="mb-6 grid grid-cols-2 gap-4">
          {/* Start Date */}
          <div>
            <label
              htmlFor="start-date-input"
              className="mb-2 block text-sm font-medium text-gray-300"
            >
              Start Date
            </label>
            <div className="relative">
              <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                id="start-date-input"
                type="date"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value);
                  setError(null);
                }}
                className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-3 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
                data-testid="start-date-input"
              />
            </div>
          </div>

          {/* End Date */}
          <div>
            <label
              htmlFor="end-date-input"
              className="mb-2 block text-sm font-medium text-gray-300"
            >
              End Date
            </label>
            <div className="relative">
              <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                id="end-date-input"
                type="date"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value);
                  setError(null);
                }}
                min={startDate || undefined}
                className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-3 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
                data-testid="end-date-input"
              />
            </div>
          </div>
        </div>

        {/* Validation Error */}
        {(error || validationError) && (
          <div
            className="mb-4 rounded-md border border-red-800 bg-red-900/20 px-3 py-2 text-sm text-red-400"
            role="alert"
            data-testid="date-range-error"
          >
            {error || validationError}
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-700 bg-[#1A1A1A] px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#252525]"
            data-testid="date-range-cancel"
          >
            Cancel
          </button>
          <button
            onClick={handleApply}
            disabled={!isValid}
            className="rounded-md bg-[#76B900] px-4 py-2 text-sm font-semibold text-black transition-all hover:bg-[#88d200] disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="date-range-apply"
          >
            Apply Range
          </button>
        </div>
      </div>
    </div>
  );
}
