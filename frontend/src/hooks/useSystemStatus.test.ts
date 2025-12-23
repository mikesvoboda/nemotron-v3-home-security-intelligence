import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useSystemStatus, SystemStatus } from './useSystemStatus';
import * as useWebSocketModule from './useWebSocket';

describe('useSystemStatus', () => {
  const mockWebSocketReturn = {
    isConnected: true,
    lastMessage: null,
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
  };

  let onMessageCallback: ((data: unknown) => void) | undefined;

  beforeEach(() => {
    // Mock useWebSocket to capture the onMessage callback
    vi.spyOn(useWebSocketModule, 'useWebSocket').mockImplementation((options) => {
      onMessageCallback = options.onMessage;
      return mockWebSocketReturn;
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    onMessageCallback = undefined;
  });

  it('should initialize with null status', () => {
    const { result } = renderHook(() => useSystemStatus());

    expect(result.current.status).toBeNull();
    expect(result.current.isConnected).toBe(true);
  });

  it('should connect to the correct WebSocket URL', () => {
    renderHook(() => useSystemStatus());

    expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
      expect.objectContaining({
        url: expect.stringContaining('/ws/system'),
        onMessage: expect.any(Function),
      })
    );
  });

  it('should update status when valid SystemStatus message is received', () => {
    const { result } = renderHook(() => useSystemStatus());

    const systemStatus: SystemStatus = {
      health: 'healthy',
      gpu_utilization: 45.5,
      active_cameras: 3,
      last_update: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(systemStatus);
    });

    expect(result.current.status).toEqual(systemStatus);
  });

  it('should handle healthy status', () => {
    const { result } = renderHook(() => useSystemStatus());

    const systemStatus: SystemStatus = {
      health: 'healthy',
      gpu_utilization: 30,
      active_cameras: 5,
      last_update: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(systemStatus);
    });

    expect(result.current.status?.health).toBe('healthy');
  });

  it('should handle degraded status', () => {
    const { result } = renderHook(() => useSystemStatus());

    const systemStatus: SystemStatus = {
      health: 'degraded',
      gpu_utilization: 85,
      active_cameras: 2,
      last_update: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(systemStatus);
    });

    expect(result.current.status?.health).toBe('degraded');
  });

  it('should handle unhealthy status', () => {
    const { result } = renderHook(() => useSystemStatus());

    const systemStatus: SystemStatus = {
      health: 'unhealthy',
      gpu_utilization: 100,
      active_cameras: 0,
      last_update: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(systemStatus);
    });

    expect(result.current.status?.health).toBe('unhealthy');
  });

  it('should handle null gpu_utilization', () => {
    const { result } = renderHook(() => useSystemStatus());

    const systemStatus: SystemStatus = {
      health: 'healthy',
      gpu_utilization: null,
      active_cameras: 3,
      last_update: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(systemStatus);
    });

    expect(result.current.status?.gpu_utilization).toBeNull();
  });

  it('should handle zero active cameras', () => {
    const { result } = renderHook(() => useSystemStatus());

    const systemStatus: SystemStatus = {
      health: 'degraded',
      gpu_utilization: 0,
      active_cameras: 0,
      last_update: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(systemStatus);
    });

    expect(result.current.status?.active_cameras).toBe(0);
  });

  it('should replace previous status with new status', () => {
    const { result } = renderHook(() => useSystemStatus());

    const firstStatus: SystemStatus = {
      health: 'healthy',
      gpu_utilization: 40,
      active_cameras: 3,
      last_update: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(firstStatus);
    });

    expect(result.current.status).toEqual(firstStatus);

    const secondStatus: SystemStatus = {
      health: 'degraded',
      gpu_utilization: 75,
      active_cameras: 2,
      last_update: '2025-12-23T10:05:00Z',
    };

    act(() => {
      onMessageCallback?.(secondStatus);
    });

    expect(result.current.status).toEqual(secondStatus);
    expect(result.current.status).not.toEqual(firstStatus);
  });

  it('should ignore invalid messages missing required fields', () => {
    const { result } = renderHook(() => useSystemStatus());

    const invalidMessages = [
      { health: 'healthy' }, // Missing other fields
      { gpu_utilization: 50, active_cameras: 2 }, // Missing health
      null,
      undefined,
      'string message',
      42,
      [],
    ];

    act(() => {
      invalidMessages.forEach((msg) => onMessageCallback?.(msg));
    });

    expect(result.current.status).toBeNull();
  });

  it('should ignore messages with partial SystemStatus fields', () => {
    const { result } = renderHook(() => useSystemStatus());

    const partialStatus = {
      health: 'healthy',
      gpu_utilization: 45.5,
      active_cameras: 3,
      // Missing last_update
    };

    act(() => {
      onMessageCallback?.(partialStatus);
    });

    expect(result.current.status).toBeNull();
  });

  it('should ignore message if health field is missing', () => {
    const { result } = renderHook(() => useSystemStatus());

    const invalidStatus = {
      gpu_utilization: 45.5,
      active_cameras: 3,
      last_update: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(invalidStatus);
    });

    expect(result.current.status).toBeNull();
  });

  it('should ignore message if gpu_utilization field is missing', () => {
    const { result } = renderHook(() => useSystemStatus());

    const invalidStatus = {
      health: 'healthy',
      active_cameras: 3,
      last_update: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(invalidStatus);
    });

    expect(result.current.status).toBeNull();
  });

  it('should ignore message if active_cameras field is missing', () => {
    const { result } = renderHook(() => useSystemStatus());

    const invalidStatus = {
      health: 'healthy',
      gpu_utilization: 45.5,
      last_update: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(invalidStatus);
    });

    expect(result.current.status).toBeNull();
  });

  it('should ignore message if last_update field is missing', () => {
    const { result } = renderHook(() => useSystemStatus());

    const invalidStatus = {
      health: 'healthy',
      gpu_utilization: 45.5,
      active_cameras: 3,
    };

    act(() => {
      onMessageCallback?.(invalidStatus);
    });

    expect(result.current.status).toBeNull();
  });

  it('should reflect connection status from useWebSocket', () => {
    const { result, rerender } = renderHook(() => useSystemStatus());

    expect(result.current.isConnected).toBe(true);

    // Update mock to return disconnected state
    mockWebSocketReturn.isConnected = false;
    rerender();

    expect(result.current.isConnected).toBe(false);
  });

  it('should handle rapid successive status updates', () => {
    const { result } = renderHook(() => useSystemStatus());

    for (let i = 0; i < 10; i++) {
      const status: SystemStatus = {
        health: i % 2 === 0 ? 'healthy' : 'degraded',
        gpu_utilization: i * 10,
        active_cameras: i,
        last_update: `2025-12-23T10:00:${String(i).padStart(2, '0')}Z`,
      };

      act(() => {
        onMessageCallback?.(status);
      });
    }

    // Should have the last status
    expect(result.current.status).toEqual({
      health: 'degraded',
      gpu_utilization: 90,
      active_cameras: 9,
      last_update: '2025-12-23T10:00:09Z',
    });
  });

  it('should handle status updates with varying gpu_utilization values', () => {
    const { result } = renderHook(() => useSystemStatus());

    const testValues = [0, 25.5, 50, 75.75, 100, null];

    testValues.forEach((gpuUtil, index) => {
      const status: SystemStatus = {
        health: 'healthy',
        gpu_utilization: gpuUtil,
        active_cameras: 3,
        last_update: `2025-12-23T10:0${index}:00Z`,
      };

      act(() => {
        onMessageCallback?.(status);
      });

      expect(result.current.status?.gpu_utilization).toBe(gpuUtil);
    });
  });

  it('should handle status updates with varying active_cameras values', () => {
    const { result } = renderHook(() => useSystemStatus());

    const testValues = [0, 1, 5, 10, 100];

    testValues.forEach((cameras, index) => {
      const status: SystemStatus = {
        health: 'healthy',
        gpu_utilization: 50,
        active_cameras: cameras,
        last_update: `2025-12-23T10:0${index}:00Z`,
      };

      act(() => {
        onMessageCallback?.(status);
      });

      expect(result.current.status?.active_cameras).toBe(cameras);
    });
  });

  it('should maintain handleMessage callback stability', () => {
    const { rerender } = renderHook(() => useSystemStatus());

    const firstCallback = onMessageCallback;

    rerender();

    const secondCallback = onMessageCallback;

    // useCallback should maintain the same reference
    expect(firstCallback).toBe(secondCallback);
  });

  it('should handle edge case with extreme gpu_utilization values', () => {
    const { result } = renderHook(() => useSystemStatus());

    const extremeValues = [-1, 0, 0.01, 99.99, 100, 150];

    extremeValues.forEach((value, index) => {
      const status: SystemStatus = {
        health: 'healthy',
        gpu_utilization: value,
        active_cameras: 3,
        last_update: `2025-12-23T10:${String(index).padStart(2, '0')}:00Z`,
      };

      act(() => {
        onMessageCallback?.(status);
      });

      expect(result.current.status?.gpu_utilization).toBe(value);
    });
  });

  it('should handle all health states in sequence', () => {
    const { result } = renderHook(() => useSystemStatus());

    const healthStates: Array<'healthy' | 'degraded' | 'unhealthy'> = [
      'healthy',
      'degraded',
      'unhealthy',
    ];

    healthStates.forEach((health, index) => {
      const status: SystemStatus = {
        health,
        gpu_utilization: 50,
        active_cameras: 3,
        last_update: `2025-12-23T10:0${index}:00Z`,
      };

      act(() => {
        onMessageCallback?.(status);
      });

      expect(result.current.status?.health).toBe(health);
    });
  });

  it('should preserve status after receiving invalid message', () => {
    const { result } = renderHook(() => useSystemStatus());

    const validStatus: SystemStatus = {
      health: 'healthy',
      gpu_utilization: 45,
      active_cameras: 3,
      last_update: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(validStatus);
    });

    expect(result.current.status).toEqual(validStatus);

    // Send invalid message
    act(() => {
      onMessageCallback?.({ invalid: 'data' });
    });

    // Status should remain unchanged
    expect(result.current.status).toEqual(validStatus);
  });

  it('should handle status with timestamp strings in different formats', () => {
    const { result } = renderHook(() => useSystemStatus());

    const timestamps = [
      '2025-12-23T10:00:00Z',
      '2025-12-23T10:00:00.000Z',
      '2025-12-23T10:00:00+00:00',
      '2025-12-23 10:00:00',
    ];

    timestamps.forEach((timestamp, index) => {
      const status: SystemStatus = {
        health: 'healthy',
        gpu_utilization: 50,
        active_cameras: index + 1,
        last_update: timestamp,
      };

      act(() => {
        onMessageCallback?.(status);
      });

      expect(result.current.status?.last_update).toBe(timestamp);
    });
  });

  it('should not mutate received status object', () => {
    const { result } = renderHook(() => useSystemStatus());

    const originalStatus: SystemStatus = {
      health: 'healthy',
      gpu_utilization: 45.5,
      active_cameras: 3,
      last_update: '2025-12-23T10:00:00Z',
    };

    const statusCopy = { ...originalStatus };

    act(() => {
      onMessageCallback?.(originalStatus);
    });

    expect(result.current.status).toEqual(originalStatus);
    expect(originalStatus).toEqual(statusCopy);
  });

  it('should handle disconnection and reconnection scenarios', () => {
    // Create a fresh mock that we can update
    let mockConnectionState = true;
    const dynamicMockReturn = {
      get isConnected() {
        return mockConnectionState;
      },
      lastMessage: null,
      send: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
    };

    vi.spyOn(useWebSocketModule, 'useWebSocket').mockImplementation((options) => {
      onMessageCallback = options.onMessage;
      return dynamicMockReturn;
    });

    const { result, rerender } = renderHook(() => useSystemStatus());

    const status: SystemStatus = {
      health: 'healthy',
      gpu_utilization: 45,
      active_cameras: 3,
      last_update: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(status);
    });

    expect(result.current.status).toEqual(status);
    expect(result.current.isConnected).toBe(true);

    // Simulate disconnection
    mockConnectionState = false;
    rerender();

    expect(result.current.isConnected).toBe(false);
    // Status should persist during disconnection
    expect(result.current.status).toEqual(status);

    // Simulate reconnection
    mockConnectionState = true;
    rerender();

    expect(result.current.isConnected).toBe(true);
    expect(result.current.status).toEqual(status);
  });
});
