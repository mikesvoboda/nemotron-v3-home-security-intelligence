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
