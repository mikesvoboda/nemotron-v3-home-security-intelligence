import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useSystemStatus } from './useSystemStatus';
import * as useWebSocketModule from './useWebSocket';

describe('useSystemStatus', () => {
  const mockWebSocketReturn = {
    isConnected: true,
    lastMessage: null,
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    hasExhaustedRetries: false,
    reconnectCount: 0,
    lastHeartbeat: null,
  };

  let onMessageCallback: ((data: unknown) => void) | undefined;

  // Helper to create a backend-formatted message
  const createBackendMessage = (
    health: 'healthy' | 'degraded' | 'unhealthy',
    gpuUtilization: number | null = 45.5,
    gpuTemperature: number | null = 65,
    activeCameras: number = 3,
    timestamp: string = '2025-12-23T10:00:00Z'
  ) => ({
    type: 'system_status',
    data: {
      gpu: {
        utilization: gpuUtilization,
        memory_used: 8192,
        memory_total: 24576,
        temperature: gpuTemperature,
        inference_fps: 30.5,
      },
      cameras: {
        active: activeCameras,
        total: 6,
      },
      queue: {
        pending: 0,
        processing: 0,
      },
      health,
    },
    timestamp,
  });

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

  it('should update status when valid backend message is received', () => {
    const { result } = renderHook(() => useSystemStatus());

    const backendMessage = createBackendMessage('healthy', 45.5, 65, 3);

    act(() => {
      onMessageCallback?.(backendMessage);
    });

    expect(result.current.status).toEqual({
      health: 'healthy',
      gpu_utilization: 45.5,
      gpu_temperature: 65,
      gpu_memory_used: 8192,
      gpu_memory_total: 24576,
      inference_fps: 30.5,
      active_cameras: 3,
      last_update: '2025-12-23T10:00:00Z',
    });
  });

  it('should handle healthy status', () => {
    const { result } = renderHook(() => useSystemStatus());

    const backendMessage = createBackendMessage('healthy', 30, 55, 5);

    act(() => {
      onMessageCallback?.(backendMessage);
    });

    expect(result.current.status?.health).toBe('healthy');
  });

  it('should handle degraded status', () => {
    const { result } = renderHook(() => useSystemStatus());

    const backendMessage = createBackendMessage('degraded', 85, 75, 2);

    act(() => {
      onMessageCallback?.(backendMessage);
    });

    expect(result.current.status?.health).toBe('degraded');
  });

  it('should handle unhealthy status', () => {
    const { result } = renderHook(() => useSystemStatus());

    const backendMessage = createBackendMessage('unhealthy', 100, 90, 0);

    act(() => {
      onMessageCallback?.(backendMessage);
    });

    expect(result.current.status?.health).toBe('unhealthy');
  });

  it('should handle null gpu_utilization', () => {
    const { result } = renderHook(() => useSystemStatus());

    const backendMessage = createBackendMessage('healthy', null, 65, 3);

    act(() => {
      onMessageCallback?.(backendMessage);
    });

    expect(result.current.status?.gpu_utilization).toBeNull();
  });

  it('should handle zero active cameras', () => {
    const { result } = renderHook(() => useSystemStatus());

    const backendMessage = createBackendMessage('degraded', 0, 45, 0);

    act(() => {
      onMessageCallback?.(backendMessage);
    });

    expect(result.current.status?.active_cameras).toBe(0);
  });

  it('should replace previous status with new status', () => {
    const { result } = renderHook(() => useSystemStatus());

    const firstMessage = createBackendMessage('healthy', 40, 60, 3, '2025-12-23T10:00:00Z');

    act(() => {
      onMessageCallback?.(firstMessage);
    });

    expect(result.current.status?.health).toBe('healthy');
    expect(result.current.status?.gpu_utilization).toBe(40);

    const secondMessage = createBackendMessage('degraded', 75, 70, 2, '2025-12-23T10:05:00Z');

    act(() => {
      onMessageCallback?.(secondMessage);
    });

    expect(result.current.status?.health).toBe('degraded');
    expect(result.current.status?.gpu_utilization).toBe(75);
    expect(result.current.status?.last_update).toBe('2025-12-23T10:05:00Z');
  });

  it('should ignore invalid messages missing required fields', () => {
    const { result } = renderHook(() => useSystemStatus());

    const invalidMessages = [
      { type: 'other_type' }, // Wrong type
      { type: 'system_status' }, // Missing data
      { type: 'system_status', data: {} }, // Missing nested fields
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

  it('should ignore messages with partial data fields', () => {
    const { result } = renderHook(() => useSystemStatus());

    const partialMessage = {
      type: 'system_status',
      data: {
        gpu: { utilization: 45.5 },
        // Missing cameras and health
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(partialMessage);
    });

    expect(result.current.status).toBeNull();
  });

  it('should ignore message if health field is missing', () => {
    const { result } = renderHook(() => useSystemStatus());

    const invalidMessage = {
      type: 'system_status',
      data: {
        gpu: {
          utilization: 45.5,
          temperature: 65,
          memory_used: 8192,
          memory_total: 24576,
          inference_fps: 30,
        },
        cameras: { active: 3, total: 6 },
        queue: { pending: 0, processing: 0 },
        // Missing health
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(invalidMessage);
    });

    expect(result.current.status).toBeNull();
  });

  it('should ignore message if gpu field is missing', () => {
    const { result } = renderHook(() => useSystemStatus());

    const invalidMessage = {
      type: 'system_status',
      data: {
        // Missing gpu
        cameras: { active: 3, total: 6 },
        health: 'healthy',
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(invalidMessage);
    });

    expect(result.current.status).toBeNull();
  });

  it('should ignore message if cameras field is missing', () => {
    const { result } = renderHook(() => useSystemStatus());

    const invalidMessage = {
      type: 'system_status',
      data: {
        gpu: {
          utilization: 45.5,
          temperature: 65,
          memory_used: 8192,
          memory_total: 24576,
          inference_fps: 30,
        },
        // Missing cameras
        health: 'healthy',
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(invalidMessage);
    });

    expect(result.current.status).toBeNull();
  });

  it('should ignore message if timestamp field is missing', () => {
    const { result } = renderHook(() => useSystemStatus());

    const invalidMessage = {
      type: 'system_status',
      data: {
        gpu: {
          utilization: 45.5,
          temperature: 65,
          memory_used: 8192,
          memory_total: 24576,
          inference_fps: 30,
        },
        cameras: { active: 3, total: 6 },
        health: 'healthy',
      },
      // Missing timestamp
    };

    act(() => {
      onMessageCallback?.(invalidMessage);
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
      const message = createBackendMessage(
        i % 2 === 0 ? 'healthy' : 'degraded',
        i * 10,
        60 + i,
        i,
        `2025-12-23T10:00:${String(i).padStart(2, '0')}Z`
      );

      act(() => {
        onMessageCallback?.(message);
      });
    }

    // Should have the last status
    expect(result.current.status?.health).toBe('degraded');
    expect(result.current.status?.gpu_utilization).toBe(90);
    expect(result.current.status?.active_cameras).toBe(9);
    expect(result.current.status?.last_update).toBe('2025-12-23T10:00:09Z');
  });

  it('should handle status updates with varying gpu_utilization values', () => {
    const { result } = renderHook(() => useSystemStatus());

    const testValues = [0, 25.5, 50, 75.75, 100, null];

    testValues.forEach((gpuUtil, index) => {
      const message = createBackendMessage(
        'healthy',
        gpuUtil,
        65,
        3,
        `2025-12-23T10:0${index}:00Z`
      );

      act(() => {
        onMessageCallback?.(message);
      });

      expect(result.current.status?.gpu_utilization).toBe(gpuUtil);
    });
  });

  it('should handle status updates with varying active_cameras values', () => {
    const { result } = renderHook(() => useSystemStatus());

    const testValues = [0, 1, 5, 10, 100];

    testValues.forEach((cameras, index) => {
      const message = createBackendMessage(
        'healthy',
        50,
        65,
        cameras,
        `2025-12-23T10:0${index}:00Z`
      );

      act(() => {
        onMessageCallback?.(message);
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
      const message = createBackendMessage(
        'healthy',
        value,
        65,
        3,
        `2025-12-23T10:${String(index).padStart(2, '0')}:00Z`
      );

      act(() => {
        onMessageCallback?.(message);
      });

      expect(result.current.status?.gpu_utilization).toBe(value);
    });
  });

  it('should handle all health states in sequence', () => {
    const { result } = renderHook(() => useSystemStatus());

    const healthStates = ['healthy', 'degraded', 'unhealthy'] as const;

    healthStates.forEach((health, index) => {
      const message = createBackendMessage(health, 50, 65, 3, `2025-12-23T10:0${index}:00Z`);

      act(() => {
        onMessageCallback?.(message);
      });

      expect(result.current.status?.health).toBe(health);
    });
  });

  it('should preserve status after receiving invalid message', () => {
    const { result } = renderHook(() => useSystemStatus());

    const validMessage = createBackendMessage('healthy', 45, 60, 3);

    act(() => {
      onMessageCallback?.(validMessage);
    });

    expect(result.current.status?.health).toBe('healthy');
    expect(result.current.status?.gpu_utilization).toBe(45);

    // Send invalid message
    act(() => {
      onMessageCallback?.({ invalid: 'data' });
    });

    // Status should remain unchanged
    expect(result.current.status?.health).toBe('healthy');
    expect(result.current.status?.gpu_utilization).toBe(45);
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
      const message = createBackendMessage('healthy', 50, 65, index + 1, timestamp);

      act(() => {
        onMessageCallback?.(message);
      });

      expect(result.current.status?.last_update).toBe(timestamp);
    });
  });

  it('should not mutate received message object', () => {
    const { result } = renderHook(() => useSystemStatus());

    const originalMessage = createBackendMessage('healthy', 45.5, 60, 3);
    const messageCopy = JSON.parse(JSON.stringify(originalMessage));

    act(() => {
      onMessageCallback?.(originalMessage);
    });

    expect(result.current.status?.gpu_utilization).toBe(45.5);
    expect(originalMessage).toEqual(messageCopy);
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
      hasExhaustedRetries: false,
      reconnectCount: 0,
      lastHeartbeat: null,
    };

    vi.spyOn(useWebSocketModule, 'useWebSocket').mockImplementation((options) => {
      onMessageCallback = options.onMessage;
      return dynamicMockReturn;
    });

    const { result, rerender } = renderHook(() => useSystemStatus());

    const message = createBackendMessage('healthy', 45, 60, 3);

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.status?.health).toBe('healthy');
    expect(result.current.status?.gpu_utilization).toBe(45);
    expect(result.current.isConnected).toBe(true);

    // Simulate disconnection
    mockConnectionState = false;
    rerender();

    expect(result.current.isConnected).toBe(false);
    // Status should persist during disconnection
    expect(result.current.status?.health).toBe('healthy');
    expect(result.current.status?.gpu_utilization).toBe(45);

    // Simulate reconnection
    mockConnectionState = true;
    rerender();

    expect(result.current.isConnected).toBe(true);
    expect(result.current.status?.health).toBe('healthy');
  });
});
