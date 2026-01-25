/**
 * AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
 *
 * This file is generated from backend Pydantic schemas using:
 *   ./scripts/generate-ws-types.py
 *
 * To regenerate, run:
 *   ./scripts/generate-ws-types.py
 *
 * Source schemas:
 *   backend/api/schemas/websocket.py
 *
 * Generated at: 2026-01-20T16:37:29Z
 *
 * Note: WebSocket messages are not covered by OpenAPI, so we generate these
 * types separately to ensure frontend/backend type synchronization.
 */

// ============================================================================
// Enums and Constants
// ============================================================================

/**
 * Valid risk levels for security events.
 *
 * This enum mirrors backend.models.enums.Severity but is specifically
 * for WebSocket message validation. The values are:
 * - low: Routine activity, no concern
 * - medium: Notable activity, worth reviewing
 * - high: Concerning activity, review soon
 * - critical: Immediate attention required
 */
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

/**
 * Valid WebSocket message types.
 */
export type WebSocketMessageType = 'ping' | 'pong' | 'subscribe' | 'unsubscribe' | 'resync';

/**
 * Valid service status values for WebSocket health monitoring messages.
 *
 * Includes both health states and worker lifecycle states for comprehensive
 * status reporting across services and workers.
 */
export type WebSocketServiceStatus =
  | 'healthy'
  | 'unhealthy'
  | 'running'
  | 'stopped'
  | 'crashed'
  | 'disabled'
  | 'restarting'
  | 'restart_failed'
  | 'failed';

/**
 * WebSocket event types for alert state changes.
 *
 * Event types:
 * - ALERT_CREATED: New alert triggered from rule evaluation
 * - ALERT_UPDATED: Alert modified (e.g., metadata, channels updated)
 * - ALERT_DELETED: Alert permanently deleted from the system
 * - ALERT_ACKNOWLEDGED: Alert marked as seen by user
 * - ALERT_RESOLVED: Alert resolved (long-running issues cleared)
 * - ALERT_DISMISSED: Alert dismissed by user
 */
export type WebSocketAlertEventType =
  | 'alert_created'
  | 'alert_updated'
  | 'alert_deleted'
  | 'alert_acknowledged'
  | 'alert_resolved'
  | 'alert_dismissed';

/**
 * Alert severity levels for WebSocket messages.
 *
 * Mirrors backend.models.alert.AlertSeverityEnum for WebSocket message validation.
 */
export type WebSocketAlertSeverity = 'low' | 'medium' | 'high' | 'critical';

/**
 * Alert status values for WebSocket messages.
 *
 * Mirrors backend.models.alert.AlertStatusEnum for WebSocket message validation.
 */
export type WebSocketAlertStatus = 'pending' | 'delivered' | 'acknowledged' | 'dismissed';

/**
 * Standard error codes for WebSocket validation errors.
 */
export const WebSocketErrorCode = {
  INVALID_JSON: 'invalid_json',
  INVALID_MESSAGE_FORMAT: 'invalid_message_format',
  UNKNOWN_MESSAGE_TYPE: 'unknown_message_type',
  VALIDATION_ERROR: 'validation_error',
} as const;

export type WebSocketErrorCodeType = (typeof WebSocketErrorCode)[keyof typeof WebSocketErrorCode];

// ============================================================================
// Data Payload Interfaces
// ============================================================================

/**
 * Data payload for event messages broadcast to /ws/events clients.
 *
 * This schema defines the contract for event data sent from the backend
 * to WebSocket clients. Any changes to this schema must be reflected in:
 * - backend/api/routes/websocket.py docstring
 * - backend/services/nemotron_analyzer.py _broadcast_event()
 * - frontend WebSocket event handlers
 *
 * Fields:
 *     id: Unique event identifier
 *     event_id: Legacy alias for id (for backward compatibility)
 *     batch_id: Detection batch identifier
 *     camera_id: Normalized camera ID (e.g., "front_door")
 *     risk_score: Risk assessment score (0-100)
 *     risk_level: Risk classification (validated against RiskLevel enum)
 *     summary: Human-readable description of the event
 *     reasoning: LLM reasoning for the risk assessment
 *     started_at: ISO 8601 timestamp when the event started (nullable)
 */
export interface WebSocketEventData {
  /** Unique event identifier */
  id: number;
  /** Legacy alias for id (backward compatibility) */
  event_id: number;
  /** Detection batch identifier */
  batch_id: string;
  /** Normalized camera ID (e.g., 'front_door') */
  camera_id: string;
  /** Risk assessment score (0-100) */
  risk_score: number;
  /** Risk classification ("low", "medium", "high", "critical") */
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  /** Human-readable description of the event */
  summary: string;
  /** LLM reasoning for the risk assessment */
  reasoning: string;
  /** ISO 8601 timestamp when the event started */
  started_at?: string | null;
}

/**
 * Data payload for service status messages.
 *
 * Broadcast by the health monitor when a service's status changes.
 *
 * Note: Accepts both 'service' and 'name' fields for compatibility with
 * ServiceInfo schema used by container orchestrator.
 */
export interface WebSocketServiceStatusData {
  /** Name of the service (redis, rtdetr, nemotron) */
  service: string;
  /** Current service status */
  status:
    | 'healthy'
    | 'unhealthy'
    | 'running'
    | 'stopped'
    | 'crashed'
    | 'disabled'
    | 'restarting'
    | 'restart_failed'
    | 'failed';
  /** Optional descriptive message */
  message?: string | null;
}

/**
 * Data payload for scene change messages broadcast to /ws/events clients.
 *
 * This schema defines the contract for scene change data sent from the backend
 * to WebSocket clients when a camera view change is detected.
 *
 * Fields:
 *     id: Unique scene change identifier
 *     camera_id: Normalized camera ID (e.g., "front_door")
 *     detected_at: ISO 8601 timestamp when the change was detected
 *     change_type: Type of change (view_blocked, angle_changed, view_tampered, unknown)
 *     similarity_score: SSIM score (0-1, lower means more different from baseline)
 */
export interface WebSocketSceneChangeData {
  /** Unique scene change identifier */
  id: number;
  /** Normalized camera ID (e.g., 'front_door') */
  camera_id: string;
  /** ISO 8601 timestamp when the change was detected */
  detected_at: string;
  /** Type of change (view_blocked, angle_changed, view_tampered, unknown) */
  change_type: string;
  /** SSIM score (0-1, lower means more different) */
  similarity_score: number;
}

/**
 * Data payload for alert messages broadcast to /ws/events clients.
 *
 * This schema defines the contract for alert data sent from the backend
 * to WebSocket clients when alerts are created, acknowledged, or dismissed.
 *
 * Fields:
 *     id: Unique alert identifier (UUID)
 *     event_id: Event ID that triggered this alert
 *     rule_id: Alert rule UUID that matched (nullable)
 *     severity: Alert severity level (low, medium, high, critical)
 *     status: Current alert status (pending, delivered, acknowledged, dismissed)
 *     dedup_key: Deduplication key for alert grouping
 *     created_at: ISO 8601 timestamp when the alert was created
 *     updated_at: ISO 8601 timestamp when the alert was last updated
 */
export interface WebSocketAlertData {
  /** Unique alert identifier (UUID) */
  id: string;
  /** Event ID that triggered this alert */
  event_id: number;
  /** Alert rule UUID that matched */
  rule_id?: string | null;
  /** Alert severity level ("low", "medium", "high", "critical") */
  severity: 'low' | 'medium' | 'high' | 'critical';
  /** Current alert status ("pending", "delivered", "acknowledged", "dismissed") */
  status: 'pending' | 'delivered' | 'acknowledged' | 'dismissed';
  /** Deduplication key for alert grouping */
  dedup_key: string;
  /** ISO 8601 timestamp when the alert was created */
  created_at: string;
  /** ISO 8601 timestamp when the alert was last updated */
  updated_at: string;
}

/**
 * Data payload for alert deleted messages broadcast to /ws/events clients.
 *
 * This schema is used when an alert is permanently deleted. It contains only
 * the alert ID and optional reason, as the full alert data is no longer available.
 *
 * Fields:
 *     id: UUID of the deleted alert
 *     reason: Optional reason for deletion
 */
export interface WebSocketAlertDeletedData {
  /** Deleted alert UUID */
  id: string;
  /** Reason for deletion */
  reason?: string | null;
}

// ============================================================================
// Message Envelope Interfaces
// ============================================================================

/**
 * Ping message for keep-alive heartbeat.
 *
 * Clients can send ping messages to verify the connection is alive.
 * Server responds with {"type": "pong"}.
 */
export interface WebSocketPingMessage {
  /** Message type, must be 'ping' */
  type: 'ping';
}

/**
 * Pong response sent in reply to ping messages.
 */
export interface WebSocketPongResponse {
  /** Message type, always 'pong' */
  type: 'pong';
}

/**
 * Subscribe message to register interest in specific channels.
 *
 * Future enhancement: allow clients to filter which events they receive.
 */
export interface WebSocketSubscribeMessage {
  /** Message type, must be 'subscribe' */
  type: 'subscribe';
  /** List of channel names to subscribe to */
  channels: string[];
}

/**
 * Unsubscribe message to stop receiving events from specific channels.
 */
export interface WebSocketUnsubscribeMessage {
  /** Message type, must be 'unsubscribe' */
  type: 'unsubscribe';
  /** List of channel names to unsubscribe from */
  channels: string[];
}

/**
 * Error response sent to client for invalid messages.
 */
export interface WebSocketErrorResponse {
  /** Message type, always 'error' */
  type: 'error';
  /** Error code identifying the type of error */
  error: string;
  /** Human-readable error description */
  message: string;
  /** Additional error context */
  details?: Record<string, unknown> | null;
}

/**
 * Complete event message envelope sent to /ws/events clients.
 *
 * This is the canonical format for event messages broadcast via WebSocket.
 * The message wraps event data in a standard envelope with a type field.
 *
 * Format:
 *     {
 *         "type": "event",
 *         "data": {
 *             "id": 1,
 *             "event_id": 1,
 *             "batch_id": "batch_abc123",
 *             "camera_id": "cam-uuid",
 *             "risk_score": 75,
 *             "risk_level": "high",
 *             "summary": "Person detected at front door",
 *             "reasoning": "Person approaching entrance during evening hours, behavior appears normal",
 *             "started_at": "2025-12-23T12:00:00"
 *         }
 *     }
 */
export interface WebSocketEventMessage {
  /** Message type, always 'event' for event messages */
  type: 'event';
  /** Event data payload */
  data: WebSocketEventData;
}

/**
 * Complete service status message envelope.
 *
 * This is the canonical format for service status messages broadcast via WebSocket.
 * Consistent with other message types, data is wrapped in a standard envelope.
 *
 * Format:
 *     {
 *         "type": "service_status",
 *         "data": {
 *             "service": "redis",
 *             "status": "healthy",
 *             "message": "Service responding normally"
 *         },
 *         "timestamp": "2025-12-23T12:00:00.000Z"
 *     }
 */
export interface WebSocketServiceStatusMessage {
  /** Message type, always 'service_status' for service status messages */
  type: 'service_status';
  /** Service status data payload */
  data: WebSocketServiceStatusData;
  /** ISO 8601 timestamp of the status change */
  timestamp: string;
}

/**
 * Complete scene change message envelope sent to /ws/events clients.
 *
 * This is the canonical format for scene change messages broadcast via WebSocket.
 * The message wraps scene change data in a standard envelope with a type field.
 *
 * Format:
 *     {
 *         "type": "scene_change",
 *         "data": {
 *             "id": 1,
 *             "camera_id": "front_door",
 *             "detected_at": "2026-01-03T10:30:00Z",
 *             "change_type": "view_blocked",
 *             "similarity_score": 0.23
 *         }
 *     }
 */
export interface WebSocketSceneChangeMessage {
  /** Message type, always 'scene_change' for scene change messages */
  type: 'scene_change';
  /** Scene change data payload */
  data: WebSocketSceneChangeData;
}

/**
 * Complete alert created message envelope sent to /ws/events clients.
 *
 * This is the canonical format for alert creation messages broadcast via WebSocket.
 * The message wraps alert data in a standard envelope with a type field.
 *
 * Format:
 *     {
 *         "type": "alert_created",
 *         "data": {
 *             "id": "550e8400-e29b-41d4-a716-446655440000",
 *             "event_id": 123,
 *             "rule_id": "550e8400-e29b-41d4-a716-446655440001",
 *             "severity": "high",
 *             "status": "pending",
 *             "dedup_key": "front_door:person:rule1",
 *             "created_at": "2026-01-09T12:00:00Z",
 *             "updated_at": "2026-01-09T12:00:00Z"
 *         }
 *     }
 */
export interface WebSocketAlertCreatedMessage {
  /** Message type, always 'alert_created' for alert creation messages */
  type: 'alert_created';
  /** Alert data payload */
  data: WebSocketAlertData;
}

/**
 * Complete alert updated message envelope sent to /ws/events clients.
 *
 * This is the canonical format for alert update messages broadcast via WebSocket.
 * Sent when an alert is modified (e.g., metadata, channels, or other properties updated).
 * The message wraps alert data in a standard envelope with a type field.
 *
 * Format:
 *     {
 *         "type": "alert_updated",
 *         "data": {
 *             "id": "550e8400-e29b-41d4-a716-446655440000",
 *             "event_id": 123,
 *             "rule_id": "550e8400-e29b-41d4-a716-446655440001",
 *             "severity": "high",
 *             "status": "pending",
 *             "dedup_key": "front_door:person:rule1",
 *             "created_at": "2026-01-09T12:00:00Z",
 *             "updated_at": "2026-01-09T12:00:30Z"
 *         }
 *     }
 */
export interface WebSocketAlertUpdatedMessage {
  /** Message type, always 'alert_updated' for alert update messages */
  type: 'alert_updated';
  /** Alert data payload */
  data: WebSocketAlertData;
}

/**
 * Complete alert deleted message envelope sent to /ws/events clients.
 *
 * This is the canonical format for alert deletion messages broadcast via WebSocket.
 * Sent when an alert is permanently deleted from the system.
 * The message wraps deletion data in a standard envelope with a type field.
 *
 * Format:
 *     {
 *         "type": "alert_deleted",
 *         "data": {
 *             "id": "550e8400-e29b-41d4-a716-446655440000",
 *             "reason": "Duplicate alert"
 *         }
 *     }
 */
export interface WebSocketAlertDeletedMessage {
  /** Message type, always 'alert_deleted' for alert deletion messages */
  type: 'alert_deleted';
  /** Alert deletion data payload */
  data: WebSocketAlertDeletedData;
}

/**
 * Complete alert acknowledged message envelope sent to /ws/events clients.
 *
 * This is the canonical format for alert acknowledgment messages broadcast via WebSocket.
 * The message wraps alert data in a standard envelope with a type field.
 *
 * Format:
 *     {
 *         "type": "alert_acknowledged",
 *         "data": {
 *             "id": "550e8400-e29b-41d4-a716-446655440000",
 *             "event_id": 123,
 *             "rule_id": "550e8400-e29b-41d4-a716-446655440001",
 *             "severity": "high",
 *             "status": "acknowledged",
 *             "dedup_key": "front_door:person:rule1",
 *             "created_at": "2026-01-09T12:00:00Z",
 *             "updated_at": "2026-01-09T12:01:00Z"
 *         }
 *     }
 */
export interface WebSocketAlertAcknowledgedMessage {
  /** Message type, always 'alert_acknowledged' for alert acknowledgment messages */
  type: 'alert_acknowledged';
  /** Alert data payload */
  data: WebSocketAlertData;
}

/**
 * Complete alert dismissed message envelope sent to /ws/events clients.
 *
 * This is the canonical format for alert dismissal messages broadcast via WebSocket.
 * The message wraps alert data in a standard envelope with a type field.
 *
 * Format:
 *     {
 *         "type": "alert_dismissed",
 *         "data": {
 *             "id": "550e8400-e29b-41d4-a716-446655440000",
 *             "event_id": 123,
 *             "rule_id": "550e8400-e29b-41d4-a716-446655440001",
 *             "severity": "high",
 *             "status": "dismissed",
 *             "dedup_key": "front_door:person:rule1",
 *             "created_at": "2026-01-09T12:00:00Z",
 *             "updated_at": "2026-01-09T12:02:00Z"
 *         }
 *     }
 */
export interface WebSocketAlertDismissedMessage {
  /** Message type, always 'alert_dismissed' for alert dismissal messages */
  type: 'alert_dismissed';
  /** Alert data payload */
  data: WebSocketAlertData;
}

/**
 * Complete alert resolved message envelope sent to /ws/events clients.
 *
 * This is the canonical format for alert resolution messages broadcast via WebSocket.
 * Sent when an alert is resolved/dismissed. Semantically similar to dismissed but
 * provides a clearer event name for resolution workflows.
 * The message wraps alert data in a standard envelope with a type field.
 *
 * Format:
 *     {
 *         "type": "alert_resolved",
 *         "data": {
 *             "id": "550e8400-e29b-41d4-a716-446655440000",
 *             "event_id": 123,
 *             "rule_id": "550e8400-e29b-41d4-a716-446655440001",
 *             "severity": "high",
 *             "status": "dismissed",
 *             "dedup_key": "front_door:person:rule1",
 *             "created_at": "2026-01-09T12:00:00Z",
 *             "updated_at": "2026-01-09T12:02:00Z"
 *         }
 *     }
 */
export interface WebSocketAlertResolvedMessage {
  /** Message type, always 'alert_resolved' for alert resolution messages */
  type: 'alert_resolved';
  /** Alert data payload */
  data: WebSocketAlertData;
}

/**
 * Generic WebSocket message for initial type detection.
 *
 * This schema is used to validate the basic structure of incoming messages
 * and determine the message type before dispatching to type-specific handlers.
 */
export interface WebSocketMessage {
  /** Message type identifier */
  type: string;
  /** Optional message payload data */
  data?: Record<string, unknown> | null;
}

// ============================================================================
// Discriminated Union Types
// ============================================================================

/**
 * All alert-related WebSocket message types.
 */
export type WebSocketAlertMessage =
  | WebSocketAlertCreatedMessage
  | WebSocketAlertUpdatedMessage
  | WebSocketAlertDeletedMessage
  | WebSocketAlertAcknowledgedMessage
  | WebSocketAlertDismissedMessage
  | WebSocketAlertResolvedMessage;

/**
 * All server-to-client WebSocket message types.
 * The `type` field serves as the discriminant for type narrowing.
 */
export type WebSocketServerMessage =
  | WebSocketEventMessage
  | WebSocketServiceStatusMessage
  | WebSocketSceneChangeMessage
  | WebSocketAlertMessage
  | WebSocketPongResponse
  | WebSocketErrorResponse
  | { type: 'ping' }; // Server heartbeat

/**
 * All client-to-server WebSocket message types.
 */
export type WebSocketClientMessage =
  | WebSocketPingMessage
  | WebSocketSubscribeMessage
  | WebSocketUnsubscribeMessage
  | { type: 'pong' }; // Client heartbeat response

/**
 * All WebSocket message types (both directions).
 */
export type AnyWebSocketMessage = WebSocketServerMessage | WebSocketClientMessage;

/**
 * Extract message type by discriminant.
 */
export type MessageByType<T extends AnyWebSocketMessage['type']> = Extract<
  AnyWebSocketMessage,
  { type: T }
>;

/**
 * Type-safe message handler function.
 */
export type MessageHandler<T extends AnyWebSocketMessage> = (message: T) => void;

/**
 * Map of message types to their handlers.
 */
export type MessageHandlerMap = {
  [K in AnyWebSocketMessage['type']]?: MessageHandler<MessageByType<K>>;
};

/**
 * Create a type-safe message dispatcher.
 *
 * @example
 * ```ts
 * const dispatch = createMessageDispatcher({
 *   event: (msg) => console.log(msg.data.risk_score),
 *   service_status: (msg) => console.log(msg.data.status),
 *   alert_created: (msg) => console.log('New alert:', msg.data.id),
 *   ping: () => ws.send(JSON.stringify({ type: 'pong' })),
 * });
 *
 * ws.onmessage = (event) => {
 *   const message = JSON.parse(event.data);
 *   dispatch(message);
 * };
 * ```
 */
export function createMessageDispatcher(handlers: MessageHandlerMap) {
  return (message: AnyWebSocketMessage): void => {
    const handler = handlers[message.type];
    if (handler) {
      (handler as (msg: AnyWebSocketMessage) => void)(message);
    }
  };
}

/**
 * Utility function for exhaustive checking in switch statements.
 */
export function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${JSON.stringify(value)}`);
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard to check if a value is an object with a type property.
 */
function hasTypeProperty(value: unknown): value is { type: unknown } {
  return typeof value === 'object' && value !== null && 'type' in value;
}

/**
 * Type guard for WebSocketEventMessage.
 */
export function isEventMessage(value: unknown): value is WebSocketEventMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'event') return false;

  const msg = value as { type: 'event'; data?: unknown };
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return (
    ('id' in data || 'event_id' in data) &&
    'camera_id' in data &&
    'risk_score' in data &&
    'risk_level' in data &&
    'summary' in data
  );
}

/**
 * Type guard for WebSocketServiceStatusMessage.
 */
export function isServiceStatusMessage(value: unknown): value is WebSocketServiceStatusMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'service_status') return false;

  const msg = value as { type: 'service_status'; data?: unknown; timestamp?: unknown };
  if (typeof msg.timestamp !== 'string') return false;
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return 'service' in data && 'status' in data;
}

/**
 * Type guard for WebSocketSceneChangeMessage.
 */
export function isSceneChangeMessage(value: unknown): value is WebSocketSceneChangeMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'scene_change') return false;

  const msg = value as { type: 'scene_change'; data?: unknown };
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return 'id' in data && 'camera_id' in data && 'change_type' in data;
}

/**
 * Type guard for WebSocketPingMessage.
 */
export function isPingMessage(value: unknown): value is WebSocketPingMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'ping';
}

/**
 * Type guard for WebSocketPongResponse.
 */
export function isPongMessage(value: unknown): value is WebSocketPongResponse {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'pong';
}

/**
 * Type guard for WebSocketErrorResponse.
 */
export function isErrorMessage(value: unknown): value is WebSocketErrorResponse {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'error') return false;

  const msg = value as { type: 'error'; message?: unknown };
  return typeof msg.message === 'string';
}

/**
 * Type guard for WebSocketAlertMessage (any alert event type).
 * Note: alert_deleted has a different data shape (only id and reason), so use isAlertDeletedMessage for that.
 */
export function isAlertMessage(value: unknown): value is WebSocketAlertMessage {
  if (!hasTypeProperty(value)) return false;
  const alertTypes = [
    'alert_created',
    'alert_updated',
    'alert_deleted',
    'alert_acknowledged',
    'alert_dismissed',
    'alert_resolved',
  ];
  if (!alertTypes.includes(value.type as string)) return false;

  const msg = value as { type: string; data?: unknown };
  if (!msg.data || typeof msg.data !== 'object') return false;

  // For deleted alerts, we only need 'id' in data
  if (value.type === 'alert_deleted') {
    const data = msg.data as Record<string, unknown>;
    return 'id' in data;
  }

  // For all other alert types, require full alert data
  const data = msg.data as Record<string, unknown>;
  return 'id' in data && 'event_id' in data && 'severity' in data && 'status' in data;
}

/**
 * Type guard for WebSocketAlertCreatedMessage.
 */
export function isAlertCreatedMessage(value: unknown): value is WebSocketAlertCreatedMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'alert_created' && isAlertMessage(value);
}

/**
 * Type guard for WebSocketAlertUpdatedMessage.
 */
export function isAlertUpdatedMessage(value: unknown): value is WebSocketAlertUpdatedMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'alert_updated' && isAlertMessage(value);
}

/**
 * Type guard for WebSocketAlertDeletedMessage.
 * Note: deleted alerts have a different data shape (only id and optional reason).
 */
export function isAlertDeletedMessage(value: unknown): value is WebSocketAlertDeletedMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'alert_deleted') return false;

  const msg = value as { type: string; data?: unknown };
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return 'id' in data;
}

/**
 * Type guard for WebSocketAlertAcknowledgedMessage.
 */
export function isAlertAcknowledgedMessage(
  value: unknown
): value is WebSocketAlertAcknowledgedMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'alert_acknowledged' && isAlertMessage(value);
}

/**
 * Type guard for WebSocketAlertDismissedMessage.
 */
export function isAlertDismissedMessage(value: unknown): value is WebSocketAlertDismissedMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'alert_dismissed' && isAlertMessage(value);
}

/**
 * Type guard for WebSocketAlertResolvedMessage.
 */
export function isAlertResolvedMessage(value: unknown): value is WebSocketAlertResolvedMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'alert_resolved' && isAlertMessage(value);
}
