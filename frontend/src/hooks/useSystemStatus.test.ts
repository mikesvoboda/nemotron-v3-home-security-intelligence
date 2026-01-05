import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useSystemStatus } from './useSystemStatus';
import * as useWebSocketModule from './useWebSocket';
import * as apiModule from '../services/api';

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

  // Mock REST API response
  const mockHealthResponse = {
    status: 'healthy' as const,
    timestamp: '2025-12-23T10:00:00Z',
    services: {
      postgresql: { status: 'healthy' as const, latency_ms: 5 },
      redis: { status: 'healthy' as const, latency_ms: 1 },
    },
  };

  beforeEach(() => {
    // Mock useWebSocket to capture the onMessage callback
    vi.spyOn(useWebSocketModule, 'useWebSocket').mockImplementation((options) => {
      onMessageCallback = options.onMessage;
      return mockWebSocketReturn;
    });

    // Mock fetchHealth API call
    vi.spyOn(apiModule, 'fetchHealth').mockResolvedValue(mockHealthResponse);
  });

  afterEach(() => {
    vi.clearAllMocks();
    onMessageCallback = undefined;
  });

  it('should initialize with null status before REST API responds', () => {
    // Make REST API never resolve to test initial state
    vi.spyOn(apiModule, 'fetchHealth').mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useSystemStatus());

    // Before any data arrives, status should be null
    expect(result.current.status).toBeNull();
    expect(result.current.isConnected).toBe(true);
  });

  it('should connect to the correct WebSocket URL', () => {
    // Prevent REST API from resolving to avoid state update after test
    vi.spyOn(apiModule, 'fetchHealth').mockReturnValue(new Promise(() => {}));

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
    // Prevent REST API from resolving to avoid state update after test
    vi.spyOn(apiModule, 'fetchHealth').mockReturnValue(new Promise(() => {}));

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
    // Prevent REST API from resolving to avoid state update after test
    vi.spyOn(apiModule, 'fetchHealth').mockReturnValue(new Promise(() => {}));

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
    // Prevent REST API from resolving to avoid state update after test
    vi.spyOn(apiModule, 'fetchHealth').mockReturnValue(new Promise(() => {}));

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
    // Prevent REST API from resolving to avoid state update after test
    vi.spyOn(apiModule, 'fetchHealth').mockReturnValue(new Promise(() => {}));

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
    // Prevent REST API from resolving to avoid state update after test
    vi.spyOn(apiModule, 'fetchHealth').mockReturnValue(new Promise(() => {}));

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
    // Prevent REST API from resolving to avoid state update after test
    vi.spyOn(apiModule, 'fetchHealth').mockReturnValue(new Promise(() => {}));

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
    // Prevent REST API from resolving to avoid state update after test
    vi.spyOn(apiModule, 'fetchHealth').mockReturnValue(new Promise(() => {}));

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
    // Prevent REST API from resolving to avoid state update after test
    vi.spyOn(apiModule, 'fetchHealth').mockReturnValue(new Promise(() => {}));

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

  describe('REST API initial fetch', () => {
    it('should fetch initial status from REST API on mount', async () => {
      renderHook(() => useSystemStatus());

      await waitFor(() => {
        expect(apiModule.fetchHealth).toHaveBeenCalledTimes(1);
      });
    });

    it('should set initial status from REST API while waiting for WebSocket', async () => {
      const { result } = renderHook(() => useSystemStatus());

      // Wait for the REST API fetch to complete
      await waitFor(() => {
        expect(result.current.status).not.toBeNull();
      });

      // Should have status from REST API with health but null GPU values
      expect(result.current.status?.health).toBe('healthy');
      expect(result.current.status?.gpu_utilization).toBeNull();
      expect(result.current.status?.gpu_temperature).toBeNull();
      expect(result.current.status?.active_cameras).toBe(0);
    });

    it('should prefer WebSocket data over REST API initial data', async () => {
      const { result } = renderHook(() => useSystemStatus());

      // Wait for initial REST fetch
      await waitFor(() => {
        expect(result.current.status).not.toBeNull();
      });

      expect(result.current.status?.health).toBe('healthy');
      expect(result.current.status?.gpu_utilization).toBeNull();

      // Now receive WebSocket message with full data
      const wsMessage = createBackendMessage('degraded', 75, 70, 5);

      act(() => {
        onMessageCallback?.(wsMessage);
      });

      // WebSocket data should replace REST API data
      expect(result.current.status?.health).toBe('degraded');
      expect(result.current.status?.gpu_utilization).toBe(75);
      expect(result.current.status?.gpu_temperature).toBe(70);
      expect(result.current.status?.active_cameras).toBe(5);
    });

    it('should not override WebSocket data with REST API data', async () => {
      // This test ensures that if WebSocket message arrives before REST fetch completes,
      // the WebSocket data is not overwritten by the slower REST response

      // Make REST API slow to respond
      let resolveApiCall: (value: typeof mockHealthResponse) => void;
      const slowApiPromise = new Promise<typeof mockHealthResponse>((resolve) => {
        resolveApiCall = resolve;
      });
      vi.spyOn(apiModule, 'fetchHealth').mockReturnValue(slowApiPromise);

      const { result } = renderHook(() => useSystemStatus());

      // WebSocket message arrives first with 'degraded' status
      const wsMessage = createBackendMessage('degraded', 80, 75, 4);
      act(() => {
        onMessageCallback?.(wsMessage);
      });

      expect(result.current.status?.health).toBe('degraded');
      expect(result.current.status?.gpu_utilization).toBe(80);

      // Now REST API finally responds with 'healthy' status
      await act(async () => {
        resolveApiCall!(mockHealthResponse);
        await Promise.resolve(); // Let the promise resolve
      });

      // Status should still be from WebSocket (degraded), not REST API (healthy)
      expect(result.current.status?.health).toBe('degraded');
      expect(result.current.status?.gpu_utilization).toBe(80);
    });

    it('should handle REST API fetch error gracefully', async () => {
      vi.spyOn(apiModule, 'fetchHealth').mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useSystemStatus());

      // Wait a bit for the async operation
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 10));
      });

      // Status should remain null (waiting for WebSocket)
      // Error is silently caught - WebSocket will provide status eventually
      expect(result.current.status).toBeNull();
    });

    it('should handle degraded status from REST API', async () => {
      vi.spyOn(apiModule, 'fetchHealth').mockResolvedValue({
        ...mockHealthResponse,
        status: 'degraded',
      });

      const { result } = renderHook(() => useSystemStatus());

      await waitFor(() => {
        expect(result.current.status).not.toBeNull();
      });

      expect(result.current.status?.health).toBe('degraded');
    });

    it('should handle unhealthy status from REST API', async () => {
      vi.spyOn(apiModule, 'fetchHealth').mockResolvedValue({
        ...mockHealthResponse,
        status: 'unhealthy',
      });

      const { result } = renderHook(() => useSystemStatus());

      await waitFor(() => {
        expect(result.current.status).not.toBeNull();
      });

      expect(result.current.status?.health).toBe('unhealthy');
    });
  });
});
