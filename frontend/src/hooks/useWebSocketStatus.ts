import { useEffect, useRef, useState, useCallback } from 'react';

export type ConnectionState = 'connected' | 'disconnected' | 'reconnecting';

export interface ChannelStatus {
  name: string;
  state: ConnectionState;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  lastMessageTime: Date | null;
}

export interface WebSocketStatusOptions {
  url: string;
  channelName: string;
  onMessage?: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnect?: boolean;
  reconnectInterval?: number;
  reconnectAttempts?: number;
}

export interface UseWebSocketStatusReturn {
  channelStatus: ChannelStatus;
  lastMessage: unknown;
  send: (data: unknown) => void;
  connect: () => void;
  disconnect: () => void;
}

export function useWebSocketStatus(
  options: WebSocketStatusOptions
): UseWebSocketStatusReturn {
  const {
    url,
    channelName,
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnect = true,
    reconnectInterval = 3000,
    reconnectAttempts = 5,
  } = options;

  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [reconnectCount, setReconnectCount] = useState(0);
  const [lastMessageTime, setLastMessageTime] = useState<Date | null>(null);
  const [lastMessage, setLastMessage] = useState<unknown>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldConnectRef = useRef(true);

  const disconnect = useCallback(() => {
    shouldConnectRef.current = false;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

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

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionState('connected');
        setReconnectCount(0);
        onOpen?.();
      };

      ws.onclose = () => {
        setConnectionState(() => {
          // If we were connected and should reconnect, transition to reconnecting
          if (shouldConnectRef.current && reconnect) {
            return 'reconnecting';
          }
          return 'disconnected';
        });
        onClose?.();

        // Attempt reconnection if enabled and within retry limits
        if (shouldConnectRef.current && reconnect) {
          setReconnectCount((prev) => {
            const newCount = prev + 1;
            if (newCount <= reconnectAttempts) {
              reconnectTimeoutRef.current = setTimeout(() => {
                connect();
              }, reconnectInterval);
            } else {
              // Max reconnect attempts reached, stay disconnected
              setConnectionState('disconnected');
            }
            return newCount;
          });
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
      console.error('WebSocket connection error:', error);
      setConnectionState('disconnected');
    }
  }, [url, onMessage, onOpen, onClose, onError, reconnect, reconnectInterval, reconnectAttempts]);

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
  };

  return {
    channelStatus,
    lastMessage,
    send,
    connect,
    disconnect,
  };
}
