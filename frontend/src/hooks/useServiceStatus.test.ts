import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useServiceStatus, ServiceName, ServiceStatusType } from './useServiceStatus';
import * as useWebSocketModule from './useWebSocket';

/**
 * Tests for useServiceStatus hook.
 *
 * This hook tracks per-service health status (RT-DETRv2, Nemotron) via WebSocket
 * messages broadcast by the backend's ServiceHealthMonitor.
 */
describe('useServiceStatus', () => {
  const mockWebSocketReturn = {
    isConnected: true,
    lastMessage: null,
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    hasExhaustedRetries: false,
    reconnectCount: 0,
  };

  let onMessageCallback: ((data: unknown) => void) | undefined;

  // Helper to create a backend service status message
  // The backend sends messages in envelope format: { type, data: {...}, timestamp }
  const createServiceStatusMessage = (
    service: ServiceName,
    status: ServiceStatusType,
    message?: string,
    timestamp: string = '2025-12-23T10:00:00Z'
  ) => ({
    type: 'service_status',
    data: {
      service,
      status,
      message,
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

  it('should initialize with null services (test_initial_state_all_services_null)', () => {
    const { result } = renderHook(() => useServiceStatus());

    expect(result.current.services.redis).toBeNull();
    expect(result.current.services.rtdetr).toBeNull();
    expect(result.current.services.nemotron).toBeNull();
    expect(result.current.hasUnhealthy).toBe(false);
    expect(result.current.isAnyRestarting).toBe(false);
  });

  it('should update state on websocket message (test_updates_on_websocket_message)', () => {
    const { result } = renderHook(() => useServiceStatus());

    const message = createServiceStatusMessage('rtdetr', 'healthy', 'RT-DETRv2 running');

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.services.rtdetr).toEqual({
      service: 'rtdetr',
      status: 'healthy',
      message: 'RT-DETRv2 running',
      timestamp: '2025-12-23T10:00:00Z',
    });
  });

  it('should return hasUnhealthy false when all healthy (test_hasUnhealthy_false_when_all_healthy)', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'healthy'));
      onMessageCallback?.(createServiceStatusMessage('nemotron', 'healthy'));
      onMessageCallback?.(createServiceStatusMessage('redis', 'healthy'));
    });

    expect(result.current.hasUnhealthy).toBe(false);
  });

  it('should return hasUnhealthy true when service unhealthy (test_hasUnhealthy_true_when_service_down)', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'healthy'));
      onMessageCallback?.(createServiceStatusMessage('nemotron', 'unhealthy'));
    });

    expect(result.current.hasUnhealthy).toBe(true);
  });

  it('should return hasUnhealthy true when service failed', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'failed'));
    });

    expect(result.current.hasUnhealthy).toBe(true);
  });

  it('should return hasUnhealthy true when service restart_failed', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'restart_failed'));
    });

    expect(result.current.hasUnhealthy).toBe(true);
  });

  it('should return isAnyRestarting true when restarting (test_isAnyRestarting_true_when_restarting)', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'restarting'));
    });

    expect(result.current.isAnyRestarting).toBe(true);
  });

  it('should track multiple services independently (test_multiple_services_tracked_independently)', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'healthy', 'RT-DETRv2 running'));
      onMessageCallback?.(
        createServiceStatusMessage('nemotron', 'unhealthy', 'Model loading failed')
      );
      onMessageCallback?.(createServiceStatusMessage('redis', 'restarting', 'Redis reconnecting'));
    });

    expect(result.current.services.rtdetr?.status).toBe('healthy');
    expect(result.current.services.nemotron?.status).toBe('unhealthy');
    expect(result.current.services.redis?.status).toBe('restarting');

    expect(result.current.services.rtdetr?.message).toBe('RT-DETRv2 running');
    expect(result.current.services.nemotron?.message).toBe('Model loading failed');
    expect(result.current.services.redis?.message).toBe('Redis reconnecting');
  });

  it('should filter non-service-status messages (test_filters_non_service_status_messages)', () => {
    const { result } = renderHook(() => useServiceStatus());

    const nonServiceMessages = [
      { type: 'system_status', data: { health: 'healthy' } },
      { type: 'event_created', data: { id: 1 } },
      { type: 'detection', data: { objects: [] } },
      null,
      undefined,
      'string message',
      42,
      [],
    ];

    act(() => {
      nonServiceMessages.forEach((msg) => onMessageCallback?.(msg));
    });

    expect(result.current.services.redis).toBeNull();
    expect(result.current.services.rtdetr).toBeNull();
    expect(result.current.services.nemotron).toBeNull();
  });

  it('should return correct service status via getServiceStatus (test_getServiceStatus_returns_correct_service)', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'healthy', 'Running'));
      onMessageCallback?.(createServiceStatusMessage('nemotron', 'unhealthy', 'Failed'));
    });

    expect(result.current.getServiceStatus('rtdetr')).toEqual({
      service: 'rtdetr',
      status: 'healthy',
      message: 'Running',
      timestamp: '2025-12-23T10:00:00Z',
    });

    expect(result.current.getServiceStatus('nemotron')?.status).toBe('unhealthy');
    expect(result.current.getServiceStatus('redis')).toBeNull();
  });

  it('should connect to the correct WebSocket URL', () => {
    renderHook(() => useServiceStatus());

    // useServiceStatus connects to /ws/events because service_status messages
    // are broadcast via EventBroadcaster (used by /ws/events), not SystemBroadcaster
    expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
      expect.objectContaining({
        url: expect.stringContaining('/ws/events'),
        onMessage: expect.any(Function),
      })
    );
  });

  it('should update service status when same service sends new status', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(
        createServiceStatusMessage('rtdetr', 'healthy', 'Running', '2025-12-23T10:00:00Z')
      );
    });

    expect(result.current.services.rtdetr?.status).toBe('healthy');

    act(() => {
      onMessageCallback?.(
        createServiceStatusMessage('rtdetr', 'unhealthy', 'Crashed', '2025-12-23T10:01:00Z')
      );
    });

    expect(result.current.services.rtdetr?.status).toBe('unhealthy');
    expect(result.current.services.rtdetr?.message).toBe('Crashed');
    expect(result.current.services.rtdetr?.timestamp).toBe('2025-12-23T10:01:00Z');
  });

  it('should handle all service status states', () => {
    const { result } = renderHook(() => useServiceStatus());

    const statuses: ServiceStatusType[] = [
      'healthy',
      'unhealthy',
      'restarting',
      'restart_failed',
      'failed',
    ];

    statuses.forEach((status) => {
      act(() => {
        onMessageCallback?.(createServiceStatusMessage('rtdetr', status));
      });

      expect(result.current.services.rtdetr?.status).toBe(status);
    });
  });

  it('should preserve other services when one service updates', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'healthy'));
      onMessageCallback?.(createServiceStatusMessage('nemotron', 'healthy'));
    });

    // Now update rtdetr
    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'unhealthy'));
    });

    // nemotron should still be there
    expect(result.current.services.nemotron?.status).toBe('healthy');
    expect(result.current.services.rtdetr?.status).toBe('unhealthy');
  });

  it('should ignore messages with invalid service name', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Backend envelope format with invalid service name in data
    const invalidMessage = {
      type: 'service_status',
      data: {
        service: 'invalid_service',
        status: 'healthy',
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(invalidMessage);
    });

    expect(result.current.services.redis).toBeNull();
    expect(result.current.services.rtdetr).toBeNull();
    expect(result.current.services.nemotron).toBeNull();
  });

  it('should ignore messages with invalid status', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Backend envelope format with invalid status in data
    const invalidMessage = {
      type: 'service_status',
      data: {
        service: 'rtdetr',
        status: 'invalid_status',
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(invalidMessage);
    });

    expect(result.current.services.rtdetr).toBeNull();
  });

  it('should ignore messages missing timestamp', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Backend envelope format missing timestamp at envelope level
    const invalidMessage = {
      type: 'service_status',
      data: {
        service: 'rtdetr',
        status: 'healthy',
      },
      // missing timestamp
    };

    act(() => {
      onMessageCallback?.(invalidMessage);
    });

    expect(result.current.services.rtdetr).toBeNull();
  });

  it('should handle rapid successive status updates', () => {
    const { result } = renderHook(() => useServiceStatus());

    for (let i = 0; i < 10; i++) {
      const status: ServiceStatusType = i % 2 === 0 ? 'healthy' : 'unhealthy';
      const message = createServiceStatusMessage(
        'rtdetr',
        status,
        `Update ${i}`,
        `2025-12-23T10:00:${String(i).padStart(2, '0')}Z`
      );

      act(() => {
        onMessageCallback?.(message);
      });
    }

    // Should have the last status
    expect(result.current.services.rtdetr?.status).toBe('unhealthy');
    expect(result.current.services.rtdetr?.message).toBe('Update 9');
  });

  it('should maintain handleMessage callback stability', () => {
    const { rerender } = renderHook(() => useServiceStatus());

    const firstCallback = onMessageCallback;

    rerender();

    const secondCallback = onMessageCallback;

    // useCallback should maintain the same reference
    expect(firstCallback).toBe(secondCallback);
  });

  it('should handle worst status correctly - failed takes precedence', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'healthy'));
      onMessageCallback?.(createServiceStatusMessage('nemotron', 'restarting'));
      onMessageCallback?.(createServiceStatusMessage('redis', 'failed'));
    });

    expect(result.current.hasUnhealthy).toBe(true);
    expect(result.current.isAnyRestarting).toBe(true);
  });

  it('should not mutate received message object', () => {
    const { result } = renderHook(() => useServiceStatus());

    const originalMessage = createServiceStatusMessage('rtdetr', 'healthy', 'Running');
    const messageCopy = JSON.parse(JSON.stringify(originalMessage));

    act(() => {
      onMessageCallback?.(originalMessage);
    });

    expect(result.current.services.rtdetr?.status).toBe('healthy');
    expect(originalMessage).toEqual(messageCopy);
  });

  it('should handle message with optional message field undefined', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Backend envelope format: { type, data: {...}, timestamp }
    const message = {
      type: 'service_status',
      data: {
        service: 'rtdetr' as ServiceName,
        status: 'healthy' as ServiceStatusType,
        // message field intentionally undefined
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.services.rtdetr?.status).toBe('healthy');
    expect(result.current.services.rtdetr?.message).toBeUndefined();
  });

  it('should handle all three known services', () => {
    const { result } = renderHook(() => useServiceStatus());

    const services: ServiceName[] = ['redis', 'rtdetr', 'nemotron'];

    services.forEach((service, index) => {
      act(() => {
        onMessageCallback?.(
          createServiceStatusMessage(
            service,
            'healthy',
            `${service} running`,
            `2025-12-23T10:0${index}:00Z`
          )
        );
      });
    });

    expect(result.current.services.redis?.status).toBe('healthy');
    expect(result.current.services.rtdetr?.status).toBe('healthy');
    expect(result.current.services.nemotron?.status).toBe('healthy');
  });

  it('should return isAnyRestarting false when no service is restarting', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'healthy'));
      onMessageCallback?.(createServiceStatusMessage('nemotron', 'unhealthy'));
      onMessageCallback?.(createServiceStatusMessage('redis', 'failed'));
    });

    expect(result.current.isAnyRestarting).toBe(false);
  });

  it('should handle hasUnhealthy with restart_failed status', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'restart_failed'));
    });

    expect(result.current.hasUnhealthy).toBe(true);
  });

  it('should handle transition from unhealthy back to healthy', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Service becomes unhealthy
    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'unhealthy'));
    });

    expect(result.current.hasUnhealthy).toBe(true);

    // Service recovers
    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'healthy'));
    });

    expect(result.current.hasUnhealthy).toBe(false);
  });

  it('should handle transition from restarting to healthy', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Service is restarting
    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'restarting'));
    });

    expect(result.current.isAnyRestarting).toBe(true);

    // Service completes restart
    act(() => {
      onMessageCallback?.(createServiceStatusMessage('rtdetr', 'healthy'));
    });

    expect(result.current.isAnyRestarting).toBe(false);
  });
});
