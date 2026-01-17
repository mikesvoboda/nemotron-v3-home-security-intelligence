import { Calendar, Filter, X } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import { useDateRangeState } from '../../hooks/useDateRangeState';

export interface AuditFilterParams {
  action?: string;
  resourceType?: string;
  actor?: string;
  status?: string;
  startDate?: string;
  endDate?: string;
}

export interface AuditFiltersProps {
  onFilterChange: (filters: AuditFilterParams) => void;
  availableActions?: string[];
  availableResourceTypes?: string[];
  availableActors?: string[];
  className?: string;
  /** Controlled filter state from parent (e.g., stats card clicks) */
  controlledFilters?: Omit<AuditFilterParams, 'startDate' | 'endDate'>;
}

const STATUS_OPTIONS = ['success', 'failure'];

/**
 * Formats an action name for display in dropdown
 */
function formatAction(action: string): string {
  return action
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * AuditFilters component provides filtering controls for the audit log page
 * Matches the styling of LogFilters component
 * Supports both internal state and controlled state from parent (e.g., stats card clicks)
 */
export default function AuditFilters({
  onFilterChange,
  availableActions = [],
  availableResourceTypes = [],
  availableActors = [],
  className = '',
  controlledFilters,
}: AuditFiltersProps) {
  // Date range state with URL persistence
  const {
    range: dateRange,
    apiParams: dateRangeApiParams,
    setCustomRange: setDateRangeCustom,
    reset: resetDateRange,
  } = useDateRangeState({
    defaultPreset: 'all',
    persistToUrl: true,
    urlParam: 'auditDateRange',
  });

  // State for non-date filters - initialized from controlled filters if provided
  const [filters, setFilters] = useState<Omit<AuditFilterParams, 'startDate' | 'endDate'>>(
    controlledFilters ?? {}
  );
  const [showFilters, setShowFilters] = useState(false);

  // Sync internal state when controlled filters change from parent
  useEffect(() => {
    if (controlledFilters !== undefined) {
      setFilters(controlledFilters);
      // Auto-expand filters when a filter is applied from stats cards
      const hasActiveFilters =
        controlledFilters.action ||
        controlledFilters.resourceType ||
        controlledFilters.actor ||
        controlledFilters.status;
      if (hasActiveFilters) {
        setShowFilters(true);
      }
    }
  }, [controlledFilters]);

  // Notify parent when filters change (including date range)
  useEffect(() => {
    const fullFilters: AuditFilterParams = {
      ...filters,
      startDate: dateRangeApiParams.start_date || undefined,
      endDate: dateRangeApiParams.end_date || undefined,
    };
    onFilterChange(fullFilters);
  }, [filters, dateRangeApiParams, onFilterChange]);

  // Handle non-date filter changes
  const handleFilterChange = (key: keyof Omit<AuditFilterParams, 'startDate' | 'endDate'>, value: string) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === '' ? undefined : value,
    }));
  };

  // Handle custom date range change
  const handleStartDateChange = useCallback(
    (value: string) => {
      if (value) {
        const startDate = new Date(value + 'T00:00:00');
        const endDate = dateRange.endDate;
        setDateRangeCustom(startDate, endDate);
      }
    },
    [dateRange.endDate, setDateRangeCustom]
  );

  const handleEndDateChange = useCallback(
    (value: string) => {
      if (value) {
        const startDate = dateRange.startDate;
        const endDate = new Date(value + 'T23:59:59');
        setDateRangeCustom(startDate, endDate);
      }
    },
    [dateRange.startDate, setDateRangeCustom]
  );

  // Clear all filters
  const handleClearFilters = () => {
    setFilters({});
    resetDateRange();
  };

  // Check if any filters are active
  const hasActiveFilters =
    filters.action ||
    filters.resourceType ||
    filters.actor ||
    filters.status ||
    dateRangeApiParams.start_date ||
    dateRangeApiParams.end_date;

  return (
    <div className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}>
      {/* Filter Toggle */}
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

        {/* Quick Stats Summary */}
        <div className="text-sm text-gray-400">
          Filter by action, resource, actor, status, or date range
        </div>
      </div>

      {/* Filter Options */}
      {showFilters && (
        <div className="grid grid-cols-1 gap-4 border-t border-gray-800 pt-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Action Filter */}
          <div>
            <label htmlFor="action-filter" className="mb-1 block text-sm font-medium text-gray-300">
              Action
            </label>
            <select
              id="action-filter"
              value={filters.action || ''}
              onChange={(e) => handleFilterChange('action', e.target.value)}
              className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            >
              <option value="">All Actions</option>
              {availableActions.map((action) => (
                <option key={action} value={action}>
                  {formatAction(action)}
                </option>
              ))}
            </select>
          </div>

          {/* Resource Type Filter */}
          <div>
            <label
              htmlFor="resource-type-filter"
              className="mb-1 block text-sm font-medium text-gray-300"
            >
              Resource Type
            </label>
            <select
              id="resource-type-filter"
              value={filters.resourceType || ''}
              onChange={(e) => handleFilterChange('resourceType', e.target.value)}
              className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            >
              <option value="">All Resources</option>
              {availableResourceTypes.map((resourceType) => (
                <option key={resourceType} value={resourceType}>
                  {resourceType}
                </option>
              ))}
            </select>
          </div>

          {/* Actor Filter */}
          <div>
            <label htmlFor="actor-filter" className="mb-1 block text-sm font-medium text-gray-300">
              Actor
            </label>
            <select
              id="actor-filter"
              value={filters.actor || ''}
              onChange={(e) => handleFilterChange('actor', e.target.value)}
              className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            >
              <option value="">All Actors</option>
              {availableActors.map((actor) => (
                <option key={actor} value={actor}>
                  {actor}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <label htmlFor="status-filter" className="mb-1 block text-sm font-medium text-gray-300">
              Status
            </label>
            <select
              id="status-filter"
              value={filters.status || ''}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            >
              <option value="">All Statuses</option>
              {STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {status.charAt(0).toUpperCase() + status.slice(1)}
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
                value={dateRangeApiParams.start_date || ''}
                onChange={(e) => handleStartDateChange(e.target.value)}
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
                value={dateRangeApiParams.end_date || ''}
                onChange={(e) => handleEndDateChange(e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-[#1A1A1A] py-2 pl-10 pr-3 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              />
            </div>
          </div>

          {/* Clear Filters Button */}
          <div className="flex items-end lg:col-span-3">
            <button
              onClick={handleClearFilters}
              disabled={!hasActiveFilters}
              className="flex w-full items-center justify-center gap-2 rounded-md border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-gray-600 hover:bg-[#1A1A1A] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            >
              <X className="h-4 w-4" />
              Clear All Filters
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
