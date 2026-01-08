/**
 * Typed WebSocket Event Emitter
 *
 * A type-safe event emitter for WebSocket message handling. Provides compile-time
 * type checking for event names and their associated payload types.
 *
 * @example
 * ```ts
 * const emitter = new TypedWebSocketEmitter();
 *
 * // Type-safe subscription
 * const unsubscribe = emitter.on('event', (data) => {
 *   // data is typed as SecurityEventData
 *   console.log(data.risk_score);
 * });
 *
 * // Type-safe emission
 * emitter.emit('event', {
 *   id: '123',
 *   camera_id: 'front_door',
 *   risk_score: 75,
 *   risk_level: 'high',
 *   summary: 'Person detected',
 * });
 *
 * // Cleanup
 * unsubscribe();
 * ```
 */

import { extractEventType, isWebSocketEventKey } from '../types/websocket-events';

import type {
  WebSocketEventHandler,
  WebSocketEventKey,
  WebSocketEventMap,
} from '../types/websocket-events';

/**
 * Generic handler type for internal storage.
 * Uses unknown payload to allow storing handlers for different event types.
 */
type AnyHandler = (data: unknown) => void;

/**
 * TypedWebSocketEmitter class
 *
 * Provides a type-safe event emitter API for WebSocket messages. Handlers
 * are strongly typed based on the event key, ensuring compile-time safety
 * for both subscription and emission.
 */
export class TypedWebSocketEmitter {
  /**
   * Internal handler storage. Maps event keys to sets of handlers.
   * Using Set ensures O(1) add/remove and prevents duplicate handlers.
   */
  private handlers: Map<WebSocketEventKey, Set<AnyHandler>> = new Map();

  /**
   * Subscribe to an event with a type-safe handler.
   *
   * @param event - The event key to subscribe to
   * @param handler - Handler function that receives the typed payload
   * @returns Unsubscribe function to remove the handler
   *
   * @example
   * ```ts
   * const unsubscribe = emitter.on('event', (data) => {
   *   console.log(data.risk_score); // TypeScript knows this is SecurityEventData
   * });
   *
   * // Later, to unsubscribe:
   * unsubscribe();
   * ```
   */
  on<K extends WebSocketEventKey>(
    event: K,
    handler: WebSocketEventHandler<K>
  ): () => void {
    let eventHandlers = this.handlers.get(event);

    if (!eventHandlers) {
      eventHandlers = new Set();
      this.handlers.set(event, eventHandlers);
    }

    eventHandlers.add(handler as AnyHandler);

    // Return unsubscribe function
    return () => this.off(event, handler);
  }

  /**
   * Unsubscribe a handler from an event.
   *
   * @param event - The event key to unsubscribe from
   * @param handler - The handler function to remove
   *
   * @example
   * ```ts
   * const handler = (data: SecurityEventData) => console.log(data);
   * emitter.on('event', handler);
   * emitter.off('event', handler);
   * ```
   */
  off<K extends WebSocketEventKey>(
    event: K,
    handler: WebSocketEventHandler<K>
  ): void {
    const eventHandlers = this.handlers.get(event);

    if (eventHandlers) {
      eventHandlers.delete(handler as AnyHandler);

      // Clean up empty sets
      if (eventHandlers.size === 0) {
        this.handlers.delete(event);
      }
    }
  }

  /**
   * Emit an event with a typed payload.
   *
   * @param event - The event key to emit
   * @param data - The payload data (must match the event's payload type)
   *
   * @example
   * ```ts
   * emitter.emit('event', {
   *   id: '123',
   *   camera_id: 'front_door',
   *   risk_score: 75,
   *   risk_level: 'high',
   *   summary: 'Person detected',
   * });
   * ```
   */
  emit<K extends WebSocketEventKey>(event: K, data: WebSocketEventMap[K]): void {
    const eventHandlers = this.handlers.get(event);

    if (eventHandlers) {
      // Create a copy to avoid issues if handlers modify the set
      const handlersToCall = Array.from(eventHandlers);

      for (const handler of handlersToCall) {
        try {
          handler(data);
        } catch (error) {
          // Log but don't throw to prevent one handler from breaking others
          console.error(`Error in ${event} handler:`, error);
        }
      }
    }
  }

  /**
   * Subscribe to an event that will only fire once.
   *
   * @param event - The event key to subscribe to
   * @param handler - Handler function that receives the typed payload
   * @returns Unsubscribe function to remove the handler before it fires
   *
   * @example
   * ```ts
   * emitter.once('system_status', (data) => {
   *   console.log('First status received:', data.health);
   * });
   * ```
   */
  once<K extends WebSocketEventKey>(
    event: K,
    handler: WebSocketEventHandler<K>
  ): () => void {
    const wrappedHandler: WebSocketEventHandler<K> = (data) => {
      this.off(event, wrappedHandler);
      handler(data);
    };

    return this.on(event, wrappedHandler);
  }

  /**
   * Handle an incoming WebSocket message by extracting its type and emitting.
   *
   * @param message - The raw WebSocket message (parsed JSON)
   * @returns true if the message was handled, false if type was unknown
   *
   * @example
   * ```ts
   * ws.onmessage = (event) => {
   *   const message = JSON.parse(event.data);
   *   const handled = emitter.handleMessage(message);
   *   if (!handled) {
   *     console.warn('Unknown message type:', message);
   *   }
   * };
   * ```
   */
  handleMessage(message: unknown): boolean {
    const eventType = extractEventType(message);

    if (!eventType) {
      return false;
    }

    // Extract payload - for messages with data field, use data; otherwise use message
    const msg = message as Record<string, unknown>;
    const payload = 'data' in msg && msg.data !== undefined ? msg.data : message;

    this.emit(eventType, payload as WebSocketEventMap[typeof eventType]);

    return true;
  }

  /**
   * Check if there are any handlers for an event.
   *
   * @param event - The event key to check
   * @returns true if there are handlers registered
   */
  has(event: WebSocketEventKey): boolean {
    const eventHandlers = this.handlers.get(event);
    return eventHandlers !== undefined && eventHandlers.size > 0;
  }

  /**
   * Get the number of handlers for an event.
   *
   * @param event - The event key to check
   * @returns Number of registered handlers
   */
  listenerCount(event: WebSocketEventKey): number {
    return this.handlers.get(event)?.size ?? 0;
  }

  /**
   * Remove all handlers for a specific event.
   *
   * @param event - The event key to clear handlers for
   */
  removeAllListeners(event: WebSocketEventKey): void {
    this.handlers.delete(event);
  }

  /**
   * Remove all handlers for all events.
   */
  clear(): void {
    this.handlers.clear();
  }

  /**
   * Get all event keys that have registered handlers.
   *
   * @returns Array of event keys with handlers
   */
  events(): WebSocketEventKey[] {
    return Array.from(this.handlers.keys());
  }
}

/**
 * Type guard to validate an event key at runtime before emitting.
 *
 * @param emitter - The typed emitter instance
 * @param event - The event key to validate
 * @param data - The payload data
 * @returns true if the event was emitted successfully
 *
 * @example
 * ```ts
 * const type = messageObj.type;
 * if (safeEmit(emitter, type, data)) {
 *   // Event was emitted
 * }
 * ```
 */
export function safeEmit(
  emitter: TypedWebSocketEmitter,
  event: unknown,
  data: unknown
): boolean {
  if (!isWebSocketEventKey(event)) {
    return false;
  }

  emitter.emit(event, data as WebSocketEventMap[typeof event]);
  return true;
}

/**
 * Create a typed emitter instance.
 * Factory function for cleaner instantiation.
 */
export function createTypedEmitter(): TypedWebSocketEmitter {
  return new TypedWebSocketEmitter();
}
