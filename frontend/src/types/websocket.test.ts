/**
 * Tests for WebSocket discriminated union types and type guards.
 *
 * Following TDD approach: these tests define the expected behavior
 * for the WebSocket message type system before implementation.
 */
import { describe, it, expect } from 'vitest';

import {
  type WebSocketMessage,
  type PingMessage,
  type PongMessage,
  type EventMessage,
  type SystemStatusMessage,
  type ServiceStatusMessage,
  type PerformanceUpdateMessage,
  isPingMessage,
  isPongMessage,
  isEventMessage,
  isSystemStatusMessage,
  isServiceStatusMessage,
  isPerformanceUpdateMessage,
  isWebSocketMessage,
  assertNever,
} from './websocket';

// ============================================================================
// Test Data Factories
// ============================================================================

function createPingMessage(): PingMessage {
  return { type: 'ping' };
}

function createPongMessage(): PongMessage {
  return { type: 'pong' };
}

function createEventMessage(): EventMessage {
  return {
    type: 'event',
    data: {
      id: 'evt-123',
      event_id: 123,
      camera_id: 'cam-001',
      camera_name: 'Front Door',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected at front door',
      timestamp: '2024-01-15T10:00:00Z',
    },
  };
}

function createSystemStatusMessage(): SystemStatusMessage {
  return {
    type: 'system_status',
    data: {
      gpu: {
        utilization: 45,
        memory_used: 8192,
        memory_total: 24576,
        temperature: 55,
        inference_fps: 12.5,
      },
      cameras: {
        active: 4,
        total: 6,
      },
      queue: {
        pending: 2,
        processing: 1,
      },
      health: 'healthy',
    },
    timestamp: '2024-01-15T10:00:00Z',
  };
}

function createServiceStatusMessage(): ServiceStatusMessage {
  return {
    type: 'service_status',
    data: {
      service: 'rtdetr',
      status: 'healthy',
      message: 'RT-DETRv2 model loaded and ready',
    },
    timestamp: '2024-01-15T10:00:00Z',
  };
}

function createPerformanceUpdateMessage(): PerformanceUpdateMessage {
  return {
    type: 'performance_update',
    data: {
      timestamp: '2024-01-15T10:00:00Z',
      gpu: {
        name: 'NVIDIA RTX A5500',
        utilization: 45,
        vram_used_gb: 8.0,
        vram_total_gb: 24.0,
        temperature: 55,
        power_watts: 120,
      },
      ai_models: {},
      nemotron: null,
      inference: null,
      databases: {},
      host: null,
      containers: [],
      alerts: [],
    },
  };
}

// ============================================================================
// Type Guard Tests
// ============================================================================

describe('WebSocket Message Type Guards', () => {
  describe('isPingMessage', () => {
    it('returns true for valid ping message', () => {
      const msg = createPingMessage();
      expect(isPingMessage(msg)).toBe(true);
    });

    it('returns false for pong message', () => {
      const msg = createPongMessage();
      expect(isPingMessage(msg)).toBe(false);
    });

    it('returns false for other message types', () => {
      expect(isPingMessage(createEventMessage())).toBe(false);
      expect(isPingMessage(createSystemStatusMessage())).toBe(false);
      expect(isPingMessage(createServiceStatusMessage())).toBe(false);
      expect(isPingMessage(createPerformanceUpdateMessage())).toBe(false);
    });

    it('returns false for null/undefined', () => {
      expect(isPingMessage(null)).toBe(false);
      expect(isPingMessage(undefined)).toBe(false);
    });

    it('returns false for non-object values', () => {
      expect(isPingMessage('ping')).toBe(false);
      expect(isPingMessage(123)).toBe(false);
      expect(isPingMessage(true)).toBe(false);
    });

    it('returns false for object without type field', () => {
      expect(isPingMessage({ data: 'ping' })).toBe(false);
    });
  });

  describe('isPongMessage', () => {
    it('returns true for valid pong message', () => {
      const msg = createPongMessage();
      expect(isPongMessage(msg)).toBe(true);
    });

    it('returns false for ping message', () => {
      const msg = createPingMessage();
      expect(isPongMessage(msg)).toBe(false);
    });

    it('returns false for other message types', () => {
      expect(isPongMessage(createEventMessage())).toBe(false);
      expect(isPongMessage(createSystemStatusMessage())).toBe(false);
    });

    it('returns false for null/undefined', () => {
      expect(isPongMessage(null)).toBe(false);
      expect(isPongMessage(undefined)).toBe(false);
    });
  });

  describe('isEventMessage', () => {
    it('returns true for valid event message', () => {
      const msg = createEventMessage();
      expect(isEventMessage(msg)).toBe(true);
    });

    it('returns false for system status message', () => {
      const msg = createSystemStatusMessage();
      expect(isEventMessage(msg)).toBe(false);
    });

    it('returns false for message with wrong type', () => {
      const msg = { type: 'event' }; // Missing data
      expect(isEventMessage(msg)).toBe(false);
    });

    it('returns false for message with invalid data structure', () => {
      const msg = {
        type: 'event',
        data: { id: 123 }, // Missing required fields
      };
      expect(isEventMessage(msg)).toBe(false);
    });

    it('validates required event data fields', () => {
      // Valid minimal event data
      const validMsg = {
        type: 'event',
        data: {
          id: 'evt-1',
          camera_id: 'cam-1',
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Test event',
        },
      };
      expect(isEventMessage(validMsg)).toBe(true);
    });

    it('returns false for null/undefined', () => {
      expect(isEventMessage(null)).toBe(false);
      expect(isEventMessage(undefined)).toBe(false);
    });
  });

  describe('isSystemStatusMessage', () => {
    it('returns true for valid system status message', () => {
      const msg = createSystemStatusMessage();
      expect(isSystemStatusMessage(msg)).toBe(true);
    });

    it('returns false for event message', () => {
      const msg = createEventMessage();
      expect(isSystemStatusMessage(msg)).toBe(false);
    });

    it('returns false for message missing timestamp', () => {
      const msg = {
        type: 'system_status',
        data: {
          gpu: {},
          cameras: { active: 0, total: 0 },
          queue: { pending: 0, processing: 0 },
          health: 'healthy',
        },
        // Missing timestamp
      };
      expect(isSystemStatusMessage(msg)).toBe(false);
    });

    it('returns false for message with invalid data structure', () => {
      const msg = {
        type: 'system_status',
        data: { health: 'healthy' }, // Missing gpu, cameras, queue
        timestamp: '2024-01-15T10:00:00Z',
      };
      expect(isSystemStatusMessage(msg)).toBe(false);
    });

    it('returns false for null/undefined', () => {
      expect(isSystemStatusMessage(null)).toBe(false);
      expect(isSystemStatusMessage(undefined)).toBe(false);
    });
  });

  describe('isServiceStatusMessage', () => {
    it('returns true for valid service status message', () => {
      const msg = createServiceStatusMessage();
      expect(isServiceStatusMessage(msg)).toBe(true);
    });

    it('returns false for system status message', () => {
      const msg = createSystemStatusMessage();
      expect(isServiceStatusMessage(msg)).toBe(false);
    });

    it('validates service name enum', () => {
      const validServices = ['redis', 'rtdetr', 'nemotron'];
      for (const service of validServices) {
        const msg = {
          type: 'service_status',
          data: { service, status: 'healthy' },
          timestamp: '2024-01-15T10:00:00Z',
        };
        expect(isServiceStatusMessage(msg)).toBe(true);
      }
    });

    it('returns false for invalid service name', () => {
      const msg = {
        type: 'service_status',
        data: { service: 'unknown_service', status: 'healthy' },
        timestamp: '2024-01-15T10:00:00Z',
      };
      expect(isServiceStatusMessage(msg)).toBe(false);
    });

    it('validates status type enum', () => {
      const validStatuses = ['healthy', 'unhealthy', 'restarting', 'restart_failed', 'failed'];
      for (const status of validStatuses) {
        const msg = {
          type: 'service_status',
          data: { service: 'rtdetr', status },
          timestamp: '2024-01-15T10:00:00Z',
        };
        expect(isServiceStatusMessage(msg)).toBe(true);
      }
    });

    it('returns false for invalid status type', () => {
      const msg = {
        type: 'service_status',
        data: { service: 'rtdetr', status: 'unknown_status' },
        timestamp: '2024-01-15T10:00:00Z',
      };
      expect(isServiceStatusMessage(msg)).toBe(false);
    });

    it('allows optional message field', () => {
      const withMessage = {
        type: 'service_status',
        data: { service: 'rtdetr', status: 'healthy', message: 'All good' },
        timestamp: '2024-01-15T10:00:00Z',
      };
      const withoutMessage = {
        type: 'service_status',
        data: { service: 'rtdetr', status: 'healthy' },
        timestamp: '2024-01-15T10:00:00Z',
      };
      expect(isServiceStatusMessage(withMessage)).toBe(true);
      expect(isServiceStatusMessage(withoutMessage)).toBe(true);
    });

    it('returns false for null/undefined', () => {
      expect(isServiceStatusMessage(null)).toBe(false);
      expect(isServiceStatusMessage(undefined)).toBe(false);
    });
  });

  describe('isPerformanceUpdateMessage', () => {
    it('returns true for valid performance update message', () => {
      const msg = createPerformanceUpdateMessage();
      expect(isPerformanceUpdateMessage(msg)).toBe(true);
    });

    it('returns false for system status message', () => {
      const msg = createSystemStatusMessage();
      expect(isPerformanceUpdateMessage(msg)).toBe(false);
    });

    it('validates required timestamp field in data', () => {
      const msg = {
        type: 'performance_update',
        data: {
          // Missing timestamp
          gpu: null,
          ai_models: {},
          nemotron: null,
          inference: null,
          databases: {},
          host: null,
          containers: [],
          alerts: [],
        },
      };
      expect(isPerformanceUpdateMessage(msg)).toBe(false);
    });

    it('returns false for null/undefined', () => {
      expect(isPerformanceUpdateMessage(null)).toBe(false);
      expect(isPerformanceUpdateMessage(undefined)).toBe(false);
    });
  });

  describe('isWebSocketMessage (union type guard)', () => {
    it('returns true for any valid message type', () => {
      expect(isWebSocketMessage(createPingMessage())).toBe(true);
      expect(isWebSocketMessage(createPongMessage())).toBe(true);
      expect(isWebSocketMessage(createEventMessage())).toBe(true);
      expect(isWebSocketMessage(createSystemStatusMessage())).toBe(true);
      expect(isWebSocketMessage(createServiceStatusMessage())).toBe(true);
      expect(isWebSocketMessage(createPerformanceUpdateMessage())).toBe(true);
    });

    it('returns false for unknown message types', () => {
      const unknown = { type: 'unknown_type', data: {} };
      expect(isWebSocketMessage(unknown)).toBe(false);
    });

    it('returns false for null/undefined', () => {
      expect(isWebSocketMessage(null)).toBe(false);
      expect(isWebSocketMessage(undefined)).toBe(false);
    });

    it('returns false for non-object values', () => {
      expect(isWebSocketMessage('string')).toBe(false);
      expect(isWebSocketMessage(123)).toBe(false);
      expect(isWebSocketMessage([])).toBe(false);
    });
  });
});

// ============================================================================
// Type Narrowing Tests (compile-time verification)
// ============================================================================

describe('Type Narrowing', () => {
  it('narrows to specific message type after type guard', () => {
    const msg: WebSocketMessage = createEventMessage();

    if (isEventMessage(msg)) {
      // TypeScript should narrow to EventMessage
      // This would fail to compile if type narrowing is broken
      const eventId: string | number | undefined = msg.data.id;
      const cameraId: string = msg.data.camera_id;
      expect(eventId).toBe('evt-123');
      expect(cameraId).toBe('cam-001');
    }
  });

  it('supports exhaustive switch statements', () => {
    function handleMessage(msg: WebSocketMessage): string {
      switch (msg.type) {
        case 'ping':
          return 'heartbeat-request';
        case 'pong':
          return 'heartbeat-response';
        case 'event':
          return `event:${msg.data.id}`;
        case 'system_status':
          return `system:${msg.data.health}`;
        case 'service_status':
          return `service:${msg.data.service}`;
        case 'performance_update':
          return `performance:${msg.data.timestamp}`;
        default:
          // This ensures exhaustive checking - if we add a new message type
          // but forget to handle it, TypeScript will error here
          return assertNever(msg);
      }
    }

    expect(handleMessage(createPingMessage())).toBe('heartbeat-request');
    expect(handleMessage(createPongMessage())).toBe('heartbeat-response');
    expect(handleMessage(createEventMessage())).toBe('event:evt-123');
    expect(handleMessage(createSystemStatusMessage())).toBe('system:healthy');
    expect(handleMessage(createServiceStatusMessage())).toBe('service:rtdetr');
    expect(handleMessage(createPerformanceUpdateMessage())).toMatch(/^performance:/);
  });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe('Edge Cases', () => {
  it('handles message with extra fields gracefully', () => {
    const msg = {
      type: 'ping',
      extra_field: 'should be ignored',
    };
    expect(isPingMessage(msg)).toBe(true);
  });

  it('handles deeply nested null values', () => {
    const msg = {
      type: 'system_status',
      data: {
        gpu: {
          utilization: null,
          memory_used: null,
          memory_total: null,
          temperature: null,
          inference_fps: null,
        },
        cameras: { active: 0, total: 0 },
        queue: { pending: 0, processing: 0 },
        health: 'healthy',
      },
      timestamp: '2024-01-15T10:00:00Z',
    };
    expect(isSystemStatusMessage(msg)).toBe(true);
  });

  it('handles event with event_id but no id', () => {
    const msg = {
      type: 'event',
      data: {
        event_id: 123,
        camera_id: 'cam-1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Test',
      },
    };
    expect(isEventMessage(msg)).toBe(true);
  });

  it('handles Array.isArray check for containers', () => {
    const msg = {
      type: 'performance_update',
      data: {
        timestamp: '2024-01-15T10:00:00Z',
        gpu: null,
        ai_models: {},
        nemotron: null,
        inference: null,
        databases: {},
        host: null,
        containers: 'not-an-array', // Invalid
        alerts: [],
      },
    };
    // Should still pass as containers is optional for type guard
    expect(isPerformanceUpdateMessage(msg)).toBe(true);
  });
});

// ============================================================================
// assertNever Tests
// ============================================================================

describe('assertNever', () => {
  it('throws error when called', () => {
    // This should never be called at runtime with valid code
    expect(() => assertNever('unexpected' as never)).toThrow();
  });

  it('includes the unexpected value in error message', () => {
    const unexpectedValue = { type: 'unknown' };
    expect(() => assertNever(unexpectedValue as never)).toThrow(/Unexpected/);
  });
});
