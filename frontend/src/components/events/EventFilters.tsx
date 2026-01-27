/**
 * EventFilters - Filter component for events with React 19 useTransition.
 *
 * Uses React 19's useTransition hook to keep the UI responsive during
 * expensive filter state updates. The filter changes are marked as low
 * priority, allowing high-priority updates (like typing) to interrupt.
 *
 * @module components/events/EventFilters
 * @see NEM-3749 - React 19 useTransition for non-blocking search/filter
 */

import { clsx } from 'clsx';
import { Filter, Loader2, X } from 'lucide-react';
import { memo, useCallback, useTransition } from 'react';

import type { RiskLevel } from '../../utils/risk';

/**
 * Filter state for events filtering.
 */
export interface FilterState {
  /** Filter by risk level */
  riskLevel?: RiskLevel | '';
  /** Filter by camera ID */
  cameraId?: string;
  /** Filter by reviewed status */
  reviewed?: boolean;
  /** Filter by object type */
  objectType?: string;
  /** Filter by start date (ISO format) */
  startDate?: string;
  /** Filter by end date (ISO format) */
  endDate?: string;
}

/**
 * Risk level filter options.
 */
const RISK_LEVELS: { value: RiskLevel | ''; label: string }[] = [
  { value: '', label: 'All Risks' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

/**
 * Object type filter options.
 */
const OBJECT_TYPES = [
  { value: '', label: 'All Objects' },
  { value: 'person', label: 'Person' },
  { value: 'vehicle', label: 'Vehicle' },
  { value: 'animal', label: 'Animal' },
  { value: 'package', label: 'Package' },
];

/**
 * Status filter options.
 */
const STATUS_OPTIONS = [
  { value: '', label: 'All Status' },
  { value: 'false', label: 'Unreviewed' },
  { value: 'true', label: 'Reviewed' },
];

export interface EventFiltersProps {
  /** Current filter state */
  filters: FilterState;
  /** Callback when filters change (wrapped in startTransition for non-blocking) */
  onFilterChange: (filters: FilterState) => void;
  /** List of available cameras for filter dropdown */
  cameras?: { id: string; name: string }[];
  /** Additional CSS classes */
  className?: string;
}

/**
 * EventFilters component with React 19 useTransition for non-blocking updates.
 *
 * Uses useTransition to mark filter changes as low priority, keeping the UI
 * responsive during expensive re-renders triggered by filter changes.
 *
 * @example
 * ```tsx
 * const [filters, setFilters] = useState<FilterState>({});
 *
 * <EventFilters
 *   filters={filters}
 *   onFilterChange={setFilters}
 *   cameras={cameraList}
 * />
 * ```
 */
const EventFilters = memo(function EventFilters({
  filters,
  onFilterChange,
  cameras = [],
  className,
}: EventFiltersProps) {
  // React 19 useTransition for non-blocking filter updates
  const [isPending, startTransition] = useTransition();

  /**
   * Handle individual filter field changes.
   * Wraps the update in startTransition to keep UI responsive.
   */
  const handleFilterFieldChange = useCallback(
    (field: keyof FilterState, value: string | boolean | undefined) => {
      startTransition(() => {
        const newFilters: FilterState = { ...filters };

        // Handle special conversions
        if (field === 'reviewed') {
          if (value === '' || value === undefined) {
            delete newFilters.reviewed;
          } else {
            newFilters.reviewed = value === 'true' || value === true;
          }
        } else if (value === '' || value === undefined) {
          // Remove empty filter values
          delete newFilters[field];
        } else {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unsafe-member-access
          (newFilters as any)[field] = value;
        }

        onFilterChange(newFilters);
      });
    },
    [filters, onFilterChange]
  );

  /**
   * Clear all filters.
   * Also wrapped in startTransition for consistency.
   */
  const handleClearFilters = useCallback(() => {
    startTransition(() => {
      onFilterChange({});
    });
  }, [onFilterChange]);

  // Check if any filters are active
  const hasActiveFilters =
    filters.riskLevel ||
    filters.cameraId ||
    filters.reviewed !== undefined ||
    filters.objectType ||
    filters.startDate ||
    filters.endDate;

  return (
    <div
      className={clsx('rounded-lg border border-gray-800 bg-[#1A1A1A] p-4', className)}
      role="group"
      aria-label="Event filters"
    >
      {/* Header with loading indicator */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-300">Filters</span>
          {isPending && (
            <Loader2
              className="h-4 w-4 animate-spin text-[#76B900]"
              data-testid="filter-loading-indicator"
              aria-label="Applying filters"
            />
          )}
        </div>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={handleClearFilters}
            disabled={isPending}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-red-400 transition-colors hover:bg-red-900/20 disabled:opacity-50"
            aria-label="Clear all filters"
          >
            <X className="h-3 w-3" />
            Clear All
          </button>
        )}
      </div>

      {/* Filter controls grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {/* Risk Level Filter */}
        <div>
          <label
            htmlFor="event-filter-risk-level"
            className="mb-1 block text-xs font-medium text-gray-400"
          >
            Risk Level
          </label>
          <select
            id="event-filter-risk-level"
            value={filters.riskLevel ?? ''}
            onChange={(e) => handleFilterFieldChange('riskLevel', e.target.value)}
            disabled={isPending}
            className="w-full rounded-md border border-gray-700 bg-[#252525] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:opacity-50"
          >
            {RISK_LEVELS.map((level) => (
              <option key={level.value} value={level.value}>
                {level.label}
              </option>
            ))}
          </select>
        </div>

        {/* Camera Filter */}
        <div>
          <label
            htmlFor="event-filter-camera"
            className="mb-1 block text-xs font-medium text-gray-400"
          >
            Camera
          </label>
          <select
            id="event-filter-camera"
            value={filters.cameraId ?? ''}
            onChange={(e) => handleFilterFieldChange('cameraId', e.target.value)}
            disabled={isPending}
            className="w-full rounded-md border border-gray-700 bg-[#252525] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:opacity-50"
          >
            <option value="">All Cameras</option>
            {cameras.map((camera) => (
              <option key={camera.id} value={camera.id}>
                {camera.name}
              </option>
            ))}
          </select>
        </div>

        {/* Object Type Filter */}
        <div>
          <label
            htmlFor="event-filter-object-type"
            className="mb-1 block text-xs font-medium text-gray-400"
          >
            Object Type
          </label>
          <select
            id="event-filter-object-type"
            value={filters.objectType ?? ''}
            onChange={(e) => handleFilterFieldChange('objectType', e.target.value)}
            disabled={isPending}
            className="w-full rounded-md border border-gray-700 bg-[#252525] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:opacity-50"
          >
            {OBJECT_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>

        {/* Status Filter */}
        <div>
          <label
            htmlFor="event-filter-status"
            className="mb-1 block text-xs font-medium text-gray-400"
          >
            Status
          </label>
          <select
            id="event-filter-status"
            value={filters.reviewed === undefined ? '' : String(filters.reviewed)}
            onChange={(e) => handleFilterFieldChange('reviewed', e.target.value)}
            disabled={isPending}
            className="w-full rounded-md border border-gray-700 bg-[#252525] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:opacity-50"
          >
            {STATUS_OPTIONS.map((status) => (
              <option key={status.value} value={status.value}>
                {status.label}
              </option>
            ))}
          </select>
        </div>

        {/* Start Date Filter */}
        <div>
          <label
            htmlFor="event-filter-start-date"
            className="mb-1 block text-xs font-medium text-gray-400"
          >
            Start Date
          </label>
          <input
            id="event-filter-start-date"
            type="date"
            value={filters.startDate ?? ''}
            onChange={(e) => handleFilterFieldChange('startDate', e.target.value)}
            disabled={isPending}
            className="w-full rounded-md border border-gray-700 bg-[#252525] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:opacity-50"
          />
        </div>

        {/* End Date Filter */}
        <div>
          <label
            htmlFor="event-filter-end-date"
            className="mb-1 block text-xs font-medium text-gray-400"
          >
            End Date
          </label>
          <input
            id="event-filter-end-date"
            type="date"
            value={filters.endDate ?? ''}
            onChange={(e) => handleFilterFieldChange('endDate', e.target.value)}
            disabled={isPending}
            className="w-full rounded-md border border-gray-700 bg-[#252525] px-3 py-2 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900] disabled:opacity-50"
          />
        </div>
      </div>
    </div>
  );
});

export default EventFilters;
