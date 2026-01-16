/**
 * Tests for TypedWebSocketEmitter
 *
 * Tests cover:
 * - Basic subscription and emission
 * - Type safety verification
 * - Handler management (on, off, once)
 * - Message handling
 * - Edge cases and error handling
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createTypedEmitter, safeEmit, TypedWebSocketEmitter } from './typedEventEmitter';

import type { SecurityEventData, SystemStatusData } from '../types/websocket';
import type { WebSocketErrorPayload } from '../types/websocket-events';

describe('TypedWebSocketEmitter', () => {
  let emitter: TypedWebSocketEmitter;

  beforeEach(() => {
    emitter = new TypedWebSocketEmitter();
  });

  describe('on() and emit()', () => {
    it('should call handler when event is emitted', () => {
      const handler = vi.fn<(data: SecurityEventData) => void>();
      const eventData: SecurityEventData = {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      };

      emitter.on('event', handler);
      emitter.emit('event', eventData);

      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler).toHaveBeenCalledWith(eventData);
    });

    it('should support multiple handlers for same event', () => {
      const handler1 = vi.fn<(data: SecurityEventData) => void>();
      const handler2 = vi.fn<(data: SecurityEventData) => void>();
      const eventData: SecurityEventData = {
        id: '456',
        camera_id: 'back_door',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Movement detected',
      };

      emitter.on('event', handler1);
      emitter.on('event', handler2);
      emitter.emit('event', eventData);

      expect(handler1).toHaveBeenCalledTimes(1);
      expect(handler2).toHaveBeenCalledTimes(1);
    });

    it('should support handlers for different event types', () => {
      const eventHandler = vi.fn<(data: SecurityEventData) => void>();
      const pingHandler = vi.fn();

      emitter.on('event', eventHandler);
      emitter.on('ping', pingHandler);

      emitter.emit('event', {
        id: '789',
        camera_id: 'garage',
        risk_score: 25,
        risk_level: 'low',
        summary: 'Cat detected',
      });
      emitter.emit('ping', { type: 'ping' });

      expect(eventHandler).toHaveBeenCalledTimes(1);
      expect(pingHandler).toHaveBeenCalledTimes(1);
    });

    it('should not call handlers for different event types', () => {
      const eventHandler = vi.fn<(data: SecurityEventData) => void>();

      emitter.on('event', eventHandler);
      emitter.emit('ping', { type: 'ping' });

      expect(eventHandler).not.toHaveBeenCalled();
    });

    it('should return unsubscribe function', () => {
      const handler = vi.fn<(data: SecurityEventData) => void>();
      const eventData: SecurityEventData = {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      };

      const unsubscribe = emitter.on('event', handler);
      unsubscribe();
      emitter.emit('event', eventData);

      expect(handler).not.toHaveBeenCalled();
    });
  });

  describe('off()', () => {
    it('should remove specific handler', () => {
      const handler1 = vi.fn<(data: SecurityEventData) => void>();
      const handler2 = vi.fn<(data: SecurityEventData) => void>();
      const eventData: SecurityEventData = {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      };

      emitter.on('event', handler1);
      emitter.on('event', handler2);
      emitter.off('event', handler1);
      emitter.emit('event', eventData);

      expect(handler1).not.toHaveBeenCalled();
      expect(handler2).toHaveBeenCalledTimes(1);
    });

    it('should handle removing non-existent handler gracefully', () => {
      const handler = vi.fn<(data: SecurityEventData) => void>();

      // Should not throw
      expect(() => emitter.off('event', handler)).not.toThrow();
    });

    it('should handle removing handler from non-existent event', () => {
      const handler = vi.fn<(data: SecurityEventData) => void>();
      emitter.on('event', handler);

      // Should not throw when removing from different event
      expect(() => emitter.off('ping', vi.fn())).not.toThrow();
    });
  });

  describe('once()', () => {
    it('should call handler only once', () => {
      const handler = vi.fn<(data: SecurityEventData) => void>();
      const eventData: SecurityEventData = {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      };

      emitter.once('event', handler);
      emitter.emit('event', eventData);
      emitter.emit('event', eventData);

      expect(handler).toHaveBeenCalledTimes(1);
    });

    it('should return unsubscribe function that works before event fires', () => {
      const handler = vi.fn<(data: SecurityEventData) => void>();
      const eventData: SecurityEventData = {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      };

      const unsubscribe = emitter.once('event', handler);
      unsubscribe();
      emitter.emit('event', eventData);

      expect(handler).not.toHaveBeenCalled();
    });
  });

  describe('handleMessage()', () => {
    it('should emit event message with data payload', () => {
      const handler = vi.fn<(data: SecurityEventData) => void>();
      const eventData: SecurityEventData = {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      };
      const message = { type: 'event', data: eventData };

      emitter.on('event', handler);
      const handled = emitter.handleMessage(message);

      expect(handled).toBe(true);
      expect(handler).toHaveBeenCalledWith(eventData);
    });

    it('should emit ping message without data field', () => {
      const handler = vi.fn();
      const message = { type: 'ping' };

      emitter.on('ping', handler);
      const handled = emitter.handleMessage(message);

      expect(handled).toBe(true);
      expect(handler).toHaveBeenCalledWith(message);
    });

    it('should return false for unknown message type', () => {
      const handled = emitter.handleMessage({ type: 'unknown' });

      expect(handled).toBe(false);
    });

    it('should return false for invalid message format', () => {
      expect(emitter.handleMessage(null)).toBe(false);
      expect(emitter.handleMessage(undefined)).toBe(false);
      expect(emitter.handleMessage('string')).toBe(false);
      expect(emitter.handleMessage(123)).toBe(false);
    });

    it('should handle system_status message', () => {
      const handler = vi.fn<(data: SystemStatusData) => void>();
      const statusData: SystemStatusData = {
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
        data: statusData,
        timestamp: '2024-01-01T00:00:00Z',
      };

      emitter.on('system_status', handler);
      const handled = emitter.handleMessage(message);

      expect(handled).toBe(true);
      expect(handler).toHaveBeenCalledWith(statusData);
    });

    it('should handle error message', () => {
      const handler = vi.fn<(data: WebSocketErrorPayload) => void>();
      const errorData: WebSocketErrorPayload = {
        code: 'CONNECTION_ERROR',
        message: 'Connection failed',
        details: { reason: 'timeout' },
      };
      const message = { type: 'error', data: errorData };

      emitter.on('error', handler);
      const handled = emitter.handleMessage(message);

      expect(handled).toBe(true);
      expect(handler).toHaveBeenCalledWith(errorData);
    });
  });

  describe('has()', () => {
    it('should return true when handlers exist', () => {
      emitter.on('event', vi.fn());

      expect(emitter.has('event')).toBe(true);
    });

    it('should return false when no handlers exist', () => {
      expect(emitter.has('event')).toBe(false);
    });

    it('should return false after all handlers removed', () => {
      const handler = vi.fn<(data: SecurityEventData) => void>();
      emitter.on('event', handler);
      emitter.off('event', handler);

      expect(emitter.has('event')).toBe(false);
    });
  });

  describe('listenerCount()', () => {
    it('should return correct count', () => {
      expect(emitter.listenerCount('event')).toBe(0);

      emitter.on('event', vi.fn());
      expect(emitter.listenerCount('event')).toBe(1);

      emitter.on('event', vi.fn());
      expect(emitter.listenerCount('event')).toBe(2);
    });

    it('should return 0 for events without handlers', () => {
      expect(emitter.listenerCount('ping')).toBe(0);
    });
  });

  describe('removeAllListeners()', () => {
    it('should remove all handlers for specific event', () => {
      const handler1 = vi.fn<(data: SecurityEventData) => void>();
      const handler2 = vi.fn<(data: SecurityEventData) => void>();

      emitter.on('event', handler1);
      emitter.on('event', handler2);
      emitter.removeAllListeners('event');

      expect(emitter.listenerCount('event')).toBe(0);
      expect(emitter.has('event')).toBe(false);
    });

    it('should not affect other events', () => {
      emitter.on('event', vi.fn());
      emitter.on('ping', vi.fn());
      emitter.removeAllListeners('event');

      expect(emitter.has('event')).toBe(false);
      expect(emitter.has('ping')).toBe(true);
    });
  });

  describe('clear()', () => {
    it('should remove all handlers for all events', () => {
      emitter.on('event', vi.fn());
      emitter.on('ping', vi.fn());
      emitter.on('system_status', vi.fn());
      emitter.clear();

      expect(emitter.has('event')).toBe(false);
      expect(emitter.has('ping')).toBe(false);
      expect(emitter.has('system_status')).toBe(false);
    });
  });

  describe('events()', () => {
    it('should return array of event keys with handlers', () => {
      emitter.on('event', vi.fn());
      emitter.on('ping', vi.fn());

      const events = emitter.events();

      expect(events).toContain('event');
      expect(events).toContain('ping');
      expect(events).toHaveLength(2);
    });

    it('should return empty array when no handlers', () => {
      expect(emitter.events()).toEqual([]);
    });
  });

  describe('error handling', () => {
    it('should continue calling other handlers if one throws', () => {
      const errorHandler = vi.fn<(data: SecurityEventData) => void>().mockImplementation(() => {
        throw new Error('Handler error');
      });
      const successHandler = vi.fn<(data: SecurityEventData) => void>();
      const eventData: SecurityEventData = {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      };

      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      emitter.on('event', errorHandler);
      emitter.on('event', successHandler);
      emitter.emit('event', eventData);

      expect(errorHandler).toHaveBeenCalled();
      expect(successHandler).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    it('should log error when handler throws', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const errorHandler = vi.fn<(data: SecurityEventData) => void>().mockImplementation(() => {
        throw new Error('Test error');
      });

      emitter.on('event', errorHandler);
      emitter.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      });

      expect(consoleSpy).toHaveBeenCalledWith('Error in event handler:', expect.any(Error));

      consoleSpy.mockRestore();
    });

    it('should include event type in error log', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const errorHandler = vi.fn<(data: SecurityEventData) => void>().mockImplementation(() => {
        throw new Error('Test error');
      });

      emitter.on('event', errorHandler);
      emitter.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      });

      // Verify the log includes the event type
      expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining('event'), expect.any(Error));

      consoleSpy.mockRestore();
    });
  });

  describe('error handler configuration', () => {
    it('should call custom error handler when provided', () => {
      const customErrorHandler = vi.fn();
      const emitterWithHandler = new TypedWebSocketEmitter({
        onError: customErrorHandler,
      });
      const errorHandler = vi.fn<(data: SecurityEventData) => void>().mockImplementation(() => {
        throw new Error('Test error');
      });

      emitterWithHandler.on('event', errorHandler);
      emitterWithHandler.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      });

      expect(customErrorHandler).toHaveBeenCalledWith({
        event: 'event',
        error: expect.any(Error),
        handlerName: expect.any(String),
      });
    });

    it('should suppress console logging when debug is false', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const emitterWithDebugOff = new TypedWebSocketEmitter({ debug: false });
      const errorHandler = vi.fn<(data: SecurityEventData) => void>().mockImplementation(() => {
        throw new Error('Test error');
      });

      emitterWithDebugOff.on('event', errorHandler);
      emitterWithDebugOff.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      });

      expect(consoleSpy).not.toHaveBeenCalled();
      consoleSpy.mockRestore();
    });

    it('should enable console logging when debug is true', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const emitterWithDebugOn = new TypedWebSocketEmitter({ debug: true });
      const errorHandler = vi.fn<(data: SecurityEventData) => void>().mockImplementation(() => {
        throw new Error('Test error');
      });

      emitterWithDebugOn.on('event', errorHandler);
      emitterWithDebugOn.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      });

      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });

    it('should default to debug enabled in development mode', () => {
      // Default emitter (debug defaults based on NODE_ENV)
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const errorHandler = vi.fn<(data: SecurityEventData) => void>().mockImplementation(() => {
        throw new Error('Test error');
      });

      // Default emitter without explicit debug option
      const defaultEmitter = new TypedWebSocketEmitter();
      defaultEmitter.on('event', errorHandler);
      defaultEmitter.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      });

      // In test environment (development), debug should be enabled by default
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });

    it('should call both custom error handler and console.error when debug is enabled', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const customErrorHandler = vi.fn();
      const emitterWithBoth = new TypedWebSocketEmitter({
        onError: customErrorHandler,
        debug: true,
      });
      const errorHandler = vi.fn<(data: SecurityEventData) => void>().mockImplementation(() => {
        throw new Error('Test error');
      });

      emitterWithBoth.on('event', errorHandler);
      emitterWithBoth.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      });

      expect(customErrorHandler).toHaveBeenCalled();
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });

    it('should extract handler name from named function', () => {
      const customErrorHandler = vi.fn();
      const emitterWithHandler = new TypedWebSocketEmitter({
        onError: customErrorHandler,
      });

      function myNamedHandler(_data: SecurityEventData): void {
        throw new Error('Test error');
      }

      emitterWithHandler.on('event', myNamedHandler);
      emitterWithHandler.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      });

      expect(customErrorHandler).toHaveBeenCalledWith(
        expect.objectContaining({
          handlerName: 'myNamedHandler',
        })
      );
    });

    it('should use "anonymous" for anonymous handlers', () => {
      const customErrorHandler = vi.fn();
      const emitterWithHandler = new TypedWebSocketEmitter({
        onError: customErrorHandler,
      });

      emitterWithHandler.on('event', () => {
        throw new Error('Test error');
      });
      emitterWithHandler.emit('event', {
        id: '123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
      });

      expect(customErrorHandler).toHaveBeenCalledWith(
        expect.objectContaining({
          handlerName: 'anonymous',
        })
      );
    });
  });
});

describe('safeEmit()', () => {
  let emitter: TypedWebSocketEmitter;

  beforeEach(() => {
    emitter = new TypedWebSocketEmitter();
  });

  it('should emit for valid event key', () => {
    const handler = vi.fn<(data: SecurityEventData) => void>();
    emitter.on('event', handler);

    const result = safeEmit(emitter, 'event', {
      id: '123',
      camera_id: 'front_door',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected',
    });

    expect(result).toBe(true);
    expect(handler).toHaveBeenCalled();
  });

  it('should return false for invalid event key', () => {
    const result = safeEmit(emitter, 'invalid', {});

    expect(result).toBe(false);
  });

  it('should return false for non-string event key', () => {
    expect(safeEmit(emitter, null, {})).toBe(false);
    expect(safeEmit(emitter, undefined, {})).toBe(false);
    expect(safeEmit(emitter, 123, {})).toBe(false);
  });
});

describe('createTypedEmitter()', () => {
  it('should create a new TypedWebSocketEmitter instance', () => {
    const emitter = createTypedEmitter();

    expect(emitter).toBeInstanceOf(TypedWebSocketEmitter);
  });

  it('should create independent instances', () => {
    const emitter1 = createTypedEmitter();
    const emitter2 = createTypedEmitter();

    emitter1.on('event', vi.fn());

    expect(emitter1.has('event')).toBe(true);
    expect(emitter2.has('event')).toBe(false);
  });
});
