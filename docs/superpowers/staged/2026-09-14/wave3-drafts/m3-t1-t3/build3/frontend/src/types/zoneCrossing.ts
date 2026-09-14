/**
 * Zone Crossing Event Types (NEM-3195)
 *
 * TypeScript types for zone crossing events (enter/exit/dwell).
 * These types correspond to the WebSocket events emitted by
 * backend/services/zone_crossing_service.py.
 *
 * @module types/zoneCrossing
 */

// ============================================================================
// Enums
// ============================================================================

/**
 * Types of zone crossing events.
 * Matches the event types emitted by ZoneCrossingService.
 */
export enum ZoneCrossingType {
  ENTER = 'enter',
  EXIT = 'exit',
  DWELL = 'dwell',
}

// ============================================================================
// Core Interfaces
// ============================================================================

/**
 * Zone crossing event data structure.
 * Matches the payload from zone.enter, zone.exit, zone.dwell WebSocket events.
 */
export interface ZoneCrossingEvent {
  /** Type of crossing event */
  type: ZoneCrossingType;
  /** Zone ID where crossing occurred */
  zone_id: string;
  /** Human-readable zone name */
  zone_name: string;
  /** Entity identifier (from re-identification or detection ID) */
  entity_id: string;
  /** Type of entity (e.g., "person", "vehicle", "unknown") */
  entity_type: string;
  /** Associated detection ID */
  detection_id: string;
  /** ISO 8601 timestamp of the event */
  timestamp: string;
  /** Optional thumbnail URL for entity */
  thumbnail_url?: string | null;
  /** Dwell time in seconds (present for exit and dwell events) */
  dwell_time?: number | null;
}

/**
 * WebSocket payload for zone crossing events.
 * This is the raw format received from the backend.
 */
export interface ZoneCrossingEventPayload {
  zone_id: string;
  zone_name: string;
  entity_id: string;
  entity_type: string;
  detection_id: string;
  timestamp: string;
  thumbnail_url?: string | null;
  dwell_time?: number | null;
}

// ============================================================================
// Hook Options and Return Types
// ============================================================================

/**
 * Filter options for zone crossing events.
 */
export interface ZoneCrossingFilters {
  /** Filter by zone ID ('all' for no filter) */
  zoneId?: string;
  /** Filter by entity type ('all' for no filter) */
  entityType?: string;
  /** Filter by event type ('all' for no filter) */
  eventType?: ZoneCrossingType | 'all';
}

/**
 * Options for the useZoneCrossingEvents hook.
 */
export interface UseZoneCrossingEventsOptions {
  /** Maximum number of events to keep in history */
  maxEvents?: number;
  /** Initial filter state */
  filters?: ZoneCrossingFilters;
  /** Whether to enable the WebSocket connection */
  enabled?: boolean;
  /** Callback when a new event is received */
  onEvent?: (event: ZoneCrossingEvent) => void;
}

/**
 * Return type for the useZoneCrossingEvents hook.
 */
export interface UseZoneCrossingEventsReturn {
  /** List of zone crossing events (newest first) */
  events: ZoneCrossingEvent[];
  /** Whether the WebSocket is currently connected */
  isConnected: boolean;
  /** Number of reconnection attempts */
  reconnectCount: number;
  /** Whether max reconnection attempts have been exhausted */
  hasExhaustedRetries: boolean;
  /** Clear all events from history */
  clearEvents: () => void;
  /** Update filter state */
  setFilters: (filters: ZoneCrossingFilters) => void;
  /** Current filter state */
  filters: ZoneCrossingFilters;
}

// ============================================================================
// Component Props
// ============================================================================

/**
 * Filter state for the ZoneCrossingFeed component.
 */
export interface ZoneCrossingFeedFilters {
  /** Filter by zone ID ('all' for no filter) */
  zoneId: string;
  /** Filter by entity type ('all' for no filter) */
  entityType: string;
  /** Filter by event type ('all' for no filter) */
  eventType: ZoneCrossingType | 'all';
}

/**
 * Props for the ZoneCrossingFeed component.
 */
export interface ZoneCrossingFeedProps {
  /** Optional zone ID to filter events */
  zoneId?: string;
  /** Initial filter state */
  initialFilters?: Partial<ZoneCrossingFeedFilters>;
  /** Maximum height for the feed container */
  maxHeight?: string | number;
  /** Maximum number of events to display */
  maxEvents?: number;
  /** Whether to enable real-time updates */
  enableRealtime?: boolean;
  /** Callback when an event is clicked */
  onEventClick?: (event: ZoneCrossingEvent) => void;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * Zone crossing type configuration for UI rendering.
 */
export interface ZoneCrossingTypeConfig {
  label: string;
  description: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: string;
}

/**
 * Map of crossing types to their UI configurations.
 */
export const ZONE_CROSSING_TYPE_CONFIG: Record<ZoneCrossingType, ZoneCrossingTypeConfig> = {
  [ZoneCrossingType.ENTER]: {
    label: 'Enter',
    description: 'Entity entered the zone',
    color: 'text-green-400',
    bgColor: 'bg-green-500/10',
    borderColor: 'border-green-500/30',
    icon: 'ArrowDownRight',
  },
  [ZoneCrossingType.EXIT]: {
    label: 'Exit',
    description: 'Entity exited the zone',
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
    icon: 'ArrowUpRight',
  },
  [ZoneCrossingType.DWELL]: {
    label: 'Dwell',
    description: 'Entity is dwelling in the zone',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/30',
    icon: 'Clock',
  },
};

/**
 * Entity type configuration for UI rendering.
 */
export interface EntityTypeConfig {
  label: string;
  icon: string;
}

/**
 * Common entity types and their UI configurations.
 */
export const ENTITY_TYPE_CONFIG: Record<string, EntityTypeConfig> = {
  person: {
    label: 'Person',
    icon: 'User',
  },
  vehicle: {
    label: 'Vehicle',
    icon: 'Car',
  },
  animal: {
    label: 'Animal',
    icon: 'Dog',
  },
  unknown: {
    label: 'Unknown',
    icon: 'HelpCircle',
  },
};

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for ZoneCrossingType enum.
 */
export function isZoneCrossingType(value: unknown): value is ZoneCrossingType {
  return (
    typeof value === 'string' && Object.values(ZoneCrossingType).includes(value as ZoneCrossingType)
  );
}

/**
 * Type guard for ZoneCrossingEventPayload from WebSocket.
 */
export function isZoneCrossingEventPayload(value: unknown): value is ZoneCrossingEventPayload {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.zone_id === 'string' &&
    typeof obj.zone_name === 'string' &&
    typeof obj.entity_id === 'string' &&
    typeof obj.entity_type === 'string' &&
    typeof obj.detection_id === 'string' &&
    typeof obj.timestamp === 'string'
  );
}

/**
 * Type guard for ZoneCrossingEvent objects.
 */
export function isZoneCrossingEvent(value: unknown): value is ZoneCrossingEvent {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const obj = value as Record<string, unknown>;
  return (
    isZoneCrossingType(obj.type) &&
    typeof obj.zone_id === 'string' &&
    typeof obj.zone_name === 'string' &&
    typeof obj.entity_id === 'string' &&
    typeof obj.entity_type === 'string' &&
    typeof obj.detection_id === 'string' &&
    typeof obj.timestamp === 'string'
  );
}

/**
 * Format dwell time for display.
 * @param seconds - Dwell time in seconds
 * @returns Formatted string (e.g., "2m 30s", "1h 5m")
 */
export function formatDwellTime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) {
    return '--';
  }

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  }
  return `${secs}s`;
}
