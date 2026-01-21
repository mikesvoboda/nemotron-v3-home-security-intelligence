/**
 * useGpuStatsWebSocket - WebSocket hook for real-time GPU statistics
 *
 * NEM-3169: Consumes gpu.stats_updated WebSocket events broadcast by the backend
 * for real-time GPU monitoring and utilization tracking.
 *
 * Events handled:
 * - gpu.stats_updated: GPU utilization, memory, temperature, and inference metrics
 *
 * @module hooks/useGpuStatsWebSocket
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { logger } from '../services/logger';
import { isHeartbeatMessage, isErrorMessage } from '../types/websocket';

import type { GpuStatsUpdatedPayload } from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/**
 * GPU stats entry with timestamp for history tracking
 */
export interface GpuStatsEntry extends GpuStatsUpdatedPayload {
  /** ISO timestamp when this update was received */
  timestamp: string;
}

/**
 * Callback type for GPU stats updates
 */
export type GpuStatsUpdateHandler = (stats: GpuStatsUpdatedPayload) => void;

/**
 * Options for configuring the useGpuStatsWebSocket hook
 */
export interface UseGpuStatsWebSocketOptions {
  /**
   * Whether to enable the WebSocket connection
   * @default true
   */
  enabled?: boolean;

  /**
   * Maximum number of historical entries to keep
   * @default 60
   */
  maxHistory?: number;

  /**
   * Threshold for high utilization warning (0-100)
   * @default 90
   */
  highUtilizationThreshold?: number;

  /**
   * Threshold for high temperature warning (Celsius)
   * @default 85
   */
  highTemperatureThreshold?: number;

  /**
   * Called when GPU stats are updated
   */
  onStatsUpdate?: GpuStatsUpdateHandler;
}

/**
 * Return type for the useGpuStatsWebSocket hook
 */
export interface UseGpuStatsWebSocketReturn {
  /** Current GPU stats (null if not yet received) */
  stats: GpuStatsUpdatedPayload | null;

  /** Historical GPU stats entries (newest first) */
  history: GpuStatsEntry[];

  /** ISO timestamp of last update */
  lastUpdate: string | null;

  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** Computed memory usage percentage (0-100 or null) */
  memoryUsagePercent: number | null;

  /** Whether GPU utilization is above threshold */
  isHighUtilization: boolean;

  /** Whether GPU temperature is above threshold */
  isHighTemperature: boolean;

  /** Clear the history buffer */
  clearHistory: () => void;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_MAX_HISTORY = 60;
const DEFAULT_HIGH_UTILIZATION_THRESHOLD = 90;
const DEFAULT_HIGH_TEMPERATURE_THRESHOLD = 85;

// ============================================================================
// Type Guard
// ============================================================================

/**
 * Type guard for gpu.stats_updated messages
 */
function isGpuStatsUpdatedMessage(
  value: unknown
): value is { type: 'gpu.stats_updated'; data: GpuStatsUpdatedPayload } {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const msg = value as Record<string, unknown>;
  if (msg.type !== 'gpu.stats_updated') {
    return false;
  }

  if (!msg.data || typeof msg.data !== 'object') {
    return false;
  }

  // GPU stats payload is valid if it has the type field set
  // All other fields can be null
  return true;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to subscribe to real-time GPU statistics WebSocket events.
 *
 * Tracks GPU utilization, memory usage, temperature, and inference FPS
 * with configurable alerting thresholds.
 *
 * @param options - Configuration options
 * @returns GPU stats state and utilities
 *
 * @example
 * ```tsx
 * const {
 *   stats,
 *   history,
 *   memoryUsagePercent,
 *   isHighUtilization,
 *   isHighTemperature,
 * } = useGpuStatsWebSocket({
 *   onStatsUpdate: (stats) => {
 *     console.log('GPU utilization:', stats.utilization);
 *   },
 *   highUtilizationThreshold: 85,
 *   highTemperatureThreshold: 80,
 * });
 *
 * // Show warning if GPU is stressed
 * if (isHighUtilization || isHighTemperature) {
 *   showWarning('GPU under stress');
 * }
 * ```
 */
export function useGpuStatsWebSocket(
  options: UseGpuStatsWebSocketOptions = {}
): UseGpuStatsWebSocketReturn {
  const {
    enabled = true,
    maxHistory = DEFAULT_MAX_HISTORY,
    highUtilizationThreshold = DEFAULT_HIGH_UTILIZATION_THRESHOLD,
    highTemperatureThreshold = DEFAULT_HIGH_TEMPERATURE_THRESHOLD,
    onStatsUpdate,
  } = options;

  // State
  const [stats, setStats] = useState<GpuStatsUpdatedPayload | null>(null);
  const [history, setHistory] = useState<GpuStatsEntry[]>([]);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  // Track mounted state
  const isMountedRef = useRef(true);

  // Store callback in ref
  const onStatsUpdateRef = useRef(onStatsUpdate);

  useEffect(() => {
    onStatsUpdateRef.current = onStatsUpdate;
  });

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback(
    (data: unknown) => {
      if (!isMountedRef.current) {
        return;
      }

      // Handle gpu.stats_updated messages
      if (isGpuStatsUpdatedMessage(data)) {
        const statsData = data.data;
        const timestamp = new Date().toISOString();

        logger.debug('GPU.stats_updated event received', {
          component: 'useGpuStatsWebSocket',
          utilization: statsData.utilization,
          memory_used: statsData.memory_used,
          temperature: statsData.temperature,
          inference_fps: statsData.inference_fps,
        });

        setStats(statsData);
        setLastUpdate(timestamp);

        const entry: GpuStatsEntry = {
          ...statsData,
          timestamp,
        };

        setHistory((prev) => {
          const updated = [entry, ...prev];
          return updated.slice(0, maxHistory);
        });

        onStatsUpdateRef.current?.(statsData);
        return;
      }

      // Handle other message types (silently ignore)
      if (isHeartbeatMessage(data)) {
        return;
      }

      if (isErrorMessage(data)) {
        logger.warn('GPU stats WebSocket error', {
          component: 'useGpuStatsWebSocket',
          message: data.message,
        });
        return;
      }
    },
    [maxHistory]
  );

  // Build WebSocket options
  const wsOptions = buildWebSocketOptions('/ws/system');

  // Connect to WebSocket
  const { isConnected } = useWebSocket(
    enabled
      ? {
          url: wsOptions.url,
          protocols: wsOptions.protocols,
          onMessage: handleMessage,
          reconnect: true,
          reconnectInterval: 1000,
          reconnectAttempts: 15,
          connectionTimeout: 10000,
          autoRespondToHeartbeat: true,
        }
      : {
          url: wsOptions.url,
          protocols: wsOptions.protocols,
          onMessage: handleMessage,
          reconnect: false,
        }
  );

  // Clear history
  const clearHistory = useCallback(() => {
    if (!isMountedRef.current) return;
    setHistory([]);
  }, []);

  // Computed values
  const memoryUsagePercent = useMemo((): number | null => {
    if (
      stats?.memory_used === null ||
      stats?.memory_used === undefined ||
      stats?.memory_total === null ||
      stats?.memory_total === undefined ||
      stats.memory_total === 0
    ) {
      return null;
    }
    return Math.round((stats.memory_used / stats.memory_total) * 100);
  }, [stats?.memory_used, stats?.memory_total]);

  const isHighUtilization = useMemo((): boolean => {
    return stats?.utilization !== null && stats?.utilization !== undefined && stats.utilization >= highUtilizationThreshold;
  }, [stats?.utilization, highUtilizationThreshold]);

  const isHighTemperature = useMemo((): boolean => {
    return stats?.temperature !== null && stats?.temperature !== undefined && stats.temperature >= highTemperatureThreshold;
  }, [stats?.temperature, highTemperatureThreshold]);

  return {
    stats,
    history,
    lastUpdate,
    isConnected,
    memoryUsagePercent,
    isHighUtilization,
    isHighTemperature,
    clearHistory,
  };
}

export default useGpuStatsWebSocket;
