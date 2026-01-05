import { useEffect, useRef, useState, useCallback } from 'react';

import {
  webSocketManager,
  generateSubscriberId,
  isHeartbeatMessage,
  calculateBackoffDelay,
} from './webSocketManager';

export interface WebSocketOptions {
  url: string;
  /**
   * Sec-WebSocket-Protocol header values for authentication.
   * When API key authentication is enabled, use ["api-key.{key}"] format.
   * This is more secure than passing the API key in the URL query string.
   * Note: protocols are not yet supported by the manager - this option is reserved for future use.
   */
  protocols?: string[];
  onMessage?: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  /** Called when max reconnection attempts are exhausted */
  onMaxRetriesExhausted?: () => void;
  /** Called when a heartbeat (ping) message is received from the server */
  onHeartbeat?: () => void;
  reconnect?: boolean;
  /** Base reconnection interval in ms (will be used with exponential backoff) */
  reconnectInterval?: number;
  reconnectAttempts?: number;
  /** Connection timeout in ms - close and retry if connection hangs */
  connectionTimeout?: number;
  /** Whether to automatically respond to server heartbeats with pong (default: true) */
  autoRespondToHeartbeat?: boolean;
}

export interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: unknown;
  send: (data: unknown) => void;
  connect: () => void;
  disconnect: () => void;
  /** True if max reconnection attempts have been exhausted */
  hasExhaustedRetries: boolean;
  /** Current reconnection attempt count */
  reconnectCount: number;
  /** Timestamp of the last heartbeat received from the server */
  lastHeartbeat: Date | null;
}

export function useWebSocket(options: WebSocketOptions): UseWebSocketReturn {
  const {
    url,
    // Note: protocols not yet supported by manager - may need to add later
    onMessage,
    onOpen,
    onClose,
    onError,
    onMaxRetriesExhausted,
    onHeartbeat,
    reconnect = true,
    reconnectInterval = 1000,
    // Default to 15 attempts for better resilience during backend restarts
    // With exponential backoff (1s base, 30s max), this provides ~8+ minutes of retry
    reconnectAttempts = 15,
    connectionTimeout = 10000,
    autoRespondToHeartbeat = true,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<unknown>(null);
  const [hasExhaustedRetries, setHasExhaustedRetries] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const [lastHeartbeat, setLastHeartbeat] = useState<Date | null>(null);

  const subscriberIdRef = useRef(generateSubscriberId());
  const unsubscribeRef = useRef<(() => void) | null>(null);

  // Store callbacks in refs to avoid stale closures
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  const onErrorRef = useRef(onError);
  const onMaxRetriesExhaustedRef = useRef(onMaxRetriesExhausted);
  const onHeartbeatRef = useRef(onHeartbeat);

  // Update refs when callbacks change
  useEffect(() => {
    onMessageRef.current = onMessage;
    onOpenRef.current = onOpen;
    onCloseRef.current = onClose;
    onErrorRef.current = onError;
    onMaxRetriesExhaustedRef.current = onMaxRetriesExhausted;
    onHeartbeatRef.current = onHeartbeat;
  });

  const connect = useCallback(() => {
    // Don't reconnect if already subscribed
    if (unsubscribeRef.current) {
      return;
    }

    setHasExhaustedRetries(false);

    unsubscribeRef.current = webSocketManager.subscribe(
      url,
      {
        id: subscriberIdRef.current,
        onMessage: (data) => {
          setLastMessage(data);
          onMessageRef.current?.(data);
        },
        onOpen: () => {
          setIsConnected(true);
          setReconnectCount(0);
          setHasExhaustedRetries(false);
          onOpenRef.current?.();
        },
        onClose: () => {
          setIsConnected(false);
          // Update reconnect count from manager state
          const state = webSocketManager.getConnectionState(url);
          setReconnectCount(state.reconnectCount);
          onCloseRef.current?.();
        },
        onError: (error) => {
          onErrorRef.current?.(error);
        },
        onHeartbeat: () => {
          const state = webSocketManager.getConnectionState(url);
          setLastHeartbeat(state.lastHeartbeat);
          onHeartbeatRef.current?.();
        },
        onMaxRetriesExhausted: () => {
          setHasExhaustedRetries(true);
          onMaxRetriesExhaustedRef.current?.();
        },
      },
      {
        reconnect,
        reconnectInterval,
        maxReconnectAttempts: reconnectAttempts,
        connectionTimeout,
        autoRespondToHeartbeat,
      }
    );
  }, [url, reconnect, reconnectInterval, reconnectAttempts, connectionTimeout, autoRespondToHeartbeat]);

  const disconnect = useCallback(() => {
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const send = useCallback(
    (data: unknown) => {
      if (!webSocketManager.send(url, data)) {
        console.warn('WebSocket is not connected. Message not sent:', data);
      }
    },
    [url]
  );

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    send,
    connect,
    disconnect,
    hasExhaustedRetries,
    reconnectCount,
    lastHeartbeat,
  };
}

// Export type guard and backoff function for testing and backward compatibility
export { isHeartbeatMessage, calculateBackoffDelay };
