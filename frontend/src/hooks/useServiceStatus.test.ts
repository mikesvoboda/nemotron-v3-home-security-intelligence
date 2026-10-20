import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useServiceStatus, ServiceName, ServiceStatusType } from './useServiceStatus';
import * as useWebSocketModule from './useWebSocket';

/**
 * Tests for useServiceStatus hook.
 *
 * The hook tracks per-service health via WebSocket `service_status` messages on
 * /ws/events. Every backend broadcast passes through
 * EventBroadcaster.broadcast_service_status, which re-serializes each payload
 * against WebSocketServiceStatusData — so the wire shape is always the flat
 * { service, status, message } envelope regardless of the emitter. Three emitters
 * are live (measured for ruling 267):
 *
 * - ServiceHealthMonitor probes `yolo26` (statuses healthy/unhealthy/restarting/
 *   restart_failed/failed/restart_disabled, message always a string).
 * - ContainerOrchestrator broadcasts the 19 discovery config keys (postgres,
 *   redis, backend, ...) — ServiceInfo payloads arrive flattened, with
 *   `message: null` on the wire, and only running/unhealthy/stopped/disabled
 *   survive the funnel's status enum.
 * - WorkerSupervisor broadcasts `worker:<name>` (running/stopped/crashed/
 *   restarting/failed) — RUNNING/RESTARTING sites pass message=None, i.e. null
 *   on the wire.
 *
 * `rtdetr` and `nemotron` are dropped: no emitter sends those names.
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
    lastHeartbeat: null,
    connectionId: 'mock-ws-001',
  };

  let onMessageCallback: ((data: unknown) => void) | undefined;

  // Helper to create a backend service status message
  // The backend sends messages in envelope format: { type, data: {...}, timestamp }
  const createServiceStatusMessage = (
    service: ServiceName,
    status: ServiceStatusType,
    message?: string | null,
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

  it('should initialize with no reported services (test_initial_state_empty)', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Services are keyed only once a report arrives: the hook cannot pre-seed
    // worker:<name> keys (their names are dynamic), so the map starts empty.
    expect(result.current.services).toEqual({});
    expect(result.current.hasUnhealthy).toBe(false);
    expect(result.current.hasDegraded).toBe(false);
    expect(result.current.isAnyRestarting).toBe(false);
    expect(result.current.allHealthy).toBe(true);
  });

  it('should store a yolo26 broadcast from the health monitor (test_health_monitor_yolo26)', () => {
    const { result } = renderHook(() => useServiceStatus());

    // ServiceHealthMonitor's real payload: flat { service, status, message },
    // message always a string (health_monitor.py:364).
    const message = createServiceStatusMessage('yolo26', 'healthy', 'Inference OK');

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.services.yolo26).toEqual({
      service: 'yolo26',
      status: 'healthy',
      message: 'Inference OK',
      timestamp: '2025-12-23T10:00:00Z',
    });
  });

  it('should store a flattened orchestrator broadcast with null message (test_orchestrator_shape)', () => {
    const { result } = renderHook(() => useServiceStatus());

    // ContainerOrchestrator emits ServiceInfo-shaped payloads; the broadcaster's
    // extra="ignore" + name→service alias flatten them before send, and
    // model_dump puts `message: null` on the wire (no message is set).
    const orchestratorPayload = {
      type: 'service_status',
      data: {
        service: 'postgres',
        status: 'running',
        message: null,
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(orchestratorPayload);
    });

    expect(result.current.services.postgres).toEqual({
      service: 'postgres',
      status: 'running',
      message: null,
      timestamp: '2025-12-23T10:00:00Z',
    });
  });

  it('should store a worker broadcast with null message (test_worker_supervisor_shape)', () => {
    const { result } = renderHook(() => useServiceStatus());

    // WorkerSupervisor's RUNNING/RESTARTING sites are 2-arg broadcasts —
    // message=None reaches the wire as null. The old guard (message ===
    // undefined || typeof message === 'string') rejected null and dropped
    // these updates; the hook accepts null now.
    const message = createServiceStatusMessage('worker:detection-0', 'running', null);

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.services['worker:detection-0']).toEqual({
      service: 'worker:detection-0',
      status: 'running',
      message: null,
      timestamp: '2025-12-23T10:00:00Z',
    });
  });

  it('should track worker names with any non-empty suffix (test_worker_prefix_matching)', () => {
    const { result } = renderHook(() => useServiceStatus());

    const workerNames: ServiceName[] = [
      'worker:detection-0',
      'worker:analysis-1',
      'worker:batch_timeout',
      'worker:metrics',
    ];

    workerNames.forEach((name) => {
      act(() => {
        onMessageCallback?.(createServiceStatusMessage(name, 'running'));
      });
      expect(result.current.services[name]?.status).toBe('running');
    });
  });

  it('should reject bare "worker:" with no name (test_worker_prefix_requires_suffix)', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      // 'worker:' is already a ServiceName ('worker:${string}' admits the empty
      // suffix), so no assertion is needed -- the hook must reject at runtime
      // what the type system admits.
      onMessageCallback?.(createServiceStatusMessage('worker:', 'running'));
    });

    expect(result.current.services).toEqual({});
  });

  it('should return hasUnhealthy false when all reported services are healthy', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
      onMessageCallback?.(createServiceStatusMessage('redis', 'running'));
      onMessageCallback?.(createServiceStatusMessage('worker:detection-0', 'running'));
    });

    expect(result.current.hasUnhealthy).toBe(false);
  });

  it('should return hasUnhealthy true when yolo26 is unhealthy (test_yolo26_unhealthy)', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'unhealthy', 'Probe failed'));
    });

    expect(result.current.hasUnhealthy).toBe(true);
    expect(result.current.services.yolo26?.status).toBe('unhealthy');
  });

  it('should return hasUnhealthy true when service failed', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('worker:analysis-0', 'failed'));
    });

    expect(result.current.hasUnhealthy).toBe(true);
  });

  it('should return hasUnhealthy true when service crashed', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('worker:detection-1', 'crashed'));
    });

    expect(result.current.hasUnhealthy).toBe(true);
  });

  it('should return hasUnhealthy true when service restart_failed', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'restart_failed'));
    });

    expect(result.current.hasUnhealthy).toBe(true);
  });

  it('should accept restart_disabled and flag hasUnhealthy (backend-emitted status)', () => {
    // 'restart_disabled' is broadcast by ServiceHealthMonitor every check
    // cycle for services with restart disabled (e.g. AI_RESTART_ENABLED=false)
    // — it must survive the hook's message guard and count as unhealthy
    // (unhealthy with no restart coming). It was missing from both the type
    // union and the runtime guard: the UI silently never saw those services
    // go down (2026-09-22 sandbox bring-up).
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'restart_disabled'));
    });

    expect(result.current.services.yolo26?.status).toBe('restart_disabled');
    expect(result.current.hasUnhealthy).toBe(true);
  });

  it('should return isAnyRestarting true when restarting (test_isAnyRestarting_true_when_restarting)', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'restarting'));
    });

    expect(result.current.isAnyRestarting).toBe(true);
  });

  it('should track multiple services independently (test_multiple_services_tracked_independently)', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy', 'Inference OK'));
      onMessageCallback?.(
        createServiceStatusMessage('worker:detection-0', 'unhealthy', 'Model loading failed')
      );
      onMessageCallback?.(createServiceStatusMessage('redis', 'restarting', 'Redis reconnecting'));
    });

    expect(result.current.services.yolo26?.status).toBe('healthy');
    expect(result.current.services['worker:detection-0']?.status).toBe('unhealthy');
    expect(result.current.services.redis?.status).toBe('restarting');

    expect(result.current.services.yolo26?.message).toBe('Inference OK');
    expect(result.current.services['worker:detection-0']?.message).toBe('Model loading failed');
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

    expect(result.current.services).toEqual({});
  });

  it('should return correct service status via getServiceStatus (test_getServiceStatus_returns_correct_service)', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy', 'Running'));
      onMessageCallback?.(createServiceStatusMessage('worker:detection-0', 'unhealthy', 'Failed'));
    });

    expect(result.current.getServiceStatus('yolo26')).toEqual({
      service: 'yolo26',
      status: 'healthy',
      message: 'Running',
      timestamp: '2025-12-23T10:00:00Z',
    });

    expect(result.current.getServiceStatus('worker:detection-0')?.status).toBe('unhealthy');
    expect(result.current.getServiceStatus('postgres')).toBeNull();
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
        createServiceStatusMessage('yolo26', 'healthy', 'Running', '2025-12-23T10:00:00Z')
      );
    });

    expect(result.current.services.yolo26?.status).toBe('healthy');

    act(() => {
      onMessageCallback?.(
        createServiceStatusMessage('yolo26', 'unhealthy', 'Crashed', '2025-12-23T10:01:00Z')
      );
    });

    expect(result.current.services.yolo26?.status).toBe('unhealthy');
    expect(result.current.services.yolo26?.message).toBe('Crashed');
    expect(result.current.services.yolo26?.timestamp).toBe('2025-12-23T10:01:00Z');
  });

  it('should handle every status the health monitor emits', () => {
    const { result } = renderHook(() => useServiceStatus());

    // ServiceHealthMonitor's full status set (health_monitor.py).
    const statuses: ServiceStatusType[] = [
      'healthy',
      'unhealthy',
      'restarting',
      'restart_failed',
      'restart_disabled',
      'failed',
    ];

    statuses.forEach((status) => {
      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', status));
      });

      expect(result.current.services.yolo26?.status).toBe(status);
    });
  });

  it('should handle every status the worker supervisor emits', () => {
    const { result } = renderHook(() => useServiceStatus());

    // WorkerSupervisor's full status set (WorkerStatus enum).
    const statuses: ServiceStatusType[] = ['running', 'stopped', 'crashed', 'restarting', 'failed'];

    statuses.forEach((status) => {
      act(() => {
        onMessageCallback?.(createServiceStatusMessage('worker:detection-0', status));
      });

      expect(result.current.services['worker:detection-0']?.status).toBe(status);
    });
  });

  it('should handle every status the container orchestrator can broadcast', () => {
    const { result } = renderHook(() => useServiceStatus());

    // ContainerOrchestrator's statuses that survive the broadcaster's enum:
    // running/unhealthy/stopped/disabled pass; starting/not_found are rejected
    // at the broadcaster and never reach the hook (so the hook never needs to
    // accept them — tested separately below).
    const statuses: ServiceStatusType[] = ['running', 'unhealthy', 'stopped', 'disabled'];

    statuses.forEach((status) => {
      act(() => {
        onMessageCallback?.(createServiceStatusMessage('backend', status, null));
      });

      expect(result.current.services.backend?.status).toBe(status);
    });
  });

  it('should preserve other services when one service updates', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
      onMessageCallback?.(createServiceStatusMessage('worker:detection-0', 'running', null));
    });

    // Now update yolo26
    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'unhealthy'));
    });

    // worker:detection-0 should still be there
    expect(result.current.services['worker:detection-0']?.status).toBe('running');
    expect(result.current.services.yolo26?.status).toBe('unhealthy');
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

    expect(result.current.services).toEqual({});
  });

  it('should ignore rtdetr and nemotron broadcasts (no emitter sends them)', () => {
    const { result } = renderHook(() => useServiceStatus());

    // R8 renamed the probed AI service to `yolo26` and removed nemotron from
    // the data; the orchestrator names the gateway `ai-gateway`. No backend
    // emitter sends `rtdetr` or `nemotron` over this channel anymore.
    act(() => {
      onMessageCallback?.(
        createServiceStatusMessage('rtdetr' as ServiceName, 'healthy', 'RT-DETRv2 running')
      );
      onMessageCallback?.(
        createServiceStatusMessage('nemotron' as ServiceName, 'healthy', 'Nemotron running')
      );
    });

    expect(result.current.services).toEqual({});
  });

  it('should ignore messages with invalid status', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Backend envelope format with invalid status in data
    const invalidMessage = {
      type: 'service_status',
      data: {
        service: 'yolo26',
        status: 'invalid_status',
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(invalidMessage);
    });

    expect(result.current.services.yolo26).toBeUndefined();
  });

  it('should ignore funnel-rejected orchestrator statuses (starting, not_found)', () => {
    const { result } = renderHook(() => useServiceStatus());

    // ContainerOrchestrator emits 'starting' and 'not_found' locally, but the
    // broadcaster's WebSocketServiceStatus enum rejects them — the orchestrator
    // logs "Failed to broadcast" and continues, so these statuses never arrive
    // at the hook. The guard rejects them defensively too.
    act(() => {
      onMessageCallback?.(createServiceStatusMessage('postgres', 'starting' as ServiceStatusType));
      onMessageCallback?.(createServiceStatusMessage('backend', 'not_found' as ServiceStatusType));
    });

    expect(result.current.services).toEqual({});
  });

  it('should ignore messages missing timestamp', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Backend envelope format missing timestamp at envelope level
    const invalidMessage = {
      type: 'service_status',
      data: {
        service: 'yolo26',
        status: 'healthy',
      },
      // missing timestamp
    };

    act(() => {
      onMessageCallback?.(invalidMessage);
    });

    expect(result.current.services.yolo26).toBeUndefined();
  });

  it('should handle rapid successive status updates', () => {
    const { result } = renderHook(() => useServiceStatus());

    for (let i = 0; i < 10; i++) {
      const status: ServiceStatusType = i % 2 === 0 ? 'healthy' : 'unhealthy';
      const message = createServiceStatusMessage(
        'yolo26',
        status,
        `Update ${i}`,
        `2025-12-23T10:00:${String(i).padStart(2, '0')}Z`
      );

      act(() => {
        onMessageCallback?.(message);
      });
    }

    // Should have the last status
    expect(result.current.services.yolo26?.status).toBe('unhealthy');
    expect(result.current.services.yolo26?.message).toBe('Update 9');
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
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
      onMessageCallback?.(createServiceStatusMessage('redis', 'restarting'));
      onMessageCallback?.(createServiceStatusMessage('worker:detection-0', 'failed'));
    });

    expect(result.current.hasUnhealthy).toBe(true);
    expect(result.current.isAnyRestarting).toBe(true);
  });

  it('should not mutate received message object', () => {
    const { result } = renderHook(() => useServiceStatus());

    const originalMessage = createServiceStatusMessage('yolo26', 'healthy', 'Running');
    const messageCopy = JSON.parse(JSON.stringify(originalMessage));

    act(() => {
      onMessageCallback?.(originalMessage);
    });

    expect(result.current.services.yolo26?.status).toBe('healthy');
    expect(originalMessage).toEqual(messageCopy);
  });

  it('should handle message with optional message field undefined', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Backend envelope format: { type, data: {...}, timestamp }
    const message = {
      type: 'service_status',
      data: {
        service: 'yolo26' as ServiceName,
        status: 'healthy' as ServiceStatusType,
        // message field intentionally undefined
      },
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.services.yolo26?.status).toBe('healthy');
    expect(result.current.services.yolo26?.message).toBeUndefined();
  });

  it('should handle one report per emitter family (test_three_emitter_families)', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Health monitor (yolo26), container orchestrator (postgres), worker
    // supervisor (worker:detection-0) — the three live emitters' namespaces.
    const services: ServiceName[] = ['yolo26', 'postgres', 'worker:detection-0'];

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

    expect(result.current.services.yolo26?.status).toBe('healthy');
    expect(result.current.services.postgres?.status).toBe('healthy');
    expect(result.current.services['worker:detection-0']?.status).toBe('healthy');
  });

  it('should return isAnyRestarting false when no service is restarting', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
      onMessageCallback?.(createServiceStatusMessage('postgres', 'running', null));
      onMessageCallback?.(createServiceStatusMessage('worker:detection-0', 'failed'));
    });

    expect(result.current.isAnyRestarting).toBe(false);
  });

  it('should handle hasUnhealthy with restart_failed status', () => {
    const { result } = renderHook(() => useServiceStatus());

    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'restart_failed'));
    });

    expect(result.current.hasUnhealthy).toBe(true);
  });

  it('should handle transition from unhealthy back to healthy', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Service becomes unhealthy
    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'unhealthy'));
    });

    expect(result.current.hasUnhealthy).toBe(true);

    // Service recovers
    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
    });

    expect(result.current.hasUnhealthy).toBe(false);
  });

  it('should handle transition from restarting to healthy', () => {
    const { result } = renderHook(() => useServiceStatus());

    // Service is restarting
    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'restarting'));
    });

    expect(result.current.isAnyRestarting).toBe(true);

    // Service completes restart
    act(() => {
      onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
    });

    expect(result.current.isAnyRestarting).toBe(false);
  });

  // Tests for new features: allHealthy, hasDegraded, onStatusChange callback

  describe('allHealthy', () => {
    it('should return true when no services have reported yet', () => {
      const { result } = renderHook(() => useServiceStatus());

      // The services map starts empty and cannot be pre-seeded (worker names
      // are dynamic), so "all healthy" is vacuously true until a report
      // arrives. Overall health for the not-yet-reported case comes from
      // useSystemStatus, not this flag.
      expect(result.current.allHealthy).toBe(true);
    });

    it('should return true when every reported service is healthy', () => {
      const { result } = renderHook(() => useServiceStatus());

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
        onMessageCallback?.(createServiceStatusMessage('postgres', 'healthy'));
      });

      expect(result.current.allHealthy).toBe(true);
    });

    it('should return false when any reported service is unhealthy', () => {
      const { result } = renderHook(() => useServiceStatus());

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
        onMessageCallback?.(createServiceStatusMessage('postgres', 'unhealthy'));
      });

      expect(result.current.allHealthy).toBe(false);
    });

    it('should return false when any reported service is restarting', () => {
      const { result } = renderHook(() => useServiceStatus());

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
        onMessageCallback?.(createServiceStatusMessage('worker:detection-0', 'restarting'));
      });

      expect(result.current.allHealthy).toBe(false);
    });

    it('should return false when a running (not healthy) report is the only one', () => {
      const { result } = renderHook(() => useServiceStatus());

      // 'running' is the orchestrator's healthy-state status; the hook's
      // allHealthy only counts literal 'healthy' reports, so an orchestrator
      // up-report does not claim "all healthy".
      act(() => {
        onMessageCallback?.(createServiceStatusMessage('postgres', 'running', null));
      });

      expect(result.current.allHealthy).toBe(false);
    });

    it('should transition from true to false when a service reports unhealthy', () => {
      const { result } = renderHook(() => useServiceStatus());

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
        onMessageCallback?.(createServiceStatusMessage('postgres', 'healthy'));
      });

      expect(result.current.allHealthy).toBe(true);

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('worker:detection-0', 'failed'));
      });

      expect(result.current.allHealthy).toBe(false);
    });
  });

  describe('hasDegraded', () => {
    it('should return false initially', () => {
      const { result } = renderHook(() => useServiceStatus());

      expect(result.current.hasDegraded).toBe(false);
    });

    it('should return true when a service is restarting', () => {
      const { result } = renderHook(() => useServiceStatus());

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'restarting'));
      });

      expect(result.current.hasDegraded).toBe(true);
    });

    it('should return false when all services are healthy', () => {
      const { result } = renderHook(() => useServiceStatus());

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
        onMessageCallback?.(createServiceStatusMessage('postgres', 'healthy'));
      });

      expect(result.current.hasDegraded).toBe(false);
    });

    it('should return false when a service is unhealthy (not degraded)', () => {
      const { result } = renderHook(() => useServiceStatus());

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'unhealthy'));
      });

      // unhealthy is not degraded, it's a failure state
      expect(result.current.hasDegraded).toBe(false);
      expect(result.current.hasUnhealthy).toBe(true);
    });
  });

  describe('onStatusChange callback', () => {
    it('should call callback when service status changes', () => {
      const onStatusChange = vi.fn();
      const { result } = renderHook(() => useServiceStatus({ onStatusChange }));

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy', 'Running'));
      });

      expect(onStatusChange).toHaveBeenCalledTimes(1);
      expect(onStatusChange).toHaveBeenCalledWith(
        'yolo26',
        expect.objectContaining({
          service: 'yolo26',
          status: 'healthy',
          message: 'Running',
        }),
        null // previous status was null
      );
      expect(result.current.services.yolo26?.status).toBe('healthy');
    });

    it('should pass previous status to callback on subsequent updates', () => {
      const onStatusChange = vi.fn();
      renderHook(() => useServiceStatus({ onStatusChange }));

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy', 'Running'));
      });

      onStatusChange.mockClear();

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'unhealthy', 'Crashed'));
      });

      expect(onStatusChange).toHaveBeenCalledTimes(1);
      expect(onStatusChange).toHaveBeenCalledWith(
        'yolo26',
        expect.objectContaining({
          service: 'yolo26',
          status: 'unhealthy',
          message: 'Crashed',
        }),
        expect.objectContaining({
          service: 'yolo26',
          status: 'healthy',
          message: 'Running',
        })
      );
    });

    it('should call callback for each service independently', () => {
      const onStatusChange = vi.fn();
      renderHook(() => useServiceStatus({ onStatusChange }));

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
      });

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('worker:detection-0', 'unhealthy'));
      });

      expect(onStatusChange).toHaveBeenCalledTimes(2);
      expect(onStatusChange).toHaveBeenNthCalledWith(
        1,
        'yolo26',
        expect.objectContaining({ status: 'healthy' }),
        null
      );
      expect(onStatusChange).toHaveBeenNthCalledWith(
        2,
        'worker:detection-0',
        expect.objectContaining({ status: 'unhealthy' }),
        null
      );
    });

    it('should not call callback when non-service-status messages are received', () => {
      const onStatusChange = vi.fn();
      renderHook(() => useServiceStatus({ onStatusChange }));

      act(() => {
        onMessageCallback?.({ type: 'system_status', data: { health: 'healthy' } });
        onMessageCallback?.({ type: 'event', data: { id: 1 } });
        onMessageCallback?.(null);
      });

      expect(onStatusChange).not.toHaveBeenCalled();
    });

    it('should not call callback for out-of-scope service names', () => {
      const onStatusChange = vi.fn();
      renderHook(() => useServiceStatus({ onStatusChange }));

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('rtdetr' as ServiceName, 'healthy'));
        onMessageCallback?.(createServiceStatusMessage('nemotron' as ServiceName, 'healthy'));
      });

      expect(onStatusChange).not.toHaveBeenCalled();
    });

    it('should handle callback being undefined', () => {
      // Should not throw when no callback is provided
      const { result } = renderHook(() => useServiceStatus());

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
      });

      expect(result.current.services.yolo26?.status).toBe('healthy');
    });

    it('should use updated callback reference after rerender', () => {
      const firstCallback = vi.fn();
      const secondCallback = vi.fn();

      const { rerender } = renderHook(
        ({ callback }) => useServiceStatus({ onStatusChange: callback }),
        { initialProps: { callback: firstCallback } }
      );

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'healthy'));
      });

      expect(firstCallback).toHaveBeenCalledTimes(1);
      expect(secondCallback).not.toHaveBeenCalled();

      // Update the callback
      rerender({ callback: secondCallback });

      act(() => {
        onMessageCallback?.(createServiceStatusMessage('yolo26', 'unhealthy'));
      });

      // First callback should still have 1 call, second should have 1
      expect(firstCallback).toHaveBeenCalledTimes(1);
      expect(secondCallback).toHaveBeenCalledTimes(1);
    });
  });
});
