/**
 * WebSocket Connection Manager
 *
 * Provides connection deduplication with reference counting for WebSocket connections.
 * Multiple components subscribing to the same WebSocket URL will share a single
 * underlying connection. The connection is only closed when all subscribers disconnect.
 *
 * Features:
 * - Connection deduplication with reference counting
 * - Automatic reconnection with exponential backoff
 * - Heartbeat/ping-pong support
 * - Comprehensive logging with message IDs and connection IDs
 */

import { TypedWebSocketEmitter } from './typedEventEmitter';
import { logger } from '../services/logger';

import type { WebSocketEventHandler, WebSocketEventKey } from '../types/websocket-events';

// ============================================================================
// Message ID Generation
// ============================================================================

/**
 * Generate a unique message ID for tracking WebSocket messages.
 * Format: msg-{timestamp_base36}-{random_5chars}
 */
export function generateMessageId(): string {
  return `msg-${Date.now().toString(36)}-${Math.random().toString(36).substr(2, 5)}`;
}

/**
 * Generate a unique connection ID for tracking WebSocket connections.
 * Format: ws-{timestamp_base36}-{random_5chars}
 */
export function generateConnectionId(): string {
  return `ws-${Date.now().toString(36)}-${Math.random().toString(36).substr(2, 5)}`;
}

export type MessageHandler = (data: unknown) => void;
export type OpenHandler = () => void;
export type CloseHandler = () => void;
export type ErrorHandler = (error: Event) => void;
export type HeartbeatHandler = () => void;
export type MaxRetriesHandler = () => void;

/**
 * Subscriber configuration for a WebSocket connection.
 */
export interface Subscriber {
  /** Unique identifier for this subscriber */
  id: string;
  /** Called when a message is received (excluding heartbeat messages) */
  onMessage?: MessageHandler;
  /** Called when the connection is established */
  onOpen?: OpenHandler;
  /** Called when the connection is closed */
  onClose?: CloseHandler;
  /** Called when an error occurs */
  onError?: ErrorHandler;
  /** Called when a heartbeat (ping) message is received */
  onHeartbeat?: HeartbeatHandler;
  /** Called when max reconnection attempts are exhausted */
  onMaxRetriesExhausted?: MaxRetriesHandler;
}

/**
 * Internal representation of a managed WebSocket connection.
 */
export interface ManagedConnection {
  ws: WebSocket | null;
  subscribers: Map<string, Subscriber>;
  refCount: number;
  isConnecting: boolean;
  reconnectAttempts: number;
  reconnectTimeout: ReturnType<typeof setTimeout> | null;
  connectionTimeout: ReturnType<typeof setTimeout> | null;
  lastHeartbeat: Date | null;
  /** Unique connection ID for logging and tracking */
  connectionId: string;
  /** Timestamp of the last pong received (for heartbeat timeout detection) */
  lastPongTime: number | null;
}

/**
 * Configuration for WebSocket connection behavior.
 */
export interface ConnectionConfig {
  /** Whether to automatically reconnect on disconnect */
  reconnect: boolean;
  /** Base interval for reconnection attempts (with exponential backoff) */
  reconnectInterval: number;
  /** Maximum number of reconnection attempts */
  maxReconnectAttempts: number;
  /** Timeout for initial connection in ms */
  connectionTimeout: number;
  /** Whether to automatically respond to server heartbeats with pong */
  autoRespondToHeartbeat: boolean;
}

/**
 * Heartbeat message structure from the server.
 */
interface HeartbeatMessage {
  type: 'ping';
}

/**
 * Pong response structure to send back to server.
 */
interface PongMessage {
  type: 'pong';
}

/**
 * Check if a message is a server heartbeat (ping) message.
 */
function isHeartbeatMessage(data: unknown): data is HeartbeatMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;
  return msg.type === 'ping';
}

/**
 * Calculate exponential backoff delay with jitter.
 */
function calculateBackoffDelay(
  attempt: number,
  baseInterval: number,
  maxInterval: number = 30000
): number {
  const exponentialDelay = baseInterval * Math.pow(2, attempt);
  const cappedDelay = Math.min(exponentialDelay, maxInterval);
  const jitter = Math.random() * 0.25 * cappedDelay;
  return Math.floor(cappedDelay + jitter);
}

/**
 * Counter for generating unique subscriber IDs.
 */
let subscriberCounter = 0;

/**
 * Generate a unique subscriber ID.
 */
export function generateSubscriberId(): string {
  subscriberCounter += 1;
  return `ws-sub-${subscriberCounter}-${Date.now()}`;
}

/**
 * Reset the subscriber counter (for testing purposes).
 */
export function resetSubscriberCounter(): void {
  subscriberCounter = 0;
}

/**
 * WebSocket Connection Manager
 *
 * Singleton class that manages WebSocket connections with deduplication.
 * Multiple subscribers to the same URL share a single underlying connection.
 */
class WebSocketManager {
  private connections: Map<string, ManagedConnection> = new Map();
  private configs: Map<string, ConnectionConfig> = new Map();

  /**
   * Subscribe to a WebSocket URL.
   */
  subscribe(url: string, subscriber: Subscriber, config: ConnectionConfig): () => void {
    let connection = this.connections.get(url);

    if (!connection) {
      connection = {
        ws: null,
        subscribers: new Map(),
        refCount: 0,
        isConnecting: false,
        reconnectAttempts: 0,
        reconnectTimeout: null,
        connectionTimeout: null,
        lastHeartbeat: null,
        connectionId: '',
        lastPongTime: null,
      };
      this.connections.set(url, connection);
      this.configs.set(url, config);
    }

    connection.subscribers.set(subscriber.id, subscriber);
    connection.refCount += 1;

    if (
      !connection.ws ||
      (connection.ws.readyState !== WebSocket.OPEN &&
        connection.ws.readyState !== WebSocket.CONNECTING)
    ) {
      this.connect(url);
    } else if (connection.ws.readyState === WebSocket.OPEN) {
      subscriber.onOpen?.();
    }

    return () => this.unsubscribe(url, subscriber.id);
  }

  private unsubscribe(url: string, subscriberId: string): void {
    const connection = this.connections.get(url);
    if (!connection) {
      return;
    }

    connection.subscribers.delete(subscriberId);
    connection.refCount -= 1;

    if (connection.refCount <= 0) {
      this.closeConnection(url);
    }
  }

  send(url: string, data: unknown): boolean {
    const connection = this.connections.get(url);

    if (!connection?.ws || connection.ws.readyState !== WebSocket.OPEN) {
      logger.warn('WebSocket is not connected. Message not sent', {
        component: 'WebSocketManager',
        url,
        connection_id: connection?.connectionId || 'none',
      });
      return false;
    }

    const messageId = generateMessageId();
    const message = typeof data === 'string' ? data : JSON.stringify(data);

    // Extract message type for logging (don't log full payload for privacy)
    const messageType =
      typeof data === 'object' && data !== null && 'type' in data
        ? (data as { type: unknown }).type
        : 'unknown';

    logger.debug('WebSocket message sent', {
      component: 'WebSocketManager',
      message_id: messageId,
      connection_id: connection.connectionId,
      type: messageType,
    });

    connection.ws.send(message);
    return true;
  }

  getConnectionState(url: string): {
    isConnected: boolean;
    reconnectCount: number;
    hasExhaustedRetries: boolean;
    lastHeartbeat: Date | null;
    connectionId: string;
    lastPongTime: number | null;
  } {
    const connection = this.connections.get(url);
    const config = this.configs.get(url);

    if (!connection) {
      return {
        isConnected: false,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
        connectionId: '',
        lastPongTime: null,
      };
    }

    return {
      isConnected: connection.ws?.readyState === WebSocket.OPEN,
      reconnectCount: connection.reconnectAttempts,
      hasExhaustedRetries: connection.reconnectAttempts >= (config?.maxReconnectAttempts ?? 5),
      lastHeartbeat: connection.lastHeartbeat,
      connectionId: connection.connectionId,
      lastPongTime: connection.lastPongTime,
    };
  }

  reconnect(url: string): void {
    const connection = this.connections.get(url);
    if (!connection || connection.refCount <= 0) {
      return;
    }

    connection.reconnectAttempts = 0;
    this.connect(url);
  }

  private connect(url: string): void {
    if (typeof window === 'undefined' || !window.WebSocket) {
      return;
    }

    const connection = this.connections.get(url);
    const config = this.configs.get(url);

    if (!connection || !config) {
      return;
    }

    if (
      connection.ws?.readyState === WebSocket.OPEN ||
      connection.ws?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    // Generate a new connection ID for this connection attempt
    connection.connectionId = generateConnectionId();
    connection.isConnecting = true;
    connection.lastPongTime = null;

    // Log reconnection attempt if this is a retry
    if (connection.reconnectAttempts > 0) {
      const delay = calculateBackoffDelay(
        connection.reconnectAttempts - 1,
        config.reconnectInterval
      );
      logger.warn('WebSocket reconnecting', {
        component: 'WebSocketManager',
        connection_id: connection.connectionId,
        url,
        attempt: connection.reconnectAttempts,
        max_attempts: config.maxReconnectAttempts,
        delay_ms: delay,
      });
    }

    try {
      const ws = new WebSocket(url);
      connection.ws = ws;

      if (config.connectionTimeout > 0) {
        connection.connectionTimeout = setTimeout(() => {
          if (ws.readyState === WebSocket.CONNECTING) {
            logger.warn('WebSocket connection timeout, retrying', {
              component: 'WebSocketManager',
              connection_id: connection.connectionId,
              url,
              timeoutMs: config.connectionTimeout,
            });
            ws.close();
          }
        }, config.connectionTimeout);
      }

      ws.onopen = () => {
        if (connection.connectionTimeout) {
          clearTimeout(connection.connectionTimeout);
          connection.connectionTimeout = null;
        }

        connection.isConnecting = false;
        const previousAttempts = connection.reconnectAttempts;
        connection.reconnectAttempts = 0;
        connection.lastPongTime = Date.now();

        logger.info('WebSocket connected', {
          component: 'WebSocketManager',
          connection_id: connection.connectionId,
          url,
          reconnect_attempt: previousAttempts,
        });

        connection.subscribers.forEach((subscriber) => {
          subscriber.onOpen?.();
        });
      };

      ws.onclose = (event: CloseEvent) => {
        if (connection.connectionTimeout) {
          clearTimeout(connection.connectionTimeout);
          connection.connectionTimeout = null;
        }

        connection.isConnecting = false;

        logger.info('WebSocket disconnected', {
          component: 'WebSocketManager',
          connection_id: connection.connectionId,
          url,
          code: event.code,
          reason: event.reason || 'No reason provided',
          was_clean: event.wasClean,
        });

        // Check if we should reconnect and update attempt count BEFORE notifying subscribers
        // This ensures subscribers get the correct reconnect count
        let shouldReconnect = false;
        if (
          connection.refCount > 0 &&
          config.reconnect &&
          connection.reconnectAttempts < config.maxReconnectAttempts
        ) {
          connection.reconnectAttempts += 1;
          shouldReconnect = true;
        }

        // Notify subscribers of close (with updated reconnect count)
        connection.subscribers.forEach((subscriber) => {
          subscriber.onClose?.();
        });

        // Schedule reconnection if needed
        if (shouldReconnect) {
          const delay = calculateBackoffDelay(
            connection.reconnectAttempts - 1,
            config.reconnectInterval
          );

          connection.reconnectTimeout = setTimeout(() => {
            this.connect(url);
          }, delay);
        } else if (
          connection.refCount > 0 &&
          config.reconnect &&
          connection.reconnectAttempts >= config.maxReconnectAttempts
        ) {
          logger.error('WebSocket max retries exhausted', {
            component: 'WebSocketManager',
            connection_id: connection.connectionId,
            url,
            total_attempts: connection.reconnectAttempts,
          });

          connection.subscribers.forEach((subscriber) => {
            subscriber.onMaxRetriesExhausted?.();
          });
        }
      };

      ws.onerror = (error: Event) => {
        logger.error('WebSocket error', {
          component: 'WebSocketManager',
          connection_id: connection.connectionId,
          url,
          error_type: error.type,
        });

        connection.subscribers.forEach((subscriber) => {
          subscriber.onError?.(error);
        });
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as unknown;

          // Extract message_id and type for logging
          const messageId =
            typeof data === 'object' && data !== null && 'message_id' in data
              ? (data as { message_id: unknown }).message_id
              : undefined;
          const messageType =
            typeof data === 'object' && data !== null && 'type' in data
              ? (data as { type: unknown }).type
              : 'unknown';
          const timestamp =
            typeof data === 'object' && data !== null && 'timestamp' in data
              ? (data as { timestamp: number }).timestamp
              : undefined;

          // Calculate latency if timestamp is provided
          const latencyMs = timestamp ? Date.now() - timestamp : undefined;

          if (isHeartbeatMessage(data)) {
            connection.lastHeartbeat = new Date();
            connection.lastPongTime = Date.now();

            logger.debug('WebSocket heartbeat received', {
              component: 'WebSocketManager',
              connection_id: connection.connectionId,
            });

            if (config.autoRespondToHeartbeat && ws.readyState === WebSocket.OPEN) {
              const pongMessage: PongMessage = { type: 'pong' };
              ws.send(JSON.stringify(pongMessage));

              logger.debug('WebSocket heartbeat sent (pong)', {
                component: 'WebSocketManager',
                connection_id: connection.connectionId,
              });
            }

            connection.subscribers.forEach((subscriber) => {
              subscriber.onHeartbeat?.();
            });

            return;
          }

          logger.debug('WebSocket message received', {
            component: 'WebSocketManager',
            connection_id: connection.connectionId,
            message_id: messageId || 'unknown',
            type: messageType,
            latency_ms: latencyMs,
          });

          connection.subscribers.forEach((subscriber) => {
            subscriber.onMessage?.(data);
          });
        } catch {
          logger.debug('WebSocket message received (non-JSON)', {
            component: 'WebSocketManager',
            connection_id: connection.connectionId,
          });

          connection.subscribers.forEach((subscriber) => {
            subscriber.onMessage?.(event.data as unknown);
          });
        }
      };
    } catch (error) {
      logger.error('WebSocket connection error', {
        component: 'WebSocketManager',
        connection_id: connection.connectionId,
        url,
        error,
      });
      connection.isConnecting = false;
    }
  }

  private closeConnection(url: string): void {
    const connection = this.connections.get(url);
    if (!connection) {
      return;
    }

    if (connection.reconnectTimeout) {
      clearTimeout(connection.reconnectTimeout);
      connection.reconnectTimeout = null;
    }
    if (connection.connectionTimeout) {
      clearTimeout(connection.connectionTimeout);
      connection.connectionTimeout = null;
    }

    if (connection.ws) {
      connection.ws.close();
      connection.ws = null;
    }

    this.connections.delete(url);
    this.configs.delete(url);
  }

  getSubscriberCount(url: string): number {
    return this.connections.get(url)?.refCount ?? 0;
  }

  hasConnection(url: string): boolean {
    return this.connections.has(url);
  }

  clearAll(): void {
    this.connections.forEach((_, url) => {
      this.closeConnection(url);
    });
  }

  reset(): void {
    this.clearAll();
    resetSubscriberCounter();
  }
}

export const webSocketManager = new WebSocketManager();

export { WebSocketManager, isHeartbeatMessage, calculateBackoffDelay };

// ============================================================================
// Typed Event Emitter Integration
// ============================================================================

/**
 * Options for creating a typed subscription.
 */
export interface TypedSubscriberOptions {
  /** Called when the connection is established */
  onOpen?: OpenHandler;
  /** Called when the connection is closed */
  onClose?: CloseHandler;
  /** Called when an error occurs */
  onError?: ErrorHandler;
  /** Called when a heartbeat (ping) message is received */
  onHeartbeat?: HeartbeatHandler;
  /** Called when max reconnection attempts are exhausted */
  onMaxRetriesExhausted?: MaxRetriesHandler;
}

/**
 * Typed subscription wrapper that combines WebSocketManager's connection
 * management with TypedWebSocketEmitter's type-safe event handling.
 */
export interface TypedSubscription {
  /** Unsubscribe from the WebSocket connection */
  unsubscribe: () => void;
  /** The typed event emitter for this subscription */
  emitter: TypedWebSocketEmitter;
  /** Subscribe to a specific event type with type safety */
  on: <K extends WebSocketEventKey>(event: K, handler: WebSocketEventHandler<K>) => () => void;
  /** Unsubscribe from a specific event type */
  off: <K extends WebSocketEventKey>(event: K, handler: WebSocketEventHandler<K>) => void;
  /** Subscribe to an event that fires only once */
  once: <K extends WebSocketEventKey>(event: K, handler: WebSocketEventHandler<K>) => () => void;
  /** Send data through the WebSocket connection */
  send: (data: unknown) => boolean;
  /** Get the current connection state */
  getState: () => {
    isConnected: boolean;
    reconnectCount: number;
    hasExhaustedRetries: boolean;
    lastHeartbeat: Date | null;
    connectionId: string;
    lastPongTime: number | null;
  };
}

/**
 * Create a typed subscription to a WebSocket URL.
 *
 * This function wraps WebSocketManager's subscribe method with a TypedWebSocketEmitter,
 * providing type-safe event handling while benefiting from connection deduplication
 * and automatic reconnection.
 *
 * @param url - The WebSocket URL to connect to
 * @param config - Connection configuration (reconnect behavior, timeouts, etc.)
 * @param options - Optional callbacks for connection lifecycle events
 * @returns A TypedSubscription object with type-safe event methods
 *
 * @example
 * ```ts
 * const subscription = createTypedSubscription(
 *   'ws://localhost:8000/ws/events',
 *   { reconnect: true, reconnectInterval: 1000, maxReconnectAttempts: 5, connectionTimeout: 5000, autoRespondToHeartbeat: true },
 *   { onOpen: () => console.log('Connected') }
 * );
 *
 * // Type-safe event subscription
 * subscription.on('event', (data) => {
 *   // data is typed as SecurityEventData
 *   console.log(data.risk_score);
 * });
 *
 * // Cleanup
 * subscription.unsubscribe();
 * ```
 */
export function createTypedSubscription(
  url: string,
  config: ConnectionConfig,
  options: TypedSubscriberOptions = {}
): TypedSubscription {
  const emitter = new TypedWebSocketEmitter();
  const subscriberId = generateSubscriberId();

  const subscriber: Subscriber = {
    id: subscriberId,
    onMessage: (data: unknown) => {
      emitter.handleMessage(data);
    },
    onOpen: options.onOpen,
    onClose: options.onClose,
    onError: options.onError,
    onHeartbeat: () => {
      // Emit ping event to typed emitter
      emitter.emit('ping', { type: 'ping' });
      // Also call the user's heartbeat handler if provided
      options.onHeartbeat?.();
    },
    onMaxRetriesExhausted: options.onMaxRetriesExhausted,
  };

  const unsubscribe = webSocketManager.subscribe(url, subscriber, config);

  return {
    unsubscribe: () => {
      emitter.clear();
      unsubscribe();
    },
    emitter,
    on: <K extends WebSocketEventKey>(event: K, handler: WebSocketEventHandler<K>) =>
      emitter.on(event, handler),
    off: <K extends WebSocketEventKey>(event: K, handler: WebSocketEventHandler<K>) =>
      emitter.off(event, handler),
    once: <K extends WebSocketEventKey>(event: K, handler: WebSocketEventHandler<K>) =>
      emitter.once(event, handler),
    send: (data: unknown) => webSocketManager.send(url, data),
    getState: () => webSocketManager.getConnectionState(url),
  };
}
