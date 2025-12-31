import { useState, useCallback, useRef, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketUrl } from '../services/api';

// ============================================================================
// Type Definitions (based on backend schemas in backend/api/schemas/performance.py)
// ============================================================================

/**
 * Time range options for historical data display.
 */
export type TimeRange = '5m' | '15m' | '60m';

/**
 * GPU metrics from nvidia-smi / pynvml.
 */
export interface GpuMetrics {
  name: string;
  utilization: number;
  vram_used_gb: number;
  vram_total_gb: number;
  temperature: number;
  power_watts: number;
}

/**
 * Metrics for RT-DETRv2 model.
 */
export interface AiModelMetrics {
  status: string;
  vram_gb: number;
  model: string;
  device: string;
}

/**
 * Metrics for Nemotron LLM.
 */
export interface NemotronMetrics {
  status: string;
  slots_active: number;
  slots_total: number;
  context_size: number;
}

/**
 * AI inference latency and throughput metrics.
 */
export interface InferenceMetrics {
  rtdetr_latency_ms: Record<string, number>;
  nemotron_latency_ms: Record<string, number>;
  pipeline_latency_ms: Record<string, number>;
  throughput: Record<string, number>;
  queues: Record<string, number>;
}

/**
 * PostgreSQL database metrics.
 */
export interface DatabaseMetrics {
  status: string;
  connections_active: number;
  connections_max: number;
  cache_hit_ratio: number;
  transactions_per_min: number;
}

/**
 * Redis cache metrics.
 */
export interface RedisMetrics {
  status: string;
  connected_clients: number;
  memory_mb: number;
  hit_ratio: number;
  blocked_clients: number;
}

/**
 * Host system metrics from psutil.
 */
export interface HostMetrics {
  cpu_percent: number;
  ram_used_gb: number;
  ram_total_gb: number;
  disk_used_gb: number;
  disk_total_gb: number;
}

/**
 * Container health status.
 */
export interface ContainerMetrics {
  name: string;
  status: string;
  health: string;
}

/**
 * Alert when metric exceeds threshold.
 */
export interface PerformanceAlert {
  severity: 'warning' | 'critical';
  metric: string;
  value: number;
  threshold: number;
  message: string;
}

/**
 * Complete performance update sent via WebSocket.
 * This is the main payload broadcast to frontend clients every 5 seconds.
 */
export interface PerformanceUpdate {
  timestamp: string;
  gpu: GpuMetrics | null;
  ai_models: Record<string, AiModelMetrics | NemotronMetrics>;
  nemotron: NemotronMetrics | null;
  inference: InferenceMetrics | null;
  databases: Record<string, DatabaseMetrics | RedisMetrics>;
  host: HostMetrics | null;
  containers: ContainerMetrics[];
  alerts: PerformanceAlert[];
}

/**
 * History buffers for different time ranges.
 */
export interface PerformanceHistory {
  '5m': PerformanceUpdate[];
  '15m': PerformanceUpdate[];
  '60m': PerformanceUpdate[];
}

/**
 * Return value of the usePerformanceMetrics hook.
 */
export interface UsePerformanceMetricsReturn {
  /** Current performance metrics (latest update) */
  current: PerformanceUpdate | null;
  /** Historical data for 5m/15m/60m time ranges */
  history: PerformanceHistory;
  /** Active alerts array */
  alerts: PerformanceAlert[];
  /** WebSocket connection status */
  isConnected: boolean;
  /** Currently selected time range */
  timeRange: TimeRange;
  /** Function to change the selected time range */
  setTimeRange: (range: TimeRange) => void;
}

// ============================================================================
// Constants
// ============================================================================

/** Maximum number of points to keep in each circular buffer */
const MAX_BUFFER_SIZE = 60;

/**
 * Sampling intervals for downsampling (in seconds).
 * 5m buffer: sample every update (5s interval from backend)
 * 15m buffer: sample every 3rd update (15s effective interval)
 * 60m buffer: sample every 12th update (60s effective interval)
 */
const SAMPLING_RATES = {
  '5m': 1, // Every update (5s interval)
  '15m': 3, // Every 3rd update (15s interval)
  '60m': 12, // Every 12th update (60s interval)
};

// ============================================================================
// WebSocket Message Types
// ============================================================================

/**
 * Backend WebSocket message envelope structure for performance updates.
 */
interface PerformanceUpdateMessage {
  type: 'performance_update';
  data: PerformanceUpdate;
}

/**
 * Type guard to check if alert has valid severity
 */
function isValidSeverity(severity: string): severity is 'warning' | 'critical' {
  return severity === 'warning' || severity === 'critical';
}

/**
 * Normalize alert to ensure severity is typed correctly
 */
function normalizeAlert(alert: Record<string, unknown>): PerformanceAlert | null {
  if (
    typeof alert.severity !== 'string' ||
    typeof alert.metric !== 'string' ||
    typeof alert.value !== 'number' ||
    typeof alert.threshold !== 'number' ||
    typeof alert.message !== 'string'
  ) {
    return null;
  }

  if (!isValidSeverity(alert.severity)) {
    return null;
  }

  return {
    severity: alert.severity,
    metric: alert.metric,
    value: alert.value,
    threshold: alert.threshold,
    message: alert.message,
  };
}

/**
 * Type guard to check if data is a valid PerformanceUpdate
 */
function isPerformanceUpdate(data: unknown): data is PerformanceUpdate {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const obj = data as Record<string, unknown>;

  // Required field: timestamp
  if (typeof obj.timestamp !== 'string') {
    return false;
  }

  // Optional fields with their expected types when present
  if (obj.gpu !== null && obj.gpu !== undefined) {
    const gpu = obj.gpu as Record<string, unknown>;
    if (typeof gpu.name !== 'string' || typeof gpu.utilization !== 'number') {
      return false;
    }
  }

  return true;
}

/**
 * Type guard to check if message is a performance update message envelope
 */
function isPerformanceUpdateMessage(data: unknown): data is PerformanceUpdateMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;
  return msg.type === 'performance_update' && isPerformanceUpdate(msg.data);
}

/**
 * Create an empty PerformanceUpdate object with default values.
 */
function createEmptyPerformanceUpdate(): PerformanceUpdate {
  return {
    timestamp: new Date().toISOString(),
    gpu: null,
    ai_models: {},
    nemotron: null,
    inference: null,
    databases: {},
    host: null,
    containers: [],
    alerts: [],
  };
}

/**
 * Normalize a raw performance update from the backend to ensure proper typing.
 */
function normalizePerformanceUpdate(raw: Record<string, unknown>): PerformanceUpdate {
  const alerts: PerformanceAlert[] = [];

  // Normalize alerts array
  if (Array.isArray(raw.alerts)) {
    for (const alert of raw.alerts) {
      if (alert && typeof alert === 'object') {
        const normalized = normalizeAlert(alert as Record<string, unknown>);
        if (normalized) {
          alerts.push(normalized);
        }
      }
    }
  }

  return {
    timestamp: typeof raw.timestamp === 'string' ? raw.timestamp : new Date().toISOString(),
    gpu: raw.gpu as GpuMetrics | null,
    ai_models: (raw.ai_models as Record<string, AiModelMetrics | NemotronMetrics>) || {},
    nemotron: raw.nemotron as NemotronMetrics | null,
    inference: raw.inference as InferenceMetrics | null,
    databases: (raw.databases as Record<string, DatabaseMetrics | RedisMetrics>) || {},
    host: raw.host as HostMetrics | null,
    containers: (raw.containers as ContainerMetrics[]) || [],
    alerts,
  };
}

// ============================================================================
// Circular Buffer Helper
// ============================================================================

/**
 * Add a new item to a circular buffer, removing the oldest item if at capacity.
 */
function addToCircularBuffer<T>(buffer: T[], item: T, maxSize: number): T[] {
  const newBuffer = [...buffer, item];
  if (newBuffer.length > maxSize) {
    return newBuffer.slice(-maxSize);
  }
  return newBuffer;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * usePerformanceMetrics - Hook for real-time system performance metrics
 *
 * Subscribes to the `/ws/system` WebSocket endpoint and filters for
 * `performance_update` messages. Maintains circular buffers for historical
 * data at different time resolutions.
 *
 * @example
 * ```tsx
 * const {
 *   current,
 *   history,
 *   alerts,
 *   isConnected,
 *   timeRange,
 *   setTimeRange
 * } = usePerformanceMetrics();
 *
 * // Display current GPU utilization
 * if (current?.gpu) {
 *   console.log(`GPU: ${current.gpu.utilization}%`);
 * }
 *
 * // Get historical data for selected time range
 * const historicalData = history[timeRange];
 * ```
 */
export function usePerformanceMetrics(): UsePerformanceMetricsReturn {
  // Current performance metrics (latest update)
  const [current, setCurrent] = useState<PerformanceUpdate | null>(null);

  // Historical data buffers for different time ranges
  const [history, setHistory] = useState<PerformanceHistory>({
    '5m': [],
    '15m': [],
    '60m': [],
  });

  // Active alerts
  const [alerts, setAlerts] = useState<PerformanceAlert[]>([]);

  // Selected time range for display
  const [timeRange, setTimeRange] = useState<TimeRange>('5m');

  // Update counters for downsampling (track how many updates received)
  const updateCountRef = useRef(0);

  /**
   * Handle incoming WebSocket messages.
   * Filters for performance_update messages and updates state.
   */
  const handleMessage = useCallback((data: unknown) => {
    // Check if message matches backend envelope structure: {type: "performance_update", data: {...}}
    if (isPerformanceUpdateMessage(data)) {
      const rawUpdate = data.data as unknown as Record<string, unknown>;
      const update = normalizePerformanceUpdate(rawUpdate);

      // Update current metrics
      setCurrent(update);

      // Update alerts
      setAlerts(update.alerts);

      // Increment update counter
      updateCountRef.current += 1;
      const count = updateCountRef.current;

      // Update history buffers with appropriate downsampling
      setHistory((prevHistory) => {
        let newHistory = { ...prevHistory };

        // 5m buffer: add every update (5s interval)
        if (count % SAMPLING_RATES['5m'] === 0) {
          newHistory = {
            ...newHistory,
            '5m': addToCircularBuffer(newHistory['5m'], update, MAX_BUFFER_SIZE),
          };
        }

        // 15m buffer: add every 3rd update (15s interval)
        if (count % SAMPLING_RATES['15m'] === 0) {
          newHistory = {
            ...newHistory,
            '15m': addToCircularBuffer(newHistory['15m'], update, MAX_BUFFER_SIZE),
          };
        }

        // 60m buffer: add every 12th update (60s interval)
        if (count % SAMPLING_RATES['60m'] === 0) {
          newHistory = {
            ...newHistory,
            '60m': addToCircularBuffer(newHistory['60m'], update, MAX_BUFFER_SIZE),
          };
        }

        return newHistory;
      });
    }
    // Ignore non-performance_update messages (e.g., service_status, ping, etc.)
  }, []);

  // Build WebSocket URL using helper (respects VITE_WS_BASE_URL and adds api_key if configured)
  const wsUrl = useMemo(() => buildWebSocketUrl('/ws/system'), []);

  const { isConnected } = useWebSocket({
    url: wsUrl,
    onMessage: handleMessage,
  });

  return {
    current,
    history,
    alerts,
    isConnected,
    timeRange,
    setTimeRange,
  };
}

// Export utility functions for testing
export { createEmptyPerformanceUpdate, addToCircularBuffer, isPerformanceUpdateMessage };
