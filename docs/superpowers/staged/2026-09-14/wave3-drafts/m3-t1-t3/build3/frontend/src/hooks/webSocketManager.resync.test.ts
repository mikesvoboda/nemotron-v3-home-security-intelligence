/**
 * Tests for WebSocket message replay/resync functionality.
 *
 * NEM-4983: Implement WebSocket message replay for gap recovery.
 *
 * These tests verify:
 * - Gap detection triggers resync request
 * - Resync request is sent with correct last_sequence
 * - Replay messages are handled correctly
 * - Replay messages are not duplicated
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import {
  WebSocketManager,
  generateSubscriberId,
  resetSubscriberCounter,
  ConnectionConfig,
  Subscriber,
} from './webSocketManager';

// Mock WebSocket
class MockWebSocket {
  url: string;
  readyState: number = WebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  sentMessages: string[] = [];
  binaryType: string = 'arraybuffer';

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 0);
  }

  send(data: string | ArrayBuffer | Uint8Array): void {
    if (this.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
    if (typeof data === 'string') {
      this.sentMessages.push(data);
    }
  }

  close(): void {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  simulateMessage(data: unknown): void {
    if (this.onmessage) {
      const messageData = typeof data === 'string' ? data : JSON.stringify(data);
      this.onmessage(new MessageEvent('message', { data: messageData }));
    }
  }
}

const defaultConfig: ConnectionConfig = {
  reconnect: true,
  reconnectInterval: 1000,
  maxReconnectAttempts: 5,
  connectionTimeout: 10000,
  autoRespondToHeartbeat: true,
};

describe('WebSocket Gap Detection and Resync', () => {
  let manager: WebSocketManager;
  let mockWebSocket: MockWebSocket | null = null;
  let createdWebSockets: MockWebSocket[] = [];

  beforeEach(() => {
    vi.useFakeTimers();
    createdWebSockets = [];

    const MockWebSocketConstructor = vi.fn(function (this: MockWebSocket, url: string) {
      mockWebSocket = new MockWebSocket(url);
      createdWebSockets.push(mockWebSocket);
      Object.assign(this, mockWebSocket);
      return mockWebSocket;
    }) as unknown as typeof WebSocket;

    Object.defineProperty(MockWebSocketConstructor, 'CONNECTING', { value: 0 });
    Object.defineProperty(MockWebSocketConstructor, 'OPEN', { value: 1 });
    Object.defineProperty(MockWebSocketConstructor, 'CLOSING', { value: 2 });
    Object.defineProperty(MockWebSocketConstructor, 'CLOSED', { value: 3 });

    vi.stubGlobal('WebSocket', MockWebSocketConstructor);

    manager = new WebSocketManager();
    resetSubscriberCounter();
  });

  afterEach(() => {
    manager.reset();
    vi.unstubAllGlobals();
    mockWebSocket = null;
    createdWebSockets = [];
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  describe('Gap Detection', () => {
    it('should detect gap when sequence number jumps', async () => {
      const url = 'ws://localhost:8000/ws/events';
      const gaps: Array<{ expected: number; received: number }> = [];

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
        onGapDetected: (expected, received) => {
          gaps.push({ expected, received });
        },
      };

      manager.subscribe(url, subscriber, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // Send messages with a gap (1, 2, 5 - missing 3, 4)
      mockWebSocket?.simulateMessage({ type: 'event', seq: 1, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 2, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 5, data: {} });

      // Should detect gap
      expect(gaps.length).toBe(1);
      expect(gaps[0].expected).toBe(3);
      expect(gaps[0].received).toBe(5);
    });

    it('should track gapCount in connection state', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
      };

      manager.subscribe(url, subscriber, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // Initial state - no gaps
      let state = manager.getConnectionState(url);
      expect(state.gapCount).toBe(0);

      // Send messages with gap
      mockWebSocket?.simulateMessage({ type: 'event', seq: 1, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 5, data: {} }); // Gap!

      state = manager.getConnectionState(url);
      expect(state.gapCount).toBe(1);
    });

    it('should not report gap for in-order messages', async () => {
      const url = 'ws://localhost:8000/ws/events';
      const gaps: Array<{ expected: number; received: number }> = [];

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
        onGapDetected: (expected, received) => {
          gaps.push({ expected, received });
        },
      };

      manager.subscribe(url, subscriber, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // Send messages in order
      mockWebSocket?.simulateMessage({ type: 'event', seq: 1, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 2, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 3, data: {} });

      expect(gaps.length).toBe(0);
    });
  });

  describe('Resync Request', () => {
    it('should send resync request when gap is detected', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
      };

      // Enable auto resync
      manager.subscribe(url, subscriber, { ...defaultConfig, autoResync: true });
      await vi.advanceTimersByTimeAsync(10);

      // Send messages with gap
      mockWebSocket?.simulateMessage({ type: 'event', seq: 1, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 5, data: {} }); // Gap!

      // Should have sent resync request
      const sentMessages = mockWebSocket?.sentMessages ?? [];
      const resyncMessages = sentMessages
        .map((m) => JSON.parse(m))
        .filter((m) => m.type === 'resync');

      expect(resyncMessages.length).toBe(1);
      expect(resyncMessages[0].data.last_sequence).toBe(1);
    });

    it('should include channel in resync request', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
      };

      manager.subscribe(url, subscriber, { ...defaultConfig, autoResync: true });
      await vi.advanceTimersByTimeAsync(10);

      // Trigger gap
      mockWebSocket?.simulateMessage({ type: 'event', seq: 1, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 5, data: {} });

      const sentMessages = mockWebSocket?.sentMessages ?? [];
      const resyncMessage = sentMessages.map((m) => JSON.parse(m)).find((m) => m.type === 'resync');

      expect(resyncMessage).toBeDefined();
      expect(resyncMessage.data.channel).toBe('events');
    });

    it('should not send resync when autoResync is disabled', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
      };

      // Disable auto resync
      manager.subscribe(url, subscriber, { ...defaultConfig, autoResync: false });
      await vi.advanceTimersByTimeAsync(10);

      // Trigger gap
      mockWebSocket?.simulateMessage({ type: 'event', seq: 1, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 5, data: {} });

      const sentMessages = mockWebSocket?.sentMessages ?? [];
      const resyncMessages = sentMessages
        .map((m) => JSON.parse(m))
        .filter((m) => m.type === 'resync');

      expect(resyncMessages.length).toBe(0);
    });

    it('should allow manual resync request via requestResync', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
      };

      manager.subscribe(url, subscriber, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // Manually request resync
      manager.requestResync(url, 10);

      const sentMessages = mockWebSocket?.sentMessages ?? [];
      const resyncMessage = sentMessages.map((m) => JSON.parse(m)).find((m) => m.type === 'resync');

      expect(resyncMessage).toBeDefined();
      expect(resyncMessage.data.last_sequence).toBe(10);
    });
  });

  describe('Replay Message Handling', () => {
    it('should handle replay messages with replay=true flag', async () => {
      const url = 'ws://localhost:8000/ws/events';
      const receivedMessages: Array<{ seq: number; replay?: boolean }> = [];

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: (data) => {
          const msg = data as { seq: number; replay?: boolean };
          receivedMessages.push(msg);
        },
      };

      manager.subscribe(url, subscriber, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // Receive replay messages
      mockWebSocket?.simulateMessage({ type: 'event', seq: 3, replay: true, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 4, replay: true, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 5, replay: true, data: {} });

      expect(receivedMessages.length).toBe(3);
      receivedMessages.forEach((msg) => {
        expect(msg.replay).toBe(true);
      });
    });

    it('should call onReplayComplete after resync_ack', async () => {
      const url = 'ws://localhost:8000/ws/events';
      let replayCompleted = false;
      let replayedCount = 0;

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
        onReplayComplete: (count) => {
          replayCompleted = true;
          replayedCount = count;
        },
      };

      manager.subscribe(url, subscriber, { ...defaultConfig, autoResync: true });
      await vi.advanceTimersByTimeAsync(10);

      // Simulate resync response with 3 replayed messages
      mockWebSocket?.simulateMessage({
        type: 'resync_ack',
        channel: 'events',
        last_sequence: 5,
        replayed_count: 3,
      });

      expect(replayCompleted).toBe(true);
      expect(replayedCount).toBe(3);
    });

    it('should not duplicate messages during replay', async () => {
      const url = 'ws://localhost:8000/ws/events';
      const receivedSeqs: number[] = [];

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: (data) => {
          const msg = data as { seq: number };
          if (msg.seq) {
            receivedSeqs.push(msg.seq);
          }
        },
      };

      manager.subscribe(url, subscriber, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // First receive: 1, 2, then gap to 5
      mockWebSocket?.simulateMessage({ type: 'event', seq: 1, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 2, data: {} });

      // Clear for fresh tracking
      receivedSeqs.length = 0;

      // Now receive replay for 3, 4, and normal 5
      mockWebSocket?.simulateMessage({ type: 'event', seq: 3, replay: true, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 4, replay: true, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 5, data: {} });

      // Should receive 3, 4, 5 without duplicates
      expect(receivedSeqs).toEqual([3, 4, 5]);
    });

    it('should handle gap_too_old in resync_ack', async () => {
      const url = 'ws://localhost:8000/ws/events';
      let gapTooOldReceived = false;
      let oldestAvailable = 0;

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
        onGapTooOld: (oldest) => {
          gapTooOldReceived = true;
          oldestAvailable = oldest;
        },
      };

      manager.subscribe(url, subscriber, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // Simulate resync_ack with gap_too_old
      mockWebSocket?.simulateMessage({
        type: 'resync_ack',
        channel: 'events',
        last_sequence: 10,
        replayed_count: 50,
        gap_too_old: true,
        oldest_available: 50,
      });

      expect(gapTooOldReceived).toBe(true);
      expect(oldestAvailable).toBe(50);
    });
  });

  describe('Resync Throttling', () => {
    it('should throttle resync requests to prevent flooding', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
      };

      manager.subscribe(url, subscriber, { ...defaultConfig, autoResync: true });
      await vi.advanceTimersByTimeAsync(10);

      // Trigger multiple gaps rapidly
      mockWebSocket?.simulateMessage({ type: 'event', seq: 1, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 5, data: {} }); // Gap 1
      mockWebSocket?.simulateMessage({ type: 'event', seq: 10, data: {} }); // Gap 2
      mockWebSocket?.simulateMessage({ type: 'event', seq: 15, data: {} }); // Gap 3

      const sentMessages = mockWebSocket?.sentMessages ?? [];
      const resyncMessages = sentMessages
        .map((m) => JSON.parse(m))
        .filter((m) => m.type === 'resync');

      // Should only send one resync request (throttled)
      expect(resyncMessages.length).toBe(1);
    });

    it('should allow resync after throttle period', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
      };

      manager.subscribe(url, subscriber, { ...defaultConfig, autoResync: true });
      await vi.advanceTimersByTimeAsync(10);

      // First gap
      mockWebSocket?.simulateMessage({ type: 'event', seq: 1, data: {} });
      mockWebSocket?.simulateMessage({ type: 'event', seq: 5, data: {} });

      // Simulate resync_ack to clear pending state
      mockWebSocket?.simulateMessage({
        type: 'resync_ack',
        channel: 'events',
        last_sequence: 1,
        replayed_count: 3,
      });

      // Wait for throttle period (default 5 seconds)
      await vi.advanceTimersByTimeAsync(6000);

      // Second gap
      mockWebSocket?.simulateMessage({ type: 'event', seq: 10, data: {} });

      const sentMessages = mockWebSocket?.sentMessages ?? [];
      const resyncMessages = sentMessages
        .map((m) => JSON.parse(m))
        .filter((m) => m.type === 'resync');

      // Should have sent two resync requests
      expect(resyncMessages.length).toBe(2);
    });
  });
});
