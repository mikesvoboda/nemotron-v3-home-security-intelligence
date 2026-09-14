import { useState, useCallback, useEffect, useRef } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions, fetchHealth } from '../services/api';
import {
  type SystemStatusData,
  type HealthStatus,
  isSystemStatusMessage,
  isServiceStatusMessage,
  isHeartbeatMessage,
  isErrorMessage,
} from '../types/websocket';

/**
 * Frontend-friendly system status representation.
 * Flattens the nested WebSocket message structure for easier consumption.
 */
export interface SystemStatus {
  health: HealthStatus;
  gpu_utilization: number | null;
  gpu_temperature: number | null;
  gpu_memory_used: number | null;
  gpu_memory_total: number | null;
  inference_fps: number | null;
  active_cameras: number;
  last_update: string;
}

export interface UseSystemStatusReturn {
  status: SystemStatus | null;
  isConnected: boolean;
}

/**
 * Transform SystemStatusData from WebSocket into the flattened SystemStatus format.
 */
function transformSystemStatus(data: SystemStatusData, timestamp: string): SystemStatus {
  return {
    health: data.health,
    gpu_utilization: data.gpu.utilization,
    gpu_temperature: data.gpu.temperature,
    gpu_memory_used: data.gpu.memory_used,
    gpu_memory_total: data.gpu.memory_total,
    inference_fps: data.gpu.inference_fps,
    active_cameras: data.cameras.active,
    last_update: timestamp,
  };
}

export function useSystemStatus(): UseSystemStatusReturn {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const isMountedRef = useRef<boolean>(true);
  const hasReceivedWsMessageRef = useRef<boolean>(false);

  // Fetch initial status via REST API to avoid "Unknown" state while waiting for WebSocket
  // This fixes the race condition where mobile devices see "Unknown" because WebSocket
  // connection takes longer to establish on slower networks.
  useEffect(() => {
    isMountedRef.current = true;

    async function fetchInitialStatus() {
      try {
        const health = await fetchHealth();
        // Only set initial status if we haven't received a WebSocket message yet
        // WebSocket data is more complete, so prefer it when available
        if (isMountedRef.current && !hasReceivedWsMessageRef.current) {
          setStatus({
            health: health.status as 'healthy' | 'degraded' | 'unhealthy',
            gpu_utilization: null,
            gpu_temperature: null,
            gpu_memory_used: null,
            gpu_memory_total: null,
            inference_fps: null,
            active_cameras: 0, // Will be updated by WebSocket
            last_update: new Date().toISOString(),
          });
        }
      } catch {
        // Silently fail - WebSocket will provide the status eventually
      }
    }

    void fetchInitialStatus();

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const handleMessage = useCallback((data: unknown) => {
    // Use type guards to validate and narrow the message type
    // First, check for system status messages (most common case for this hook)
    if (isSystemStatusMessage(data)) {
      hasReceivedWsMessageRef.current = true;
      // Use the transform function to flatten the nested structure
      const systemStatus = transformSystemStatus(data.data, data.timestamp);
      setStatus(systemStatus);
      return;
    }

    // Handle other valid SystemChannelMessage types with exhaustive checking pattern
    if (isServiceStatusMessage(data)) {
      // Service status messages could be handled here if needed
      // For now, we just acknowledge them - system status will update from
      // the regular system_status broadcasts
      return;
    }

    if (isHeartbeatMessage(data)) {
      // Heartbeat messages are handled by useWebSocket internally
      return;
    }

    if (isErrorMessage(data)) {
      // Error messages could be logged or handled here
      console.warn('System WebSocket error:', data.message);
      return;
    }

    // Unknown message types are silently ignored
    // This is intentional - the backend may send messages we don't care about
  }, []);

  // Build WebSocket options using helper (respects VITE_WS_BASE_URL)
  // SECURITY: API key is passed via Sec-WebSocket-Protocol header, not URL query param
  const wsOptions = buildWebSocketOptions('/ws/system');

  const { isConnected } = useWebSocket({
    url: wsOptions.url,
    protocols: wsOptions.protocols,
    onMessage: handleMessage,
  });

  return {
    status,
    isConnected,
  };
}
