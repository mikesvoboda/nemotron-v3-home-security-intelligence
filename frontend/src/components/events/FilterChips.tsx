import { clsx } from 'clsx';
import { subHours, startOfDay, startOfWeek, format } from 'date-fns';
import { Calendar, X } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

import type { EventFilters } from '../../hooks/useEventsQuery';
import type { RiskLevel } from '../../utils/risk';

/**
 * Color variants for filter chips.
 * Maps to risk levels plus default for non-risk chips.
 */
type ChipVariant = 'critical' | 'high' | 'medium' | 'low' | 'default';

export interface FilterChipProps {
  /** Label text displayed on the chip */
  label: string;
  /** Optional count to display (e.g., event count for risk levels) */
  count?: number;
  /** Whether this chip is currently active/selected */
  isActive?: boolean;
  /** Color variant for the chip */
  variant?: ChipVariant;
  /** Click handler */
  onClick: () => void;
  /** Whether the chip is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Individual filter chip component with color variants and accessibility support.
 */
export function FilterChip({
  label,
  count,
  isActive = false,
  variant = 'default',
  onClick,
  disabled = false,
  className,
}: FilterChipProps) {
  // Get active background color classes based on variant
  const getActiveClasses = () => {
    switch (variant) {
      case 'critical':
        return 'bg-risk-critical/20 border-risk-critical text-risk-critical';
      case 'high':
        return 'bg-risk-high/20 border-risk-high text-risk-high';
      case 'medium':
        return 'bg-risk-medium/20 border-risk-medium text-risk-medium';
      case 'low':
        return 'bg-risk-low/20 border-risk-low text-risk-low';
      case 'default':
      default:
        return 'bg-[#76B900]/20 border-[#76B900] text-[#76B900]';
    }
  };

  // Inactive state - gray border and text
  const inactiveClasses =
    'border-gray-700 text-gray-400 hover:border-gray-500 hover:bg-gray-800/50';

  // Disabled state
  const disabledClasses = 'opacity-50 cursor-not-allowed';

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={isActive}
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium transition-all',
        isActive ? getActiveClasses() : inactiveClasses,
        disabled && disabledClasses,
        className
      )}
    >
      <span>{label}</span>
      {count !== undefined && (
        <span
          className={clsx(
            'rounded-full px-1.5 py-0.5 text-xs font-semibold',
            isActive ? 'bg-black/20' : 'bg-gray-800'
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
}

/**
 * Time preset type for quick date filtering.
 */
type TimePreset = 'last_hour' | 'today' | 'this_week' | 'custom';

export interface FilterChipsProps {
  /** Current active filters */
  filters: EventFilters;
  /** Risk level counts for displaying on chips */
  riskCounts: Record<RiskLevel, number>;
  /** Handler for filter changes */
  onFilterChange: (key: keyof EventFilters, value: string | boolean) => void;
  /** Handler for clearing all filters */
  onClearFilters: () => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Horizontal chip bar for quick one-click filtering of events.
 * Includes risk level chips, time presets, and status filters.
 */
export default function FilterChips({
  filters,
  riskCounts,
  onFilterChange,
  onClearFilters,
  className,
}: FilterChipsProps) {
  // Track whether custom date picker is shown
  const [showCustomDates, setShowCustomDates] = useState(false);

  // Calculate which time preset is active based on current filters
  const activeTimePreset = useMemo((): TimePreset | null => {
    if (!filters.start_date) return null;

    // Parse the start_date - it could be YYYY-MM-DD format or full ISO string
    const startDateStr = filters.start_date.split('T')[0]; // Get just the date part
    const now = new Date();

    // Check if start_date matches "Today"
    const todayStr = format(startOfDay(now), 'yyyy-MM-dd');
    if (startDateStr === todayStr) {
      return 'today';
    }

    // Check if start_date matches "This Week"
    const weekStartStr = format(startOfWeek(now, { weekStartsOn: 0 }), 'yyyy-MM-dd');
    if (startDateStr === weekStartStr) {
      return 'this_week';
    }

    // Note: "last hour" preset cannot be reliably detected from just a date string
    // since it requires timestamp precision. It will fall through to 'custom'.

    // Custom date range
    return 'custom';
  }, [filters.start_date]);

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return !!(
      filters.risk_level ||
      filters.start_date ||
      filters.end_date ||
      filters.reviewed !== undefined ||
      filters.camera_id ||
      filters.object_type
    );
  }, [filters]);

  // Handle risk level chip click
  const handleRiskLevelClick = useCallback(
    (level: RiskLevel) => {
      if (filters.risk_level === level) {
        // Toggle off if already active
        onFilterChange('risk_level', '');
      } else {
        onFilterChange('risk_level', level);
      }
    },
    [filters.risk_level, onFilterChange]
  );

  // Handle time preset click
  const handleTimePresetClick = useCallback(
    (preset: TimePreset) => {
      // If clicking the active preset, clear it
      if (activeTimePreset === preset && preset !== 'custom') {
        onFilterChange('start_date', '');
        onFilterChange('end_date', '');
        return;
      }

      if (preset === 'custom') {
        // Toggle custom date picker visibility
        setShowCustomDates((prev) => !prev);
        return;
      }

      // Close custom dates if it was open
      setShowCustomDates(false);

      const now = new Date();
      let startDate: Date;

      switch (preset) {
        case 'last_hour':
          startDate = subHours(now, 1);
          break;
        case 'today':
          startDate = startOfDay(now);
          break;
        case 'this_week':
          startDate = startOfWeek(now, { weekStartsOn: 0 });
          break;
        default:
          return;
      }

      // Format as YYYY-MM-DD for the API
      onFilterChange('start_date', format(startDate, 'yyyy-MM-dd'));
      // Clear end_date for presets
      onFilterChange('end_date', '');
    },
    [activeTimePreset, onFilterChange]
  );

  // Handle unreviewed filter click
  const handleUnreviewedClick = useCallback(() => {
    if (filters.reviewed === false) {
      // Toggle off if already active
      onFilterChange('reviewed', '');
    } else {
      onFilterChange('reviewed', false);
    }
  }, [filters.reviewed, onFilterChange]);

  // Handle custom date changes
  const handleCustomDateChange = useCallback(
    (field: 'start_date' | 'end_date', value: string) => {
      onFilterChange(field, value);
    },
    [onFilterChange]
  );

  return (
    <div
      role="group"
      aria-label="Filter options"
      className={clsx('flex flex-col gap-3', className)}
    >
      <div className="flex flex-wrap items-center gap-2">
        {/* Risk Level Section */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium uppercase tracking-wider text-gray-500">
            Risk Level
          </span>
          <div className="flex flex-wrap gap-1.5">
            <FilterChip
              label="Critical"
              count={riskCounts.critical}
              variant="critical"
              isActive={filters.risk_level === 'critical'}
              onClick={() => handleRiskLevelClick('critical')}
            />
            <FilterChip
              label="High"
              count={riskCounts.high}
              variant="high"
              isActive={filters.risk_level === 'high'}
              onClick={() => handleRiskLevelClick('high')}
            />
            <FilterChip
              label="Medium"
              count={riskCounts.medium}
              variant="medium"
              isActive={filters.risk_level === 'medium'}
              onClick={() => handleRiskLevelClick('medium')}
            />
          </div>
        </div>

        {/* Divider */}
        <div className="h-6 w-px bg-gray-700" />

        {/* Time Section */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium uppercase tracking-wider text-gray-500">Time</span>
          <div className="flex flex-wrap gap-1.5">
            <FilterChip
              label="Last Hour"
              isActive={activeTimePreset === 'last_hour'}
              onClick={() => handleTimePresetClick('last_hour')}
            />
            <FilterChip
              label="Today"
              isActive={activeTimePreset === 'today'}
              onClick={() => handleTimePresetClick('today')}
            />
            <FilterChip
              label="This Week"
              isActive={activeTimePreset === 'this_week'}
              onClick={() => handleTimePresetClick('this_week')}
            />
            <FilterChip
              label="Custom"
              isActive={showCustomDates || activeTimePreset === 'custom'}
              onClick={() => handleTimePresetClick('custom')}
            />
          </div>
        </div>

        {/* Divider */}
        <div className="h-6 w-px bg-gray-700" />

        {/* Status Section */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium uppercase tracking-wider text-gray-500">Status</span>
          <div className="flex flex-wrap gap-1.5">
            <FilterChip
              label="Unreviewed"
              isActive={filters.reviewed === false}
              onClick={handleUnreviewedClick}
            />
            <FilterChip label="With Video" isActive={false} onClick={() => {}} disabled={true} />
          </div>
        </div>

        {/* Clear All Button */}
        {hasActiveFilters && (
          <>
            <div className="h-6 w-px bg-gray-700" />
            <button
              type="button"
              onClick={onClearFilters}
              className="flex items-center gap-1 rounded-full bg-red-900/20 px-3 py-1 text-sm font-medium text-red-400 transition-colors hover:bg-red-900/40"
            >
              <X className="h-3.5 w-3.5" />
              <span>Clear All</span>
            </button>
          </>
        )}
      </div>

      {/* Custom Date Picker (inline) */}
      {showCustomDates && (
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-gray-800 bg-[#1A1A1A] p-3">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-gray-400" />
            <label htmlFor="filter-chips-start-date" className="text-sm font-medium text-gray-300">
              Start Date
            </label>
            <input
              id="filter-chips-start-date"
              type="date"
              value={filters.start_date || ''}
              onChange={(e) => handleCustomDateChange('start_date', e.target.value)}
              className="rounded-md border border-gray-700 bg-[#1F1F1F] px-2 py-1 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            />
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="filter-chips-end-date" className="text-sm font-medium text-gray-300">
              End Date
            </label>
            <input
              id="filter-chips-end-date"
              type="date"
              value={filters.end_date || ''}
              onChange={(e) => handleCustomDateChange('end_date', e.target.value)}
              className="rounded-md border border-gray-700 bg-[#1F1F1F] px-2 py-1 text-sm text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            />
          </div>
        </div>
      )}
    </div>
  );
}
