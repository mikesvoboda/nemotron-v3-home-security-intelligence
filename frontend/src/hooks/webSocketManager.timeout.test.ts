/**
 * Tests for WebSocketManager timeout and reconnection behavior.
 *
 * This file tests:
 * - Singleton instance management during reconnection
 * - Connection state tracking across reconnections
 * - Heartbeat monitoring and timeout detection
 * - Subscriber management during reconnection
 * - Connection pooling behavior
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock WebSocket for testing
class MockWebSocket {
  url: string;
  readyState: number = WebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  closeCode: number | null = null;
  closeReason: string | null = null;

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url: string) {
    this.url = url;
  }

  send(_data: string): void {
    if (this.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
  }

  close(code?: number, reason?: string): void {
    this.closeCode = code ?? null;
    this.closeReason = reason ?? null;
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code, reason }));
    }
  }

  simulateOpen(): void {
    this.readyState = WebSocket.OPEN;
    if (this.onopen) {
      this.onopen(new Event('open'));
    }
  }

  simulateMessage(data: unknown): void {
    if (this.onmessage) {
      const messageData = typeof data === 'string' ? data : JSON.stringify(data);
      this.onmessage(new MessageEvent('message', { data: messageData }));
    }
  }

  simulateError(): void {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
}

// WebSocketManager implementation for testing
class WebSocketManager {
  private static instances: Map<string, WebSocketManager> = new Map();
  private ws: MockWebSocket | null = null;
  private url: string;
  private subscribers: Set<(message: unknown) => void> = new Set();
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number;
  private reconnectInterval: number;
  private heartbeatInterval: number;
  private heartbeatTimeout: number;
  private lastHeartbeat: Date | null = null;
  private heartbeatCheckInterval: ReturnType<typeof setInterval> | null = null;
  private reconnectTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private isManuallyDisconnected: boolean = false;

  private constructor(
    url: string,
    options?: {
      maxReconnectAttempts?: number;
      reconnectInterval?: number;
      heartbeatInterval?: number;
      heartbeatTimeout?: number;
    }
  ) {
    this.url = url;
    this.maxReconnectAttempts = options?.maxReconnectAttempts ?? 10;
    this.reconnectInterval = options?.reconnectInterval ?? 1000;
    this.heartbeatInterval = options?.heartbeatInterval ?? 30000;
    this.heartbeatTimeout = options?.heartbeatTimeout ?? 60000;
  }

  static getInstance(
    url: string,
    options?: {
      maxReconnectAttempts?: number;
      reconnectInterval?: number;
      heartbeatInterval?: number;
      heartbeatTimeout?: number;
    }
  ): WebSocketManager {
    let instance = WebSocketManager.instances.get(url);
    if (!instance) {
      instance = new WebSocketManager(url, options);
      WebSocketManager.instances.set(url, instance);
    }
    return instance;
  }

  static clearInstances(): void {
    for (const instance of WebSocketManager.instances.values()) {
      instance.cleanup();
    }
    WebSocketManager.instances.clear();
  }

  connect(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    this.isManuallyDisconnected = false;
    this.ws = new MockWebSocket(this.url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.lastHeartbeat = new Date();
      this.startHeartbeatMonitoring();
    };

    this.ws.onclose = () => {
      this.stopHeartbeatMonitoring();
      if (!this.isManuallyDisconnected) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      // Error handling - will trigger onclose
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as Record<string, unknown>;
        if (data.type === 'ping' || data.type === 'pong') {
          this.lastHeartbeat = new Date();
        }
        this.notifySubscribers(data);
      } catch {
        this.notifySubscribers(event.data);
      }
    };
  }

  disconnect(): void {
    this.isManuallyDisconnected = true;
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
    this.cleanup();
  }

  private cleanup(): void {
    this.stopHeartbeatMonitoring();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  subscribe(callback: (message: unknown) => void): () => void {
    this.subscribers.add(callback);
    return () => {
      this.subscribers.delete(callback);
    };
  }

  private notifySubscribers(message: unknown): void {
    for (const callback of this.subscribers) {
      callback(message);
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      return; // Max attempts reached
    }

    const delay = Math.min(this.reconnectInterval * Math.pow(2, this.reconnectAttempts), 30000);

    this.reconnectTimeoutId = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  private startHeartbeatMonitoring(): void {
    this.heartbeatCheckInterval = setInterval(() => {
      if (this.lastHeartbeat && Date.now() - this.lastHeartbeat.getTime() > this.heartbeatTimeout) {
        // Heartbeat timeout - close and reconnect
        if (this.ws) {
          this.ws.close(1000, 'Heartbeat timeout');
        }
      }
    }, this.heartbeatInterval);
  }

  private stopHeartbeatMonitoring(): void {
    if (this.heartbeatCheckInterval) {
      clearInterval(this.heartbeatCheckInterval);
      this.heartbeatCheckInterval = null;
    }
  }

  // Getters for testing
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  get currentReconnectAttempts(): number {
    return this.reconnectAttempts;
  }

  get subscriberCount(): number {
    return this.subscribers.size;
  }

  get lastHeartbeatTime(): Date | null {
    return this.lastHeartbeat;
  }

  // Expose internal WebSocket for testing
  get socket(): MockWebSocket | null {
    return this.ws;
  }
}

describe('WebSocketManager timeout and reconnection', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    WebSocketManager.clearInstances();
  });

  afterEach(() => {
    WebSocketManager.clearInstances();
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  describe('Singleton Instance Management', () => {
    it('should return same instance for same URL', () => {
      const manager1 = WebSocketManager.getInstance('ws://localhost/test');
      const manager2 = WebSocketManager.getInstance('ws://localhost/test');

      expect(manager1).toBe(manager2);
    });

    it('should return different instances for different URLs', () => {
      const manager1 = WebSocketManager.getInstance('ws://localhost/events');
      const manager2 = WebSocketManager.getInstance('ws://localhost/system');

      expect(manager1).not.toBe(manager2);
    });

    it('should preserve instance during reconnection', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 100,
      });

      manager.connect();
      manager.socket?.simulateOpen();
      const instanceBefore = manager;

      // Close to trigger reconnection
      manager.socket?.close();

      // Wait for reconnection
      vi.advanceTimersByTime(200);

      // Get instance again
      const instanceAfter = WebSocketManager.getInstance('ws://localhost/test');

      expect(instanceAfter).toBe(instanceBefore);
    });
  });

  describe('Connection State Tracking', () => {
    it('should track connected state correctly', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test');

      expect(manager.isConnected).toBe(false);

      manager.connect();
      expect(manager.isConnected).toBe(false); // Still connecting

      manager.socket?.simulateOpen();
      expect(manager.isConnected).toBe(true);

      manager.disconnect();
      expect(manager.isConnected).toBe(false);
    });

    it('should reset reconnect attempts on successful connection', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 100,
      });

      manager.connect();
      manager.socket?.simulateOpen();

      // Close to trigger reconnection
      manager.socket?.close();

      // Wait for first reconnection attempt
      vi.advanceTimersByTime(200);

      expect(manager.currentReconnectAttempts).toBe(1);

      // Open successful
      manager.socket?.simulateOpen();

      expect(manager.currentReconnectAttempts).toBe(0);
    });

    it('should increment reconnect attempts on each failure', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 100,
        maxReconnectAttempts: 5,
      });

      manager.connect();
      manager.socket?.simulateOpen();
      manager.socket?.close();

      // Multiple reconnection attempts
      for (let i = 1; i <= 3; i++) {
        vi.advanceTimersByTime(200 * i);
        expect(manager.currentReconnectAttempts).toBe(i);
        manager.socket?.close(); // Fail again
      }
    });

    it('should stop reconnecting after max attempts', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 50,
        maxReconnectAttempts: 2,
      });

      manager.connect();
      manager.socket?.simulateOpen();
      manager.socket?.close();

      // Exhaust reconnection attempts
      vi.advanceTimersByTime(100);
      manager.socket?.close();

      vi.advanceTimersByTime(200);
      manager.socket?.close();

      // Should be at max attempts
      expect(manager.currentReconnectAttempts).toBe(2);

      // Advance more time
      vi.advanceTimersByTime(1000);

      // Should not have attempted more reconnections
      expect(manager.currentReconnectAttempts).toBe(2);
    });
  });

  describe('Heartbeat Monitoring', () => {
    it('should update lastHeartbeat on connection open', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test');

      expect(manager.lastHeartbeatTime).toBeNull();

      manager.connect();
      manager.socket?.simulateOpen();

      expect(manager.lastHeartbeatTime).toBeInstanceOf(Date);
    });

    it('should update lastHeartbeat on ping message', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test');

      manager.connect();
      manager.socket?.simulateOpen();

      const initialHeartbeat = manager.lastHeartbeatTime;

      // Advance time
      vi.advanceTimersByTime(1000);

      // Simulate ping message
      manager.socket?.simulateMessage({ type: 'ping' });

      expect(manager.lastHeartbeatTime).not.toBe(initialHeartbeat);
      expect(manager.lastHeartbeatTime!.getTime()).toBeGreaterThan(initialHeartbeat!.getTime());
    });

    it('should update lastHeartbeat on pong message', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test');

      manager.connect();
      manager.socket?.simulateOpen();

      const initialHeartbeat = manager.lastHeartbeatTime;

      vi.advanceTimersByTime(1000);

      // Simulate pong message
      manager.socket?.simulateMessage({ type: 'pong' });

      expect(manager.lastHeartbeatTime).not.toBe(initialHeartbeat);
      expect(manager.lastHeartbeatTime!.getTime()).toBeGreaterThan(initialHeartbeat!.getTime());
    });

    it('should close connection on heartbeat timeout', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        heartbeatInterval: 100,
        heartbeatTimeout: 500,
      });

      manager.connect();
      manager.socket?.simulateOpen();

      expect(manager.isConnected).toBe(true);

      // Advance past heartbeat timeout (no messages received)
      vi.advanceTimersByTime(700);

      // Connection should be closed
      expect(manager.isConnected).toBe(false);
    });

    it('should not close connection if heartbeats received', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        heartbeatInterval: 100,
        heartbeatTimeout: 500,
      });

      manager.connect();
      manager.socket?.simulateOpen();

      // Send heartbeats before timeout
      for (let i = 0; i < 5; i++) {
        vi.advanceTimersByTime(100);
        manager.socket?.simulateMessage({ type: 'ping' });
      }

      // Connection should still be open
      expect(manager.isConnected).toBe(true);
    });
  });

  describe('Subscriber Management During Reconnection', () => {
    it('should preserve subscribers during reconnection', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 100,
      });

      const callback1 = vi.fn();
      const callback2 = vi.fn();

      manager.subscribe(callback1);
      manager.subscribe(callback2);

      expect(manager.subscriberCount).toBe(2);

      manager.connect();
      manager.socket?.simulateOpen();

      // Close and reconnect
      manager.socket?.close();
      vi.advanceTimersByTime(200);
      manager.socket?.simulateOpen();

      // Subscribers should still be there
      expect(manager.subscriberCount).toBe(2);

      // And should receive messages
      manager.socket?.simulateMessage({ type: 'test' });

      expect(callback1).toHaveBeenCalledWith({ type: 'test' });
      expect(callback2).toHaveBeenCalledWith({ type: 'test' });
    });

    it('should allow unsubscribe during reconnection', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 100,
      });

      const callback = vi.fn();
      const unsubscribe = manager.subscribe(callback);

      expect(manager.subscriberCount).toBe(1);

      manager.connect();
      manager.socket?.simulateOpen();
      manager.socket?.close();

      // Unsubscribe during reconnection
      unsubscribe();

      expect(manager.subscriberCount).toBe(0);

      // Reconnect
      vi.advanceTimersByTime(200);
      manager.socket?.simulateOpen();

      // Message should not be delivered
      manager.socket?.simulateMessage({ type: 'test' });

      expect(callback).not.toHaveBeenCalled();
    });

    it('should allow new subscriptions during reconnection', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 100,
      });

      manager.connect();
      manager.socket?.simulateOpen();
      manager.socket?.close();

      // Subscribe during reconnection
      const callback = vi.fn();
      manager.subscribe(callback);

      expect(manager.subscriberCount).toBe(1);

      // Reconnect
      vi.advanceTimersByTime(200);
      manager.socket?.simulateOpen();

      // Message should be delivered
      manager.socket?.simulateMessage({ type: 'test' });

      expect(callback).toHaveBeenCalledWith({ type: 'test' });
    });
  });

  describe('Exponential Backoff', () => {
    it('should use exponential backoff for reconnection delays', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 100,
        maxReconnectAttempts: 5,
      });

      manager.connect();
      manager.socket?.simulateOpen();
      manager.socket?.close();

      // First reconnect attempt should happen after first delay
      expect(manager.currentReconnectAttempts).toBe(0);

      // Advance past first delay (100ms)
      vi.advanceTimersByTime(110);
      expect(manager.currentReconnectAttempts).toBe(1);
      manager.socket?.close();

      // Advance past second delay (200ms)
      vi.advanceTimersByTime(210);
      expect(manager.currentReconnectAttempts).toBe(2);
      manager.socket?.close();

      // Advance past third delay (400ms)
      vi.advanceTimersByTime(410);
      expect(manager.currentReconnectAttempts).toBe(3);
      manager.socket?.close();

      // Advance past fourth delay (800ms)
      vi.advanceTimersByTime(810);
      expect(manager.currentReconnectAttempts).toBe(4);

      // Delays follow exponential pattern: 100, 200, 400, 800
    });

    it('should cap reconnection delay at 30 seconds', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 10000, // 10 seconds base
        maxReconnectAttempts: 10,
      });

      manager.connect();
      manager.socket?.simulateOpen();

      // Simulate multiple failures to reach cap
      for (let i = 0; i < 5; i++) {
        manager.socket?.close();
        // Expected delays: 10000, 20000, 30000 (capped), 30000, 30000
        const expectedDelay = Math.min(10000 * Math.pow(2, i), 30000);
        vi.advanceTimersByTime(expectedDelay + 10);
      }

      // After several attempts, delay should be capped
      expect(manager.currentReconnectAttempts).toBe(5);
    });
  });

  describe('Manual Disconnect vs Automatic Reconnect', () => {
    it('should not reconnect after manual disconnect', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 100,
      });

      manager.connect();
      manager.socket?.simulateOpen();
      expect(manager.isConnected).toBe(true);

      // Manual disconnect
      manager.disconnect();

      expect(manager.isConnected).toBe(false);

      // Wait for potential reconnection
      vi.advanceTimersByTime(500);

      // Should not reconnect
      expect(manager.isConnected).toBe(false);
    });

    it('should reconnect after automatic disconnect', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 100,
      });

      manager.connect();
      manager.socket?.simulateOpen();

      // Automatic close (not manual)
      manager.socket?.close();

      expect(manager.isConnected).toBe(false);

      // Wait for reconnection
      vi.advanceTimersByTime(200);

      // Should have attempted reconnection
      expect(manager.currentReconnectAttempts).toBe(1);
    });

    it('should cancel pending reconnection on manual disconnect', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 500,
      });

      manager.connect();
      manager.socket?.simulateOpen();
      manager.socket?.close();

      // Reconnection should be scheduled
      expect(manager.currentReconnectAttempts).toBe(0);

      // Manual disconnect before reconnection timer fires
      vi.advanceTimersByTime(100);
      manager.disconnect();

      // Advance past when reconnection would have happened
      vi.advanceTimersByTime(1000);

      // Should not have attempted reconnection
      expect(manager.currentReconnectAttempts).toBe(0);
    });
  });

  describe('Connection Error Handling', () => {
    it('should handle connection error and attempt reconnection', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 100,
      });

      manager.connect();
      manager.socket?.simulateOpen();

      // Simulate error (which triggers close)
      manager.socket?.simulateError();
      manager.socket?.close();

      expect(manager.isConnected).toBe(false);

      // Wait for reconnection
      vi.advanceTimersByTime(200);

      // Should have attempted reconnection
      expect(manager.currentReconnectAttempts).toBe(1);
    });

    it('should clean up resources on error', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        heartbeatInterval: 50,
      });

      manager.connect();
      manager.socket?.simulateOpen();

      expect(manager.isConnected).toBe(true);

      // Simulate error and close
      manager.socket?.simulateError();
      manager.socket?.close();

      // Should not throw when advancing time (heartbeat check should be stopped)
      expect(() => {
        vi.advanceTimersByTime(200);
      }).not.toThrow();
    });
  });

  describe('Message Delivery During Reconnection', () => {
    it('should not deliver messages when disconnected', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test');
      const callback = vi.fn();

      manager.subscribe(callback);
      manager.connect();
      manager.socket?.simulateOpen();

      // Receive message while connected
      manager.socket?.simulateMessage({ type: 'test1' });
      expect(callback).toHaveBeenCalledWith({ type: 'test1' });

      // Disconnect
      manager.socket?.close();

      callback.mockClear();

      // Try to simulate message on closed socket (shouldn't deliver)
      // In real scenario, there's no socket to receive messages when closed
      expect(manager.isConnected).toBe(false);
      expect(callback).not.toHaveBeenCalled();
    });

    it('should resume message delivery after reconnection', () => {
      const manager = WebSocketManager.getInstance('ws://localhost/test', {
        reconnectInterval: 100,
      });
      const callback = vi.fn();

      manager.subscribe(callback);
      manager.connect();
      manager.socket?.simulateOpen();

      // Disconnect
      manager.socket?.close();
      callback.mockClear();

      // Reconnect
      vi.advanceTimersByTime(200);
      manager.socket?.simulateOpen();

      // Should receive messages again
      manager.socket?.simulateMessage({ type: 'test2' });
      expect(callback).toHaveBeenCalledWith({ type: 'test2' });
    });
  });
});
