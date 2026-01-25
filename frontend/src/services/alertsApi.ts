/**
 * Alerts API Client
 *
 * API client for alert mutation operations (acknowledge, dismiss)
 * with optimistic locking support for conflict detection.
 *
 * @see NEM-3626
 */

import type { AlertResponse } from '../types/alerts';

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
      typeof (errorBody as { detail: unknown }).detail === 'string'
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
    throw new AlertsApiError(
      error instanceof Error ? error.message : 'Network error',
      0,
      false
    );
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
    throw new AlertsApiError(
      error instanceof Error ? error.message : 'Network error',
      0,
      false
    );
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
