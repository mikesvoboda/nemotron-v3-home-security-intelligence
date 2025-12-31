import { useEffect, useRef, useState, useCallback } from 'react';

export interface WebSocketOptions {
  url: string;
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
}

/**
 * Calculate exponential backoff delay with jitter
 * @param attempt - Current attempt number (0-indexed)
 * @param baseInterval - Base interval in ms
 * @param maxInterval - Maximum interval cap in ms
 * @returns Delay in ms with jitter
 */
function calculateBackoffDelay(
  attempt: number,
  baseInterval: number,
  maxInterval: number = 30000
): number {
  // Exponential backoff: baseInterval * 2^attempt
  const exponentialDelay = baseInterval * Math.pow(2, attempt);
  // Cap at maxInterval
  const cappedDelay = Math.min(exponentialDelay, maxInterval);
  // Add jitter (0-25% of delay) to prevent thundering herd
  const jitter = Math.random() * 0.25 * cappedDelay;
  return Math.floor(cappedDelay + jitter);
}

export function useWebSocket(options: WebSocketOptions): UseWebSocketReturn {
  const {
    url,
    onMessage,
    onOpen,
    onClose,
    onError,
    onMaxRetriesExhausted,
    reconnect = true,
    reconnectInterval = 1000, // Base interval for exponential backoff
    reconnectAttempts = 5,
    connectionTimeout = 10000, // 10 second connection timeout
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<unknown>(null);
  const [hasExhaustedRetries, setHasExhaustedRetries] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const connectionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldConnectRef = useRef(true);

  // Store callbacks in refs to avoid stale closures during reconnection
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  const onErrorRef = useRef(onError);
  const onMaxRetriesExhaustedRef = useRef(onMaxRetriesExhausted);

  // Update refs when callbacks change
  onMessageRef.current = onMessage;
  onOpenRef.current = onOpen;
  onCloseRef.current = onClose;
  onErrorRef.current = onError;
  onMaxRetriesExhaustedRef.current = onMaxRetriesExhausted;

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
      const ws = new WebSocket(url);
      wsRef.current = ws;

      // Set connection timeout - if we don't connect within timeout, close and retry
      if (connectionTimeout > 0) {
        connectionTimeoutRef.current = setTimeout(() => {
          if (ws.readyState === WebSocket.CONNECTING) {
            console.warn(`WebSocket connection timeout after ${connectionTimeout}ms, retrying...`);
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

        setIsConnected(true);
        reconnectCountRef.current = 0;
        setReconnectCount(0);
        setHasExhaustedRetries(false);
        // Use ref to get latest callback
        onOpenRef.current?.();
      };

      ws.onclose = () => {
        // Clear connection timeout
        if (connectionTimeoutRef.current) {
          clearTimeout(connectionTimeoutRef.current);
          connectionTimeoutRef.current = null;
        }

        setIsConnected(false);
        // Use ref to get latest callback
        onCloseRef.current?.();

        // Attempt reconnection if enabled and within retry limits
        if (
          shouldConnectRef.current &&
          reconnect &&
          reconnectCountRef.current < reconnectAttempts
        ) {
          const currentAttempt = reconnectCountRef.current;
          reconnectCountRef.current += 1;
          setReconnectCount(reconnectCountRef.current);

          // Calculate delay with exponential backoff
          const delay = calculateBackoffDelay(currentAttempt, reconnectInterval);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (
          shouldConnectRef.current &&
          reconnect &&
          reconnectCountRef.current >= reconnectAttempts
        ) {
          // Max retries exhausted
          setHasExhaustedRetries(true);
          // Use ref to get latest callback
          onMaxRetriesExhaustedRef.current?.();
        }
      };

      ws.onerror = (error: Event) => {
        // Use ref to get latest callback
        onErrorRef.current?.(error);
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as unknown;
          setLastMessage(data);
          // Use ref to get latest callback
          onMessageRef.current?.(data);
        } catch {
          // If parsing fails, pass the raw data
          setLastMessage(event.data as unknown);
          // Use ref to get latest callback
          onMessageRef.current?.(event.data as unknown);
        }
      };
    } catch (error) {
      console.error('WebSocket connection error:', error);
    }
    // Reduced dependencies - callbacks are accessed via refs to avoid stale closures
  }, [url, reconnect, reconnectInterval, reconnectAttempts, connectionTimeout]);

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

  return {
    isConnected,
    lastMessage,
    send,
    connect,
    disconnect,
    hasExhaustedRetries,
    reconnectCount,
  };
}
