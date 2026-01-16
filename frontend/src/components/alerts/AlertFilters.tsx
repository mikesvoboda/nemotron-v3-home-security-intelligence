import { AlertTriangle, Bell } from 'lucide-react';
import { memo } from 'react';

export type AlertFilterType = 'all' | 'critical' | 'high' | 'medium' | 'unread';

export interface AlertFilterCounts {
  all: number;
  critical: number;
  high: number;
  medium: number;
  unread: number;
}

export interface AlertFiltersProps {
  activeFilter: AlertFilterType;
  onFilterChange: (filter: AlertFilterType) => void;
  counts: AlertFilterCounts;
}

/**
 * AlertFilters component provides severity-based filtering for alerts
 * Displays counts and allows users to filter by severity or unread status
 */
const AlertFilters = memo(function AlertFilters({
  activeFilter,
  onFilterChange,
  counts,
}: AlertFiltersProps) {
  const handleFilterClick = (filter: AlertFilterType) => {
    // Don't trigger change if already active
    if (filter === activeFilter) {
      return;
    }
    onFilterChange(filter);
  };

  const getButtonClasses = (filter: AlertFilterType, colorClasses: string) => {
    const isActive = activeFilter === filter;
    const count = counts[filter];
    const isDisabled = count === 0;

    if (isActive) {
      return `${colorClasses} text-white`;
    }

    if (isDisabled) {
      return 'bg-gray-800/50 text-gray-600 cursor-not-allowed';
    }

    return 'bg-gray-800/30 text-gray-300 hover:bg-gray-700 hover:text-white';
  };

  return (
    <div
      className="flex flex-wrap items-center gap-3"
      role="group"
      aria-label="Alert severity filters"
    >
      {/* All Alerts - Using darker green (#4B7600) for WCAG AA color contrast compliance */}
      <button
        onClick={() => handleFilterClick('all')}
        disabled={counts.all === 0}
        aria-pressed={activeFilter === 'all'}
        aria-label="Filter by all alerts"
        className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${getButtonClasses('all', 'bg-[#4B7600] hover:bg-[#5A8C00]')}`}
      >
        <Bell className="h-4 w-4" />
        <span>All</span>
        <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs font-semibold">
          {counts.all}
        </span>
      </button>

      {/* Critical */}
      <button
        onClick={() => handleFilterClick('critical')}
        disabled={counts.critical === 0}
        aria-pressed={activeFilter === 'critical'}
        aria-label="Filter by critical severity"
        className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${getButtonClasses('critical', 'bg-red-700 hover:bg-red-800')}`}
      >
        <AlertTriangle className="h-4 w-4" />
        <span>Critical</span>
        <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs font-semibold">
          {counts.critical}
        </span>
      </button>

      {/* High */}
      <button
        onClick={() => handleFilterClick('high')}
        disabled={counts.high === 0}
        aria-pressed={activeFilter === 'high'}
        aria-label="Filter by high severity"
        className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${getButtonClasses('high', 'bg-orange-600 hover:bg-orange-700')}`}
      >
        <AlertTriangle className="h-4 w-4" />
        <span>High</span>
        <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs font-semibold">
          {counts.high}
        </span>
      </button>

      {/* Medium */}
      <button
        onClick={() => handleFilterClick('medium')}
        disabled={counts.medium === 0}
        aria-pressed={activeFilter === 'medium'}
        aria-label="Filter by medium severity"
        className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${getButtonClasses('medium', 'bg-yellow-600 hover:bg-yellow-700')}`}
      >
        <AlertTriangle className="h-4 w-4" />
        <span>Medium</span>
        <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs font-semibold">
          {counts.medium}
        </span>
      </button>

      {/* Unread Only */}
      <button
        onClick={() => handleFilterClick('unread')}
        disabled={counts.unread === 0}
        aria-pressed={activeFilter === 'unread'}
        aria-label="Filter by unread alerts"
        className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${getButtonClasses('unread', 'bg-blue-600 hover:bg-blue-700')}`}
      >
        <Bell className="h-4 w-4" />
        <span>Unread Only</span>
        <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs font-semibold">
          {counts.unread}
        </span>
      </button>
    </div>
  );
});

export default AlertFilters;
