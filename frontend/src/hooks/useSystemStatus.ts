import { useState, useCallback } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketUrl } from '../services/api';

export interface SystemStatus {
  health: 'healthy' | 'degraded' | 'unhealthy';
  gpu_utilization: number | null;
  gpu_temperature: number | null;
  gpu_memory_used: number | null;
  gpu_memory_total: number | null;
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

  const handleMessage = useCallback((data: unknown) => {
    // Check if message matches backend structure
    if (isBackendSystemStatus(data)) {
      const systemStatus: SystemStatus = {
        health: data.data.health,
        gpu_utilization: data.data.gpu.utilization,
        gpu_temperature: data.data.gpu.temperature,
        gpu_memory_used: data.data.gpu.memory_used,
        gpu_memory_total: data.data.gpu.memory_total,
        active_cameras: data.data.cameras.active,
        last_update: data.timestamp,
      };
      setStatus(systemStatus);
    }
  }, []);

  // Build WebSocket URL using helper (respects VITE_WS_BASE_URL and adds api_key if configured)
  const wsUrl = buildWebSocketUrl('/ws/system');

  const { isConnected } = useWebSocket({
    url: wsUrl,
    onMessage: handleMessage,
  });

  return {
    status,
    isConnected,
  };
}
