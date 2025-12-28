import { Calendar, Filter, Search, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import type { LogLevel } from '../../services/logger';

export interface LogFiltersProps {
  onFilterChange: (filters: LogFilterParams) => void;
  cameras?: Array<{ id: string; name: string }>;
  className?: string;
}

export interface LogFilterParams {
  level?: LogLevel;
  component?: string;
  camera?: string;
  startDate?: string;
  endDate?: string;
  search?: string;
}

const LOG_LEVELS: LogLevel[] = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];

const COMMON_COMPONENTS = [
  'frontend',
  'api',
  'user_event',
  'file_watcher',
  'detector',
  'aggregator',
  'risk_analyzer',
  'event_broadcaster',
  'gpu_monitor',
  'cleanup_service',
];

/**
 * LogFilters component provides filtering controls for the logging dashboard
 * Matches the styling of EventTimeline filter panel
 */
export default function LogFilters({
  onFilterChange,
  cameras = [],
  className = '',
}: LogFiltersProps) {
  // State for filters
  const [filters, setFilters] = useState<LogFilterParams>({});
  const [showFilters, setShowFilters] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Notify parent when filters change
  useEffect(() => {
    onFilterChange(filters);
  }, [filters, onFilterChange]);

  // Handle filter changes
  const handleFilterChange = (key: keyof LogFilterParams, value: string) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === '' ? undefined : value,
    }));
  };

  // Handle search
  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    setFilters((prev) => ({
      ...prev,
      search: value === '' ? undefined : value,
    }));
  };

  // Clear all filters
  const handleClearFilters = () => {
    setFilters({});
    setSearchQuery('');
  };

  // Check if any filters are active
  const hasActiveFilters =
    filters.level ||
    filters.component ||
    filters.camera ||
    filters.startDate ||
    filters.endDate ||
    searchQuery;

  return (
    <div className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}>
      {/* Filter Toggle and Search */}
      <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="flex items-center gap-2 rounded-md bg-[#76B900]/10 px-4 py-2 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20"
          aria-expanded={showFilters}
        >
          <Filter className="h-4 w-4" />
          {showFilters ? 'Hide Filters' : 'Show Filters'}
          {hasActiveFilters && (
            <span className="ml-1 rounded-full bg-[#76B900] px-2 py-0.5 text-xs text-black">
              Active
            </span>
          )}
        </button>

        {/* Search */}
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search log messages..."
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-10 text-sm text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
          />
          {searchQuery && (
            <button
              onClick={() => handleSearchChange('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Filter Options */}
      {showFilters && (
        <div className="grid grid-cols-1 gap-4 border-t border-gray-800 pt-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Log Level Filter */}
          <div>
            <label htmlFor="level-filter" className="mb-1 block text-sm font-medium text-gray-300">
              Log Level
            </label>
            <select
              id="level-filter"
              value={filters.level || ''}
              onChange={(e) => handleFilterChange('level', e.target.value)}
              className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            >
              <option value="">All Levels</option>
              {LOG_LEVELS.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </div>

          {/* Component Filter */}
          <div>
            <label
              htmlFor="component-filter"
              className="mb-1 block text-sm font-medium text-gray-300"
            >
              Component
            </label>
            <select
              id="component-filter"
              value={filters.component || ''}
              onChange={(e) => handleFilterChange('component', e.target.value)}
              className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            >
              <option value="">All Components</option>
              {COMMON_COMPONENTS.map((component) => (
                <option key={component} value={component}>
                  {component}
                </option>
              ))}
            </select>
          </div>

          {/* Camera Filter */}
          <div>
            <label htmlFor="camera-filter" className="mb-1 block text-sm font-medium text-gray-300">
              Camera
            </label>
            <select
              id="camera-filter"
              value={filters.camera || ''}
              onChange={(e) => handleFilterChange('camera', e.target.value)}
              className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            >
              <option value="">All Cameras</option>
              {cameras.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.name}
                </option>
              ))}
            </select>
          </div>

          {/* Start Date Filter */}
          <div>
            <label
              htmlFor="start-date-filter"
              className="mb-1 block text-sm font-medium text-gray-300"
            >
              Start Date
            </label>
            <div className="relative">
              <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                id="start-date-filter"
                type="date"
                value={filters.startDate || ''}
                onChange={(e) => handleFilterChange('startDate', e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-3 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              />
            </div>
          </div>

          {/* End Date Filter */}
          <div>
            <label
              htmlFor="end-date-filter"
              className="mb-1 block text-sm font-medium text-gray-300"
            >
              End Date
            </label>
            <div className="relative">
              <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                id="end-date-filter"
                type="date"
                value={filters.endDate || ''}
                onChange={(e) => handleFilterChange('endDate', e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-3 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              />
            </div>
          </div>

          {/* Clear Filters Button */}
          <div className="flex items-end">
            <button
              onClick={handleClearFilters}
              disabled={!hasActiveFilters}
              className="w-full rounded-md border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#1A1A1A] disabled:cursor-not-allowed disabled:opacity-50"
            >
              Clear All Filters
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
