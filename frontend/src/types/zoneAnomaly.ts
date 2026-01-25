/**
 * Zone Anomaly Types (NEM-3199)
 *
 * TypeScript types for zone anomaly detection and display.
 * These types correspond to backend models in backend/models/zone_anomaly.py
 * and the zone_anomaly_service.py WebSocket events.
 *
 * @module types/zoneAnomaly
 */

// ============================================================================
// Enums
// ============================================================================

/**
 * Types of zone anomalies that can be detected.
 * Matches backend AnomalyType enum.
 */
export enum AnomalyType {
  UNUSUAL_TIME = 'unusual_time',
  UNUSUAL_FREQUENCY = 'unusual_frequency',
  UNUSUAL_DWELL = 'unusual_dwell',
  UNUSUAL_ENTITY = 'unusual_entity',
}

/**
 * Severity levels for detected anomalies.
 * Matches backend AnomalySeverity enum.
 */
export enum AnomalySeverity {
  INFO = 'info',
  WARNING = 'warning',
  CRITICAL = 'critical',
}

// ============================================================================
// Core Interfaces
// ============================================================================

/**
 * Zone anomaly data structure.
 * Represents a detected anomaly in zone activity patterns.
 */
export interface ZoneAnomaly {
  /** Unique identifier for the anomaly */
  id: string;
  /** Zone ID where anomaly was detected */
  zone_id: string;
  /** Camera ID associated with the zone */
  camera_id: string;
  /** Type of anomaly detected */
  anomaly_type: AnomalyType;
  /** Severity level of the anomaly */
  severity: AnomalySeverity;
  /** Human-readable title */
  title: string;
  /** Detailed description of the anomaly */
  description: string | null;
  /** Expected value from baseline */
  expected_value: number | null;
  /** Actual observed value */
  actual_value: number | null;
  /** Statistical deviation from baseline */
  deviation: number | null;
  /** Related detection ID if applicable */
  detection_id: number | null;
  /** URL to thumbnail image for visual context */
  thumbnail_url: string | null;
  /** Whether the anomaly has been acknowledged */
  acknowledged: boolean;
  /** When the anomaly was acknowledged */
  acknowledged_at: string | null;
  /** Who acknowledged the anomaly */
  acknowledged_by: string | null;
  /** When the anomaly occurred */
  timestamp: string;
  /** When the record was created */
  created_at: string;
  /** When the record was last updated */
  updated_at: string;
}

/**
 * API response for zone anomaly list endpoint.
 */
export interface ZoneAnomalyListResponse {
  items: ZoneAnomaly[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
    next_cursor?: string | null;
  };
}

/**
 * API response for acknowledging an anomaly.
 */
export interface ZoneAnomalyAcknowledgeResponse {
  id: string;
  acknowledged: boolean;
  acknowledged_at: string;
  acknowledged_by: string | null;
}

// ============================================================================
// WebSocket Event Types
// ============================================================================

/**
 * WebSocket payload for zone.anomaly events.
 * Matches the format emitted by ZoneAnomalyService._emit_websocket_event
 */
export interface ZoneAnomalyEventPayload {
  id: string;
  zone_id: string;
  camera_id: string;
  anomaly_type: AnomalyType;
  severity: AnomalySeverity;
  title: string;
  description: string | null;
  expected_value: number | null;
  actual_value: number | null;
  deviation: number | null;
  detection_id: number | null;
  thumbnail_url: string | null;
  timestamp: string | null;
}

// ============================================================================
// Query Options
// ============================================================================

/**
 * Options for fetching zone anomalies.
 */
export interface ZoneAnomalyQueryOptions {
  /** Zone ID to fetch anomalies for */
  zoneId?: string;
  /** Filter by severity level */
  severity?: AnomalySeverity | AnomalySeverity[];
  /** Only return unacknowledged anomalies */
  unacknowledgedOnly?: boolean;
  /** Start time filter (ISO 8601) */
  since?: string;
  /** End time filter (ISO 8601) */
  until?: string;
  /** Maximum number of results */
  limit?: number;
  /** Pagination offset */
  offset?: number;
  /** Whether to enable the query */
  enabled?: boolean;
}

/**
 * Options for the useZoneAnomalies hook.
 */
export interface UseZoneAnomaliesOptions extends ZoneAnomalyQueryOptions {
  /** Enable real-time WebSocket updates */
  enableRealtime?: boolean;
  /** Callback when new anomaly is received via WebSocket */
  onNewAnomaly?: (anomaly: ZoneAnomaly) => void;
  /** Custom stale time in milliseconds */
  staleTime?: number;
  /** Refetch interval in milliseconds */
  refetchInterval?: number | false;
}

// ============================================================================
// Hook Return Types
// ============================================================================

/**
 * Return type for the useZoneAnomalies hook.
 */
export interface UseZoneAnomaliesReturn {
  /** List of anomalies */
  anomalies: ZoneAnomaly[];
  /** Total count of anomalies matching filters */
  totalCount: number;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether any fetch is in progress */
  isFetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query has errored */
  isError: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Mutation to acknowledge an anomaly */
  acknowledgeAnomaly: (anomalyId: string) => Promise<ZoneAnomalyAcknowledgeResponse>;
  /** Whether acknowledge mutation is in progress */
  isAcknowledging: boolean;
  /** WebSocket connection status */
  isConnected: boolean;
}

// ============================================================================
// Component Props
// ============================================================================

/**
 * Props for the ZoneAnomalyAlert component.
 */
export interface ZoneAnomalyAlertProps {
  /** The anomaly to display */
  anomaly: ZoneAnomaly;
  /** Optional zone name for display */
  zoneName?: string;
  /** Callback when acknowledge button is clicked */
  onAcknowledge?: (anomalyId: string) => void;
  /** Callback when the card is clicked */
  onClick?: (anomaly: ZoneAnomaly) => void;
  /** Whether the acknowledge button is disabled */
  isAcknowledging?: boolean;
  /** Whether to show the full description or truncate */
  expanded?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Filter state for the ZoneAnomalyFeed component.
 */
export interface ZoneAnomalyFeedFilters {
  /** Filter by severity level */
  severity: AnomalySeverity | 'all';
  /** Filter by zone ID */
  zoneId: string;
  /** Filter by acknowledged status */
  acknowledged: 'all' | 'acknowledged' | 'unacknowledged';
}

/**
 * Props for the ZoneAnomalyFeed component.
 */
export interface ZoneAnomalyFeedProps {
  /** Optional zone ID to filter anomalies */
  zoneId?: string;
  /** Initial filter state */
  initialFilters?: Partial<ZoneAnomalyFeedFilters>;
  /** Maximum height for the feed container */
  maxHeight?: string | number;
  /** Whether to enable real-time updates */
  enableRealtime?: boolean;
  /** Callback when an anomaly is clicked */
  onAnomalyClick?: (anomaly: ZoneAnomaly) => void;
  /** Additional CSS classes */
  className?: string;
  /** Number of hours to look back for anomalies */
  hoursLookback?: number;
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * Anomaly severity configuration for UI rendering.
 */
export interface AnomalySeverityConfig {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: string;
}

/**
 * Map of severity levels to their UI configurations.
 */
export const ANOMALY_SEVERITY_CONFIG: Record<AnomalySeverity, AnomalySeverityConfig> = {
  [AnomalySeverity.INFO]: {
    label: 'Info',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
    icon: 'Info',
  },
  [AnomalySeverity.WARNING]: {
    label: 'Warning',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-500/10',
    borderColor: 'border-yellow-500/30',
    icon: 'AlertTriangle',
  },
  [AnomalySeverity.CRITICAL]: {
    label: 'Critical',
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
    icon: 'AlertOctagon',
  },
};

/**
 * Anomaly type configuration for UI rendering.
 */
export interface AnomalyTypeConfig {
  label: string;
  description: string;
  icon: string;
}

/**
 * Map of anomaly types to their UI configurations.
 */
export const ANOMALY_TYPE_CONFIG: Record<AnomalyType, AnomalyTypeConfig> = {
  [AnomalyType.UNUSUAL_TIME]: {
    label: 'Unusual Time',
    description: 'Activity detected at an unexpected hour',
    icon: 'Clock',
  },
  [AnomalyType.UNUSUAL_FREQUENCY]: {
    label: 'High Frequency',
    description: 'Unusual number of detections in a short period',
    icon: 'Activity',
  },
  [AnomalyType.UNUSUAL_DWELL]: {
    label: 'Extended Presence',
    description: 'Entity lingered longer than typical',
    icon: 'Timer',
  },
  [AnomalyType.UNUSUAL_ENTITY]: {
    label: 'Unusual Entity',
    description: 'Unexpected object type detected in zone',
    icon: 'HelpCircle',
  },
};

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for AnomalySeverity enum.
 */
export function isAnomalySeverity(value: unknown): value is AnomalySeverity {
  return (
    typeof value === 'string' && Object.values(AnomalySeverity).includes(value as AnomalySeverity)
  );
}

/**
 * Type guard for AnomalyType enum.
 */
export function isAnomalyType(value: unknown): value is AnomalyType {
  return typeof value === 'string' && Object.values(AnomalyType).includes(value as AnomalyType);
}

/**
 * Type guard for ZoneAnomaly objects.
 */
export function isZoneAnomaly(value: unknown): value is ZoneAnomaly {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.id === 'string' &&
    typeof obj.zone_id === 'string' &&
    typeof obj.camera_id === 'string' &&
    isAnomalyType(obj.anomaly_type) &&
    isAnomalySeverity(obj.severity) &&
    typeof obj.title === 'string' &&
    typeof obj.acknowledged === 'boolean' &&
    typeof obj.timestamp === 'string'
  );
}

/**
 * Type guard for ZoneAnomalyEventPayload from WebSocket.
 */
export function isZoneAnomalyEventPayload(value: unknown): value is ZoneAnomalyEventPayload {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.id === 'string' &&
    typeof obj.zone_id === 'string' &&
    typeof obj.camera_id === 'string' &&
    isAnomalyType(obj.anomaly_type) &&
    isAnomalySeverity(obj.severity) &&
    typeof obj.title === 'string'
  );
}
