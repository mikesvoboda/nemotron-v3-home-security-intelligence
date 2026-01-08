/**
 * Tests for WebSocket Event Map types and utilities
 */

import { describe, it, expect } from 'vitest';

import {
  isWebSocketEventKey,
  extractEventType,
  WEBSOCKET_EVENT_KEYS,
} from './websocket-events';

import type {
  WebSocketEventMap,
  WebSocketEventKey,
  WebSocketEventPayload,
  WebSocketEventHandler,
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

    it('should be a readonly array type', () => {
      // TypeScript compilation would fail if we tried to modify it
      // The 'as const' assertion makes it readonly at compile time
      // At runtime, we just verify it's an array
      expect(Array.isArray(WEBSOCKET_EVENT_KEYS)).toBe(true);
      expect(WEBSOCKET_EVENT_KEYS.length).toBeGreaterThan(0);
    });
  });

  describe('isWebSocketEventKey', () => {
    it('should return true for valid event keys', () => {
      expect(isWebSocketEventKey('event')).toBe(true);
      expect(isWebSocketEventKey('service_status')).toBe(true);
      expect(isWebSocketEventKey('system_status')).toBe(true);
      expect(isWebSocketEventKey('ping')).toBe(true);
      expect(isWebSocketEventKey('gpu_stats')).toBe(true);
      expect(isWebSocketEventKey('error')).toBe(true);
      expect(isWebSocketEventKey('pong')).toBe(true);
    });

    it('should return false for invalid event keys', () => {
      expect(isWebSocketEventKey('invalid')).toBe(false);
      expect(isWebSocketEventKey('unknown_type')).toBe(false);
      expect(isWebSocketEventKey('')).toBe(false);
      expect(isWebSocketEventKey(null)).toBe(false);
      expect(isWebSocketEventKey(undefined)).toBe(false);
      expect(isWebSocketEventKey(123)).toBe(false);
      expect(isWebSocketEventKey({})).toBe(false);
    });
  });

  describe('extractEventType', () => {
    it('should extract event type from valid messages', () => {
      expect(extractEventType({ type: 'event', data: {} })).toBe('event');
      expect(extractEventType({ type: 'ping' })).toBe('ping');
      expect(extractEventType({ type: 'system_status', data: {}, timestamp: '' })).toBe(
        'system_status'
      );
    });

    it('should return undefined for invalid messages', () => {
      expect(extractEventType(null)).toBeUndefined();
      expect(extractEventType(undefined)).toBeUndefined();
      expect(extractEventType('string')).toBeUndefined();
      expect(extractEventType(123)).toBeUndefined();
      expect(extractEventType({})).toBeUndefined();
      expect(extractEventType({ invalid: 'message' })).toBeUndefined();
      expect(extractEventType({ type: 'unknown_type' })).toBeUndefined();
    });
  });

  describe('Type Inference', () => {
    it('should correctly type event payloads', () => {
      // These are compile-time checks - if the types are wrong, TypeScript will fail
      const eventKey: WebSocketEventKey = 'event';
      const eventPayload: WebSocketEventPayload<'event'> = {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test',
      };

      const pingPayload: WebSocketEventPayload<'ping'> = {
        type: 'ping',
      };

      const errorPayload: WebSocketEventPayload<'error'> = {
        message: 'Test error',
      };

      expect(eventKey).toBe('event');
      expect(eventPayload.risk_score).toBe(75);
      expect(pingPayload.type).toBe('ping');
      expect(errorPayload.message).toBe('Test error');
    });

    it('should correctly type event handlers', () => {
      const handler: WebSocketEventHandler<'event'> = (data) => {
        // TypeScript knows data is SecurityEventData
        const _riskScore: number = data.risk_score;
        expect(typeof _riskScore).toBe('number');
      };

      handler({
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test',
      });
    });
  });

  describe('WebSocketEventMap', () => {
    it('should have all expected event types', () => {
      // Type-level test - ensure all keys are present in the map
      const keys: (keyof WebSocketEventMap)[] = [
        'event',
        'service_status',
        'system_status',
        'ping',
        'gpu_stats',
        'error',
        'pong',
      ];

      expect(keys).toHaveLength(7);
    });
  });
});
