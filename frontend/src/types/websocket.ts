/**
 * Discriminated Union Types for WebSocket Messages
 *
 * This module provides type-safe WebSocket message handling using discriminated unions.
 * The `type` field serves as the discriminant, enabling TypeScript to narrow the message
 * type and provide proper type inference for the data payload.
 *
 * NOTE: Core message types are now generated from backend Pydantic schemas.
 * See `frontend/src/types/generated/websocket.ts` for the auto-generated types.
 * This file extends those types with application-specific types and maintains
 * backward compatibility with existing code.
 *
 * To regenerate types from backend schemas:
 *   ./scripts/generate-ws-types.py
 *
 * @example
 * ```ts
 * function handleMessage(message: WebSocketMessage) {
 *   switch (message.type) {
 *     case 'event':
 *       // message.data is typed as SecurityEventData
 *       console.log(message.data.risk_score);
 *       break;
 *     case 'system_status':
 *       // message.data is typed as SystemStatusData
 *       console.log(message.data.gpu.utilization);
 *       break;
 *     case 'ping':
 *       // TypeScript knows this is a HeartbeatMessage (no data field)
 *       break;
 *   }
 * }
 * ```
 */

// ============================================================================
// Import and Re-export Generated Types from Backend Schemas
// ============================================================================

// Import types that are used locally in this file
import type { RiskLevel as GeneratedRiskLevel } from './generated/websocket';

// Re-export for consumers
// Core types generated from backend/api/schemas/websocket.py
export type {
  // Enums
  RiskLevel,
  WebSocketMessageType as GeneratedWebSocketMessageType,
  WebSocketServiceStatus,
  WebSocketErrorCodeType,
  // Data payloads
  WebSocketEventData,
  WebSocketServiceStatusData,
  WebSocketSceneChangeData,
  // Message envelopes
  WebSocketPingMessage,
  WebSocketPongResponse,
  WebSocketSubscribeMessage,
  WebSocketUnsubscribeMessage,
  WebSocketErrorResponse,
  WebSocketEventMessage,
  WebSocketServiceStatusMessage,
  WebSocketSceneChangeMessage,
  // Discriminated unions
  WebSocketServerMessage,
  WebSocketClientMessage,
  AnyWebSocketMessage,
  MessageByType as GeneratedMessageByType,
  MessageHandler as GeneratedMessageHandler,
  MessageHandlerMap as GeneratedMessageHandlerMap,
} from './generated/websocket';

// Re-export type guards and utilities from generated file
// Note: Some are aliased to avoid conflicts with local definitions that work
// with app-specific message types (e.g., SystemStatusMessage with GPU data)
export {
  WebSocketErrorCode,
  isEventMessage as isGeneratedEventMessage,
  isServiceStatusMessage as isGeneratedServiceStatusMessage,
  isSceneChangeMessage,
  isPingMessage as isGeneratedPingMessage,
  isPongMessage as isGeneratedPongMessage,
  isErrorMessage as isGeneratedErrorMessage,
  createMessageDispatcher as createGeneratedMessageDispatcher,
  assertNever as generatedAssertNever,
} from './generated/websocket';

// Note: Branded types are available but not used in message definitions
// to maintain backward compatibility with existing WebSocket message parsing.
// The types use plain string/number for IDs, but consumers can wrap them
// using the branded type factory functions when needed.

// ============================================================================
// Event Message Types
// ============================================================================

/**
 * Security event data payload from the events WebSocket channel.
 * Contains AI-analyzed security event information.
 */
export interface SecurityEventData {
  /** Unique event identifier (can be numeric ID or string for compatibility) */
  id: string | number;
  /** Numeric event ID when available */
  event_id?: number;
  /** Batch ID grouping related detections */
  batch_id?: string;
  /** Camera that captured the event */
  camera_id: string;
  /** Human-readable camera name */
  camera_name?: string;
  /** AI-determined risk score (0-100) */
  risk_score: number;
  /** Categorical risk level */
  risk_level: GeneratedRiskLevel;
  /** AI-generated event summary */
  summary: string;
  /** Event timestamp (ISO format) */
  timestamp?: string;
  /** When the event started (ISO format) */
  started_at?: string;
}

/**
 * Event message envelope from the events WebSocket channel.
 */
export interface EventMessage {
  type: 'event';
  data: SecurityEventData;
  /** Monotonically increasing sequence number for ordering (NEM-2019) */
  sequence?: number;
  /** ISO 8601 timestamp when the message was created */
  timestamp?: string;
  /** Whether the client should acknowledge receipt (high-priority events) */
  requires_ack?: boolean;
  /** Whether this is a replayed message from the buffer (on reconnection) */
  replay?: boolean;
}

// ============================================================================
// System Status Message Types
// ============================================================================

/**
 * GPU metrics from the system status broadcast.
 */
export interface GpuStatusData {
  /** GPU utilization percentage (0-100) */
  utilization: number | null;
  /** GPU memory used in bytes */
  memory_used: number | null;
  /** Total GPU memory in bytes */
  memory_total: number | null;
  /** GPU temperature in Celsius */
  temperature: number | null;
  /** Current inference FPS */
  inference_fps: number | null;
}

/**
 * Camera status from the system status broadcast.
 */
export interface CameraStatusData {
  /** Number of active/online cameras */
  active: number;
  /** Total number of configured cameras */
  total: number;
}

/**
 * Processing queue status from the system status broadcast.
 */
export interface QueueStatusData {
  /** Number of items pending processing */
  pending: number;
  /** Number of items currently being processed */
  processing: number;
}

/**
 * System health status.
 */
export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';

/**
 * System status data payload from the system WebSocket channel.
 */
export interface SystemStatusData {
  /** GPU metrics */
  gpu: GpuStatusData;
  /** Camera status */
  cameras: CameraStatusData;
  /** Processing queue status */
  queue: QueueStatusData;
  /** Overall system health */
  health: HealthStatus;
}

/**
 * System status message envelope from the system WebSocket channel.
 */
export interface SystemStatusMessage {
  type: 'system_status';
  data: SystemStatusData;
  /** ISO timestamp of the status update */
  timestamp: string;
  /** Monotonically increasing sequence number for ordering (NEM-2019) */
  sequence?: number;
  /** Whether the client should acknowledge receipt */
  requires_ack?: boolean;
  /** Whether this is a replayed message from the buffer (on reconnection) */
  replay?: boolean;
}

// ============================================================================
// Service Status Message Types
// ============================================================================

/**
 * Container service status values from the orchestrator.
 */
export type ContainerStatus =
  | 'running'
  | 'starting'
  | 'unhealthy'
  | 'stopped'
  | 'error'
  | 'unknown';

/**
 * Service status data for a single AI service.
 */
export interface ServiceStatusData {
  /** Service name (e.g., 'rtdetr', 'nemotron') */
  service: string;
  /** Current status */
  status: ContainerStatus;
  /** Status message or error description */
  message?: string;
  /** Additional status details */
  details?: Record<string, unknown>;
}

/**
 * Service status message for AI service state changes.
 */
export interface ServiceStatusMessage {
  type: 'service_status';
  data: ServiceStatusData;
  timestamp: string;
  /** Monotonically increasing sequence number for ordering (NEM-2019) */
  sequence?: number;
  /** Whether the client should acknowledge receipt */
  requires_ack?: boolean;
  /** Whether this is a replayed message from the buffer (on reconnection) */
  replay?: boolean;
}

// ============================================================================
// Heartbeat Message Types
// ============================================================================

/**
 * Heartbeat (ping) message from the server.
 * Used to keep the WebSocket connection alive and detect disconnections.
 */
export interface HeartbeatMessage {
  type: 'ping';
}

/**
 * Pong response to send back to the server.
 */
export interface PongMessage {
  type: 'pong';
}

// ============================================================================
// Sequence Control Message Types (NEM-2019)
// ============================================================================

/**
 * Resync request message from frontend to backend.
 *
 * Sent when the frontend detects a gap in sequence numbers that exceeds
 * the threshold, requesting missed messages from the backend buffer.
 */
export interface ResyncRequestMessage {
  type: 'resync';
  /** Last sequence number successfully received (0 if none) */
  last_sequence: number;
  /** Channel to resync (e.g., 'events', 'system') */
  channel: string;
}

/**
 * Acknowledgment message from frontend to backend.
 *
 * Sent to acknowledge receipt of high-priority messages
 * (events with risk_score >= 80 or risk_level === 'critical').
 */
export interface AckMessage {
  type: 'ack';
  /** Sequence number being acknowledged */
  sequence: number;
}

// ============================================================================
// Error Message Types
// ============================================================================

/**
 * Error message from the WebSocket server.
 */
export interface ErrorMessage {
  type: 'error';
  /** Error code for programmatic handling */
  code?: string;
  /** Human-readable error message */
  message: string;
  /** Additional error details */
  details?: Record<string, unknown>;
}

// ============================================================================
// Detection Message Types (NEM-2506)
// ============================================================================

/**
 * Bounding box coordinates for a detection.
 * Coordinates are normalized values (0.0 to 1.0) relative to the image dimensions.
 */
export interface DetectionBbox {
  /** Normalized X coordinate (left edge) */
  x: number;
  /** Normalized Y coordinate (top edge) */
  y: number;
  /** Normalized width */
  width: number;
  /** Normalized height */
  height: number;
}

/**
 * Data payload for detection.new WebSocket events.
 * Sent when a new detection is added to a batch.
 */
export interface DetectionNewData {
  /** Unique detection identifier (database ID) */
  detection_id: number;
  /** Batch identifier this detection belongs to */
  batch_id: string;
  /** Camera identifier */
  camera_id: string;
  /** Detection class label (e.g., "person", "vehicle") */
  label: string;
  /** Detection confidence score (0.0-1.0) */
  confidence: number;
  /** Bounding box coordinates (optional) */
  bbox?: DetectionBbox;
  /** ISO 8601 timestamp when the detection occurred */
  timestamp: string;
}

/**
 * Detection.new message envelope.
 * Broadcast when a new detection is added to a batch.
 */
export interface DetectionNewMessage {
  type: 'detection.new';
  data: DetectionNewData;
  /** Monotonically increasing sequence number for ordering */
  sequence?: number;
  /** ISO 8601 timestamp when the message was created */
  timestamp?: string;
}

/**
 * Data payload for detection.batch WebSocket events.
 * Sent when a batch is closed and ready for analysis.
 */
export interface DetectionBatchData {
  /** Unique batch identifier */
  batch_id: string;
  /** Camera identifier */
  camera_id: string;
  /** List of detection IDs in this batch */
  detection_ids: number[];
  /** Number of detections in the batch */
  detection_count: number;
  /** ISO 8601 timestamp when the batch started */
  started_at: string;
  /** ISO 8601 timestamp when the batch was closed */
  closed_at: string;
  /** Reason for batch closure (timeout, idle, max_size) */
  close_reason?: string | null;
}

/**
 * Detection.batch message envelope.
 * Broadcast when a batch is closed.
 */
export interface DetectionBatchMessage {
  type: 'detection.batch';
  data: DetectionBatchData;
  /** Monotonically increasing sequence number for ordering */
  sequence?: number;
  /** ISO 8601 timestamp when the message was created */
  timestamp?: string;
}

// ============================================================================
// Discriminated Union - Events Channel
// ============================================================================

/**
 * All possible message types from the /ws/events channel.
 * Use this type when handling messages from the events WebSocket.
 */
export type EventsChannelMessage = EventMessage | HeartbeatMessage | ErrorMessage;

// ============================================================================
// Discriminated Union - Detections Channel
// ============================================================================

/**
 * All possible message types from the /ws/detections channel.
 * Use this type when handling messages from the detections WebSocket.
 */
export type DetectionsChannelMessage =
  | DetectionNewMessage
  | DetectionBatchMessage
  | HeartbeatMessage
  | ErrorMessage;

// ============================================================================
// Discriminated Union - System Channel
// ============================================================================

/**
 * All possible message types from the /ws/system channel.
 * Use this type when handling messages from the system WebSocket.
 */
export type SystemChannelMessage =
  | SystemStatusMessage
  | ServiceStatusMessage
  | HeartbeatMessage
  | ErrorMessage;

// ============================================================================
// Job Message Types
// ============================================================================

/**
 * Status of a background job.
 */
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed';

/**
 * Data payload for job progress WebSocket events.
 */
export interface JobProgressData {
  /** Unique job identifier */
  job_id: string;
  /** Type of job (export, cleanup, backup, sync) */
  job_type: string;
  /** Job progress percentage (0-100) */
  progress: number;
  /** Current job status */
  status: string;
}

/**
 * Job progress message envelope.
 */
export interface JobProgressMessage {
  type: 'job_progress';
  data: JobProgressData;
}

/**
 * Data payload for job completed WebSocket events.
 */
export interface JobCompletedData {
  /** Unique job identifier */
  job_id: string;
  /** Type of job (export, cleanup, backup, sync) */
  job_type: string;
  /** Optional result data from the job */
  result: unknown;
}

/**
 * Job completed message envelope.
 */
export interface JobCompletedMessage {
  type: 'job_completed';
  data: JobCompletedData;
}

/**
 * Data payload for job failed WebSocket events.
 */
export interface JobFailedData {
  /** Unique job identifier */
  job_id: string;
  /** Type of job (export, cleanup, backup, sync) */
  job_type: string;
  /** Error message describing the failure */
  error: string;
}

/**
 * Job failed message envelope.
 */
export interface JobFailedMessage {
  type: 'job_failed';
  data: JobFailedData;
}

// ============================================================================
// Combined Union - All Messages
// ============================================================================

/**
 * All possible WebSocket message types across all channels.
 * The `type` field serves as the discriminant for type narrowing.
 */
export type WebSocketMessage =
  | EventMessage
  | SystemStatusMessage
  | ServiceStatusMessage
  | HeartbeatMessage
  | PongMessage
  | ErrorMessage
  | JobProgressMessage
  | JobCompletedMessage
  | JobFailedMessage
  | DetectionNewMessage
  | DetectionBatchMessage;

/**
 * All message type discriminants.
 */
export type WebSocketMessageType = WebSocketMessage['type'];

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
 * Type guard for EventMessage.
 *
 * @example
 * ```ts
 * if (isEventMessage(message)) {
 *   console.log(message.data.risk_score);
 * }
 * ```
 */
export function isEventMessage(value: unknown): value is EventMessage {
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
 * Type guard for SystemStatusMessage.
 *
 * @example
 * ```ts
 * if (isSystemStatusMessage(message)) {
 *   console.log(message.data.gpu.utilization);
 * }
 * ```
 */
export function isSystemStatusMessage(value: unknown): value is SystemStatusMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'system_status') return false;

  const msg = value as { type: 'system_status'; data?: unknown; timestamp?: unknown };
  if (typeof msg.timestamp !== 'string') return false;
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return 'gpu' in data && 'cameras' in data && 'health' in data;
}

/**
 * Type guard for ServiceStatusMessage.
 */
export function isServiceStatusMessage(value: unknown): value is ServiceStatusMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'service_status') return false;

  const msg = value as { type: 'service_status'; data?: unknown; timestamp?: unknown };
  if (typeof msg.timestamp !== 'string') return false;
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return 'service' in data && 'status' in data;
}

/**
 * Type guard for HeartbeatMessage (ping).
 *
 * @example
 * ```ts
 * if (isHeartbeatMessage(message)) {
 *   // Respond with pong
 *   ws.send(JSON.stringify({ type: 'pong' }));
 * }
 * ```
 */
export function isHeartbeatMessage(value: unknown): value is HeartbeatMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'ping';
}

/**
 * Type guard for PongMessage.
 */
export function isPongMessage(value: unknown): value is PongMessage {
  if (!hasTypeProperty(value)) return false;
  return value.type === 'pong';
}

/**
 * Type guard for ErrorMessage.
 */
export function isErrorMessage(value: unknown): value is ErrorMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'error') return false;

  const msg = value as { type: 'error'; message?: unknown };
  return typeof msg.message === 'string';
}

/**
 * Type guard for JobProgressMessage.
 */
export function isJobProgressMessage(value: unknown): value is JobProgressMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'job_progress') return false;

  const msg = value as { type: 'job_progress'; data?: unknown };
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return 'job_id' in data && 'job_type' in data && 'progress' in data && 'status' in data;
}

/**
 * Type guard for JobCompletedMessage.
 */
export function isJobCompletedMessage(value: unknown): value is JobCompletedMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'job_completed') return false;

  const msg = value as { type: 'job_completed'; data?: unknown };
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return 'job_id' in data && 'job_type' in data;
}

/**
 * Type guard for JobFailedMessage.
 */
export function isJobFailedMessage(value: unknown): value is JobFailedMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'job_failed') return false;

  const msg = value as { type: 'job_failed'; data?: unknown };
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return 'job_id' in data && 'job_type' in data && 'error' in data;
}

/**
 * Type guard for DetectionNewMessage.
 *
 * @example
 * ```ts
 * if (isDetectionNewMessage(message)) {
 *   console.log(message.data.detection_id);
 * }
 * ```
 */
export function isDetectionNewMessage(value: unknown): value is DetectionNewMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'detection.new') return false;

  const msg = value as { type: 'detection.new'; data?: unknown };
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return (
    'detection_id' in data &&
    'batch_id' in data &&
    'camera_id' in data &&
    'label' in data &&
    'confidence' in data &&
    'timestamp' in data
  );
}

/**
 * Type guard for DetectionBatchMessage.
 *
 * @example
 * ```ts
 * if (isDetectionBatchMessage(message)) {
 *   console.log(message.data.detection_count);
 * }
 * ```
 */
export function isDetectionBatchMessage(value: unknown): value is DetectionBatchMessage {
  if (!hasTypeProperty(value)) return false;
  if (value.type !== 'detection.batch') return false;

  const msg = value as { type: 'detection.batch'; data?: unknown };
  if (!msg.data || typeof msg.data !== 'object') return false;

  const data = msg.data as Record<string, unknown>;
  return (
    'batch_id' in data &&
    'camera_id' in data &&
    'detection_ids' in data &&
    'detection_count' in data &&
    'started_at' in data &&
    'closed_at' in data
  );
}

/**
 * Type guard for any valid WebSocket message.
 * Useful for initial validation before more specific type guards.
 */
export function isWebSocketMessage(value: unknown): value is WebSocketMessage {
  return (
    isEventMessage(value) ||
    isSystemStatusMessage(value) ||
    isServiceStatusMessage(value) ||
    isHeartbeatMessage(value) ||
    isPongMessage(value) ||
    isErrorMessage(value) ||
    isJobProgressMessage(value) ||
    isJobCompletedMessage(value) ||
    isJobFailedMessage(value) ||
    isDetectionNewMessage(value) ||
    isDetectionBatchMessage(value)
  );
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * Extract the data type from a message type.
 *
 * @example
 * ```ts
 * type EventData = MessageData<EventMessage>; // SecurityEventData
 * ```
 */
export type MessageData<T extends WebSocketMessage> = T extends { data: infer D } ? D : never;

/**
 * Extract message type by discriminant.
 *
 * @example
 * ```ts
 * type Event = MessageByType<'event'>; // EventMessage
 * ```
 */
export type MessageByType<T extends WebSocketMessageType> = Extract<WebSocketMessage, { type: T }>;

// ============================================================================
// Message Handler Types
// ============================================================================

/**
 * Type-safe message handler function.
 */
export type MessageHandler<T extends WebSocketMessage> = (message: T) => void;

/**
 * Map of message types to their handlers.
 *
 * @example
 * ```ts
 * const handlers: MessageHandlerMap = {
 *   event: (msg) => console.log(msg.data.risk_score),
 *   system_status: (msg) => console.log(msg.data.gpu.utilization),
 *   ping: (msg) => console.log('heartbeat'),
 * };
 * ```
 */
export type MessageHandlerMap = {
  [K in WebSocketMessageType]?: MessageHandler<MessageByType<K>>;
};

/**
 * Create a type-safe message dispatcher.
 *
 * @example
 * ```ts
 * const dispatch = createMessageDispatcher({
 *   event: (msg) => setLatestEvent(msg.data),
 *   system_status: (msg) => setSystemStatus(msg.data),
 *   ping: () => console.log('heartbeat received'),
 * });
 *
 * ws.onmessage = (event) => {
 *   const message = JSON.parse(event.data);
 *   if (isWebSocketMessage(message)) {
 *     dispatch(message);
 *   }
 * };
 * ```
 */
export function createMessageDispatcher(handlers: MessageHandlerMap) {
  return (message: WebSocketMessage): void => {
    const handler = handlers[message.type];
    if (handler) {
      // TypeScript knows the handler matches the message type due to the discriminant
      (handler as (msg: WebSocketMessage) => void)(message);
    }
  };
}

// ============================================================================
// Exhaustive Check Utilities
// ============================================================================

/**
 * Utility function for exhaustive checking in switch statements.
 * When used in the default case, TypeScript will error if any case is missed.
 *
 * @example
 * ```ts
 * function handleMessage(message: WebSocketMessage) {
 *   switch (message.type) {
 *     case 'event':
 *       // handle event
 *       break;
 *     case 'system_status':
 *       // handle system_status
 *       break;
 *     case 'service_status':
 *       // handle service_status
 *       break;
 *     case 'ping':
 *       // handle ping
 *       break;
 *     case 'pong':
 *       // handle pong
 *       break;
 *     case 'error':
 *       // handle error
 *       break;
 *     default:
 *       // TypeScript will error here if any case is missed
 *       assertNever(message);
 *   }
 * }
 * ```
 */
export function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${JSON.stringify(value)}`);
}

/**
 * Non-throwing variant for cases where you want to log unhandled messages
 * but not crash the application.
 *
 * @example
 * ```ts
 * function handleMessage(message: WebSocketMessage) {
 *   switch (message.type) {
 *     // ... cases ...
 *     default:
 *       // Logs warning but doesn't throw
 *       assertNeverSoft(message, 'WebSocket message');
 *   }
 * }
 * ```
 */
export function assertNeverSoft(value: never, context?: string): void {
  console.warn(`Unhandled ${context ?? 'value'}: ${JSON.stringify(value)}`);
}
