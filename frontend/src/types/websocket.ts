/**
 * Discriminated Union Types for WebSocket Messages
 *
 * This module provides type-safe WebSocket message handling using discriminated unions.
 * The `type` field serves as the discriminant, enabling TypeScript to narrow the message
 * type and provide proper type inference for the data payload.
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

// Note: Branded types are available but not used in message definitions
// to maintain backward compatibility with existing WebSocket message parsing.
// The types use plain string/number for IDs, but consumers can wrap them
// using the branded type factory functions when needed.

// ============================================================================
// Risk Level Types
// ============================================================================

/**
 * Risk level classification from the AI analysis.
 * Uses literal types for compile-time safety.
 */
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

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
  risk_level: RiskLevel;
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
// Discriminated Union - Events Channel
// ============================================================================

/**
 * All possible message types from the /ws/events channel.
 * Use this type when handling messages from the events WebSocket.
 */
export type EventsChannelMessage = EventMessage | HeartbeatMessage | ErrorMessage;

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
  | ErrorMessage;

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
    isErrorMessage(value)
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
  console.warn(
    `Unhandled ${context ?? 'value'}: ${JSON.stringify(value)}`
  );
}
