/**
 * Tests for WebSocket Discriminated Union Types
 */

import { describe, it, expect, vi } from 'vitest';

import {
  isEventMessage,
  isSystemStatusMessage,
  isServiceStatusMessage,
  isHeartbeatMessage,
  isPongMessage,
  isErrorMessage,
  isWebSocketMessage,
  createMessageDispatcher,
  assertNever,
  assertNeverSoft,
  type EventMessage,
  type SystemStatusMessage,
  type ServiceStatusMessage,
  type HeartbeatMessage,
  type PongMessage,
  type ErrorMessage,
  type SecurityEventData,
  type SystemStatusData,
  type WebSocketMessage,
} from './websocket';

// ============================================================================
// Test Fixtures
// ============================================================================

const validEventData: SecurityEventData = {
  id: 123,
  event_id: 123,
  camera_id: 'cam-uuid-123',
  camera_name: 'Front Door',
  risk_score: 75,
  risk_level: 'high',
  summary: 'Person detected at front door',
  timestamp: '2024-01-15T10:30:00Z',
  started_at: '2024-01-15T10:29:55Z',
};

const validEventMessage: EventMessage = {
  type: 'event',
  data: validEventData,
};

const validSystemStatusData: SystemStatusData = {
  gpu: {
    utilization: 85,
    memory_used: 8000000000,
    memory_total: 24000000000,
    temperature: 72,
    inference_fps: 30,
  },
  cameras: {
    active: 4,
    total: 5,
  },
  queue: {
    pending: 3,
    processing: 1,
  },
  health: 'healthy',
};

const validSystemStatusMessage: SystemStatusMessage = {
  type: 'system_status',
  data: validSystemStatusData,
  timestamp: '2024-01-15T10:30:00Z',
};

const validServiceStatusMessage: ServiceStatusMessage = {
  type: 'service_status',
  data: {
    service: 'rtdetr',
    status: 'running',
    message: 'Model loaded successfully',
  },
  timestamp: '2024-01-15T10:30:00Z',
};

const validHeartbeatMessage: HeartbeatMessage = {
  type: 'ping',
};

const validPongMessage: PongMessage = {
  type: 'pong',
};

const validErrorMessage: ErrorMessage = {
  type: 'error',
  code: 'AUTH_FAILED',
  message: 'Authentication required',
};

// ============================================================================
// Type Guard Tests
// ============================================================================

describe('WebSocket Type Guards', () => {
  describe('isEventMessage', () => {
    it('returns true for valid event message', () => {
      expect(isEventMessage(validEventMessage)).toBe(true);
    });

    it('returns true for minimal event message', () => {
      const minimal = {
        type: 'event',
        data: {
          id: 1,
          camera_id: 'cam',
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Test',
        },
      };
      expect(isEventMessage(minimal)).toBe(true);
    });

    it('returns true for event message with event_id instead of id', () => {
      const withEventId = {
        type: 'event',
        data: {
          event_id: 123,
          camera_id: 'cam',
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Test',
        },
      };
      expect(isEventMessage(withEventId)).toBe(true);
    });

    it('returns false for non-event type', () => {
      expect(isEventMessage({ type: 'ping' })).toBe(false);
      expect(isEventMessage({ type: 'system_status' })).toBe(false);
    });

    it('returns false for missing required fields', () => {
      expect(isEventMessage({ type: 'event', data: {} })).toBe(false);
      expect(
        isEventMessage({ type: 'event', data: { id: 1, camera_id: 'cam' } })
      ).toBe(false);
    });

    it('returns false for null or undefined', () => {
      expect(isEventMessage(null)).toBe(false);
      expect(isEventMessage(undefined)).toBe(false);
    });

    it('returns false for non-objects', () => {
      expect(isEventMessage('string')).toBe(false);
      expect(isEventMessage(123)).toBe(false);
      expect(isEventMessage(true)).toBe(false);
    });
  });

  describe('isSystemStatusMessage', () => {
    it('returns true for valid system status message', () => {
      expect(isSystemStatusMessage(validSystemStatusMessage)).toBe(true);
    });

    it('returns false for missing timestamp', () => {
      const noTimestamp = {
        type: 'system_status',
        data: validSystemStatusData,
      };
      expect(isSystemStatusMessage(noTimestamp)).toBe(false);
    });

    it('returns false for missing required data fields', () => {
      const missingGpu = {
        type: 'system_status',
        data: { cameras: { active: 1, total: 2 }, health: 'healthy' },
        timestamp: '2024-01-15T10:30:00Z',
      };
      expect(isSystemStatusMessage(missingGpu)).toBe(false);
    });

    it('returns false for non-system_status type', () => {
      expect(isSystemStatusMessage({ type: 'event' })).toBe(false);
    });

    it('returns false for null or undefined', () => {
      expect(isSystemStatusMessage(null)).toBe(false);
      expect(isSystemStatusMessage(undefined)).toBe(false);
    });
  });

  describe('isServiceStatusMessage', () => {
    it('returns true for valid service status message', () => {
      expect(isServiceStatusMessage(validServiceStatusMessage)).toBe(true);
    });

    it('returns true for minimal service status message', () => {
      const minimal = {
        type: 'service_status',
        data: { service: 'nemotron', status: 'running' },
        timestamp: '2024-01-15T10:30:00Z',
      };
      expect(isServiceStatusMessage(minimal)).toBe(true);
    });

    it('returns false for missing timestamp', () => {
      const noTimestamp = {
        type: 'service_status',
        data: { service: 'rtdetr', status: 'running' },
      };
      expect(isServiceStatusMessage(noTimestamp)).toBe(false);
    });

    it('returns false for missing required data fields', () => {
      const missingService = {
        type: 'service_status',
        data: { status: 'running' },
        timestamp: '2024-01-15T10:30:00Z',
      };
      expect(isServiceStatusMessage(missingService)).toBe(false);
    });
  });

  describe('isHeartbeatMessage', () => {
    it('returns true for valid ping message', () => {
      expect(isHeartbeatMessage(validHeartbeatMessage)).toBe(true);
      expect(isHeartbeatMessage({ type: 'ping' })).toBe(true);
    });

    it('returns false for non-ping type', () => {
      expect(isHeartbeatMessage({ type: 'pong' })).toBe(false);
      expect(isHeartbeatMessage({ type: 'event' })).toBe(false);
    });

    it('returns false for null or undefined', () => {
      expect(isHeartbeatMessage(null)).toBe(false);
      expect(isHeartbeatMessage(undefined)).toBe(false);
    });
  });

  describe('isPongMessage', () => {
    it('returns true for valid pong message', () => {
      expect(isPongMessage(validPongMessage)).toBe(true);
      expect(isPongMessage({ type: 'pong' })).toBe(true);
    });

    it('returns false for non-pong type', () => {
      expect(isPongMessage({ type: 'ping' })).toBe(false);
    });
  });

  describe('isErrorMessage', () => {
    it('returns true for valid error message', () => {
      expect(isErrorMessage(validErrorMessage)).toBe(true);
    });

    it('returns true for minimal error message', () => {
      expect(isErrorMessage({ type: 'error', message: 'Something went wrong' })).toBe(true);
    });

    it('returns false for missing message field', () => {
      expect(isErrorMessage({ type: 'error' })).toBe(false);
      expect(isErrorMessage({ type: 'error', code: 'ERR' })).toBe(false);
    });

    it('returns false for non-error type', () => {
      expect(isErrorMessage({ type: 'event' })).toBe(false);
    });
  });

  describe('isWebSocketMessage', () => {
    it('returns true for all valid message types', () => {
      expect(isWebSocketMessage(validEventMessage)).toBe(true);
      expect(isWebSocketMessage(validSystemStatusMessage)).toBe(true);
      expect(isWebSocketMessage(validServiceStatusMessage)).toBe(true);
      expect(isWebSocketMessage(validHeartbeatMessage)).toBe(true);
      expect(isWebSocketMessage(validPongMessage)).toBe(true);
      expect(isWebSocketMessage(validErrorMessage)).toBe(true);
    });

    it('returns false for unknown message types', () => {
      expect(isWebSocketMessage({ type: 'unknown' })).toBe(false);
      expect(isWebSocketMessage({ type: 'custom_type' })).toBe(false);
    });

    it('returns false for invalid data', () => {
      expect(isWebSocketMessage(null)).toBe(false);
      expect(isWebSocketMessage(undefined)).toBe(false);
      expect(isWebSocketMessage('string')).toBe(false);
      expect(isWebSocketMessage({})).toBe(false);
    });
  });
});

// ============================================================================
// Message Dispatcher Tests
// ============================================================================

describe('createMessageDispatcher', () => {
  it('dispatches to correct handler based on message type', () => {
    const eventHandler = vi.fn();
    const systemHandler = vi.fn();
    const pingHandler = vi.fn();

    const dispatch = createMessageDispatcher({
      event: eventHandler,
      system_status: systemHandler,
      ping: pingHandler,
    });

    dispatch(validEventMessage);
    expect(eventHandler).toHaveBeenCalledWith(validEventMessage);
    expect(systemHandler).not.toHaveBeenCalled();
    expect(pingHandler).not.toHaveBeenCalled();

    eventHandler.mockClear();
    dispatch(validSystemStatusMessage);
    expect(systemHandler).toHaveBeenCalledWith(validSystemStatusMessage);
    expect(eventHandler).not.toHaveBeenCalled();

    systemHandler.mockClear();
    dispatch(validHeartbeatMessage);
    expect(pingHandler).toHaveBeenCalledWith(validHeartbeatMessage);
  });

  it('does nothing for unhandled message types', () => {
    const eventHandler = vi.fn();

    const dispatch = createMessageDispatcher({
      event: eventHandler,
    });

    // Should not throw for unhandled message types
    expect(() => dispatch(validSystemStatusMessage)).not.toThrow();
    expect(() => dispatch(validHeartbeatMessage)).not.toThrow();
    expect(eventHandler).not.toHaveBeenCalled();
  });

  it('handles all message types when all handlers provided', () => {
    const handlers = {
      event: vi.fn(),
      system_status: vi.fn(),
      service_status: vi.fn(),
      ping: vi.fn(),
      pong: vi.fn(),
      error: vi.fn(),
    };

    const dispatch = createMessageDispatcher(handlers);

    const messages: WebSocketMessage[] = [
      validEventMessage,
      validSystemStatusMessage,
      validServiceStatusMessage,
      validHeartbeatMessage,
      validPongMessage,
      validErrorMessage,
    ];

    messages.forEach((msg) => dispatch(msg));

    expect(handlers.event).toHaveBeenCalledTimes(1);
    expect(handlers.system_status).toHaveBeenCalledTimes(1);
    expect(handlers.service_status).toHaveBeenCalledTimes(1);
    expect(handlers.ping).toHaveBeenCalledTimes(1);
    expect(handlers.pong).toHaveBeenCalledTimes(1);
    expect(handlers.error).toHaveBeenCalledTimes(1);
  });

  it('provides correctly typed message to handler', () => {
    // This test verifies type inference at compile time
    const dispatch = createMessageDispatcher({
      event: (msg) => {
        // TypeScript should infer msg as EventMessage
        expect(msg.type).toBe('event');
        expect(msg.data.risk_score).toBeDefined();
        expect(msg.data.camera_id).toBeDefined();
      },
      system_status: (msg) => {
        // TypeScript should infer msg as SystemStatusMessage
        expect(msg.type).toBe('system_status');
        expect(msg.data.gpu).toBeDefined();
        expect(msg.timestamp).toBeDefined();
      },
    });

    dispatch(validEventMessage);
    dispatch(validSystemStatusMessage);
  });
});

// ============================================================================
// Type Inference Tests
// ============================================================================

describe('Type Inference', () => {
  it('correctly narrows type in switch statement', () => {
    function handleMessage(message: WebSocketMessage): string {
      switch (message.type) {
        case 'event':
          // TypeScript knows message is EventMessage here
          return `Event: ${message.data.summary}`;
        case 'system_status':
          // TypeScript knows message is SystemStatusMessage here
          return `Health: ${message.data.health}`;
        case 'service_status':
          // TypeScript knows message is ServiceStatusMessage here
          return `Service: ${message.data.service}`;
        case 'ping':
          return 'Heartbeat';
        case 'pong':
          return 'Pong';
        case 'error':
          // TypeScript knows message is ErrorMessage here
          return `Error: ${message.message}`;
        case 'job_progress':
          return `Job Progress: ${message.data.progress}%`;
        case 'job_completed':
          return `Job Completed: ${message.data.job_id}`;
        case 'job_failed':
          return `Job Failed: ${message.data.error}`;
        case 'detection.new':
          return `Detection: ${message.data.label}`;
        case 'detection.batch':
          return `Batch: ${message.data.batch_id}`;
      }
    }

    expect(handleMessage(validEventMessage)).toBe(
      'Event: Person detected at front door'
    );
    expect(handleMessage(validSystemStatusMessage)).toBe('Health: healthy');
    expect(handleMessage(validServiceStatusMessage)).toBe('Service: rtdetr');
    expect(handleMessage(validHeartbeatMessage)).toBe('Heartbeat');
    expect(handleMessage(validPongMessage)).toBe('Pong');
    expect(handleMessage(validErrorMessage)).toBe('Error: Authentication required');
  });

  it('correctly narrows type with type guard', () => {
    function processMessage(data: unknown): string | null {
      if (isEventMessage(data)) {
        // TypeScript knows data is EventMessage here
        return data.data.summary;
      }
      if (isSystemStatusMessage(data)) {
        // TypeScript knows data is SystemStatusMessage here
        return data.data.health;
      }
      return null;
    }

    expect(processMessage(validEventMessage)).toBe('Person detected at front door');
    expect(processMessage(validSystemStatusMessage)).toBe('healthy');
    expect(processMessage({ type: 'unknown' })).toBeNull();
  });
});

// ============================================================================
// Exhaustive Check Utility Tests
// ============================================================================

describe('assertNever', () => {
  it('throws an error with the unexpected value', () => {
    // We need to cast to never to test the function
    const unexpectedValue = { type: 'unexpected' } as never;

    expect(() => assertNever(unexpectedValue)).toThrow(
      'Unexpected value: {"type":"unexpected"}'
    );
  });

  it('provides type safety for exhaustive switch statements', () => {
    // This test verifies the pattern works at runtime
    function handleMessage(message: WebSocketMessage): string {
      switch (message.type) {
        case 'event':
          return 'event';
        case 'system_status':
          return 'system_status';
        case 'service_status':
          return 'service_status';
        case 'ping':
          return 'ping';
        case 'pong':
          return 'pong';
        case 'error':
          return 'error';
        case 'job_progress':
          return 'job_progress';
        case 'job_completed':
          return 'job_completed';
        case 'job_failed':
          return 'job_failed';
        case 'detection.new':
          return 'detection.new';
        case 'detection.batch':
          return 'detection.batch';
        default:
          // TypeScript knows this is never reached if all cases are covered
          return assertNever(message);
      }
    }

    expect(handleMessage(validEventMessage)).toBe('event');
    expect(handleMessage(validSystemStatusMessage)).toBe('system_status');
    expect(handleMessage(validServiceStatusMessage)).toBe('service_status');
    expect(handleMessage(validHeartbeatMessage)).toBe('ping');
    expect(handleMessage(validPongMessage)).toBe('pong');
    expect(handleMessage(validErrorMessage)).toBe('error');
  });
});

describe('assertNeverSoft', () => {
  it('logs a warning instead of throwing', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    // We need to cast to never to test the function
    const unexpectedValue = { type: 'unexpected' } as never;

    // Should not throw
    expect(() => assertNeverSoft(unexpectedValue)).not.toThrow();

    expect(warnSpy).toHaveBeenCalledWith(
      'Unhandled value: {"type":"unexpected"}'
    );

    warnSpy.mockRestore();
  });

  it('uses context in the warning message', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const unexpectedValue = { type: 'custom_type' } as never;
    assertNeverSoft(unexpectedValue, 'WebSocket message');

    expect(warnSpy).toHaveBeenCalledWith(
      'Unhandled WebSocket message: {"type":"custom_type"}'
    );

    warnSpy.mockRestore();
  });

  it('is useful for graceful degradation', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    // Simulate a handler that gracefully handles unknown types
    function handleMessageGracefully(message: WebSocketMessage): string {
      switch (message.type) {
        case 'event':
          return 'handled event';
        case 'system_status':
          return 'handled system_status';
        case 'service_status':
          return 'handled service_status';
        case 'ping':
          return 'handled ping';
        case 'pong':
          return 'handled pong';
        case 'error':
          return 'handled error';
        case 'job_progress':
          return 'handled job_progress';
        case 'job_completed':
          return 'handled job_completed';
        case 'job_failed':
          return 'handled job_failed';
        case 'detection.new':
          return 'handled detection.new';
        case 'detection.batch':
          return 'handled detection.batch';
        default:
          assertNeverSoft(message, 'WebSocket message');
          return 'unknown';
      }
    }

    // All known types should be handled
    expect(handleMessageGracefully(validEventMessage)).toBe('handled event');
    expect(warnSpy).not.toHaveBeenCalled();

    warnSpy.mockRestore();
  });
});
