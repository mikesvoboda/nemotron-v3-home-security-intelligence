import { useState, useCallback } from 'react';

import { useWebSocket } from './useWebSocket';

export interface SystemStatus {
  health: 'healthy' | 'degraded' | 'unhealthy';
  gpu_utilization: number | null;
  active_cameras: number;
  last_update: string;
}

export interface UseSystemStatusReturn {
  status: SystemStatus | null;
  isConnected: boolean;
}

export function useSystemStatus(): UseSystemStatusReturn {
  const [status, setStatus] = useState<SystemStatus | null>(null);

  const handleMessage = useCallback((data: unknown) => {
    // Validate that the message is a SystemStatus
    if (
      data &&
      typeof data === 'object' &&
      'health' in data &&
      'gpu_utilization' in data &&
      'active_cameras' in data &&
      'last_update' in data
    ) {
      const systemStatus = data as SystemStatus;
      setStatus(systemStatus);
    }
  }, []);

  const { isConnected } = useWebSocket({
    url: `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/system`,
    onMessage: handleMessage,
  });

  return {
    status,
    isConnected,
  };
}
