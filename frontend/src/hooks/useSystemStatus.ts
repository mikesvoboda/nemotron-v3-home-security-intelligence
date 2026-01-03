import { useState, useCallback, useEffect, useRef } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions, fetchHealth } from '../services/api';

export interface SystemStatus {
  health: 'healthy' | 'degraded' | 'unhealthy';
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

// Backend message structure from SystemBroadcaster
interface BackendSystemStatus {
  type: 'system_status';
  data: {
    gpu: {
      utilization: number | null;
      memory_used: number | null;
      memory_total: number | null;
      temperature: number | null;
      inference_fps: number | null;
    };
    cameras: {
      active: number;
      total: number;
    };
    queue: {
      pending: number;
      processing: number;
    };
    health: 'healthy' | 'degraded' | 'unhealthy';
  };
  timestamp: string;
}

function isBackendSystemStatus(data: unknown): data is BackendSystemStatus {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const msg = data as Record<string, unknown>;

  return (
    msg.type === 'system_status' &&
    typeof msg.data === 'object' &&
    msg.data !== null &&
    typeof msg.timestamp === 'string' &&
    'gpu' in msg.data &&
    'cameras' in msg.data &&
    'health' in msg.data
  );
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
    // Check if message matches backend structure
    if (isBackendSystemStatus(data)) {
      hasReceivedWsMessageRef.current = true;
      const systemStatus: SystemStatus = {
        health: data.data.health,
        gpu_utilization: data.data.gpu.utilization,
        gpu_temperature: data.data.gpu.temperature,
        gpu_memory_used: data.data.gpu.memory_used,
        gpu_memory_total: data.data.gpu.memory_total,
        inference_fps: data.data.gpu.inference_fps,
        active_cameras: data.data.cameras.active,
        last_update: data.timestamp,
      };
      setStatus(systemStatus);
    }
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
