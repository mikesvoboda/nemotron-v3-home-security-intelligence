/**
 * useJobLogsWebSocket - Hook for real-time job log streaming via WebSocket
 *
 * Provides WebSocket-based real-time log streaming for active jobs.
 * Features:
 * - Connects only for active jobs (processing/pending)
 * - Auto-reconnect with exponential backoff
 * - Max 5 reconnection attempts (configurable)
 * - Log deduplication
 * - Sorted logs by timestamp
 *
 * NEM-2711
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { webSocketManager, generateSubscriberId } from './webSocketManager';
import { logger } from '../services/logger';

import type { ConnectionConfig, Subscriber } from './webSocketManager';

// ============================================================================
// Types
// ============================================================================

/**
 * Log level for job log entries.
 */
export type JobLogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';

/**
 * A single log entry from the job.
 */
export interface JobLogEntry {
  /** ISO 8601 timestamp when the log entry was created */
  timestamp: string;
  /** Log level (DEBUG, INFO, WARNING, ERROR) */
  level: JobLogLevel;
  /** Log message */
  message: string;
  /** Additional context data */
  context?: Record<string, unknown>;
  /** Which attempt generated this log (optional) */
  attempt_number?: number;
}

/**
 * WebSocket message format for job logs.
 */
interface JobLogMessage {
  type: 'log';
  data: JobLogEntry;
}

/**
 * Connection status for the job logs WebSocket.
 */
export type JobLogsConnectionStatus = 'connected' | 'reconnecting' | 'disconnected' | 'failed';

/**
 * Options for useJobLogsWebSocket hook.
 */
export interface UseJobLogsWebSocketOptions {
  /** The job ID to stream logs for */
  jobId: string;
  /** Whether to enable the WebSocket connection */
  enabled: boolean;
  /** Maximum number of reconnection attempts (default: 5) */
  maxReconnectAttempts?: number;
  /** Base reconnection interval in ms (default: 1000) */
  reconnectInterval?: number;
  /** Callback when a new log entry is received */
  onLog?: (log: JobLogEntry) => void;
  /** Callback when connected */
  onConnect?: () => void;
  /** Callback when disconnected */
  onDisconnect?: () => void;
  /** Callback when an error occurs */
  onError?: (error: Event) => void;
  /** Callback when max retries exhausted */
  onMaxRetriesExhausted?: () => void;
}

/**
 * Return type for useJobLogsWebSocket hook.
 */
export interface UseJobLogsWebSocketReturn {
  /** Array of log entries received */
  logs: JobLogEntry[];
  /** Current connection status */
  status: JobLogsConnectionStatus;
  /** Whether currently connected */
  isConnected: boolean;
  /** Current reconnection attempt count */
  reconnectCount: number;
  /** Whether max retries have been exhausted */
  hasExhaustedRetries: boolean;
  /** Clear all logs */
  clearLogs: () => void;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Generate a unique key for a log entry (for deduplication).
 */
function getLogKey(log: JobLogEntry): string {
  return `${log.timestamp}:${log.level}:${log.message}`;
}

/**
 * Check if a message is a job log message.
 */
function isJobLogMessage(data: unknown): data is JobLogMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;
  if (msg.type !== 'log') {
    return false;
  }
  if (!msg.data || typeof msg.data !== 'object') {
    return false;
  }
  const logData = msg.data as Record<string, unknown>;
  return (
    typeof logData.timestamp === 'string' &&
    typeof logData.level === 'string' &&
    typeof logData.message === 'string'
  );
}

/**
 * Get the WebSocket URL for job logs.
 */
function getJobLogsWebSocketUrl(jobId: string): string {
  const protocol =
    typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
  return `${protocol}//${host}/ws/jobs/${jobId}/logs`;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for real-time job log streaming via WebSocket.
 *
 * @example
 * ```tsx
 * const { logs, status, isConnected } = useJobLogsWebSocket({
 *   jobId: 'job-123',
 *   enabled: job.status === 'running' || job.status === 'pending',
 *   onLog: (log) => console.log('New log:', log),
 * });
 * ```
 */
export function useJobLogsWebSocket(
  options: UseJobLogsWebSocketOptions
): UseJobLogsWebSocketReturn {
  const {
    jobId,
    enabled,
    maxReconnectAttempts = 5,
    reconnectInterval = 1000,
    onLog,
    onConnect,
    onDisconnect,
    onError,
    onMaxRetriesExhausted,
  } = options;

  // State
  const [logs, setLogs] = useState<JobLogEntry[]>([]);
  const [status, setStatus] = useState<JobLogsConnectionStatus>('disconnected');
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const [hasExhaustedRetries, setHasExhaustedRetries] = useState(false);

  // Refs for callbacks to avoid stale closures
  const onLogRef = useRef(onLog);
  const onConnectRef = useRef(onConnect);
  const onDisconnectRef = useRef(onDisconnect);
  const onErrorRef = useRef(onError);
  const onMaxRetriesExhaustedRef = useRef(onMaxRetriesExhausted);

  // Ref for tracking seen log keys (for deduplication)
  const seenLogsRef = useRef<Set<string>>(new Set());

  // Unsubscribe function ref
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const subscriberIdRef = useRef(generateSubscriberId());

  // Update callback refs
  useEffect(() => {
    onLogRef.current = onLog;
    onConnectRef.current = onConnect;
    onDisconnectRef.current = onDisconnect;
    onErrorRef.current = onError;
    onMaxRetriesExhaustedRef.current = onMaxRetriesExhausted;
  });

  // Clear logs function
  const clearLogs = useCallback(() => {
    setLogs([]);
    seenLogsRef.current.clear();
  }, []);

  // Connect/disconnect based on enabled state and jobId
  useEffect(() => {
    if (!enabled || !jobId) {
      // Disconnect if not enabled
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
      setStatus('disconnected');
      setIsConnected(false);
      setReconnectCount(0);
      setHasExhaustedRetries(false);
      return;
    }

    const url = getJobLogsWebSocketUrl(jobId);

    const config: ConnectionConfig = {
      reconnect: true,
      reconnectInterval,
      maxReconnectAttempts,
      connectionTimeout: 10000,
      autoRespondToHeartbeat: true,
    };

    const subscriber: Subscriber = {
      id: subscriberIdRef.current,
      onMessage: (data: unknown) => {
        if (!isJobLogMessage(data)) {
          // Ignore non-log messages
          return;
        }

        const logEntry = data.data;
        const logKey = getLogKey(logEntry);

        // Deduplicate logs
        if (seenLogsRef.current.has(logKey)) {
          return;
        }
        seenLogsRef.current.add(logKey);

        // Add log and sort by timestamp
        setLogs((prevLogs) => {
          const newLogs = [...prevLogs, logEntry];
          // Sort by timestamp (ascending)
          newLogs.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
          return newLogs;
        });

        // Call callback
        onLogRef.current?.(logEntry);
      },
      onOpen: () => {
        logger.debug('Job logs WebSocket connected', {
          component: 'useJobLogsWebSocket',
          jobId,
        });
        setStatus('connected');
        setIsConnected(true);
        setReconnectCount(0);
        setHasExhaustedRetries(false);
        onConnectRef.current?.();
      },
      onClose: () => {
        logger.debug('Job logs WebSocket closed', {
          component: 'useJobLogsWebSocket',
          jobId,
        });
        setIsConnected(false);
        // Update reconnect count from manager state
        const state = webSocketManager.getConnectionState(url);
        setReconnectCount(state.reconnectCount);
        if (state.reconnectCount > 0 && !state.hasExhaustedRetries) {
          setStatus('reconnecting');
        } else if (!state.hasExhaustedRetries) {
          setStatus('disconnected');
        }
        onDisconnectRef.current?.();
      },
      onError: (error: Event) => {
        logger.warn('Job logs WebSocket error', {
          component: 'useJobLogsWebSocket',
          jobId,
          error,
        });
        onErrorRef.current?.(error);
      },
      onMaxRetriesExhausted: () => {
        logger.warn('Job logs WebSocket max retries exhausted', {
          component: 'useJobLogsWebSocket',
          jobId,
        });
        setStatus('failed');
        setHasExhaustedRetries(true);
        onMaxRetriesExhaustedRef.current?.();
      },
    };

    unsubscribeRef.current = webSocketManager.subscribe(url, subscriber, config);

    // Cleanup on unmount or when dependencies change
    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
    };
  }, [enabled, jobId, maxReconnectAttempts, reconnectInterval]);

  return {
    logs,
    status,
    isConnected,
    reconnectCount,
    hasExhaustedRetries,
    clearLogs,
  };
}

export default useJobLogsWebSocket;
