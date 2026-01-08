/**
 * Typed WebSocket Event Emitter
 *
 * A type-safe event emitter for WebSocket messages that provides compile-time
 * type checking for event subscriptions and emissions. This ensures that event
 * handlers receive correctly typed payloads.
 *
 * @example
 * ```ts
 * const emitter = new TypedWebSocketEmitter();
 *
 * // Type-safe subscription - TypeScript knows `data` is SecurityEventData
 * emitter.on('event', (data) => {
 *   console.log(data.risk_score);
 * });
 *
 * // Type-safe emission - TypeScript enforces correct payload type
 * emitter.emit('event', {
 *   id: '123',
 *   camera_id: 'front_door',
 *   risk_score: 75,
 *   risk_level: 'high',
 *   summary: 'Person detected',
 * });
 * ```
 */

import { logger } from '../services/logger';
import { isWebSocketEventKey } from '../types/websocket-events';

import type {
  WebSocketEventMap,
  WebSocketEventKey,
  WebSocketEventHandler,
} from '../types/websocket-events';

/**
 * TypedWebSocketEmitter - A type-safe event emitter for WebSocket messages.
 *
 * Features:
 * - Full TypeScript type safety for event keys and payloads
 * - Prevents duplicate handlers for the same event
 * - Graceful error handling (handlers that throw don't break other handlers)
 * - One-time subscriptions via `once()`
 * - Handles raw WebSocket messages via `handleMessage()`
 */
export class TypedWebSocketEmitter {
  /**
   * Internal storage for event handlers.
   * Uses Set to prevent duplicate handlers and provide O(1) add/remove.
   */
  private handlers: Map<WebSocketEventKey, Set<WebSocketEventHandler<WebSocketEventKey>>> =
    new Map();

  /**
   * Subscribe to an event type.
   *
   * @param event - The event key to subscribe to
   * @param handler - The handler function to call when the event is emitted
   * @returns An unsubscribe function
   *
   * @example
   * ```ts
   * const unsubscribe = emitter.on('event', (data) => {
   *   console.log(data.risk_score);
   * });
   *
   * // Later, to unsubscribe:
   * unsubscribe();
   * ```
   */
  on<K extends WebSocketEventKey>(event: K, handler: WebSocketEventHandler<K>): () => void {
    let handlers = this.handlers.get(event);
    if (!handlers) {
      handlers = new Set();
      this.handlers.set(event, handlers);
    }

    // Cast is safe because we're adding to the correct event key's set
    handlers.add(handler as WebSocketEventHandler<WebSocketEventKey>);

    // Return unsubscribe function
    return () => this.off(event, handler);
  }

  /**
   * Unsubscribe a handler from an event type.
   *
   * @param event - The event key to unsubscribe from
   * @param handler - The handler function to remove
   *
   * @example
   * ```ts
   * const handler = (data) => console.log(data);
   * emitter.on('event', handler);
   *
   * // Later, to unsubscribe:
   * emitter.off('event', handler);
   * ```
   */
  off<K extends WebSocketEventKey>(event: K, handler: WebSocketEventHandler<K>): void {
    const handlers = this.handlers.get(event);
    if (handlers) {
      handlers.delete(handler as WebSocketEventHandler<WebSocketEventKey>);
      // Clean up empty sets
      if (handlers.size === 0) {
        this.handlers.delete(event);
      }
    }
  }

  /**
   * Emit an event to all subscribed handlers.
   *
   * @param event - The event key to emit
   * @param data - The payload to pass to handlers (must match the event's type)
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
    const handlers = this.handlers.get(event);
    if (!handlers) {
      return;
    }

    // Create a copy of handlers to allow safe modification during iteration
    const handlersCopy = Array.from(handlers);

    for (const handler of handlersCopy) {
      try {
        // Cast is safe because we stored with the correct type
        (handler as WebSocketEventHandler<K>)(data);
      } catch (error) {
        // Log error but don't break other handlers
        logger.error('Error in WebSocket event handler', {
          component: 'TypedWebSocketEmitter',
          event,
          error,
        });
      }
    }
  }

  /**
   * Subscribe to an event type for one-time delivery.
   * The handler will be automatically unsubscribed after the first event.
   *
   * @param event - The event key to subscribe to
   * @param handler - The handler function to call once
   * @returns An unsubscribe function (can be called to cancel before event fires)
   *
   * @example
   * ```ts
   * // Handler will only be called once
   * emitter.once('event', (data) => {
   *   console.log('First event:', data);
   * });
   * ```
   */
  once<K extends WebSocketEventKey>(event: K, handler: WebSocketEventHandler<K>): () => void {
    const wrappedHandler: WebSocketEventHandler<K> = (data) => {
      // Remove the handler first to ensure it's only called once
      // even if the handler itself triggers another emit
      this.off(event, wrappedHandler);
      handler(data);
    };

    return this.on(event, wrappedHandler);
  }

  /**
   * Check if an event has any listeners.
   *
   * @param event - The event key to check
   * @returns True if the event has at least one listener
   */
  has<K extends WebSocketEventKey>(event: K): boolean {
    const handlers = this.handlers.get(event);
    return handlers !== undefined && handlers.size > 0;
  }

  /**
   * Get the number of listeners for an event.
   *
   * @param event - The event key to check
   * @returns The number of listeners for the event
   */
  listenerCount<K extends WebSocketEventKey>(event: K): number {
    return this.handlers.get(event)?.size ?? 0;
  }

  /**
   * Remove all listeners for a specific event.
   *
   * @param event - The event key to clear
   */
  removeAllListeners<K extends WebSocketEventKey>(event: K): void {
    this.handlers.delete(event);
  }

  /**
   * Remove all listeners for all events.
   */
  clear(): void {
    this.handlers.clear();
  }

  /**
   * Get all event keys that have listeners.
   *
   * @returns Array of event keys with at least one listener
   */
  events(): WebSocketEventKey[] {
    return Array.from(this.handlers.keys());
  }

  /**
   * Handle a raw WebSocket message.
   * Parses the message type and emits to the appropriate handlers.
   *
   * This method supports two message formats:
   * 1. Envelope format: `{ type: 'event', data: { ... } }`
   * 2. Direct format: `{ type: 'ping' }` (for messages without data payload)
   *
   * @param message - The raw message to handle (already parsed from JSON)
   * @returns True if the message was handled, false if it was invalid or unknown
   *
   * @example
   * ```ts
   * ws.onmessage = (event) => {
   *   const data = JSON.parse(event.data);
   *   if (emitter.handleMessage(data)) {
   *     console.log('Message handled');
   *   } else {
   *     console.log('Unknown message type');
   *   }
   * };
   * ```
   */
  handleMessage(message: unknown): boolean {
    // Validate message is an object
    if (typeof message !== 'object' || message === null) {
      return false;
    }

    // Extract type from message
    const msgObj = message as Record<string, unknown>;
    const eventType = msgObj.type;

    // Validate type is a known event key
    if (!isWebSocketEventKey(eventType)) {
      return false;
    }

    // Determine the payload to emit
    // Messages with a 'data' field use envelope format
    // Messages without 'data' (like ping/pong) use the entire message as payload
    const payload = 'data' in msgObj ? msgObj.data : message;

    // Emit the event (cast is safe because we validated the event type)
    this.emit(eventType, payload as WebSocketEventMap[typeof eventType]);

    return true;
  }
}

/**
 * Default singleton instance for shared use.
 * Applications can import this for simple cases or create their own instances
 * for isolated event handling.
 */
export const typedEventEmitter = new TypedWebSocketEmitter();

// Re-export types for convenience
export type {
  WebSocketEventMap,
  WebSocketEventKey,
  WebSocketEventHandler,
} from '../types/websocket-events';
