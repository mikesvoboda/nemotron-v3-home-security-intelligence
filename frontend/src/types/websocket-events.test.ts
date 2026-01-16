/**
 * Tests for WebSocket Event Map Types and Utilities
 *
 * These tests verify the type guards and utility functions for WebSocket
 * event handling. Type-level tests are verified through compilation.
 */

import { describe, it, expect } from 'vitest';

import {
  WEBSOCKET_EVENT_KEYS,
  extractEventPayload,
  extractEventType,
  isWebSocketEventKey,
} from './websocket-events';

describe('WebSocket Event Types', () => {
  describe('WEBSOCKET_EVENT_KEYS', () => {
    it('should contain all expected event keys', () => {
      expect(WEBSOCKET_EVENT_KEYS).toContain('event');
      expect(WEBSOCKET_EVENT_KEYS).toContain('service_status');
      expect(WEBSOCKET_EVENT_KEYS).toContain('system_status');
      expect(WEBSOCKET_EVENT_KEYS).toContain('ping');
      expect(WEBSOCKET_EVENT_KEYS).toContain('gpu_stats');
      expect(WEBSOCKET_EVENT_KEYS).toContain('error');
      expect(WEBSOCKET_EVENT_KEYS).toContain('pong');
    });

    it('should have correct number of event keys', () => {
      // NEM-2295: Added camera_status event type
      // NEM-2382: Added hierarchical event types (alert.*, camera.*, job.*, system.*)
      // NEM-2504: Added alert.resolved event type
      // 8 legacy keys + 16 new hierarchical keys = 24 total
      expect(WEBSOCKET_EVENT_KEYS).toHaveLength(24);
    });

    it('should include new hierarchical event keys', () => {
      // NEM-2382: Verify new event types
      // NEM-2504: Added alert.resolved event type
      expect(WEBSOCKET_EVENT_KEYS).toContain('alert.created');
      expect(WEBSOCKET_EVENT_KEYS).toContain('alert.updated');
      expect(WEBSOCKET_EVENT_KEYS).toContain('alert.deleted');
      expect(WEBSOCKET_EVENT_KEYS).toContain('alert.acknowledged');
      expect(WEBSOCKET_EVENT_KEYS).toContain('alert.dismissed');
      expect(WEBSOCKET_EVENT_KEYS).toContain('alert.resolved');
      expect(WEBSOCKET_EVENT_KEYS).toContain('camera.online');
      expect(WEBSOCKET_EVENT_KEYS).toContain('camera.offline');
      expect(WEBSOCKET_EVENT_KEYS).toContain('camera.status_changed');
      expect(WEBSOCKET_EVENT_KEYS).toContain('camera.error');
      expect(WEBSOCKET_EVENT_KEYS).toContain('job.started');
      expect(WEBSOCKET_EVENT_KEYS).toContain('job.progress');
      expect(WEBSOCKET_EVENT_KEYS).toContain('job.completed');
      expect(WEBSOCKET_EVENT_KEYS).toContain('job.failed');
      expect(WEBSOCKET_EVENT_KEYS).toContain('system.health_changed');
      expect(WEBSOCKET_EVENT_KEYS).toContain('system.error');
    });
  });

  describe('isWebSocketEventKey', () => {
    it('should return true for valid legacy event keys', () => {
      expect(isWebSocketEventKey('event')).toBe(true);
      expect(isWebSocketEventKey('service_status')).toBe(true);
      expect(isWebSocketEventKey('system_status')).toBe(true);
      expect(isWebSocketEventKey('ping')).toBe(true);
      expect(isWebSocketEventKey('gpu_stats')).toBe(true);
      expect(isWebSocketEventKey('error')).toBe(true);
      expect(isWebSocketEventKey('pong')).toBe(true);
    });

    it('should return true for new hierarchical event keys', () => {
      // NEM-2382: Test new event types
      // NEM-2504: Added alert.resolved event type
      expect(isWebSocketEventKey('alert.created')).toBe(true);
      expect(isWebSocketEventKey('alert.updated')).toBe(true);
      expect(isWebSocketEventKey('alert.resolved')).toBe(true);
      expect(isWebSocketEventKey('camera.online')).toBe(true);
      expect(isWebSocketEventKey('camera.offline')).toBe(true);
      expect(isWebSocketEventKey('job.started')).toBe(true);
      expect(isWebSocketEventKey('job.completed')).toBe(true);
      expect(isWebSocketEventKey('job.failed')).toBe(true);
      expect(isWebSocketEventKey('system.health_changed')).toBe(true);
      expect(isWebSocketEventKey('system.error')).toBe(true);
    });

    it('should return false for invalid event keys', () => {
      expect(isWebSocketEventKey('invalid')).toBe(false);
      expect(isWebSocketEventKey('unknown')).toBe(false);
      expect(isWebSocketEventKey('message')).toBe(false);
      expect(isWebSocketEventKey('')).toBe(false);
    });

    it('should return false for non-string values', () => {
      expect(isWebSocketEventKey(null)).toBe(false);
      expect(isWebSocketEventKey(undefined)).toBe(false);
      expect(isWebSocketEventKey(123)).toBe(false);
      expect(isWebSocketEventKey({})).toBe(false);
      expect(isWebSocketEventKey([])).toBe(false);
    });
  });

  describe('extractEventType', () => {
    it('should extract valid event type from message object', () => {
      expect(extractEventType({ type: 'event' })).toBe('event');
      expect(extractEventType({ type: 'ping' })).toBe('ping');
      expect(extractEventType({ type: 'system_status', data: {} })).toBe('system_status');
    });

    it('should return undefined for invalid type', () => {
      expect(extractEventType({ type: 'invalid' })).toBeUndefined();
      expect(extractEventType({ type: 123 })).toBeUndefined();
    });

    it('should return undefined for missing type', () => {
      expect(extractEventType({})).toBeUndefined();
      expect(extractEventType({ data: {} })).toBeUndefined();
    });

    it('should return undefined for non-object values', () => {
      expect(extractEventType(null)).toBeUndefined();
      expect(extractEventType(undefined)).toBeUndefined();
      expect(extractEventType('event')).toBeUndefined();
      expect(extractEventType(123)).toBeUndefined();
    });
  });

  describe('extractEventPayload', () => {
    it('should extract data payload from message with data field', () => {
      const eventData = {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      };
      const message = { type: 'event', data: eventData };

      const payload = extractEventPayload(message, 'event');
      expect(payload).toEqual(eventData);
    });

    it('should return message itself for simple messages without data field', () => {
      const pingMessage = { type: 'ping' };

      const payload = extractEventPayload(pingMessage, 'ping');
      expect(payload).toEqual(pingMessage);
    });

    it('should return undefined if type does not match', () => {
      const message = { type: 'event', data: {} };

      const payload = extractEventPayload(message, 'ping');
      expect(payload).toBeUndefined();
    });

    it('should return undefined for non-object values', () => {
      expect(extractEventPayload(null, 'event')).toBeUndefined();
      expect(extractEventPayload(undefined, 'event')).toBeUndefined();
      expect(extractEventPayload('string', 'event')).toBeUndefined();
    });

    it('should handle system_status messages with nested data', () => {
      const systemData = {
        gpu: {
          utilization: 50,
          memory_used: 1024,
          memory_total: 2048,
          temperature: 65,
          inference_fps: 30,
        },
        cameras: { active: 4, total: 4 },
        queue: { pending: 0, processing: 0 },
        health: 'healthy',
      };
      const message = {
        type: 'system_status',
        data: systemData,
        timestamp: '2024-01-01T00:00:00Z',
      };

      const payload = extractEventPayload(message, 'system_status');
      expect(payload).toEqual(systemData);
    });
  });
});

/**
 * Type-level tests (these fail at compile time if types are wrong)
 *
 * These tests verify that the type system correctly infers handler
 * parameter types based on event keys.
 */
describe('Type-level verification', () => {
  it('should correctly type handler parameters', () => {
    // This test verifies compilation - if types are wrong, TypeScript will error
    type EventHandler = (data: { risk_score: number }) => void;
    const _handler: EventHandler = (data) => {
      // TypeScript should know data has risk_score
      expect(typeof data.risk_score).toBe('number');
    };

    _handler({ risk_score: 75 });
  });

  it('should correctly narrow types with type guards', () => {
    const key = 'event';
    if (isWebSocketEventKey(key)) {
      // TypeScript knows key is WebSocketEventKey
      expect(WEBSOCKET_EVENT_KEYS).toContain(key);
    }
  });
});
