/**
 * Zone Alert Types (NEM-3196)
 *
 * TypeScript types for the unified zone alert feed that combines
 * anomaly alerts and trust violation alerts.
 *
 * @module types/zoneAlert
 */

import { AnomalySeverity } from './zoneAnomaly';

import type { ZoneAnomaly } from './zoneAnomaly';

// ============================================================================
// Enums
// ============================================================================

/**
 * Types of trust violations that can be detected.
 * Represents security-related alerts from the trust system.
 */
export enum TrustViolationType {
  UNKNOWN_ENTITY = 'unknown_entity',
  UNAUTHORIZED_TIME = 'unauthorized_time',
  RESTRICTED_ZONE = 'restricted_zone',
}

/**
 * Alert priority levels for unified feed sorting.
 * Maps to severity levels but provides consistent sorting.
 */
export enum AlertPriority {
  CRITICAL = 0,
  WARNING = 1,
  INFO = 2,
}

/**
 * Source types for zone alerts.
 */
export type AlertSource = 'anomaly' | 'trust_violation';

// ============================================================================
// Core Interfaces
// ============================================================================

/**
 * Severity type that accepts both enum values and string literals.
 * This provides flexibility when working with API responses.
 */
export type SeverityValue = AnomalySeverity | 'critical' | 'warning' | 'info';

/**
 * Trust violation alert data structure.
 * Represents a security violation detected by the trust system.
 */
export interface TrustViolation {
  /** Unique identifier for the violation */
  id: string;
  /** Zone ID where violation was detected */
  zone_id: string;
  /** Camera ID associated with the zone */
  camera_id: string;
  /** Type of trust violation */
  violation_type: TrustViolationType;
  /** Severity level of the violation */
  severity: SeverityValue;
  /** Human-readable title */
  title: string;
  /** Detailed description of the violation */
  description: string | null;
  /** Entity ID if applicable (person/vehicle) */
  entity_id: string | null;
  /** Entity type (person, vehicle, unknown) */
  entity_type: string | null;
  /** Related detection ID if applicable */
  detection_id: number | null;
  /** URL to thumbnail image for visual context */
  thumbnail_url: string | null;
  /** Whether the violation has been acknowledged */
  acknowledged: boolean;
  /** When the violation was acknowledged */
  acknowledged_at: string | null;
  /** Who acknowledged the violation */
  acknowledged_by: string | null;
  /** When the violation occurred */
  timestamp: string;
  /** When the record was created */
  created_at: string;
  /** When the record was last updated */
  updated_at: string;
}

/**
 * Unified zone alert that can represent either an anomaly or trust violation.
 * Used in the ZoneAlertFeed component for unified display.
 */
export interface UnifiedZoneAlert {
  /** Unique identifier */
  id: string;
  /** Source type (anomaly or trust_violation) */
  source: AlertSource;
  /** Zone ID where alert originated */
  zone_id: string;
  /** Camera ID associated with the zone */
  camera_id: string;
  /** Severity level */
  severity: SeverityValue;
  /** Computed priority for sorting (lower = higher priority) */
  priority: AlertPriority;
  /** Human-readable title */
  title: string;
  /** Detailed description */
  description: string | null;
  /** URL to thumbnail image */
  thumbnail_url: string | null;
  /** Whether acknowledged */
  acknowledged: boolean;
  /** When acknowledged */
  acknowledged_at: string | null;
  /** Alert timestamp */
  timestamp: string;
  /** Original alert data */
  originalAlert: ZoneAnomaly | TrustViolation;
}

// ============================================================================
// API Response Types
// ============================================================================

/**
 * API response for trust violation list endpoint.
 */
export interface TrustViolationListResponse {
  items: TrustViolation[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

/**
 * API response for acknowledging a trust violation.
 */
export interface TrustViolationAcknowledgeResponse {
  id: string;
  acknowledged: boolean;
  acknowledged_at: string;
  acknowledged_by: string | null;
}

// ============================================================================
// Hook Options and Return Types
// ============================================================================

/**
 * Options for the useZoneAlerts hook.
 */
export interface UseZoneAlertsOptions {
  /** Filter by zone IDs */
  zones?: string[];
  /** Filter by severity levels */
  severities?: SeverityValue[];
  /** Filter by acknowledged status (true = only acknowledged, false = only unacknowledged, undefined = all) */
  acknowledged?: boolean;
  /** Start time filter (ISO 8601) */
  since?: string;
  /** Maximum number of results */
  limit?: number;
  /** Whether to enable the query */
  enabled?: boolean;
  /** Enable real-time WebSocket updates */
  enableRealtime?: boolean;
  /** Custom refetch interval in milliseconds */
  refetchInterval?: number | false;
}

/**
 * Return type for the useZoneAlerts hook.
 */
export interface UseZoneAlertsReturn {
  /** Combined list of alerts sorted by priority and time */
  alerts: UnifiedZoneAlert[];
  /** Total count of unacknowledged alerts */
  unacknowledgedCount: number;
  /** Total count of all alerts */
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
  /** Acknowledge a single alert */
  acknowledgeAlert: (alertId: string, source: AlertSource) => Promise<void>;
  /** Acknowledge all alerts */
  acknowledgeAll: () => Promise<void>;
  /** Acknowledge all alerts of a specific severity */
  acknowledgeBySeverity: (severity: SeverityValue) => Promise<void>;
  /** Whether acknowledge mutation is in progress */
  isAcknowledging: boolean;
  /** WebSocket connection status */
  isConnected: boolean;
}

// ============================================================================
// Component Props
// ============================================================================

/**
 * Props for the ZoneAlertFeed component.
 */
export interface ZoneAlertFeedProps {
  /** Filter by zone IDs */
  zones?: string[];
  /** Maximum alerts to display */
  maxAlerts?: number;
  /** How to group alerts */
  groupBy?: 'zone' | 'time' | 'severity';
  /** Whether to show acknowledged alerts */
  showAcknowledged?: boolean;
  /** Enable sound notifications for critical alerts */
  enableSound?: boolean;
  /** Maximum height of the feed container */
  maxHeight?: string | number;
  /** Callback when an alert is clicked */
  onAlertClick?: (alert: UnifiedZoneAlert) => void;
  /** Additional CSS classes */
  className?: string;
  /** Number of hours to look back for alerts */
  hoursLookback?: number;
}

/**
 * Filter state for the ZoneAlertFeed component.
 */
export interface ZoneAlertFeedFilters {
  /** Filter by severity level */
  severity: SeverityValue | 'all';
  /** Filter by zone ID */
  zoneId: string;
  /** Filter by acknowledged status */
  acknowledged: 'all' | 'acknowledged' | 'unacknowledged';
  /** Filter by alert source */
  source: AlertSource | 'all';
}

/**
 * Grouped alerts structure for display.
 */
export interface AlertGroup {
  /** Group key (zone ID, time period, or severity) */
  key: string;
  /** Display label for the group */
  label: string;
  /** Alerts in this group */
  alerts: UnifiedZoneAlert[];
  /** Count of unacknowledged alerts in this group */
  unacknowledgedCount: number;
}

// ============================================================================
// Utility Types and Constants
// ============================================================================

/**
 * Trust violation type configuration for UI rendering.
 */
export interface TrustViolationTypeConfig {
  label: string;
  description: string;
  icon: string;
}

/**
 * Map of trust violation types to their UI configurations.
 */
export const TRUST_VIOLATION_TYPE_CONFIG: Record<TrustViolationType, TrustViolationTypeConfig> = {
  [TrustViolationType.UNKNOWN_ENTITY]: {
    label: 'Unknown Entity',
    description: 'Unrecognized person or vehicle detected in zone',
    icon: 'UserX',
  },
  [TrustViolationType.UNAUTHORIZED_TIME]: {
    label: 'Unauthorized Time',
    description: 'Known entity detected outside permitted hours',
    icon: 'Clock',
  },
  [TrustViolationType.RESTRICTED_ZONE]: {
    label: 'Restricted Zone',
    description: 'Entity detected in restricted area',
    icon: 'ShieldOff',
  },
};

/**
 * Map severity to priority for sorting.
 * Accepts both enum values and string literals for flexibility.
 */
export function severityToPriority(severity: AnomalySeverity | string): AlertPriority {
  const normalizedSeverity = String(severity).toLowerCase();
  if (normalizedSeverity === 'critical') {
    return AlertPriority.CRITICAL;
  }
  if (normalizedSeverity === 'warning') {
    return AlertPriority.WARNING;
  }
  return AlertPriority.INFO;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for TrustViolationType enum.
 */
export function isTrustViolationType(value: unknown): value is TrustViolationType {
  return (
    typeof value === 'string' &&
    Object.values(TrustViolationType).includes(value as TrustViolationType)
  );
}

/**
 * Type guard for TrustViolation objects.
 */
export function isTrustViolation(value: unknown): value is TrustViolation {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.id === 'string' &&
    typeof obj.zone_id === 'string' &&
    typeof obj.camera_id === 'string' &&
    isTrustViolationType(obj.violation_type) &&
    typeof obj.title === 'string' &&
    typeof obj.acknowledged === 'boolean' &&
    typeof obj.timestamp === 'string'
  );
}

/**
 * Type guard for UnifiedZoneAlert objects.
 */
export function isUnifiedZoneAlert(value: unknown): value is UnifiedZoneAlert {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.id === 'string' &&
    (obj.source === 'anomaly' || obj.source === 'trust_violation') &&
    typeof obj.zone_id === 'string' &&
    typeof obj.title === 'string' &&
    typeof obj.acknowledged === 'boolean' &&
    typeof obj.timestamp === 'string'
  );
}

/**
 * Check if an alert is from an anomaly source.
 */
export function isAnomalyAlert(alert: UnifiedZoneAlert): alert is UnifiedZoneAlert & { source: 'anomaly'; originalAlert: ZoneAnomaly } {
  return alert.source === 'anomaly';
}

/**
 * Check if an alert is from a trust violation source.
 */
export function isTrustViolationAlert(alert: UnifiedZoneAlert): alert is UnifiedZoneAlert & { source: 'trust_violation'; originalAlert: TrustViolation } {
  return alert.source === 'trust_violation';
}
