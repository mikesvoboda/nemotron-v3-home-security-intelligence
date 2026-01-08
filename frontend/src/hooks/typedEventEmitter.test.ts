/**
 * TDD Tests for TypedWebSocketEmitter
 *
 * These tests define the expected behavior of the typed event emitter
 * and were written BEFORE the implementation (TDD RED phase).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { TypedWebSocketEmitter } from './typedEventEmitter';

import type { SecurityEventData, ServiceStatusData } from '../types/websocket';
import type { WebSocketEventHandler } from '../types/websocket-events';

describe('TypedWebSocketEmitter', () => {
  let emitter: TypedWebSocketEmitter;

  beforeEach(() => {
    emitter = new TypedWebSocketEmitter();
  });

  afterEach(() => {
    emitter.clear();
  });

  describe('on() - Subscribe to Events', () => {
    it('should allow subscribing to an event and receive typed data', () => {
      const handler = vi.fn<(data: SecurityEventData) => void>();

      emitter.on('event', handler);

      const eventData: SecurityEventData = {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected at front door',
      };

      emitter.emit('event', eventData);

      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler).toHaveBeenCalledWith(eventData);
    });

    it('should return an unsubscribe function', () => {
      const handler = vi.fn();
      const unsubscribe = emitter.on('event', handler);

      expect(typeof unsubscribe).toBe('function');

      unsubscribe();

      emitter.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test event',
      });

      expect(handler).not.toHaveBeenCalled();
    });

    it('should support multiple handlers for the same event', () => {
      const handler1 = vi.fn();
      const handler2 = vi.fn();
      const handler3 = vi.fn();

      emitter.on('event', handler1);
      emitter.on('event', handler2);
      emitter.on('event', handler3);

      const eventData: SecurityEventData = {
        id: '456',
        camera_id: 'backyard',
        risk_score: 30,
        risk_level: 'low',
        summary: 'Cat detected',
      };

      emitter.emit('event', eventData);

      expect(handler1).toHaveBeenCalledWith(eventData);
      expect(handler2).toHaveBeenCalledWith(eventData);
      expect(handler3).toHaveBeenCalledWith(eventData);
    });

    it('should not allow duplicate handlers for the same event', () => {
      const handler = vi.fn();

      emitter.on('event', handler);
      emitter.on('event', handler); // Duplicate

      emitter.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Test',
      });

      // Handler should only be called once (no duplicates)
      expect(handler).toHaveBeenCalledTimes(1);
    });

    it('should support subscribing to different event types', () => {
      const eventHandler = vi.fn();
      const serviceHandler = vi.fn();

      emitter.on('event', eventHandler);
      emitter.on('service_status', serviceHandler);

      const eventData: SecurityEventData = {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test event',
      };

      const serviceData: ServiceStatusData = {
        service: 'rtdetr',
        status: 'running',
        message: 'Service is healthy',
      };

      emitter.emit('event', eventData);
      emitter.emit('service_status', serviceData);

      expect(eventHandler).toHaveBeenCalledTimes(1);
      expect(eventHandler).toHaveBeenCalledWith(eventData);
      expect(serviceHandler).toHaveBeenCalledTimes(1);
      expect(serviceHandler).toHaveBeenCalledWith(serviceData);
    });
  });

  describe('off() - Unsubscribe from Events', () => {
    it('should remove a specific handler', () => {
      const handler1 = vi.fn();
      const handler2 = vi.fn();

      emitter.on('event', handler1);
      emitter.on('event', handler2);

      emitter.off('event', handler1);

      emitter.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Test',
      });

      expect(handler1).not.toHaveBeenCalled();
      expect(handler2).toHaveBeenCalledTimes(1);
    });

    it('should not throw when removing a non-existent handler', () => {
      const handler = vi.fn();

      expect(() => {
        emitter.off('event', handler);
      }).not.toThrow();
    });

    it('should not throw when removing from an event with no subscribers', () => {
      const handler = vi.fn();

      expect(() => {
        emitter.off('service_status', handler);
      }).not.toThrow();
    });
  });

  describe('emit() - Dispatch Events', () => {
    it('should dispatch event to all handlers', () => {
      const handlers = [vi.fn(), vi.fn(), vi.fn()];
      handlers.forEach((h) => emitter.on('ping', h));

      const pingData = { type: 'ping' as const };
      emitter.emit('ping', pingData);

      handlers.forEach((handler) => {
        expect(handler).toHaveBeenCalledWith(pingData);
      });
    });

    it('should not throw when emitting to an event with no subscribers', () => {
      expect(() => {
        emitter.emit('event', {
          id: '123',
          camera_id: 'front_door',
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Test',
        });
      }).not.toThrow();
    });

    it('should only dispatch to handlers of the correct event type', () => {
      const eventHandler = vi.fn();
      const pingHandler = vi.fn();
      const errorHandler = vi.fn();

      emitter.on('event', eventHandler);
      emitter.on('ping', pingHandler);
      emitter.on('error', errorHandler);

      emitter.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Test',
      });

      expect(eventHandler).toHaveBeenCalledTimes(1);
      expect(pingHandler).not.toHaveBeenCalled();
      expect(errorHandler).not.toHaveBeenCalled();
    });

    it('should handle handler errors gracefully', () => {
      const errorThrowingHandler = vi.fn(() => {
        throw new Error('Handler error');
      });
      const normalHandler = vi.fn();

      emitter.on('event', errorThrowingHandler);
      emitter.on('event', normalHandler);

      // Should not throw, and should still call the second handler
      expect(() => {
        emitter.emit('event', {
          id: '123',
          camera_id: 'front_door',
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Test',
        });
      }).not.toThrow();

      expect(errorThrowingHandler).toHaveBeenCalledTimes(1);
      expect(normalHandler).toHaveBeenCalledTimes(1);
    });
  });

  describe('once() - One-time Subscription', () => {
    it('should only call handler once then automatically unsubscribe', () => {
      const handler = vi.fn();

      emitter.once('event', handler);

      const eventData: SecurityEventData = {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'First event',
      };

      emitter.emit('event', eventData);
      emitter.emit('event', { ...eventData, id: '456' });
      emitter.emit('event', { ...eventData, id: '789' });

      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler).toHaveBeenCalledWith(eventData);
    });

    it('should return an unsubscribe function that works before event fires', () => {
      const handler = vi.fn();
      const unsubscribe = emitter.once('event', handler);

      unsubscribe();

      emitter.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test event',
      });

      expect(handler).not.toHaveBeenCalled();
    });
  });

  describe('has() - Check for Listeners', () => {
    it('should return true when event has listeners', () => {
      emitter.on('event', vi.fn());

      expect(emitter.has('event')).toBe(true);
    });

    it('should return false when event has no listeners', () => {
      expect(emitter.has('event')).toBe(false);
    });

    it('should return false after all listeners are removed', () => {
      const handler = vi.fn();
      const unsubscribe = emitter.on('event', handler);

      expect(emitter.has('event')).toBe(true);

      unsubscribe();

      expect(emitter.has('event')).toBe(false);
    });
  });

  describe('listenerCount() - Get Listener Count', () => {
    it('should return 0 when no listeners are registered', () => {
      expect(emitter.listenerCount('event')).toBe(0);
    });

    it('should return correct count of listeners', () => {
      emitter.on('event', vi.fn());
      emitter.on('event', vi.fn());
      emitter.on('event', vi.fn());

      expect(emitter.listenerCount('event')).toBe(3);
    });

    it('should decrement count when listener is removed', () => {
      const handler = vi.fn();
      emitter.on('event', vi.fn());
      const unsubscribe = emitter.on('event', handler);
      emitter.on('event', vi.fn());

      expect(emitter.listenerCount('event')).toBe(3);

      unsubscribe();

      expect(emitter.listenerCount('event')).toBe(2);
    });
  });

  describe('removeAllListeners() - Clear Specific Event', () => {
    it('should remove all listeners for a specific event', () => {
      const handler1 = vi.fn();
      const handler2 = vi.fn();

      emitter.on('event', handler1);
      emitter.on('event', handler2);

      emitter.removeAllListeners('event');

      emitter.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Test',
      });

      expect(handler1).not.toHaveBeenCalled();
      expect(handler2).not.toHaveBeenCalled();
    });

    it('should not affect listeners for other events', () => {
      const eventHandler = vi.fn();
      const pingHandler = vi.fn();

      emitter.on('event', eventHandler);
      emitter.on('ping', pingHandler);

      emitter.removeAllListeners('event');

      emitter.emit('ping', { type: 'ping' });

      expect(pingHandler).toHaveBeenCalledTimes(1);
    });
  });

  describe('clear() - Remove All Listeners', () => {
    it('should remove all listeners for all events', () => {
      const eventHandler = vi.fn();
      const pingHandler = vi.fn();
      const errorHandler = vi.fn();

      emitter.on('event', eventHandler);
      emitter.on('ping', pingHandler);
      emitter.on('error', errorHandler);

      emitter.clear();

      emitter.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Test',
      });
      emitter.emit('ping', { type: 'ping' });
      emitter.emit('error', { message: 'Test error' });

      expect(eventHandler).not.toHaveBeenCalled();
      expect(pingHandler).not.toHaveBeenCalled();
      expect(errorHandler).not.toHaveBeenCalled();
    });
  });

  describe('events() - Get Event Names', () => {
    it('should return empty array when no events are registered', () => {
      expect(emitter.events()).toEqual([]);
    });

    it('should return array of event names with listeners', () => {
      emitter.on('event', vi.fn());
      emitter.on('ping', vi.fn());
      emitter.on('error', vi.fn());

      const events = emitter.events();

      expect(events).toHaveLength(3);
      expect(events).toContain('event');
      expect(events).toContain('ping');
      expect(events).toContain('error');
    });

    it('should not include events after all listeners are removed', () => {
      const unsubscribe = emitter.on('event', vi.fn());
      emitter.on('ping', vi.fn());

      unsubscribe();

      const events = emitter.events();

      expect(events).not.toContain('event');
      expect(events).toContain('ping');
    });
  });

  describe('Type Safety', () => {
    it('should enforce type safety for event handlers', () => {
      // This test ensures TypeScript compilation catches type mismatches
      // The actual type checking happens at compile time

      const securityEventHandler: WebSocketEventHandler<'event'> = (data) => {
        // TypeScript should know data is SecurityEventData
        expect(data.camera_id).toBeDefined();
        expect(data.risk_score).toBeDefined();
        expect(data.risk_level).toBeDefined();
        expect(data.summary).toBeDefined();
      };

      emitter.on('event', securityEventHandler);

      emitter.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test event',
      });
    });

    it('should provide correct types for all event keys', () => {
      // Verify handler types for each event type

      emitter.on('event', (data) => {
        // data should be SecurityEventData
        const _id: string | number = data.id;
        const _cameraId: string = data.camera_id;
        const _riskScore: number = data.risk_score;
        expect(_id).toBeDefined();
        expect(_cameraId).toBeDefined();
        expect(_riskScore).toBeDefined();
      });

      emitter.on('service_status', (data) => {
        // data should be ServiceStatusData
        const _service: string = data.service;
        const _status: string = data.status;
        expect(_service).toBeDefined();
        expect(_status).toBeDefined();
      });

      emitter.on('ping', (data) => {
        // data should be HeartbeatPayload
        const _type: 'ping' = data.type;
        expect(_type).toBe('ping');
      });

      emitter.on('error', (data) => {
        // data should be WebSocketErrorPayload
        const _message: string = data.message;
        expect(_message).toBeDefined();
      });
    });
  });
});

describe('TypedWebSocketEmitter Static Methods', () => {
  describe('fromMessage()', () => {
    it('should parse and emit valid WebSocket messages', () => {
      const emitter = new TypedWebSocketEmitter();
      const handler = vi.fn();

      emitter.on('event', handler);

      const message = {
        type: 'event',
        data: {
          id: '123',
          camera_id: 'front_door',
          risk_score: 75,
          risk_level: 'high',
          summary: 'Test event',
        },
      };

      const result = emitter.handleMessage(message);

      expect(result).toBe(true);
      expect(handler).toHaveBeenCalledWith(message.data);
    });

    it('should handle messages with data at top level (ping/pong)', () => {
      const emitter = new TypedWebSocketEmitter();
      const handler = vi.fn();

      emitter.on('ping', handler);

      const message = { type: 'ping' };
      const result = emitter.handleMessage(message);

      expect(result).toBe(true);
      expect(handler).toHaveBeenCalledWith(message);
    });

    it('should return false for invalid messages', () => {
      const emitter = new TypedWebSocketEmitter();
      const handler = vi.fn();

      emitter.on('event', handler);

      const result = emitter.handleMessage({ invalid: 'message' });

      expect(result).toBe(false);
      expect(handler).not.toHaveBeenCalled();
    });

    it('should return false for unknown event types', () => {
      const emitter = new TypedWebSocketEmitter();

      const result = emitter.handleMessage({ type: 'unknown_type', data: {} });

      expect(result).toBe(false);
    });

    it('should return false for non-object messages', () => {
      const emitter = new TypedWebSocketEmitter();

      expect(emitter.handleMessage('string')).toBe(false);
      expect(emitter.handleMessage(123)).toBe(false);
      expect(emitter.handleMessage(null)).toBe(false);
      expect(emitter.handleMessage(undefined)).toBe(false);
    });
  });
});
