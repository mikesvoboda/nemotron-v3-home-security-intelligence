/**
 * EventSelector - Component for selecting an event for A/B testing
 *
 * Displays a searchable list of recent events that users can select
 * to test prompt configurations against.
 *
 * @see NEM-2698 - Implement prompt A/B testing UI with real inference comparison
 */

import { Card, TextInput, Badge } from '@tremor/react';
import { Search, Calendar, Camera, AlertTriangle } from 'lucide-react';
import { useState, useMemo, useCallback } from 'react';

import type { Event } from '../../../types/generated';

// ============================================================================
// Types
// ============================================================================

export interface EventSelectorProps {
  /** List of events to display */
  events: Event[];
  /** Currently selected event ID */
  selectedEventId: number | null;
  /** Callback when an event is selected */
  onSelect: (eventId: number) => void;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Loading state indicator */
  isLoading?: boolean;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format a date string for display
 */
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} min${diffMins !== 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
  return date.toLocaleDateString();
}

/**
 * Get badge color for risk level
 */
function getRiskBadgeColor(riskLevel: string | null | undefined): 'gray' | 'green' | 'yellow' | 'orange' | 'red' {
  switch (riskLevel?.toLowerCase()) {
    case 'low':
      return 'green';
    case 'medium':
      return 'yellow';
    case 'high':
      return 'orange';
    case 'critical':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * Format camera ID for display
 */
function formatCameraName(cameraId: string): string {
  return cameraId
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ============================================================================
// Component
// ============================================================================

/**
 * Event selector component for A/B testing.
 *
 * Displays a list of recent events with search functionality,
 * allowing users to select an event for prompt testing.
 *
 * @example
 * ```tsx
 * <EventSelector
 *   events={events}
 *   selectedEventId={selected}
 *   onSelect={setSelected}
 * />
 * ```
 */
export default function EventSelector({
  events,
  selectedEventId,
  onSelect,
  disabled = false,
  isLoading = false,
}: EventSelectorProps) {
  const [searchQuery, setSearchQuery] = useState('');

  // Filter events based on search query
  const filteredEvents = useMemo(() => {
    if (!searchQuery.trim()) return events;

    const query = searchQuery.toLowerCase();
    return events.filter((event) => {
      const cameraMatch = event.camera_id.toLowerCase().includes(query);
      const idMatch = event.id.toString().includes(query);
      const riskMatch = event.risk_level?.toLowerCase().includes(query);
      return cameraMatch || idMatch || riskMatch;
    });
  }, [events, searchQuery]);

  // Handle event selection
  const handleSelect = useCallback(
    (eventId: number) => {
      if (!disabled) {
        onSelect(eventId);
      }
    },
    [disabled, onSelect]
  );

  // Handle search input
  const handleSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setSearchQuery(e.target.value);
    },
    []
  );

  return (
    <div className="space-y-4" data-testid="event-selector">
      {/* Search Input */}
      <div className="relative">
        <TextInput
          icon={Search}
          placeholder="Search by camera, event ID, or risk level..."
          value={searchQuery}
          onChange={handleSearchChange}
          disabled={disabled}
          className="bg-gray-900"
        />
      </div>

      {/* Events List */}
      <div
        className="max-h-64 space-y-2 overflow-y-auto"
        role="listbox"
        aria-label="Select an event for testing"
      >
        {isLoading ? (
          <div className="py-8 text-center text-gray-400">
            Loading events...
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="py-8 text-center text-gray-400">
            {searchQuery ? 'No events match your search' : 'No events available'}
          </div>
        ) : (
          filteredEvents.map((event) => {
            const isSelected = event.id === selectedEventId;
            return (
              <Card
                key={event.id}
                role="option"
                aria-selected={isSelected}
                data-testid={`event-option-${event.id}`}
                className={`cursor-pointer border transition-all ${
                  isSelected
                    ? 'border-blue-500 bg-blue-900/20'
                    : 'border-gray-700 bg-gray-900/50 hover:border-gray-600 hover:bg-gray-800/50'
                } ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
                onClick={() => handleSelect(event.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-800">
                      <AlertTriangle className="h-4 w-4 text-gray-400" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white">
                          Event #{event.id}
                        </span>
                        {event.risk_level && (
                          <Badge color={getRiskBadgeColor(event.risk_level)} size="xs">
                            {event.risk_level.charAt(0).toUpperCase() + event.risk_level.slice(1)} Risk
                          </Badge>
                        )}
                      </div>
                      <div className="mt-1 flex items-center gap-3 text-xs text-gray-400">
                        <span className="flex items-center gap-1">
                          <Camera className="h-3 w-3" />
                          {formatCameraName(event.camera_id)}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {formatRelativeTime(event.started_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right text-sm text-gray-400">
                    <div>{event.detection_count} detection{event.detection_count !== 1 ? 's' : ''}</div>
                    {event.risk_score !== null && event.risk_score !== undefined && (
                      <div className="text-xs">Score: {event.risk_score}</div>
                    )}
                  </div>
                </div>
              </Card>
            );
          })
        )}
      </div>

      {/* Event count indicator */}
      {!isLoading && filteredEvents.length > 0 && (
        <div className="text-center text-xs text-gray-500">
          Showing {filteredEvents.length} of {events.length} event{events.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}
