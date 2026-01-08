/**
 * WebSocket Event Map Types
 *
 * This module defines a typed event map for WebSocket message handling.
 * It provides compile-time type safety for event subscriptions and emissions,
 * ensuring that event handlers receive correctly typed payloads.
 *
 * @example
 * ```ts
 * import type { WebSocketEventMap, WebSocketEventKey } from './websocket-events';
 *
 * // Type-safe event subscription
 * emitter.on('event', (data: WebSocketEventMap['event']) => {
 *   console.log(data.risk_score); // TypeScript knows the type
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
// Event Payload Types
// ============================================================================

/**
 * Heartbeat/ping message payload.
 * Represents keep-alive messages from the WebSocket server.
 */
export interface HeartbeatPayload {
  type: 'ping';
}

/**
 * GPU stats payload for real-time GPU monitoring.
 * Extends the base GpuStatusData with optional timestamp.
 */
export interface GpuStatsPayload extends GpuStatusData {
  /** Timestamp of the GPU stats snapshot (ISO format) */
  timestamp?: string;
}

/**
 * Error payload for WebSocket errors.
 * Contains error details without the discriminant type field.
 */
export interface WebSocketErrorPayload {
  /** Error code for programmatic handling */
  code?: string;
  /** Human-readable error message */
  message: string;
  /** Additional error details */
  details?: Record<string, unknown>;
}

// ============================================================================
// WebSocket Event Map
// ============================================================================

/**
 * Map of WebSocket event keys to their corresponding payload types.
 *
 * This interface enables type-safe event handling where:
 * - Event keys are string literal types
 * - Each event key maps to a specific payload type
 * - TypeScript infers the correct type for event handlers
 *
 * @example
 * ```ts
 * // Event handler receives correctly typed payload
 * function handleEvent<K extends WebSocketEventKey>(
 *   event: K,
 *   handler: (data: WebSocketEventMap[K]) => void
 * ): void {
 *   // TypeScript ensures handler receives the correct type
 * }
 * ```
 */
export interface WebSocketEventMap {
  /** Security event from AI detection pipeline */
  event: SecurityEventData;
  /** Service status update (e.g., rtdetr, nemotron container status) */
  service_status: ServiceStatusData;
  /** System status update with GPU, cameras, and health info */
  system_status: SystemStatusData;
  /** Heartbeat/ping message for connection keep-alive */
  ping: HeartbeatPayload;
  /** GPU statistics for real-time monitoring */
  gpu_stats: GpuStatsPayload;
  /** Error message from the WebSocket server */
  error: WebSocketErrorPayload;
  /** Pong response (client-initiated, less common to subscribe to) */
  pong: { type: 'pong' };
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * All valid WebSocket event keys.
 * Use this type to constrain event parameters.
 */
export type WebSocketEventKey = keyof WebSocketEventMap;

/**
 * Get the payload type for a specific event key.
 *
 * @example
 * ```ts
 * type EventPayload = WebSocketEventPayload<'event'>; // SecurityEventData
 * type ErrorPayload = WebSocketEventPayload<'error'>; // WebSocketErrorPayload
 * ```
 */
export type WebSocketEventPayload<K extends WebSocketEventKey> = WebSocketEventMap[K];

/**
 * Type-safe event handler function signature.
 *
 * @template K - The event key this handler is registered for
 *
 * @example
 * ```ts
 * const eventHandler: WebSocketEventHandler<'event'> = (data) => {
 *   console.log(data.risk_score); // TypeScript knows data is SecurityEventData
 * };
 * ```
 */
export type WebSocketEventHandler<K extends WebSocketEventKey> = (
  data: WebSocketEventMap[K]
) => void;

/**
 * Map of event keys to arrays of handlers.
 * Internal type for the emitter's handler storage.
 */
export type WebSocketEventHandlerMap = {
  [K in WebSocketEventKey]?: Set<WebSocketEventHandler<K>>;
};

// ============================================================================
// Type Guards
// ============================================================================

/**
 * All valid event keys as a runtime array.
 * Useful for validation and iteration.
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
 * const key: string = 'event';
 * if (isWebSocketEventKey(key)) {
 *   // TypeScript knows key is WebSocketEventKey
 *   emitter.emit(key, payload);
 * }
 * ```
 */
export function isWebSocketEventKey(value: unknown): value is WebSocketEventKey {
  return (
    typeof value === 'string' &&
    (WEBSOCKET_EVENT_KEYS as readonly string[]).includes(value)
  );
}

/**
 * Extract the event type from a WebSocket message object.
 * Returns the type field if it's a valid event key, undefined otherwise.
 *
 * @example
 * ```ts
 * const message = { type: 'event', data: { ... } };
 * const eventType = extractEventType(message);
 * if (eventType) {
 *   emitter.emit(eventType, message.data);
 * }
 * ```
 */
export function extractEventType(message: unknown): WebSocketEventKey | undefined {
  if (
    typeof message === 'object' &&
    message !== null &&
    'type' in message &&
    isWebSocketEventKey((message as { type: unknown }).type)
  ) {
    return (message as { type: WebSocketEventKey }).type;
  }
  return undefined;
}
