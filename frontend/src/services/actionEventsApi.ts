/**
 * Action Events API client functions
 *
 * Provides functions to interact with the X-CLIP action recognition
 * results API. Action events represent detected actions from analyzing
 * sequences of video frames for security-relevant human activities.
 *
 * @module services/actionEventsApi
 * @see backend/api/routes/action_events.py
 * Linear issue: NEM-5024 (Phase 7)
 */

// ============================================================================
// Types
// ============================================================================

/**
 * Pagination metadata for list responses.
 * Standard pagination envelope matching backend schema.
 */
export interface PaginationMeta {
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

/**
 * Represents a single action event detected by X-CLIP.
 * Maps to backend ActionEventResponse schema.
 */
export interface ActionEvent {
  /** Unique identifier for the action event */
  id: number;
  /** Camera ID where the action was detected */
  camera_id: string;
  /** Optional track ID for the detected person */
  track_id: number | null;
  /** Detected action label (e.g., 'walking normally', 'climbing') */
  action: string;
  /** Action classification confidence (0.0 to 1.0) */
  confidence: number;
  /** Whether the action is flagged as security-relevant */
  is_suspicious: boolean;
  /** When the action was detected */
  timestamp: string;
  /** Number of frames analyzed for this action */
  frame_count: number;
  /** Dictionary mapping all action classes to their confidence scores */
  all_scores: Record<string, number> | null;
  /** Record creation timestamp */
  created_at: string;
}

/**
 * Response for action event list endpoint.
 * Includes pagination metadata.
 */
export interface ActionEventListResponse {
  items: ActionEvent[];
  pagination: PaginationMeta;
}

/**
 * Response for suspicious actions endpoint.
 * Includes additional count information.
 */
export interface SuspiciousActionsResponse extends ActionEventListResponse {
  suspicious_count: number;
  total_count: number;
}

/**
 * Query parameters for action events list endpoint.
 */
export interface ActionEventsQueryParams {
  /** Filter by camera ID */
  camera_id?: string;
  /** Filter by track ID */
  track_id?: number;
  /** Filter by action label (exact match) */
  action?: string;
  /** Filter by suspicious flag */
  is_suspicious?: boolean;
  /** Filter by minimum confidence score (0.0 to 1.0) */
  min_confidence?: number;
  /** Filter by timestamp >= start_time (ISO format) */
  start_time?: string;
  /** Filter by timestamp <= end_time (ISO format) */
  end_time?: string;
  /** Maximum number of results to return */
  limit?: number;
  /** Number of results to skip for pagination */
  offset?: number;
}

// ============================================================================
// Known Action Types
// ============================================================================

/**
 * List of suspicious action types for display purposes.
 * From ai/enrichment/models/action_recognizer.py
 */
export const SUSPICIOUS_ACTIONS = [
  'fighting',
  'climbing',
  'breaking window',
  'picking lock',
  'hiding',
  'loitering',
  'looking around suspiciously',
] as const;

/**
 * List of normal/benign action types.
 */
export const NORMAL_ACTIONS = [
  'walking normally',
  'running',
  'standing',
  'sitting',
  'talking',
  'carrying package',
  'waving',
] as const;

/**
 * All known action types.
 */
export const ALL_ACTION_TYPES = [...NORMAL_ACTIONS, ...SUSPICIOUS_ACTIONS] as const;

export type SuspiciousAction = (typeof SUSPICIOUS_ACTIONS)[number];
export type NormalAction = (typeof NORMAL_ACTIONS)[number];
export type ActionType = (typeof ALL_ACTION_TYPES)[number];

// ============================================================================
// API Functions
// ============================================================================

/** Type for query parameter values */
type QueryParamValue = string | number | boolean | undefined | null;

/** Type for query parameters object */
type QueryParams = Record<string, QueryParamValue>;

/**
 * Build query string from parameters object.
 * Filters out undefined values.
 */
function buildQueryString(params: QueryParams): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value));
    }
  }

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : '';
}

/**
 * Fetch action events with optional filtering and pagination.
 *
 * @param params - Query parameters for filtering
 * @returns Action events list response with pagination
 * @throws Error if the request fails
 *
 * @example
 * ```typescript
 * // Fetch all action events
 * const response = await fetchActionEvents();
 *
 * // Fetch suspicious actions for a camera
 * const response = await fetchActionEvents({
 *   camera_id: 'front_door',
 *   is_suspicious: true,
 *   min_confidence: 0.8,
 * });
 * ```
 */
export async function fetchActionEvents(
  params: ActionEventsQueryParams = {}
): Promise<ActionEventListResponse> {
  const queryString = buildQueryString(params as QueryParams);
  const response = await fetch(`/api/action-events${queryString}`);

  if (!response.ok) {
    throw new Error(
      `Failed to fetch action events: ${response.status} ${response.statusText}`
    );
  }

  return (await response.json()) as ActionEventListResponse;
}

/**
 * Fetch suspicious action events only.
 * Includes counts of suspicious vs total events.
 *
 * @param params - Query parameters for filtering
 * @returns Suspicious actions response with counts
 * @throws Error if the request fails
 *
 * @example
 * ```typescript
 * const response = await fetchSuspiciousActions({
 *   camera_id: 'back_yard',
 *   min_confidence: 0.9,
 * });
 * console.log(`${response.suspicious_count} of ${response.total_count} actions are suspicious`);
 * ```
 */
export async function fetchSuspiciousActions(
  params: Omit<ActionEventsQueryParams, 'is_suspicious' | 'track_id' | 'action'> = {}
): Promise<SuspiciousActionsResponse> {
  const queryString = buildQueryString(params as QueryParams);
  const response = await fetch(`/api/action-events/suspicious${queryString}`);

  if (!response.ok) {
    throw new Error(
      `Failed to fetch suspicious actions: ${response.status} ${response.statusText}`
    );
  }

  return (await response.json()) as SuspiciousActionsResponse;
}

/**
 * Fetch a single action event by ID.
 *
 * @param eventId - Action event ID
 * @returns Action event details
 * @throws Error if the request fails or event not found
 *
 * @example
 * ```typescript
 * const event = await fetchActionEvent(123);
 * console.log(`Action: ${event.action} (${event.confidence * 100}% confidence)`);
 * ```
 */
export async function fetchActionEvent(eventId: number): Promise<ActionEvent> {
  const response = await fetch(`/api/action-events/${eventId}`);

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Action event ${eventId} not found`);
    }
    throw new Error(
      `Failed to fetch action event: ${response.status} ${response.statusText}`
    );
  }

  return (await response.json()) as ActionEvent;
}

/**
 * Fetch action events for a specific camera.
 * Convenience function for camera-specific queries.
 *
 * @param cameraId - Camera ID to filter by
 * @param params - Additional query parameters
 * @returns Action events list response with pagination
 * @throws Error if the request fails
 *
 * @example
 * ```typescript
 * const response = await fetchActionEventsForCamera('front_door', {
 *   start_time: '2026-01-01T00:00:00Z',
 *   limit: 20,
 * });
 * ```
 */
export async function fetchActionEventsForCamera(
  cameraId: string,
  params: Pick<ActionEventsQueryParams, 'start_time' | 'end_time' | 'limit' | 'offset'> = {}
): Promise<ActionEventListResponse> {
  const queryString = buildQueryString(params as QueryParams);
  const response = await fetch(`/api/action-events/camera/${cameraId}${queryString}`);

  if (!response.ok) {
    throw new Error(
      `Failed to fetch action events for camera: ${response.status} ${response.statusText}`
    );
  }

  return (await response.json()) as ActionEventListResponse;
}

/**
 * Fetch action events for a specific event (by track or time correlation).
 * Used to display action events in the event detail modal.
 *
 * @param eventId - Security event ID
 * @param cameraId - Camera ID for the event
 * @param startTime - Event start time (ISO format)
 * @param endTime - Event end time (ISO format), optional for ongoing events
 * @param limit - Maximum number of results
 * @returns Action events list response
 * @throws Error if the request fails
 */
export async function fetchActionEventsForEvent(
  _eventId: number,
  cameraId: string,
  startTime: string,
  endTime?: string | null,
  limit = 50
): Promise<ActionEventListResponse> {
  // For ongoing events without end time, use a reasonable window (5 minutes after start)
  const effectiveEndTime =
    endTime || new Date(new Date(startTime).getTime() + 5 * 60 * 1000).toISOString();

  return fetchActionEvents({
    camera_id: cameraId,
    start_time: startTime,
    end_time: effectiveEndTime,
    limit,
  });
}
