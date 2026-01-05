import { useEffect, useRef, useState, useCallback } from 'react';

export type ConnectionState = 'connected' | 'disconnected' | 'reconnecting' | 'failed';

export interface ChannelStatus {
  name: string;
  state: ConnectionState;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  lastMessageTime: Date | null;
  /** True when max reconnection attempts have been exhausted */
  hasExhaustedRetries: boolean;
}

export interface WebSocketStatusOptions {
  url: string;
  /**
   * Sec-WebSocket-Protocol header values for authentication.
   * When API key authentication is enabled, use ["api-key.{key}"] format.
   * This is more secure than passing the API key in the URL query string.
   */
  protocols?: string[];
  channelName: string;
  onMessage?: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  /** Called when max reconnection attempts are exhausted */
  onMaxRetriesExhausted?: () => void;
  reconnect?: boolean;
  /** Base reconnection interval in ms (will be used with exponential backoff) */
  reconnectInterval?: number;
  reconnectAttempts?: number;
  /** Connection timeout in ms - close and retry if connection hangs */
  connectionTimeout?: number;
}

export interface UseWebSocketStatusReturn {
  channelStatus: ChannelStatus;
  lastMessage: unknown;
  send: (data: unknown) => void;
  connect: () => void;
  disconnect: () => void;
}

/**
 * Calculate exponential backoff delay with jitter
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

export function useWebSocketStatus(
  options: WebSocketStatusOptions
): UseWebSocketStatusReturn {
  const {
    url,
    protocols,
    channelName,
    onMessage,
    onOpen,
    onClose,
    onError,
    onMaxRetriesExhausted,
    reconnect = true,
    reconnectInterval = 1000, // Base interval for exponential backoff
    // Default to 15 attempts for better resilience during backend restarts
    // With exponential backoff (1s base, 30s max), this provides ~8+ minutes of retry
    reconnectAttempts = 15,
    connectionTimeout = 10000, // 10 second connection timeout
  } = options;

  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [reconnectCount, setReconnectCount] = useState(0);
  const [lastMessageTime, setLastMessageTime] = useState<Date | null>(null);
  const [lastMessage, setLastMessage] = useState<unknown>(null);
  const [hasExhaustedRetries, setHasExhaustedRetries] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const connectionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldConnectRef = useRef(true);
  const reconnectCountRef = useRef(0);

  const clearAllTimeouts = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (connectionTimeoutRef.current) {
      clearTimeout(connectionTimeoutRef.current);
      connectionTimeoutRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    shouldConnectRef.current = false;
    clearAllTimeouts();

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, [clearAllTimeouts]);

  const connect = useCallback(() => {
    // Check if WebSocket is available (SSR support)
    if (typeof window === 'undefined' || !window.WebSocket) {
      return;
    }

    // Don't create a new connection if already connected or connecting
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    shouldConnectRef.current = true;
    // Reset exhausted state when manually connecting
    setHasExhaustedRetries(false);

    try {
      // Pass protocols to WebSocket constructor for Sec-WebSocket-Protocol header
      // This is used for API key authentication without exposing the key in the URL
      const ws = protocols ? new WebSocket(url, protocols) : new WebSocket(url);
      wsRef.current = ws;

      // Set connection timeout - if we don't connect within timeout, close and retry
      if (connectionTimeout > 0) {
        connectionTimeoutRef.current = setTimeout(() => {
          if (ws.readyState === WebSocket.CONNECTING) {
            console.warn(`[${channelName}] WebSocket connection timeout after ${connectionTimeout}ms, retrying...`);
            ws.close();
          }
        }, connectionTimeout);
      }

      ws.onopen = () => {
        // Clear connection timeout
        if (connectionTimeoutRef.current) {
          clearTimeout(connectionTimeoutRef.current);
          connectionTimeoutRef.current = null;
        }

        setConnectionState('connected');
        reconnectCountRef.current = 0;
        setReconnectCount(0);
        setHasExhaustedRetries(false);
        onOpen?.();
      };

      ws.onclose = () => {
        // Clear connection timeout
        if (connectionTimeoutRef.current) {
          clearTimeout(connectionTimeoutRef.current);
          connectionTimeoutRef.current = null;
        }

        onClose?.();

        // Attempt reconnection if enabled and within retry limits
        if (shouldConnectRef.current && reconnect && reconnectCountRef.current < reconnectAttempts) {
          setConnectionState('reconnecting');

          const currentAttempt = reconnectCountRef.current;
          reconnectCountRef.current += 1;
          setReconnectCount(reconnectCountRef.current);

          // Calculate delay with exponential backoff
          const delay = calculateBackoffDelay(currentAttempt, reconnectInterval);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (shouldConnectRef.current && reconnect && reconnectCountRef.current >= reconnectAttempts) {
          // Max retries exhausted
          setConnectionState('failed');
          setHasExhaustedRetries(true);
          onMaxRetriesExhausted?.();
        } else {
          setConnectionState('disconnected');
        }
      };

      ws.onerror = (error: Event) => {
        onError?.(error);
      };

      ws.onmessage = (event: MessageEvent) => {
        setLastMessageTime(new Date());
        try {
          const data = JSON.parse(event.data as string) as unknown;
          setLastMessage(data);
          onMessage?.(data);
        } catch {
          // If parsing fails, pass the raw data
          setLastMessage(event.data as unknown);
          onMessage?.(event.data as unknown);
        }
      };
    } catch (error) {
      console.error(`[${channelName}] WebSocket connection error:`, error);
      setConnectionState('disconnected');
    }
    // protocols is joined for stable comparison (array contents vs reference)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, protocols?.join(','), channelName, onMessage, onOpen, onClose, onError, onMaxRetriesExhausted, reconnect, reconnectInterval, reconnectAttempts, connectionTimeout]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const message = typeof data === 'string' ? data : JSON.stringify(data);
      wsRef.current.send(message);
    } else {
      console.warn('WebSocket is not connected. Message not sent:', data);
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  const channelStatus: ChannelStatus = {
    name: channelName,
    state: connectionState,
    reconnectAttempts: reconnectCount,
    maxReconnectAttempts: reconnectAttempts,
    lastMessageTime,
    hasExhaustedRetries,
  };

  return {
    channelStatus,
    lastMessage,
    send,
    connect,
    disconnect,
  };
}
