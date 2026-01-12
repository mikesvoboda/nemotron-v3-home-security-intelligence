/**
 * WebSocket Event Map and Typed Event Utilities
 *
 * Provides a type-safe event map for WebSocket message handling with utility types
 * for handlers, event keys, and payload extraction. This module complements the
 * discriminated union types in websocket.ts by providing an event-based API
 * for typed event subscription and emission.
 *
 * @example
 * ```ts
 * const emitter = new TypedWebSocketEmitter();
 *
 * // Type-safe subscription - handler parameter is typed correctly
 * emitter.on('event', (data) => {
 *   // data is typed as SecurityEventData
 *   console.log(data.risk_score);
 * });
 *
 * // Type-safe emission - data must match event type
 * emitter.emit('event', {
 *   id: '123',
 *   camera_id: 'front_door',
 *   risk_score: 75,
 *   risk_level: 'high',
 *   summary: 'Person detected',
 * });
 * ```
 */

import type {
  SecurityEventData,
  ServiceStatusData,
  SystemStatusData,
  GpuStatusData,
} from './websocket';

// ============================================================================
// Event Map Definition
// ============================================================================

/**
 * Heartbeat payload for ping messages.
 * Matches the HeartbeatMessage type from websocket.ts but as a payload.
 */
export interface HeartbeatPayload {
  type: 'ping';
}

/**
 * GPU stats payload for dedicated GPU monitoring events.
 */
export interface GpuStatsPayload extends GpuStatusData {
  timestamp?: string;
}

/**
 * Error payload for WebSocket errors.
 */
export interface WebSocketErrorPayload {
  code?: string;
  message: string;
  details?: Record<string, unknown>;
}

/**
 * Pong payload for pong responses.
 */
export interface PongPayload {
  type: 'pong';
}

/**
 * WebSocket Event Map
 *
 * Maps event keys to their corresponding payload types for type-safe
 * event handling. This provides an event-based API on top of the
 * discriminated union message types.
 *
 * Event keys correspond to the `type` field in WebSocket messages:
 * - 'event' -> SecurityEventData (from EventMessage.data)
 * - 'service_status' -> ServiceStatusData (from ServiceStatusMessage.data)
 * - 'system_status' -> SystemStatusData (from SystemStatusMessage.data)
 * - 'camera_status' -> CameraStatusEventPayload (NEM-2295)
 * - 'ping' -> HeartbeatPayload
 * - 'gpu_stats' -> GpuStatsPayload (derived from system status)
 * - 'error' -> WebSocketErrorPayload
 * - 'pong' -> PongPayload
 */
export interface WebSocketEventMap {
  /** Security event from the events channel */
  event: SecurityEventData;
  /** Service status update (e.g., AI service health) */
  service_status: ServiceStatusData;
  /** System status broadcast */
  system_status: SystemStatusData;
  /** Camera status change event (NEM-2295) */
  camera_status: CameraStatusEventPayload;
  /** Server heartbeat ping */
  ping: HeartbeatPayload;
  /** GPU statistics (can be extracted from system_status or dedicated) */
  gpu_stats: GpuStatsPayload;
  /** WebSocket error */
  error: WebSocketErrorPayload;
  /** Pong response */
  pong: PongPayload;
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * All valid event keys from the WebSocket event map.
 */
export type WebSocketEventKey = keyof WebSocketEventMap;

/**
 * Extract the payload type for a specific event key.
 *
 * @example
 * ```ts
 * type EventPayload = WebSocketEventPayload<'event'>; // SecurityEventData
 * type StatusPayload = WebSocketEventPayload<'system_status'>; // SystemStatusData
 * ```
 */
export type WebSocketEventPayload<K extends WebSocketEventKey> = WebSocketEventMap[K];

/**
 * Type-safe event handler function for a specific event key.
 *
 * @example
 * ```ts
 * const handler: WebSocketEventHandler<'event'> = (data) => {
 *   // data is SecurityEventData
 *   console.log(data.risk_score);
 * };
 * ```
 */
export type WebSocketEventHandler<K extends WebSocketEventKey> = (
  data: WebSocketEventMap[K]
) => void;

/**
 * Handler map type for registering multiple handlers at once.
 *
 * @example
 * ```ts
 * const handlers: WebSocketEventHandlerMap = {
 *   event: (data) => console.log(data.risk_score),
 *   system_status: (data) => console.log(data.health),
 * };
 * ```
 */
export type WebSocketEventHandlerMap = {
  [K in WebSocketEventKey]?: WebSocketEventHandler<K>;
};

// ============================================================================
// Type Guards
// ============================================================================

/**
 * All valid event keys as a constant array for runtime checks.
 */
export const WEBSOCKET_EVENT_KEYS: readonly WebSocketEventKey[] = [
  'event',
  'service_status',
  'system_status',
  'camera_status',
  'ping',
  'gpu_stats',
  'error',
  'pong',
] as const;

/**
 * Type guard to check if a string is a valid WebSocket event key.
 *
 * @example
 * ```ts
 * const type = 'event';
 * if (isWebSocketEventKey(type)) {
 *   // type is narrowed to WebSocketEventKey
 *   emitter.emit(type, payload);
 * }
 * ```
 */
export function isWebSocketEventKey(value: unknown): value is WebSocketEventKey {
  return (
    typeof value === 'string' && WEBSOCKET_EVENT_KEYS.includes(value as WebSocketEventKey)
  );
}

/**
 * Extract the event type from a WebSocket message object.
 * Returns undefined if the message doesn't have a valid type field.
 *
 * @example
 * ```ts
 * const message = JSON.parse(event.data);
 * const eventType = extractEventType(message);
 * if (eventType) {
 *   emitter.emit(eventType, message.data ?? message);
 * }
 * ```
 */
export function extractEventType(message: unknown): WebSocketEventKey | undefined {
  if (!message || typeof message !== 'object') {
    return undefined;
  }

  const msg = message as Record<string, unknown>;

  if ('type' in msg && isWebSocketEventKey(msg.type)) {
    return msg.type;
  }

  return undefined;
}

/**
 * Extract the payload from a WebSocket message based on its type.
 * For messages with a 'data' field, returns the data. Otherwise returns the message itself.
 *
 * @example
 * ```ts
 * const message = { type: 'event', data: { risk_score: 75, ... } };
 * const payload = extractEventPayload(message, 'event');
 * // payload is the SecurityEventData object
 * ```
 */
export function extractEventPayload<K extends WebSocketEventKey>(
  message: unknown,
  eventType: K
): WebSocketEventMap[K] | undefined {
  if (!message || typeof message !== 'object') {
    return undefined;
  }

  const msg = message as Record<string, unknown>;

  // Verify the type matches
  if (msg.type !== eventType) {
    return undefined;
  }

  // For messages with data field, return the data
  if ('data' in msg && msg.data !== undefined) {
    return msg.data as WebSocketEventMap[K];
  }

  // For simple messages (like ping/pong), return the message itself
  return msg as unknown as WebSocketEventMap[K];
}

// ============================================================================
// WebSocket Event Type Registry (NEM-1984)
// Matches backend/api/schemas/websocket.py WSEventType enum
// ============================================================================

/**
 * Comprehensive WebSocket event type registry.
 *
 * This enum defines all WebSocket event types used in the system.
 * Event types follow a hierarchical naming convention: {domain}.{action}
 *
 * Domains:
 * - detection: AI detection events from the pipeline
 * - event: Security event lifecycle events
 * - alert: Alert notifications and state changes
 * - camera: Camera status and configuration changes
 * - job: Background job lifecycle events
 * - system: System health and status events
 * - gpu: GPU monitoring events
 */
export enum WSEventType {
  // Detection events - AI pipeline results
  DETECTION_NEW = 'detection.new',
  DETECTION_BATCH = 'detection.batch',

  // Event events - Security event lifecycle
  EVENT_CREATED = 'event.created',
  EVENT_UPDATED = 'event.updated',
  EVENT_DELETED = 'event.deleted',

  // Alert events - Alert notifications
  ALERT_CREATED = 'alert.created',
  ALERT_ACKNOWLEDGED = 'alert.acknowledged',
  ALERT_DISMISSED = 'alert.dismissed',

  // Camera events - Camera status changes (NEM-2295)
  CAMERA_ONLINE = 'camera.online',
  CAMERA_OFFLINE = 'camera.offline',
  CAMERA_ERROR = 'camera.error',
  CAMERA_UPDATED = 'camera.updated',
  // Legacy camera events
  CAMERA_STATUS_CHANGED = 'camera.status_changed',
  CAMERA_ENABLED = 'camera.enabled',
  CAMERA_DISABLED = 'camera.disabled',

  // Job events - Background job lifecycle
  JOB_STARTED = 'job.started',
  JOB_PROGRESS = 'job.progress',
  JOB_COMPLETED = 'job.completed',
  JOB_FAILED = 'job.failed',

  // System events - System health monitoring
  SYSTEM_HEALTH_CHANGED = 'system.health_changed',
  SYSTEM_STATUS = 'system.status',

  // GPU events - GPU monitoring
  GPU_STATS_UPDATED = 'gpu.stats_updated',

  // Service events - Container/service status
  SERVICE_STATUS_CHANGED = 'service.status_changed',

  // Scene change events - Camera view monitoring
  SCENE_CHANGE_DETECTED = 'scene_change.detected',

  // Legacy event types for backward compatibility
  // These map to the existing message types in the codebase
  EVENT = 'event',
  SERVICE_STATUS = 'service_status',
  CAMERA_STATUS = 'camera_status',
  SCENE_CHANGE = 'scene_change',
  PING = 'ping',
  PONG = 'pong',
  ERROR = 'error',
}

/**
 * Generic WebSocket event wrapper with type, payload, and metadata.
 * Matches backend WSEvent model.
 */
export interface WSEvent<T = Record<string, unknown>> {
  /** Event type from WSEventType enum */
  type: WSEventType;
  /** Event-specific payload data */
  payload: T;
  /** ISO 8601 timestamp when the event occurred */
  timestamp: string;
  /** Optional channel identifier (e.g., 'events', 'system') */
  channel?: string;
}

// ============================================================================
// Type-Safe Payload Interfaces
// ============================================================================

/**
 * Payload for detection.new events.
 */
export interface DetectionNewPayload {
  detection_id: string;
  event_id?: string;
  label: string;
  confidence: number;
  bbox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  camera_id: string;
  timestamp?: string;
}

/**
 * Payload for detection.batch events.
 */
export interface DetectionBatchPayload {
  batch_id: string;
  detections: DetectionNewPayload[];
  frame_timestamp: string;
  camera_id: string;
}

/**
 * Payload for event.created events.
 */
export interface EventCreatedPayload {
  id: number;
  event_id: number;
  batch_id: string;
  camera_id: string;
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  summary: string;
  reasoning: string;
  started_at?: string;
}

/**
 * Payload for event.updated events.
 */
export interface EventUpdatedPayload {
  id: number;
  updated_fields: string[];
  risk_score?: number;
  risk_level?: 'low' | 'medium' | 'high' | 'critical';
}

/**
 * Payload for event.deleted events.
 */
export interface EventDeletedPayload {
  id: number;
  reason?: string;
}

/**
 * Payload for alert.created events.
 */
export interface AlertCreatedPayload {
  alert_id: number;
  event_id: number;
  severity: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  created_at: string;
}

/**
 * Payload for alert.acknowledged events.
 */
export interface AlertAcknowledgedPayload {
  alert_id: number;
  acknowledged_at: string;
}

/**
 * Payload for alert.dismissed events.
 */
export interface AlertDismissedPayload {
  alert_id: number;
  dismissed_at: string;
  reason?: string;
}

/**
 * Camera event types for WebSocket messages (NEM-2295).
 *
 * Distinguishes between different types of camera status changes:
 * - camera.online: Camera came online
 * - camera.offline: Camera went offline
 * - camera.error: Camera encountered an error
 * - camera.updated: Camera configuration was updated
 */
export type CameraEventType =
  | 'camera.online'
  | 'camera.offline'
  | 'camera.error'
  | 'camera.updated';

/**
 * Camera status values.
 */
export type CameraStatusValue = 'online' | 'offline' | 'error' | 'unknown';

/**
 * Payload for camera status events (NEM-2295).
 *
 * This is the new unified payload format for all camera status WebSocket events.
 * Includes event_type to distinguish between camera.online, camera.offline,
 * camera.error, and camera.updated events.
 */
export interface CameraStatusEventPayload {
  /** Type of camera event */
  event_type: CameraEventType;
  /** Normalized camera ID (e.g., 'front_door') */
  camera_id: string;
  /** Human-readable camera name */
  camera_name: string;
  /** Current camera status */
  status: CameraStatusValue;
  /** ISO 8601 timestamp when the event occurred */
  timestamp: string;
  /** Previous camera status before this change */
  previous_status?: CameraStatusValue | null;
  /** Optional reason for the status change */
  reason?: string | null;
  /** Optional additional details */
  details?: Record<string, unknown> | null;
}

/**
 * Payload for camera.status_changed events.
 * @deprecated Use CameraStatusEventPayload instead (NEM-2295)
 */
export interface CameraStatusChangedPayload {
  camera_id: string;
  status: CameraStatusValue;
  previous_status: CameraStatusValue;
  message?: string;
}

/**
 * Payload for camera.enabled events.
 */
export interface CameraEnabledPayload {
  camera_id: string;
  enabled_at: string;
}

/**
 * Payload for camera.disabled events.
 */
export interface CameraDisabledPayload {
  camera_id: string;
  disabled_at: string;
  reason?: string;
}

/**
 * Payload for job.started events.
 */
export interface JobStartedPayload {
  job_id: string;
  job_type: string;
  started_at: string;
  estimated_duration?: number;
}

/**
 * Payload for job.progress events.
 */
export interface JobProgressPayload {
  job_id: string;
  progress: number;
  message?: string;
}

/**
 * Payload for job.completed events.
 */
export interface JobCompletedPayload {
  job_id: string;
  completed_at: string;
  result?: Record<string, unknown>;
}

/**
 * Payload for job.failed events.
 */
export interface JobFailedPayload {
  job_id: string;
  failed_at: string;
  error: string;
  retryable: boolean;
}

/**
 * Payload for system.health_changed events.
 */
export interface SystemHealthChangedPayload {
  health: 'healthy' | 'degraded' | 'unhealthy';
  previous_health: 'healthy' | 'degraded' | 'unhealthy';
  components: Record<string, 'healthy' | 'degraded' | 'unhealthy'>;
}

/**
 * Payload for system.status events.
 */
export interface SystemStatusPayload {
  gpu: {
    utilization: number | null;
    memory_used: number | null;
    memory_total: number | null;
    temperature: number | null;
    inference_fps: number | null;
  };
  cameras: {
    active: number;
    total: number;
  };
  queue: {
    pending: number;
    processing: number;
  };
  health: 'healthy' | 'degraded' | 'unhealthy';
}

/**
 * Payload for gpu.stats_updated events.
 */
export interface GpuStatsUpdatedPayload {
  utilization: number | null;
  memory_used: number | null;
  memory_total: number | null;
  temperature: number | null;
  inference_fps: number | null;
}

/**
 * Payload for service.status_changed events.
 */
export interface ServiceStatusChangedPayload {
  service: string;
  status: 'healthy' | 'unhealthy' | 'restarting' | 'restart_failed' | 'failed';
  previous_status?: string;
  message?: string;
}

/**
 * Payload for scene_change.detected events.
 */
export interface SceneChangeDetectedPayload {
  id: number;
  camera_id: string;
  detected_at: string;
  change_type: 'view_blocked' | 'angle_changed' | 'view_tampered' | 'unknown';
  similarity_score: number;
}

// ============================================================================
// Event Registry Response Types (from API)
// ============================================================================

/**
 * Information about a single WebSocket event type.
 * Matches backend EventTypeInfo model.
 */
export interface EventTypeInfo {
  /** Event type identifier */
  type: string;
  /** Human-readable description */
  description: string;
  /** WebSocket channel this event is broadcast on */
  channel: string | null;
  /** JSON Schema for the event payload */
  payload_schema: Record<string, unknown>;
  /** Example payload */
  example?: Record<string, unknown>;
  /** Whether this event type is deprecated */
  deprecated: boolean;
  /** Replacement event type if deprecated */
  replacement: string | null;
}

/**
 * Response from GET /api/system/websocket/events endpoint.
 * Matches backend EventRegistryResponse model.
 */
export interface EventRegistryResponse {
  /** List of all available event types */
  event_types: EventTypeInfo[];
  /** List of all available WebSocket channels */
  channels: string[];
  /** Total number of event types */
  total_count: number;
  /** Number of deprecated event types */
  deprecated_count: number;
}

// ============================================================================
// Typed Event Registry Map
// ============================================================================

/**
 * Maps WSEventType values to their typed payload interfaces.
 * Use this for type-safe event handling.
 *
 * @example
 * ```ts
 * function handleEvent<T extends WSEventType>(
 *   type: T,
 *   payload: WSEventPayloadMap[T]
 * ) {
 *   // payload is typed based on event type
 * }
 * ```
 */
export interface WSEventPayloadMap {
  [WSEventType.DETECTION_NEW]: DetectionNewPayload;
  [WSEventType.DETECTION_BATCH]: DetectionBatchPayload;
  [WSEventType.EVENT_CREATED]: EventCreatedPayload;
  [WSEventType.EVENT_UPDATED]: EventUpdatedPayload;
  [WSEventType.EVENT_DELETED]: EventDeletedPayload;
  [WSEventType.ALERT_CREATED]: AlertCreatedPayload;
  [WSEventType.ALERT_ACKNOWLEDGED]: AlertAcknowledgedPayload;
  [WSEventType.ALERT_DISMISSED]: AlertDismissedPayload;
  // Camera events (NEM-2295)
  [WSEventType.CAMERA_ONLINE]: CameraStatusEventPayload;
  [WSEventType.CAMERA_OFFLINE]: CameraStatusEventPayload;
  [WSEventType.CAMERA_ERROR]: CameraStatusEventPayload;
  [WSEventType.CAMERA_UPDATED]: CameraStatusEventPayload;
  // Legacy camera events
  [WSEventType.CAMERA_STATUS_CHANGED]: CameraStatusChangedPayload;
  [WSEventType.CAMERA_ENABLED]: CameraEnabledPayload;
  [WSEventType.CAMERA_DISABLED]: CameraDisabledPayload;
  [WSEventType.JOB_STARTED]: JobStartedPayload;
  [WSEventType.JOB_PROGRESS]: JobProgressPayload;
  [WSEventType.JOB_COMPLETED]: JobCompletedPayload;
  [WSEventType.JOB_FAILED]: JobFailedPayload;
  [WSEventType.SYSTEM_HEALTH_CHANGED]: SystemHealthChangedPayload;
  [WSEventType.SYSTEM_STATUS]: SystemStatusPayload;
  [WSEventType.GPU_STATS_UPDATED]: GpuStatsUpdatedPayload;
  [WSEventType.SERVICE_STATUS_CHANGED]: ServiceStatusChangedPayload;
  [WSEventType.SCENE_CHANGE_DETECTED]: SceneChangeDetectedPayload;
  // Legacy types
  [WSEventType.EVENT]: SecurityEventData;
  [WSEventType.SERVICE_STATUS]: ServiceStatusData;
  [WSEventType.CAMERA_STATUS]: CameraStatusEventPayload;
  [WSEventType.SCENE_CHANGE]: SceneChangeDetectedPayload;
  [WSEventType.PING]: HeartbeatPayload;
  [WSEventType.PONG]: PongPayload;
  [WSEventType.ERROR]: WebSocketErrorPayload;
}

/**
 * Type-safe event handler for a specific WSEventType.
 */
export type WSEventHandler<T extends WSEventType> = (payload: WSEventPayloadMap[T]) => void;

/**
 * All WSEventType values as an array for runtime validation.
 */
export const WS_EVENT_TYPES: readonly WSEventType[] = Object.values(WSEventType);

/**
 * Type guard to check if a string is a valid WSEventType.
 */
export function isWSEventType(value: unknown): value is WSEventType {
  return typeof value === 'string' && WS_EVENT_TYPES.includes(value as WSEventType);
}
