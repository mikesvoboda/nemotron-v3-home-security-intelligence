/**
 * PlateSearchBar - Search bar component for plate reads
 *
 * Provides text search with exact/partial matching toggle and an
 * advanced filters panel for camera, date range, and confidence filtering.
 *
 * @module components/plate-reads/PlateSearchBar
 * @see frontend/src/hooks/usePlateSearchQuery.ts - Query hook
 * @see frontend/src/components/search/SearchBar.tsx - Pattern reference
 */

import { clsx } from 'clsx';
import { ChevronDown, ChevronUp, Search, X, SlidersHorizontal } from 'lucide-react';
import { memo, useCallback, useState } from 'react';

import { useCamerasQuery } from '../../hooks/useCamerasQuery';
import DateRangePicker from '../DateRangePicker';

import type { DateRange } from '../DateRangePicker';

// ============================================================================
// Types
// ============================================================================

/**
 * Filter values for plate search.
 */
export interface PlateSearchFilters {
  /** Filter by camera ID */
  camera_id?: string;
  /** Filter by start time (ISO 8601 format) */
  start_time?: string;
  /** Filter by end time (ISO 8601 format) */
  end_time?: string;
  /** Minimum OCR confidence threshold (0-1) */
  min_confidence?: number;
}

export interface PlateSearchBarProps {
  /** Current search text */
  searchText: string;
  /** Called when search text changes */
  onSearchTextChange: (text: string) => void;
  /** Whether to use exact matching */
  exactMatch: boolean;
  /** Called when exact match toggle changes */
  onExactMatchChange: (exact: boolean) => void;
  /** Current filter values */
  filters: PlateSearchFilters;
  /** Called when filters change */
  onFiltersChange: (filters: PlateSearchFilters) => void;
  /** Whether a search is in progress */
  isSearching?: boolean;
  /** Optional class name */
  className?: string;
  /** Placeholder text */
  placeholder?: string;
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Confidence threshold presets for the slider.
 */
const CONFIDENCE_PRESETS = [
  { value: 0, label: 'All' },
  { value: 0.5, label: '50%+' },
  { value: 0.7, label: '70%+' },
  { value: 0.85, label: '85%+' },
  { value: 0.95, label: '95%+' },
];

// ============================================================================
// Component
// ============================================================================

/**
 * PlateSearchBar component for searching and filtering plate reads.
 *
 * Features:
 * - Text search input with exact/partial match toggle
 * - Expandable advanced filters panel
 * - Camera dropdown filter
 * - Date range picker with presets (Today, 7d, 30d, 90d)
 * - Confidence threshold slider
 * - Clear filters button
 *
 * @example
 * ```tsx
 * const [searchText, setSearchText] = useState('');
 * const [exactMatch, setExactMatch] = useState(false);
 * const [filters, setFilters] = useState({});
 *
 * <PlateSearchBar
 *   searchText={searchText}
 *   onSearchTextChange={setSearchText}
 *   exactMatch={exactMatch}
 *   onExactMatchChange={setExactMatch}
 *   filters={filters}
 *   onFiltersChange={setFilters}
 * />
 * ```
 */
const PlateSearchBar = memo(function PlateSearchBar({
  searchText,
  onSearchTextChange,
  exactMatch,
  onExactMatchChange,
  filters,
  onFiltersChange,
  isSearching = false,
  className,
  placeholder = 'Search plate text (e.g., ABC123, XYZ)...',
}: PlateSearchBarProps) {
  // State for advanced filters panel visibility
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);

  // Fetch cameras for the dropdown
  const { cameras, isLoading: camerasLoading } = useCamerasQuery({
    placeholderCount: 0,
  });

  // Date range state derived from filters
  const dateRange: DateRange = {
    startDate: filters.start_time ? filters.start_time.split('T')[0] : '',
    endDate: filters.end_time ? filters.end_time.split('T')[0] : '',
  };

  // Handle keyboard events
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Escape') {
        onSearchTextChange('');
      }
    },
    [onSearchTextChange]
  );

  // Handle date range changes
  const handleDateRangeChange = useCallback(
    (range: DateRange) => {
      onFiltersChange({
        ...filters,
        start_time: range.startDate ? `${range.startDate}T00:00:00Z` : undefined,
        end_time: range.endDate ? `${range.endDate}T23:59:59Z` : undefined,
      });
    },
    [filters, onFiltersChange]
  );

  // Handle camera filter change
  const handleCameraChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      onFiltersChange({
        ...filters,
        camera_id: e.target.value || undefined,
      });
    },
    [filters, onFiltersChange]
  );

  // Handle confidence filter change
  const handleConfidenceChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = parseFloat(e.target.value);
      onFiltersChange({
        ...filters,
        min_confidence: value > 0 ? value : undefined,
      });
    },
    [filters, onFiltersChange]
  );

  // Clear all filters
  const handleClearFilters = useCallback(() => {
    onSearchTextChange('');
    onExactMatchChange(false);
    onFiltersChange({});
  }, [onSearchTextChange, onExactMatchChange, onFiltersChange]);

  // Check if any filters are active
  const hasActiveFilters =
    searchText.length > 0 ||
    filters.camera_id ||
    filters.start_time ||
    filters.end_time ||
    (filters.min_confidence && filters.min_confidence > 0);

  // Get the current confidence label
  const confidenceLabel =
    CONFIDENCE_PRESETS.find((p) => p.value === (filters.min_confidence ?? 0))?.label ??
    `${((filters.min_confidence ?? 0) * 100).toFixed(0)}%+`;

  return (
    <div className={clsx('w-full', className)}>
      {/* Main Search Input Row */}
      <div className="flex items-center gap-3">
        {/* Search Input */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={searchText}
            onChange={(e) => onSearchTextChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isSearching}
            className={clsx(
              'w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2.5 pl-10 pr-10 text-sm text-white',
              'placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]',
              'disabled:cursor-not-allowed disabled:opacity-50'
            )}
            aria-label="Search plate text"
          />
          {/* Clear button */}
          {searchText && (
            <button
              onClick={() => onSearchTextChange('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Exact Match Toggle */}
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={exactMatch}
            onChange={(e) => onExactMatchChange(e.target.checked)}
            disabled={isSearching}
            className={clsx(
              'h-4 w-4 rounded border-gray-600 bg-[#1A1A1A] text-[#76B900]',
              'focus:ring-[#76B900] focus:ring-offset-0',
              'disabled:cursor-not-allowed disabled:opacity-50'
            )}
          />
          <span className="text-sm text-gray-300">Exact match</span>
        </label>

        {/* Advanced Filters Toggle */}
        <button
          onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
          className={clsx(
            'flex items-center gap-2 rounded-md border px-4 py-2.5 text-sm font-medium transition-colors',
            showAdvancedFilters || hasActiveFilters
              ? 'border-[#76B900] bg-[#76B900]/10 text-[#76B900]'
              : 'border-gray-700 bg-[#1A1A1A] text-gray-300 hover:border-gray-600 hover:bg-[#252525]'
          )}
          aria-expanded={showAdvancedFilters}
          aria-label="Toggle advanced filters"
        >
          <SlidersHorizontal className="h-4 w-4" />
          <span>Filters</span>
          {hasActiveFilters && (
            <span className="rounded-full bg-[#76B900] px-2 py-0.5 text-xs font-semibold text-black">
              Active
            </span>
          )}
          {showAdvancedFilters ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Advanced Filters Panel */}
      {showAdvancedFilters && (
        <div className="mt-4 rounded-lg border border-gray-800 bg-[#1A1A1A] p-4">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            {/* Camera Filter */}
            <div>
              <label
                htmlFor="plate-search-camera"
                className="mb-2 block text-sm font-medium text-gray-300"
              >
                Camera
              </label>
              <select
                id="plate-search-camera"
                value={filters.camera_id ?? ''}
                onChange={handleCameraChange}
                disabled={camerasLoading}
                className={clsx(
                  'w-full rounded-md border border-gray-700 bg-[#252525] px-3 py-2 text-sm text-white',
                  'focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]',
                  'disabled:cursor-not-allowed disabled:opacity-50'
                )}
              >
                <option value="">All Cameras</option>
                {cameras.map((camera) => (
                  <option key={camera.id} value={camera.id}>
                    {camera.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Date Range Picker - spans 2 columns */}
            <div className="md:col-span-2">
              <span className="mb-2 block text-sm font-medium text-gray-300">Date Range</span>
              <DateRangePicker
                value={dateRange}
                onChange={handleDateRangeChange}
                showPresets={true}
                labels={{ start: 'From', end: 'To' }}
              />
            </div>

            {/* Confidence Threshold */}
            <div>
              <label
                htmlFor="plate-search-confidence"
                className="mb-2 block text-sm font-medium text-gray-300"
              >
                Min. Confidence: {confidenceLabel}
              </label>
              <input
                id="plate-search-confidence"
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={filters.min_confidence ?? 0}
                onChange={handleConfidenceChange}
                className={clsx(
                  'w-full cursor-pointer appearance-none rounded-lg bg-gray-700 h-2',
                  '[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4',
                  '[&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#76B900]',
                  '[&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:transition-transform',
                  '[&::-webkit-slider-thumb]:hover:scale-110',
                  '[&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4',
                  '[&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-[#76B900]',
                  '[&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer'
                )}
              />
              <div className="mt-1 flex justify-between text-xs text-gray-500">
                <span>0%</span>
                <span>50%</span>
                <span>100%</span>
              </div>
            </div>
          </div>

          {/* Clear Filters Button */}
          <div className="mt-4 flex justify-end">
            <button
              onClick={handleClearFilters}
              disabled={!hasActiveFilters}
              className={clsx(
                'rounded-md border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300',
                'transition-colors hover:border-gray-600 hover:bg-[#252525]',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
            >
              Clear All Filters
            </button>
          </div>
        </div>
      )}
    </div>
  );
});

export default PlateSearchBar;
