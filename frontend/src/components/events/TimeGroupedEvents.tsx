import { clsx } from 'clsx';
import { isToday, isYesterday, isThisWeek, format, parseISO } from 'date-fns';
import { CheckSquare, ChevronDown, ChevronRight, Square } from 'lucide-react';
import { memo, useCallback, useMemo, useState } from 'react';

import { getRiskLevel, type RiskLevel } from '../../utils/risk';
import { EventCardSkeleton } from '../common';
import EventCard, { type Detection } from './EventCard';

import type { Event } from '../../services/api';

// ============================================================================
// Types
// ============================================================================

export type TimeGroupKey = 'today' | 'yesterday' | 'this-week' | 'older';

export interface TimeGroup {
  key: TimeGroupKey;
  label: string;
  events: Event[];
  dateRange: string;
  riskCounts: Record<RiskLevel, number>;
}

export interface TimeGroupedEventsProps {
  events: Event[];
  onEventClick?: (eventId: number) => void;
  cameraNameMap: Map<string, string>;
  selectedEventIds: Set<number>;
  onToggleSelection: (eventId: number) => void;
  onViewEventDetails?: (eventId: number) => void;
  isLoading?: boolean;
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

function getEventTimeGroup(eventDate: Date): TimeGroupKey {
  if (isToday(eventDate)) {
    return 'today';
  }
  if (isYesterday(eventDate)) {
    return 'yesterday';
  }
  if (isThisWeek(eventDate, { weekStartsOn: 0 })) {
    return 'this-week';
  }
  return 'older';
}

function formatGroupDateRange(key: TimeGroupKey, events: Event[], now: Date): string {
  if (events.length === 0) return '';

  const sortedDates = events
    .map((e) => parseISO(e.started_at))
    .sort((a, b) => a.getTime() - b.getTime());

  switch (key) {
    case 'today':
      return format(now, 'MMMM d');
    case 'yesterday': {
      const yesterday = new Date(now);
      yesterday.setDate(yesterday.getDate() - 1);
      return format(yesterday, 'MMMM d');
    }
    case 'this-week': {
      const earliest = sortedDates[0];
      const latest = sortedDates[sortedDates.length - 1];
      return `${format(earliest, 'MMM d')} - ${format(latest, 'MMM d')}`;
    }
    case 'older': {
      const earliest = sortedDates[0];
      const latest = sortedDates[sortedDates.length - 1];
      if (format(earliest, 'MMM yyyy') === format(latest, 'MMM yyyy')) {
        return `${format(earliest, 'MMM d')} - ${format(latest, 'd')}`;
      }
      return `${format(earliest, 'MMM d')} - ${format(latest, 'MMM d')}`;
    }
  }
}

function calculateRiskCounts(events: Event[]): Record<RiskLevel, number> {
  const counts: Record<RiskLevel, number> = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
  };

  events.forEach((event) => {
    const level = (event.risk_level || getRiskLevel(event.risk_score || 0)) as RiskLevel;
    counts[level] = (counts[level] || 0) + 1;
  });

  return counts;
}

function groupEventsByTime(events: Event[]): TimeGroup[] {
  const now = new Date();
  const groups: Record<TimeGroupKey, Event[]> = {
    today: [],
    yesterday: [],
    'this-week': [],
    older: [],
  };

  events.forEach((event) => {
    const eventDate = parseISO(event.started_at);
    const groupKey = getEventTimeGroup(eventDate);
    groups[groupKey].push(event);
  });

  const groupConfigs: Array<{ key: TimeGroupKey; label: string }> = [
    { key: 'today', label: 'Today' },
    { key: 'yesterday', label: 'Yesterday' },
    { key: 'this-week', label: 'Earlier This Week' },
    { key: 'older', label: 'Older' },
  ];

  return groupConfigs
    .filter((config) => groups[config.key].length > 0)
    .map((config) => ({
      key: config.key,
      label: config.label,
      events: groups[config.key],
      dateRange: formatGroupDateRange(config.key, groups[config.key], now),
      riskCounts: calculateRiskCounts(groups[config.key]),
    }));
}

// ============================================================================
// Sub-Components
// ============================================================================

interface RiskBreakdownBadgesProps {
  riskCounts: Record<RiskLevel, number>;
}

function RiskBreakdownBadges({ riskCounts }: RiskBreakdownBadgesProps) {
  const riskLevels: RiskLevel[] = ['critical', 'high', 'medium', 'low'];
  const colorClasses: Record<RiskLevel, string> = {
    critical: 'bg-red-500/20 text-red-400',
    high: 'bg-orange-500/20 text-orange-400',
    medium: 'bg-yellow-500/20 text-yellow-400',
    low: 'bg-green-500/20 text-green-400',
  };

  return (
    <div className="flex items-center gap-1.5">
      {riskLevels.map((level) => {
        const count = riskCounts[level];
        if (count === 0) return null;
        return (
          <span
            key={level}
            data-risk={level}
            className={clsx(
              'flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
              colorClasses[level]
            )}
            title={`${count} ${level} risk event${count !== 1 ? 's' : ''}`}
          >
            {count}
          </span>
        );
      })}
    </div>
  );
}

interface TimeGroupSectionProps {
  group: TimeGroup;
  isExpanded: boolean;
  onToggle: () => void;
  cameraNameMap: Map<string, string>;
  selectedEventIds: Set<number>;
  onEventClick?: (eventId: number) => void;
  onToggleSelection: (eventId: number) => void;
  onViewEventDetails?: (eventId: number) => void;
}

function TimeGroupSection({
  group,
  isExpanded,
  onToggle,
  cameraNameMap,
  selectedEventIds,
  onEventClick,
  onToggleSelection,
  onViewEventDetails,
}: TimeGroupSectionProps) {
  const ChevronIcon = isExpanded ? ChevronDown : ChevronRight;
  const testIdKey = group.key;

  return (
    <div
      data-testid={`group-${testIdKey}`}
      role="region"
      aria-labelledby={`group-${testIdKey}-header`}
      className="mb-6"
    >
      <button
        id={`group-${testIdKey}-header`}
        data-testid={`group-${testIdKey}-header`}
        onClick={onToggle}
        aria-expanded={isExpanded}
        aria-controls={`group-${testIdKey}-content`}
        className={clsx(
          'flex w-full items-center justify-between rounded-lg px-4 py-3',
          'border border-gray-800 bg-[#1A1A1A]',
          'transition-colors hover:border-gray-700 hover:bg-[#222]',
          'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#141414]'
        )}
      >
        <div className="flex items-center gap-3">
          <ChevronIcon className="h-5 w-5 text-gray-400" aria-hidden="true" />
          <div className="flex items-center gap-3">
            <span className="text-lg font-semibold text-white">{group.label}</span>
            <span
              data-testid={`group-${testIdKey}-date`}
              className="text-sm text-gray-400"
            >
              {group.dateRange}
            </span>
            <span
              data-testid={`group-${testIdKey}-count`}
              className={clsx(
                'rounded-full bg-[#76B900]/20 px-2.5 py-0.5',
                'text-sm font-medium text-[#76B900]'
              )}
            >
              {group.events.length}
            </span>
          </div>
        </div>

        <RiskBreakdownBadges riskCounts={group.riskCounts} />
      </button>

      {isExpanded && (
        <div
          id={`group-${testIdKey}-content`}
          data-testid={`group-${testIdKey}-content`}
          className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3"
          role="list"
        >
          {group.events.map((event) => {
            const cameraName = cameraNameMap.get(event.camera_id) || 'Unknown Camera';
            const isSelected = selectedEventIds.has(event.id);
            const detections: Detection[] = [];

            return (
              <div key={event.id} className="relative" role="listitem">
                <div className="absolute left-2 top-2 z-10">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleSelection(event.id);
                    }}
                    className={clsx(
                      'flex h-8 w-8 items-center justify-center rounded-md',
                      'border border-gray-700 bg-[#1A1A1A]/90 backdrop-blur-sm',
                      'transition-colors hover:border-gray-600 hover:bg-[#252525]/90'
                    )}
                    aria-label={isSelected ? `Deselect event ${event.id}` : `Select event ${event.id}`}
                  >
                    {isSelected ? (
                      <CheckSquare className="h-5 w-5 text-[#76B900]" />
                    ) : (
                      <Square className="h-5 w-5 text-gray-400" />
                    )}
                  </button>
                </div>

                <EventCard
                  id={String(event.id)}
                  timestamp={event.started_at}
                  camera_name={cameraName}
                  risk_score={event.risk_score || 0}
                  risk_label={event.risk_level || getRiskLevel(event.risk_score || 0)}
                  summary={event.summary || 'No summary available'}
                  thumbnail_url={event.thumbnail_url || undefined}
                  detections={detections}
                  started_at={event.started_at}
                  ended_at={event.ended_at}
                  onClick={onEventClick ? () => onEventClick(event.id) : undefined}
                  onViewDetails={
                    onViewEventDetails ? () => onViewEventDetails(event.id) : undefined
                  }
                  hasCheckboxOverlay
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

const TimeGroupedEvents = memo(function TimeGroupedEvents({
  events,
  onEventClick,
  cameraNameMap,
  selectedEventIds,
  onToggleSelection,
  onViewEventDetails,
  isLoading = false,
  className,
}: TimeGroupedEventsProps) {
  const timeGroups = useMemo(() => groupEventsByTime(events), [events]);

  const [expandedGroups, setExpandedGroups] = useState<Set<TimeGroupKey>>(
    () => new Set<TimeGroupKey>(['today'])
  );

  const handleToggleGroup = useCallback((key: TimeGroupKey) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  if (isLoading) {
    return (
      <div className={clsx('grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3', className)}>
        {Array.from({ length: 6 }, (_, i) => (
          <EventCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div
        className={clsx(
          'flex min-h-[200px] items-center justify-center',
          'rounded-lg border border-gray-800 bg-[#1F1F1F]',
          className
        )}
      >
        <p className="text-gray-400">No events to display</p>
      </div>
    );
  }

  return (
    <div className={className}>
      {timeGroups.map((group) => (
        <TimeGroupSection
          key={group.key}
          group={group}
          isExpanded={expandedGroups.has(group.key)}
          onToggle={() => handleToggleGroup(group.key)}
          cameraNameMap={cameraNameMap}
          selectedEventIds={selectedEventIds}
          onEventClick={onEventClick}
          onToggleSelection={onToggleSelection}
          onViewEventDetails={onViewEventDetails}
        />
      ))}
    </div>
  );
});

export default TimeGroupedEvents;
