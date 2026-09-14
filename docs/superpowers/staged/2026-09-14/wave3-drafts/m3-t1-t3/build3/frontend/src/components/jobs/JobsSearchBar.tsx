/**
 * JobsSearchBar component for filtering and searching background jobs.
 *
 * Features:
 * - Search input with 300ms debounce (handled by parent)
 * - Status dropdown filter (All, Pending, Processing, Completed, Failed, Cancelled)
 * - Type dropdown filter (All, Export, Batch Audit, Cleanup, Re-evaluation)
 * - Clear filters button
 * - Keyboard shortcuts: Escape to clear
 */

import { Search, X, Filter } from 'lucide-react';
import { useCallback } from 'react';

import type { JobStatusEnum } from '../../types/generated';

/**
 * Job status options for the dropdown.
 */
export const JOB_STATUSES = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'running', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
] as const;

/**
 * Job type options for the dropdown.
 */
export const JOB_TYPES = [
  { value: '', label: 'All' },
  { value: 'export', label: 'Export' },
  { value: 'batch_audit', label: 'Batch Audit' },
  { value: 'cleanup', label: 'Cleanup' },
  { value: 're_evaluation', label: 'Re-evaluation' },
] as const;

/**
 * Props for the JobsSearchBar component.
 */
export interface JobsSearchBarProps {
  /** Current search query */
  query: string;
  /** Current status filter */
  status?: JobStatusEnum;
  /** Current type filter */
  type?: string;
  /** Called when search query changes */
  onSearchChange: (query: string) => void;
  /** Called when status filter changes */
  onStatusChange: (status?: JobStatusEnum) => void;
  /** Called when type filter changes */
  onTypeChange: (type?: string) => void;
  /** Called when clearing all filters */
  onClear: () => void;
  /** Whether the search is loading */
  isLoading?: boolean;
  /** Total count of matching jobs */
  totalCount?: number;
  /** Optional className */
  className?: string;
}

/**
 * Search and filter bar for the Jobs page.
 *
 * Provides text search input with status and type dropdowns for filtering
 * background jobs. The search input is debounced by the parent component.
 */
export default function JobsSearchBar({
  query,
  status,
  type,
  onSearchChange,
  onStatusChange,
  onTypeChange,
  onClear,
  isLoading = false,
  totalCount,
  className = '',
}: JobsSearchBarProps) {
  // Check if any filters are active
  const hasActiveFilters = Boolean(query || status || type);

  // Handle keyboard events
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Escape') {
        onClear();
      }
    },
    [onClear]
  );

  // Handle status change
  const handleStatusChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const value = e.target.value;
      onStatusChange(value ? (value as JobStatusEnum) : undefined);
    },
    [onStatusChange]
  );

  // Handle type change
  const handleTypeChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const value = e.target.value;
      onTypeChange(value || undefined);
    },
    [onTypeChange]
  );

  return (
    <div className={`w-full ${className}`}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        {/* Search Input */}
        <div className="relative flex-1">
          <Search
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
            data-testid="search-icon"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => onSearchChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search jobs..."
            disabled={isLoading}
            className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2.5 pl-10 pr-10 text-sm text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Search jobs"
          />
          {query && (
            <button
              onClick={onClear}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Dropdowns Container */}
        <div className="flex items-center gap-3">
          {/* Status Dropdown */}
          <div className="flex items-center gap-2">
            <label htmlFor="jobs-status-filter" className="sr-only">
              Status
            </label>
            <select
              id="jobs-status-filter"
              value={status || ''}
              onChange={handleStatusChange}
              disabled={isLoading}
              className="rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="Status"
            >
              {JOB_STATUSES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {/* Type Dropdown */}
          <div className="flex items-center gap-2">
            <label htmlFor="jobs-type-filter" className="sr-only">
              Type
            </label>
            <select
              id="jobs-type-filter"
              value={type || ''}
              onChange={handleTypeChange}
              disabled={isLoading}
              className="rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="Type"
            >
              {JOB_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {/* Clear All Button */}
          {hasActiveFilters && (
            <button
              onClick={onClear}
              className="flex items-center gap-1.5 rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#252525]"
              aria-label="Clear all"
            >
              <X className="h-4 w-4" />
              <span>Clear all</span>
            </button>
          )}
        </div>
      </div>

      {/* Status Bar */}
      <div className="mt-3 flex items-center justify-between">
        {/* Results Count */}
        <div className="flex items-center gap-2">
          {totalCount !== undefined && (
            <span className="text-sm text-gray-400">
              {totalCount} {totalCount === 1 ? 'job' : 'jobs'}
            </span>
          )}

          {/* Active Filters Indicator */}
          {hasActiveFilters && (
            <div
              className="flex items-center gap-1.5 rounded-full bg-[#76B900]/10 px-2.5 py-1 text-xs font-medium text-[#76B900]"
              data-testid="active-filters-indicator"
            >
              <Filter className="h-3 w-3" />
              <span>Filters active</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
