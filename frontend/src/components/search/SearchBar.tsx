import {
  Calendar,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Search,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import type { Camera } from '../../services/api';

/**
 * Search filters that can be applied alongside the search query
 */
export interface SearchFilters {
  /** Filter by camera IDs (comma-separated) */
  camera_id?: string;
  /** Filter by start date (ISO format) */
  start_date?: string;
  /** Filter by end date (ISO format) */
  end_date?: string;
  /** Filter by risk levels (comma-separated) */
  severity?: string;
  /** Filter by object types (comma-separated) */
  object_type?: string;
  /** Filter by reviewed status */
  reviewed?: boolean;
}

export interface SearchBarProps {
  /** Current search query */
  query: string;
  /** Called when search query changes */
  onQueryChange: (query: string) => void;
  /** Called when user submits the search */
  onSearch: (query: string, filters: SearchFilters) => void;
  /** Whether a search is currently in progress */
  isSearching?: boolean;
  /** Optional list of cameras for filter dropdown */
  cameras?: Camera[];
  /** Initial filter values */
  initialFilters?: SearchFilters;
  /** Optional class name */
  className?: string;
  /** Placeholder text */
  placeholder?: string;
}

/**
 * Query syntax hints shown to users
 */
const QUERY_HINTS = [
  { syntax: 'person vehicle', description: 'Find events with both terms (implicit AND)' },
  { syntax: '"suspicious person"', description: 'Find exact phrase' },
  { syntax: 'person OR animal', description: 'Find events with either term' },
  { syntax: 'person NOT cat', description: 'Find person but exclude cat' },
  { syntax: 'front_door', description: 'Search by camera name' },
];

/**
 * SearchBar component with advanced full-text search capabilities.
 *
 * Features:
 * - Full-text search input with query syntax hints
 * - Expandable advanced filters panel
 * - Query syntax help tooltip
 * - Clear search button
 * - Keyboard shortcuts (Enter to search, Escape to clear)
 */
export default function SearchBar({
  query,
  onQueryChange,
  onSearch,
  isSearching = false,
  cameras = [],
  initialFilters = {},
  className = '',
  placeholder = 'Search events (e.g., "suspicious person", vehicle OR animal)...',
}: SearchBarProps) {
  // State for advanced filters panel visibility
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);

  // State for query syntax help visibility
  const [showQueryHelp, setShowQueryHelp] = useState(false);

  // Local filter state
  const [filters, setFilters] = useState<SearchFilters>(initialFilters);

  // Ref for the help tooltip
  const helpRef = useRef<HTMLDivElement>(null);

  // Sync filters with initial filters prop
  useEffect(() => {
    setFilters(initialFilters);
  }, [initialFilters]);

  // Close help tooltip when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (helpRef.current && !helpRef.current.contains(event.target as Node)) {
        setShowQueryHelp(false);
      }
    };

    if (showQueryHelp) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showQueryHelp]);

  // Handle search submission
  const handleSubmit = useCallback(() => {
    if (query.trim()) {
      onSearch(query.trim(), filters);
    }
  }, [query, filters, onSearch]);

  // Handle keyboard events
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSubmit();
      } else if (e.key === 'Escape') {
        onQueryChange('');
      }
    },
    [handleSubmit, onQueryChange]
  );

  // Handle filter changes
  const handleFilterChange = useCallback(
    (key: keyof SearchFilters, value: string | boolean | undefined) => {
      setFilters((prev) => ({
        ...prev,
        [key]: value === '' ? undefined : value,
      }));
    },
    []
  );

  // Clear all filters
  const handleClearFilters = useCallback(() => {
    setFilters({});
    onQueryChange('');
  }, [onQueryChange]);

  // Check if any filters are active
  const hasActiveFilters =
    filters.camera_id ||
    filters.start_date ||
    filters.end_date ||
    filters.severity ||
    filters.object_type ||
    filters.reviewed !== undefined;

  return (
    <div className={`w-full ${className}`}>
      {/* Main Search Input Row */}
      <div className="flex items-center gap-2">
        {/* Search Input */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isSearching}
            className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2.5 pl-10 pr-20 text-sm text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Search events"
          />
          {/* Clear and Help buttons */}
          <div className="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-1">
            {query && (
              <button
                onClick={() => onQueryChange('')}
                className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
                aria-label="Clear search"
              >
                <X className="h-4 w-4" />
              </button>
            )}
            <div className="relative" ref={helpRef}>
              <button
                onClick={() => setShowQueryHelp(!showQueryHelp)}
                className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-[#76B900]"
                aria-label="Show search syntax help"
                aria-expanded={showQueryHelp}
              >
                <HelpCircle className="h-4 w-4" />
              </button>
              {/* Query syntax help tooltip */}
              {showQueryHelp && (
                <div className="absolute right-0 top-full z-50 mt-2 w-80 rounded-lg border border-gray-700 bg-[#1F1F1F] p-4 shadow-xl">
                  <h3 className="mb-3 text-sm font-semibold text-white">Search Syntax</h3>
                  <div className="space-y-2">
                    {QUERY_HINTS.map((hint, index) => (
                      <div key={index} className="text-sm">
                        <code className="rounded bg-gray-800 px-1.5 py-0.5 font-mono text-xs text-[#76B900]">
                          {hint.syntax}
                        </code>
                        <p className="mt-0.5 text-gray-400">{hint.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Search Button */}
        <button
          onClick={handleSubmit}
          disabled={isSearching || !query.trim()}
          className="flex items-center gap-2 rounded-md bg-[#76B900] px-5 py-2.5 text-sm font-semibold text-black transition-all hover:bg-[#88d200] active:bg-[#68a000] disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Search"
        >
          {isSearching ? (
            <>
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-black border-t-transparent" />
              <span>Searching...</span>
            </>
          ) : (
            <>
              <Search className="h-4 w-4" />
              <span>Search</span>
            </>
          )}
        </button>

        {/* Advanced Filters Toggle */}
        <button
          onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
          className={`flex items-center gap-2 rounded-md border px-4 py-2.5 text-sm font-medium transition-colors ${
            showAdvancedFilters || hasActiveFilters
              ? 'border-[#76B900] bg-[#76B900]/10 text-[#76B900]'
              : 'border-gray-700 bg-[#1A1A1A] text-gray-300 hover:border-gray-600 hover:bg-[#252525]'
          }`}
          aria-expanded={showAdvancedFilters}
          aria-label="Toggle advanced filters"
        >
          Filters
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
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {/* Camera Filter */}
            <div>
              <label htmlFor="search-camera-filter" className="mb-1 block text-sm font-medium text-gray-300">
                Camera
              </label>
              <select
                id="search-camera-filter"
                value={filters.camera_id || ''}
                onChange={(e) => handleFilterChange('camera_id', e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-[#252525] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              >
                <option value="">All Cameras</option>
                {cameras.map((camera) => (
                  <option key={camera.id} value={camera.id}>
                    {camera.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Severity Filter */}
            <div>
              <label htmlFor="search-severity-filter" className="mb-1 block text-sm font-medium text-gray-300">
                Severity
              </label>
              <select
                id="search-severity-filter"
                value={filters.severity || ''}
                onChange={(e) => handleFilterChange('severity', e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-[#252525] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              >
                <option value="">All Severities</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
                <option value="high,critical">High & Critical</option>
              </select>
            </div>

            {/* Object Type Filter */}
            <div>
              <label htmlFor="search-object-filter" className="mb-1 block text-sm font-medium text-gray-300">
                Object Type
              </label>
              <select
                id="search-object-filter"
                value={filters.object_type || ''}
                onChange={(e) => handleFilterChange('object_type', e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-[#252525] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              >
                <option value="">All Objects</option>
                <option value="person">Person</option>
                <option value="vehicle">Vehicle</option>
                <option value="animal">Animal</option>
                <option value="package">Package</option>
                <option value="other">Other</option>
              </select>
            </div>

            {/* Reviewed Status Filter */}
            <div>
              <label htmlFor="search-reviewed-filter" className="mb-1 block text-sm font-medium text-gray-300">
                Status
              </label>
              <select
                id="search-reviewed-filter"
                value={filters.reviewed === undefined ? '' : filters.reviewed ? 'true' : 'false'}
                onChange={(e) =>
                  handleFilterChange(
                    'reviewed',
                    e.target.value === '' ? undefined : e.target.value === 'true'
                  )
                }
                className="w-full rounded-md border border-gray-700 bg-[#252525] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              >
                <option value="">All Events</option>
                <option value="false">Unreviewed</option>
                <option value="true">Reviewed</option>
              </select>
            </div>

            {/* Start Date Filter */}
            <div>
              <label htmlFor="search-start-date" className="mb-1 block text-sm font-medium text-gray-300">
                Start Date
              </label>
              <div className="relative">
                <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  id="search-start-date"
                  type="date"
                  value={filters.start_date || ''}
                  onChange={(e) => handleFilterChange('start_date', e.target.value)}
                  className="w-full rounded-md border border-gray-700 bg-[#252525] py-2 pl-10 pr-3 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
                />
              </div>
            </div>

            {/* End Date Filter */}
            <div>
              <label htmlFor="search-end-date" className="mb-1 block text-sm font-medium text-gray-300">
                End Date
              </label>
              <div className="relative">
                <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  id="search-end-date"
                  type="date"
                  value={filters.end_date || ''}
                  onChange={(e) => handleFilterChange('end_date', e.target.value)}
                  className="w-full rounded-md border border-gray-700 bg-[#252525] py-2 pl-10 pr-3 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
                />
              </div>
            </div>

            {/* Clear Filters Button */}
            <div className="flex items-end">
              <button
                onClick={handleClearFilters}
                disabled={!hasActiveFilters && !query}
                className="w-full rounded-md border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#252525] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Clear All
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
