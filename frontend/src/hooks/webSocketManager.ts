/**
 * WebSocket Connection Manager
 *
 * Provides connection deduplication with reference counting for WebSocket connections.
 * Multiple components subscribing to the same WebSocket URL will share a single
 * underlying connection. The connection is only closed when all subscribers disconnect.
 */

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
  type: "ping";
}

/**
 * Pong response structure to send back to server.
 */
interface PongMessage {
  type: "pong";
}

/**
 * Check if a message is a server heartbeat (ping) message.
 */
function isHeartbeatMessage(data: unknown): data is HeartbeatMessage {
  if (!data || typeof data !== "object") {
    return false;
  }
  const msg = data as Record<string, unknown>;
  return msg.type === "ping";
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
  subscribe(
    url: string,
    subscriber: Subscriber,
    config: ConnectionConfig
  ): () => void {
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
      console.warn("WebSocket is not connected. Message not sent:", data);
      return false;
    }

    const message = typeof data === "string" ? data : JSON.stringify(data);
    connection.ws.send(message);
    return true;
  }

  getConnectionState(url: string): {
    isConnected: boolean;
    reconnectCount: number;
    hasExhaustedRetries: boolean;
    lastHeartbeat: Date | null;
  } {
    const connection = this.connections.get(url);
    const config = this.configs.get(url);

    if (!connection) {
      return {
        isConnected: false,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      };
    }

    return {
      isConnected: connection.ws?.readyState === WebSocket.OPEN,
      reconnectCount: connection.reconnectAttempts,
      hasExhaustedRetries:
        connection.reconnectAttempts >= (config?.maxReconnectAttempts ?? 5),
      lastHeartbeat: connection.lastHeartbeat,
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
    if (typeof window === "undefined" || !window.WebSocket) {
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

    connection.isConnecting = true;

    try {
      const ws = new WebSocket(url);
      connection.ws = ws;

      if (config.connectionTimeout > 0) {
        connection.connectionTimeout = setTimeout(() => {
          if (ws.readyState === WebSocket.CONNECTING) {
            console.warn(
              `WebSocket connection timeout after ${config.connectionTimeout}ms, retrying...`
            );
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
        connection.reconnectAttempts = 0;

        connection.subscribers.forEach((subscriber) => {
          subscriber.onOpen?.();
        });
      };

      ws.onclose = () => {
        if (connection.connectionTimeout) {
          clearTimeout(connection.connectionTimeout);
          connection.connectionTimeout = null;
        }

        connection.isConnecting = false;

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
          connection.subscribers.forEach((subscriber) => {
            subscriber.onMaxRetriesExhausted?.();
          });
        }
      };

      ws.onerror = (error: Event) => {
        connection.subscribers.forEach((subscriber) => {
          subscriber.onError?.(error);
        });
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as unknown;

          if (isHeartbeatMessage(data)) {
            connection.lastHeartbeat = new Date();

            if (config.autoRespondToHeartbeat && ws.readyState === WebSocket.OPEN) {
              const pongMessage: PongMessage = { type: "pong" };
              ws.send(JSON.stringify(pongMessage));
            }

            connection.subscribers.forEach((subscriber) => {
              subscriber.onHeartbeat?.();
            });

            return;
          }

          connection.subscribers.forEach((subscriber) => {
            subscriber.onMessage?.(data);
          });
        } catch {
          connection.subscribers.forEach((subscriber) => {
            subscriber.onMessage?.(event.data as unknown);
          });
        }
      };
    } catch (error) {
      console.error("WebSocket connection error:", error);
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
