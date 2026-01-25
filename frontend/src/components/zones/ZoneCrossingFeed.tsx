/**
 * ZoneCrossingFeed - Real-time feed of zone crossing events (NEM-3195)
 *
 * Displays a filterable feed of zone crossing events (enter/exit/dwell)
 * with real-time updates via WebSocket subscription.
 *
 * Features:
 * - Filter by zone, entity type, event type
 * - Real-time WebSocket updates for zone.enter, zone.exit, zone.dwell
 * - Entity thumbnail display
 * - Dwell time formatting
 * - Empty state handling
 *
 * @module components/zones/ZoneCrossingFeed
 * @see NEM-3195 Phase 3.2 - Zone Crossing Feed Component
 */

import { clsx } from 'clsx';
import {
  ArrowDownRight,
  ArrowUpRight,
  Clock,
  Filter,
  User,
  Car,
  HelpCircle,
  Wifi,
  WifiOff,
  Trash2,
} from 'lucide-react';
import { memo, useCallback, useMemo, useState } from 'react';

import { useZoneCrossingEvents } from '../../hooks/useZoneCrossingEvents';
import { useZonesQuery } from '../../hooks/useZones';
import {
  ZoneCrossingType,
  ZONE_CROSSING_TYPE_CONFIG,
  ENTITY_TYPE_CONFIG,
  formatDwellTime,
} from '../../types/zoneCrossing';

import type {
  ZoneCrossingFeedProps,
  ZoneCrossingFeedFilters,
  ZoneCrossingEvent,
  ZoneCrossingFilters,
} from '../../types/zoneCrossing';

// ============================================================================
// Icons Mapping
// ============================================================================

const EVENT_TYPE_ICONS = {
  [ZoneCrossingType.ENTER]: ArrowDownRight,
  [ZoneCrossingType.EXIT]: ArrowUpRight,
  [ZoneCrossingType.DWELL]: Clock,
};

const ENTITY_TYPE_ICONS: Record<string, typeof User> = {
  person: User,
  vehicle: Car,
  unknown: HelpCircle,
};

// ============================================================================
// Filter Components
// ============================================================================

interface FilterBarProps {
  filters: ZoneCrossingFeedFilters;
  onFilterChange: (filters: ZoneCrossingFeedFilters) => void;
  zones: Array<{ id: string; name: string }>;
  entityTypes: string[];
  disabled?: boolean;
  onClear?: () => void;
  eventCount: number;
}

/**
 * Filter bar for the crossing feed.
 */
function FilterBar({
  filters,
  onFilterChange,
  zones,
  entityTypes,
  disabled,
  onClear,
  eventCount,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg bg-gray-800/50 p-3">
      <div className="flex items-center gap-2 text-sm text-text-secondary">
        <Filter className="h-4 w-4" />
        <span>Filters:</span>
      </div>

      {/* Event type filter */}
      <select
        value={filters.eventType}
        onChange={(e) =>
          onFilterChange({
            ...filters,
            eventType: e.target.value as ZoneCrossingFeedFilters['eventType'],
          })
        }
        disabled={disabled}
        className={clsx(
          'rounded border border-gray-700 bg-gray-800 px-2 py-1 text-sm text-text-primary',
          'focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary',
          disabled && 'cursor-not-allowed opacity-50'
        )}
        aria-label="Filter by event type"
      >
        <option value="all">All Events</option>
        {Object.entries(ZONE_CROSSING_TYPE_CONFIG).map(([key, config]) => (
          <option key={key} value={key}>
            {config.label}
          </option>
        ))}
      </select>

      {/* Zone filter */}
      <select
        value={filters.zoneId}
        onChange={(e) =>
          onFilterChange({
            ...filters,
            zoneId: e.target.value,
          })
        }
        disabled={disabled}
        className={clsx(
          'rounded border border-gray-700 bg-gray-800 px-2 py-1 text-sm text-text-primary',
          'focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary',
          disabled && 'cursor-not-allowed opacity-50'
        )}
        aria-label="Filter by zone"
      >
        <option value="all">All Zones</option>
        {zones.map((zone) => (
          <option key={zone.id} value={zone.id}>
            {zone.name}
          </option>
        ))}
      </select>

      {/* Entity type filter */}
      <select
        value={filters.entityType}
        onChange={(e) =>
          onFilterChange({
            ...filters,
            entityType: e.target.value,
          })
        }
        disabled={disabled}
        className={clsx(
          'rounded border border-gray-700 bg-gray-800 px-2 py-1 text-sm text-text-primary',
          'focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary',
          disabled && 'cursor-not-allowed opacity-50'
        )}
        aria-label="Filter by entity type"
      >
        <option value="all">All Entities</option>
        {entityTypes.map((type) => {
          const config = ENTITY_TYPE_CONFIG[type] ?? ENTITY_TYPE_CONFIG['unknown'];
          return (
            <option key={type} value={type}>
              {config.label}
            </option>
          );
        })}
      </select>

      {/* Clear button */}
      {eventCount > 0 && onClear && (
        <button
          type="button"
          onClick={onClear}
          disabled={disabled}
          className={clsx(
            'ml-auto inline-flex items-center gap-1.5 rounded px-2 py-1',
            'bg-gray-700 text-sm text-text-secondary',
            'hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-primary',
            disabled && 'cursor-not-allowed opacity-50'
          )}
          aria-label="Clear events"
        >
          <Trash2 className="h-3 w-3" />
          Clear
        </button>
      )}
    </div>
  );
}

// ============================================================================
// Empty State
// ============================================================================

interface EmptyStateProps {
  hasFilters: boolean;
}

/**
 * Empty state when no crossing events are found.
 */
function EmptyState({ hasFilters }: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center py-12 text-center"
      data-testid="crossing-feed-empty"
    >
      <div className="rounded-full bg-gray-800 p-3">
        <ArrowDownRight className="h-6 w-6 text-gray-500" />
      </div>
      <h3 className="mt-3 text-sm font-medium text-text-primary">No crossing events</h3>
      <p className="mt-1 text-xs text-text-secondary">
        {hasFilters
          ? 'Try adjusting your filters to see more events.'
          : 'Waiting for zone crossing activity...'}
      </p>
    </div>
  );
}

// ============================================================================
// Event Card Component
// ============================================================================

interface EventCardProps {
  event: ZoneCrossingEvent;
  onClick?: (event: ZoneCrossingEvent) => void;
}

/**
 * Individual zone crossing event card.
 */
function EventCard({ event, onClick }: EventCardProps) {
  const typeConfig = ZONE_CROSSING_TYPE_CONFIG[event.type];
  const EntityIcon = ENTITY_TYPE_ICONS[event.entity_type] ?? HelpCircle;
  const EventIcon = EVENT_TYPE_ICONS[event.type];

  const handleClick = useCallback(() => {
    onClick?.(event);
  }, [event, onClick]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onClick?.(event);
      }
    },
    [event, onClick]
  );

  // Format timestamp for display
  const formattedTime = useMemo(() => {
    try {
      const date = new Date(event.timestamp);
      return date.toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return event.timestamp;
    }
  }, [event.timestamp]);

  const entityConfig = ENTITY_TYPE_CONFIG[event.entity_type] ?? ENTITY_TYPE_CONFIG['unknown'];

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- role and tabIndex are conditionally set when interactive
    <div
      className={clsx(
        'flex items-start gap-3 rounded-lg border p-3',
        typeConfig.bgColor,
        typeConfig.borderColor,
        onClick && 'cursor-pointer transition-colors hover:bg-opacity-20'
      )}
      onClick={onClick ? handleClick : undefined}
      onKeyDown={onClick ? handleKeyDown : undefined}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      data-testid="zone-crossing-event"
    >
      {/* Thumbnail or entity icon */}
      <div
        className={clsx(
          'flex h-12 w-12 shrink-0 items-center justify-center rounded-lg',
          'bg-gray-800'
        )}
      >
        {event.thumbnail_url ? (
          <img
            src={event.thumbnail_url}
            alt={`${event.entity_type} thumbnail`}
            className="h-full w-full rounded-lg object-cover"
            onError={(e) => {
              // On error, hide the image and show the icon
              e.currentTarget.style.display = 'none';
            }}
          />
        ) : (
          <EntityIcon className="h-6 w-6 text-gray-400" />
        )}
      </div>

      {/* Event details */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2">
          <EventIcon className={clsx('h-4 w-4', typeConfig.color)} />
          <span className={clsx('text-sm font-medium', typeConfig.color)}>{typeConfig.label}</span>
          <span className="text-sm text-text-secondary">-</span>
          <span className="truncate text-sm text-text-primary" title={event.zone_name}>
            {event.zone_name}
          </span>
        </div>

        <div className="mt-1 flex items-center gap-2 text-xs text-text-secondary">
          <span className="inline-flex items-center gap-1">
            <EntityIcon className="h-3 w-3" />
            {entityConfig.label}
          </span>
          <span>|</span>
          <span>{formattedTime}</span>
          {event.dwell_time !== null && event.dwell_time !== undefined && (
            <>
              <span>|</span>
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatDwellTime(event.dwell_time)}
              </span>
            </>
          )}
        </div>

        {/* Entity ID (truncated) */}
        <div className="mt-1 truncate text-xs text-text-muted" title={event.entity_id}>
          ID: {event.entity_id.slice(0, 12)}
          {event.entity_id.length > 12 && '...'}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneCrossingFeed displays a real-time feed of zone crossing events.
 *
 * Subscribes to zone.enter, zone.exit, and zone.dwell WebSocket events
 * and displays them in chronological order with filtering capabilities.
 *
 * @example
 * ```tsx
 * <ZoneCrossingFeed
 *   enableRealtime
 *   maxEvents={50}
 *   onEventClick={(event) => console.log('Clicked:', event)}
 * />
 * ```
 */
function ZoneCrossingFeedComponent({
  zoneId,
  initialFilters,
  maxHeight = '600px',
  maxEvents = 100,
  enableRealtime = true,
  onEventClick,
  className,
}: ZoneCrossingFeedProps) {
  // Filter state
  const [filters, setFilters] = useState<ZoneCrossingFeedFilters>({
    eventType: 'all',
    zoneId: zoneId ?? 'all',
    entityType: 'all',
    ...initialFilters,
  });

  // Fetch zones for the filter dropdown
  const { zones } = useZonesQuery(undefined, { enabled: false });

  // Convert component filters to hook filters
  const hookFilters = useMemo<ZoneCrossingFilters>(
    () => ({
      zoneId: filters.zoneId,
      entityType: filters.entityType,
      eventType: filters.eventType,
    }),
    [filters]
  );

  // Subscribe to zone crossing events
  const { events, isConnected, clearEvents } = useZoneCrossingEvents({
    maxEvents,
    filters: hookFilters,
    enabled: enableRealtime,
  });

  // Check if any filters are active
  const hasActiveFilters =
    filters.eventType !== 'all' || filters.zoneId !== 'all' || filters.entityType !== 'all';

  // Handle filter change
  const handleFilterChange = useCallback((newFilters: ZoneCrossingFeedFilters) => {
    setFilters(newFilters);
  }, []);

  // Handle event click
  const handleEventClick = useCallback(
    (event: ZoneCrossingEvent) => {
      onEventClick?.(event);
    },
    [onEventClick]
  );

  // Build zone options for filter
  const zoneOptions = useMemo(() => {
    const zoneSet = new Map<string, string>();
    zones.forEach((z) => zoneSet.set(z.id, z.name));
    // Also include zones from events that might not be in the zones query
    events.forEach((e) => {
      if (!zoneSet.has(e.zone_id)) {
        zoneSet.set(e.zone_id, e.zone_name);
      }
    });
    return Array.from(zoneSet.entries()).map(([id, name]) => ({ id, name }));
  }, [zones, events]);

  // Build entity type options from events
  const entityTypeOptions = useMemo(() => {
    const types = new Set<string>();
    events.forEach((e) => types.add(e.entity_type));
    // Ensure common types are always available
    ['person', 'vehicle', 'unknown'].forEach((t) => types.add(t));
    return Array.from(types).sort();
  }, [events]);

  return (
    <div className={clsx('flex flex-col', className)} data-testid="zone-crossing-feed">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Zone Crossings</h3>
          <p className="text-sm text-text-secondary">
            {events.length} {events.length === 1 ? 'event' : 'events'} in feed
          </p>
        </div>

        {/* Connection status */}
        <div className="flex items-center gap-2">
          {enableRealtime && (
            <div
              className={clsx(
                'flex items-center gap-1 rounded px-2 py-1 text-xs',
                isConnected ? 'bg-green-500/10 text-green-400' : 'bg-gray-700 text-gray-400'
              )}
              title={isConnected ? 'Real-time updates active' : 'Connecting...'}
              data-testid="connection-status"
            >
              {isConnected ? (
                <>
                  <Wifi className="h-3 w-3" />
                  <span>Live</span>
                </>
              ) : (
                <>
                  <WifiOff className="h-3 w-3" />
                  <span>Offline</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Filter bar */}
      <FilterBar
        filters={filters}
        onFilterChange={handleFilterChange}
        zones={zoneOptions}
        entityTypes={entityTypeOptions}
        onClear={clearEvents}
        eventCount={events.length}
      />

      {/* Content */}
      <div
        className="mt-4 overflow-y-auto"
        style={{ maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight }}
      >
        {events.length === 0 ? (
          <EmptyState hasFilters={hasActiveFilters} />
        ) : (
          <div className="space-y-2" data-testid="crossing-feed-list">
            {events.map((event, index) => (
              <EventCard
                key={`${event.timestamp}-${event.entity_id}-${index}`}
                event={event}
                onClick={onEventClick ? handleEventClick : undefined}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Memoized ZoneCrossingFeed component for performance.
 */
export const ZoneCrossingFeed = memo(ZoneCrossingFeedComponent);

export default ZoneCrossingFeed;
