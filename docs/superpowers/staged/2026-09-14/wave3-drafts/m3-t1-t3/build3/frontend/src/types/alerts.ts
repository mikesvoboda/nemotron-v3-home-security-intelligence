/**
 * Alert Types
 *
 * Types for the alert system including optimistic locking support.
 * These types extend the generated API types with frontend-specific
 * requirements for conflict handling.
 *
 * @see NEM-3626
 */

import type { components } from './generated/api';

/**
 * Generated alert response type from OpenAPI schema
 */
export type GeneratedAlertResponse = components['schemas']['AlertResponse'];

/**
 * Alert severity type from generated API
 */
export type AlertSeverity = components['schemas']['AlertSeverity'];

/**
 * Alert status type from generated API
 */
export type AlertStatus = components['schemas']['AlertStatus'];

/**
 * Alert response type with version_id for optimistic locking.
 *
 * Extends the generated AlertResponse to include version_id which is
 * used for optimistic locking during concurrent acknowledge/dismiss operations.
 */
export interface AlertResponse {
  /** Alert UUID */
  id: string;
  /** Event ID that triggered this alert */
  event_id: number;
  /** Alert rule UUID that matched */
  rule_id?: string | null;
  /** Alert severity level */
  severity: AlertSeverity;
  /** Alert status */
  status: AlertStatus;
  /** Creation timestamp */
  created_at: string;
  /** Last update timestamp */
  updated_at: string;
  /** Delivery timestamp */
  delivered_at?: string | null;
  /** Notification channels */
  channels?: string[];
  /** Deduplication key */
  dedup_key: string;
  /** Additional context */
  metadata?: Record<string, unknown> | null;
  /**
   * Version ID for optimistic locking.
   * Incremented on each update to detect concurrent modifications.
   *
   * @see NEM-3626
   */
  version_id: number;
}

/**
 * Parameters for alert acknowledge/dismiss requests with optimistic locking
 */
export interface AlertMutationParams {
  /** Alert UUID */
  alertId: string;
  /**
   * Version ID for optimistic locking.
   * If provided, the request will fail with 409 if the server-side
   * version_id doesn't match (indicating concurrent modification).
   */
  versionId?: number;
}

/**
 * Error response for optimistic locking conflicts
 */
export interface OptimisticLockError {
  /** HTTP status code (409 for conflicts) */
  status: 409;
  /** Error detail message from server */
  detail: string;
  /**
   * Indicates this is a stale data error (concurrent modification)
   */
  isStaleDataError: true;
}

/**
 * Type guard to check if an error is an optimistic locking conflict
 */
export function isOptimisticLockError(error: unknown): error is OptimisticLockError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    error.status === 409 &&
    'isStaleDataError' in error &&
    error.isStaleDataError === true
  );
}

/**
 * Conflict resolution options for UI
 */
export type ConflictResolution = 'retry' | 'cancel' | 'force';

/**
 * State for tracking conflict resolution in components
 */
export interface ConflictState {
  /** Whether there is an active conflict */
  hasConflict: boolean;
  /** The alert ID that has a conflict */
  alertId: string | null;
  /** The action that was being attempted */
  action: 'acknowledge' | 'dismiss' | null;
  /** Error message from the conflict */
  errorMessage: string | null;
}

/**
 * Alert card props with version_id support
 * Used by AlertCard component for optimistic locking
 */
export interface AlertWithVersion {
  id: string;
  eventId: number;
  severity: AlertSeverity;
  status: AlertStatus;
  timestamp: string;
  camera_name: string;
  risk_score: number;
  summary: string;
  dedup_key: string;
  /** Version ID for optimistic locking */
  version_id: number;
}
