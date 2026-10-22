/**
 * Alerts API Client
 *
 * API client for alert mutation operations (acknowledge, dismiss)
 * with optimistic locking support for conflict detection.
 *
 * @see NEM-3626
 */

import type { AlertResponse } from '../types/alerts';
import type { components } from '../types/generated/api';

/** Alert row from the Alert Service list (the alerts table, B4.1/F4.1). */
export type AlertServiceResponse = components['schemas']['AlertServiceResponse'];
/** List wrapper: `items` plus the pagination block. */
export type AlertServiceListResponse = components['schemas']['AlertServiceListResponse'];

// Re-export AlertResponse from types for use by consumers
export type { AlertResponse } from '../types/alerts';

/**
 * Custom error class for alerts API operations
 */
export class AlertsApiError extends Error {
  /** HTTP status code */
  readonly status: number;
  /**
   * Whether this is a conflict error (HTTP 409)
   * indicating concurrent modification
   */
  readonly isConflict: boolean;

  constructor(message: string, status: number, isConflict: boolean) {
    super(message);
    this.name = 'AlertsApiError';
    this.status = status;
    this.isConflict = isConflict;
  }
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get the base URL for API requests
 */
function getBaseUrl(): string {
  return (import.meta.env.VITE_API_URL as string | undefined) || '';
}

/**
 * Handle API response and throw AlertsApiError if not successful
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return response.json() as Promise<T>;
  }

  // Try to extract error detail from response body
  let detail: string | undefined;
  try {
    const errorBody: unknown = await response.json();
    if (
      typeof errorBody === 'object' &&
      errorBody !== null &&
      'detail' in errorBody &&
      typeof errorBody.detail === 'string'
    ) {
      detail = (errorBody as { detail: string }).detail;
    }
  } catch {
    // Ignore JSON parsing errors
  }

  // Determine if this is a conflict error
  const isConflict = response.status === 409;

  // Map status codes to user-friendly messages
  let message: string;
  if (response.status === 404) {
    message = detail || 'Alert not found';
  } else if (isConflict) {
    message = detail || 'Alert was modified by another request. Please refresh and retry.';
  } else if (response.status >= 500) {
    message = detail || 'Server error occurred';
  } else {
    message = detail || `Request failed: ${response.statusText}`;
  }

  throw new AlertsApiError(message, response.status, isConflict);
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Acknowledge an alert.
 *
 * Marks an alert as acknowledged and returns the updated alert with
 * a new version_id. If the alert was modified by another request
 * since it was loaded, the server will return HTTP 409 Conflict.
 *
 * @param alertId - Alert UUID to acknowledge
 * @returns Updated AlertResponse with new version_id
 * @throws AlertsApiError with isConflict=true on concurrent modification
 * @throws AlertsApiError with isConflict=false on other errors
 *
 * @example
 * ```typescript
 * try {
 *   const updated = await acknowledgeAlert('alert-123');
 *   console.log('Acknowledged, new version:', updated.version_id);
 * } catch (error) {
 *   if (isConflictError(error)) {
 *     // Handle conflict - show refresh dialog
 *   }
 * }
 * ```
 */
export async function acknowledgeAlert(alertId: string): Promise<AlertResponse> {
  const baseUrl = getBaseUrl();

  try {
    const response = await fetch(`${baseUrl}/api/alerts/${alertId}/acknowledge`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    return handleResponse<AlertResponse>(response);
  } catch (error) {
    if (error instanceof AlertsApiError) {
      throw error;
    }
    // Wrap network errors
    throw new AlertsApiError(error instanceof Error ? error.message : 'Network error', 0, false);
  }
}

/**
 * Dismiss an alert.
 *
 * Marks an alert as dismissed and returns the updated alert with
 * a new version_id. If the alert was modified by another request
 * since it was loaded, the server will return HTTP 409 Conflict.
 *
 * @param alertId - Alert UUID to dismiss
 * @returns Updated AlertResponse with new version_id
 * @throws AlertsApiError with isConflict=true on concurrent modification
 * @throws AlertsApiError with isConflict=false on other errors
 *
 * @example
 * ```typescript
 * try {
 *   const updated = await dismissAlert('alert-123');
 *   console.log('Dismissed, new version:', updated.version_id);
 * } catch (error) {
 *   if (isConflictError(error)) {
 *     // Handle conflict - show refresh dialog
 *   }
 * }
 * ```
 */
export async function dismissAlert(alertId: string): Promise<AlertResponse> {
  const baseUrl = getBaseUrl();

  try {
    const response = await fetch(`${baseUrl}/api/alerts/${alertId}/dismiss`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    return handleResponse<AlertResponse>(response);
  } catch (error) {
    if (error instanceof AlertsApiError) {
      throw error;
    }
    // Wrap network errors
    throw new AlertsApiError(error instanceof Error ? error.message : 'Network error', 0, false);
  }
}

// ============================================================================
// Alert Service list (the alerts table, not events)
// ============================================================================

/** Query parameters for listing alerts through the Alert Service. */
export interface ListAlertsParams {
  /** Filter by alert status ("open", "pending", "delivered", "acknowledged", "dismissed") */
  status?: string;
  /** Filter by severity ("low", "medium", "high", "critical") */
  severity?: string;
  /** Filter by the event that triggered the alert */
  event_id?: number;
  /** Filter by the rule that matched */
  rule_id?: string;
  /** Maximum number of results (server default 50, max 1000) */
  limit?: number;
  /** Number of results to skip */
  offset?: number;
}

/**
 * List alerts through the Alert Service (`GET /api/alert-service/alerts`).
 *
 * This reads the alerts table itself (F4.1) — the rows the alerting pipeline
 * writes — not the events feed the Alerts page used before F4.1. The response
 * is the generated `AlertServiceListResponse`: `items` plus a
 * `pagination` block (`total`, `limit`, `offset`, `has_more`).
 *
 * @param params - Optional status/severity/event/rule filters and pagination
 * @returns The generated list response (items + pagination)
 * @throws AlertsApiError on non-2xx responses
 */
export async function fetchAlerts(
  params: ListAlertsParams = {}
): Promise<AlertServiceListResponse> {
  const baseUrl = getBaseUrl();
  const search = new URLSearchParams();
  if (params.status !== undefined) search.set('status', params.status);
  if (params.severity !== undefined) search.set('severity', params.severity);
  if (params.event_id !== undefined) search.set('event_id', String(params.event_id));
  if (params.rule_id !== undefined) search.set('rule_id', params.rule_id);
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  const qs = search.toString();

  try {
    const response = await fetch(`${baseUrl}/api/alert-service/alerts${qs ? `?${qs}` : ''}`, {
      headers: {
        'Content-Type': 'application/json',
      },
    });

    return await handleResponse<AlertServiceListResponse>(response);
  } catch (error) {
    if (error instanceof AlertsApiError) {
      throw error;
    }
    // Wrap network errors
    throw new AlertsApiError(error instanceof Error ? error.message : 'Network error', 0, false);
  }
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if an error is a conflict error.
 *
 * Use this to detect when an alert operation failed due to
 * concurrent modification (optimistic locking conflict).
 *
 * @param error - The error to check
 * @returns True if this is an AlertsApiError with isConflict flag
 *
 * @example
 * ```typescript
 * try {
 *   await acknowledgeAlert(alertId);
 * } catch (error) {
 *   if (isConflictError(error)) {
 *     showConflictModal();
 *   } else {
 *     showErrorToast(error.message);
 *   }
 * }
 * ```
 */
export function isConflictError(error: unknown): error is AlertsApiError {
  return error instanceof AlertsApiError && error.isConflict;
}
