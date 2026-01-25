import { ChevronDown, ChevronUp, Eye } from 'lucide-react';
import { memo, useCallback, useEffect, useRef } from 'react';

import { getRiskLevel, type RiskLevel } from '../../utils/risk';
import RiskBadge from '../common/RiskBadge';

/** Sort field options for the event list */
export type SortField = 'time' | 'camera' | 'risk';

/** Sort direction options */
export type SortDirection = 'asc' | 'desc';

/** Event data structure for list view */
export interface EventListItem {
  id: number;
  camera_id: string;
  camera_name: string;
  started_at: string;
  ended_at: string | null | undefined;
  risk_score: number;
  risk_level: string;
  summary: string | null;
  thumbnail_url: string | null;
  reviewed: boolean;
}

export interface EventListViewProps {
  /** Array of events to display */
  events: EventListItem[];
  /** Set of selected event IDs */
  selectedIds: Set<number>;
  /** Callback when an individual event's selection is toggled */
  onToggleSelection: (eventId: number) => void;
  /** Callback when select all is toggled */
  onToggleSelectAll: () => void;
  /** Callback when an event row is clicked */
  onEventClick: (eventId: number) => void;
  /** Callback when mark reviewed action is triggered */
  onMarkReviewed: (eventId: number) => void;
  /** Current sort field */
  sortField?: SortField;
  /** Current sort direction */
  sortDirection?: SortDirection;
  /** Callback when a column header is clicked for sorting */
  onSort?: (field: SortField) => void;
  /** Optional className for additional styling */
  className?: string;
}

/** Props for the SortHeader subcomponent */
interface SortHeaderProps {
  field: SortField;
  label: string;
  currentField?: SortField;
  currentDirection?: SortDirection;
  onSort?: (field: SortField) => void;
  className?: string;
}

/**
 * SortHeader - Column header with sort indicator and click handler
 */
function SortHeader({
  field,
  label,
  currentField,
  currentDirection,
  onSort,
  className = '',
}: SortHeaderProps) {
  const isActive = currentField === field;
  const ariaSort = isActive ? (currentDirection === 'asc' ? 'ascending' : 'descending') : undefined;

  const handleClick = () => {
    onSort?.(field);
  };

  return (
    <th
      scope="col"
      className={`cursor-pointer select-none px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-400 transition-colors hover:text-white ${className}`}
      onClick={handleClick}
      aria-sort={ariaSort}
    >
      <div className="flex items-center gap-1">
        <span>{label}</span>
        <span
          data-testid={`sort-indicator-${field}`}
          className={`transition-opacity ${isActive ? 'opacity-100' : 'opacity-0'}`}
        >
          {currentDirection === 'asc' ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </span>
      </div>
    </th>
  );
}

/**
 * Format timestamp to relative time string
 */
function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;

    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    });
  } catch {
    return isoString;
  }
}

/**
 * EventListView - Compact table view of events for rapid scanning
 *
 * Features:
 * - Sortable columns (Time, Camera, Risk)
 * - Row selection with checkboxes for bulk actions
 * - Quick actions per row (view details, mark reviewed)
 * - Reviewed rows are dimmed
 * - Selected rows have green tint
 * - Responsive: hides Summary column on mobile
 */
const EventListView = memo(function EventListView({
  events,
  selectedIds,
  onToggleSelection,
  onToggleSelectAll,
  onEventClick,
  onMarkReviewed,
  sortField,
  sortDirection,
  onSort,
  className = '',
}: EventListViewProps) {
  const headerCheckboxRef = useRef<HTMLInputElement>(null);

  // Update indeterminate state of header checkbox
  useEffect(() => {
    if (headerCheckboxRef.current) {
      const someSelected = selectedIds.size > 0;
      const allSelected = selectedIds.size === events.length && events.length > 0;
      headerCheckboxRef.current.indeterminate = someSelected && !allSelected;
    }
  }, [selectedIds, events.length]);

  // Handle row click - don't trigger if clicking interactive elements
  const handleRowClick = useCallback(
    (eventId: number, e: React.MouseEvent) => {
      const target = e.target as HTMLElement;
      const isInteractive =
        target.closest('button') || target.closest('input') || target.closest('a');

      if (!isInteractive) {
        onEventClick(eventId);
      }
    },
    [onEventClick]
  );

  // Handle keyboard navigation for rows
  const handleRowKeyDown = useCallback(
    (eventId: number, e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onEventClick(eventId);
      }
    },
    [onEventClick]
  );

  if (events.length === 0) {
    return (
      <div
        className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-8 text-center ${className}`}
      >
        <p className="text-gray-400">No events to display</p>
      </div>
    );
  }

  const allSelected = selectedIds.size === events.length;
  const someSelected = selectedIds.size > 0 && !allSelected;

  return (
    <div className={`overflow-hidden rounded-lg border border-gray-800 bg-[#1F1F1F] ${className}`}>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-800">
          <thead className="bg-[#1A1A1A]">
            <tr>
              {/* Select All Checkbox */}
              <th scope="col" className="w-12 px-4 py-3">
                <input
                  ref={headerCheckboxRef}
                  type="checkbox"
                  checked={allSelected}
                  onChange={onToggleSelectAll}
                  data-indeterminate={someSelected}
                  aria-label="Select all events"
                  className="h-4 w-4 cursor-pointer rounded border-gray-600 bg-gray-800 text-[#76B900] focus:ring-[#76B900] focus:ring-offset-0"
                />
              </th>

              {/* Time Column */}
              <SortHeader
                field="time"
                label="Time"
                currentField={sortField}
                currentDirection={sortDirection}
                onSort={onSort}
              />

              {/* Camera Column */}
              <SortHeader
                field="camera"
                label="Camera"
                currentField={sortField}
                currentDirection={sortDirection}
                onSort={onSort}
              />

              {/* Summary Column - Hidden on mobile */}
              <th
                scope="col"
                className="hidden px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-400 md:table-cell"
              >
                Summary
              </th>

              {/* Risk Column */}
              <SortHeader
                field="risk"
                label="Risk"
                currentField={sortField}
                currentDirection={sortDirection}
                onSort={onSort}
              />

              {/* Actions Column */}
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-400"
              >
                Actions
              </th>
            </tr>
          </thead>

          <tbody className="divide-y divide-gray-800">
            {events.map((event) => {
              const isSelected = selectedIds.has(event.id);
              const riskLevel = (event.risk_level || getRiskLevel(event.risk_score)) as RiskLevel;

              return (
                <tr
                  key={event.id}
                  onClick={(e) => handleRowClick(event.id, e)}
                  onKeyDown={(e) => handleRowKeyDown(event.id, e)}
                  tabIndex={0}
                  className={`cursor-pointer transition-colors hover:bg-[#252525] ${
                    event.reviewed ? 'opacity-60' : ''
                  } ${isSelected ? 'bg-[#76B900]/10' : ''}`}
                  data-testid={`event-list-row-${event.id}`}
                >
                  {/* Selection Checkbox */}
                  <td className="w-12 px-4 py-3">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => onToggleSelection(event.id)}
                      aria-label={`Select event ${event.id}`}
                      className="h-4 w-4 cursor-pointer rounded border-gray-600 bg-gray-800 text-[#76B900] focus:ring-[#76B900] focus:ring-offset-0"
                    />
                  </td>

                  {/* Time */}
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-300">
                    {formatTimestamp(event.started_at)}
                  </td>

                  {/* Camera with mini thumbnail */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {event.thumbnail_url ? (
                        <img
                          src={event.thumbnail_url}
                          alt={`${event.camera_name} thumbnail`}
                          className="h-8 w-8 flex-shrink-0 rounded object-cover"
                        />
                      ) : (
                        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded bg-gray-800">
                          <Eye className="h-4 w-4 text-gray-600" />
                        </div>
                      )}
                      <span className="text-sm font-medium text-white">{event.camera_name}</span>
                    </div>
                  </td>

                  {/* Summary - Hidden on mobile */}
                  <td className="hidden max-w-xs truncate px-4 py-3 text-sm text-gray-400 md:table-cell">
                    {event.summary || 'No summary available'}
                  </td>

                  {/* Risk */}
                  <td className="px-4 py-3">
                    <RiskBadge
                      level={riskLevel}
                      score={event.risk_score}
                      showScore={true}
                      size="sm"
                      animated={false}
                    />
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => onEventClick(event.id)}
                        className="rounded px-2 py-1 text-xs font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/10"
                        aria-label={`View details for event ${event.id}`}
                      >
                        View Details
                      </button>
                      {!event.reviewed && (
                        <button
                          type="button"
                          onClick={() => onMarkReviewed(event.id)}
                          className="rounded px-2 py-1 text-xs font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
                          aria-label={`Mark event ${event.id} as reviewed`}
                        >
                          Mark Reviewed
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
});

export default EventListView;
