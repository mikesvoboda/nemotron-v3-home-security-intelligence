import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import {
  WebSocketManager,
  webSocketManager,
  generateSubscriberId,
  resetSubscriberCounter,
  ConnectionConfig,
  Subscriber,
  generateMessageId,
  generateConnectionId,
} from './webSocketManager';

// Extend Window interface for WebSocket
declare global {
  interface Window {
    WebSocket: typeof WebSocket;
  }
}

// Mock WebSocket
class MockWebSocket {
  url: string;
  readyState: number = WebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  sentMessages: string[] = [];

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    // Simulate connection opening
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 0);
  }

  send(data: string): void {
    if (this.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
    this.sentMessages.push(data);
  }

  close(): void {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  // Helper method to simulate receiving a message
  simulateMessage(data: unknown): void {
    if (this.onmessage) {
      const messageData = typeof data === 'string' ? data : JSON.stringify(data);
      this.onmessage(new MessageEvent('message', { data: messageData }));
    }
  }

  // Helper method to simulate an error
  simulateError(): void {
    if (this.onerror) {
      this.onerror(new Event('error'));
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

describe('WebSocketManager', () => {
  let manager: WebSocketManager;
  let mockWebSocket: MockWebSocket | null = null;
  let createdWebSockets: MockWebSocket[] = [];

  beforeEach(() => {
    vi.useFakeTimers();
    createdWebSockets = [];

    // Create mock WebSocket constructor
    const MockWebSocketConstructor = vi.fn(function (this: MockWebSocket, url: string) {
      mockWebSocket = new MockWebSocket(url);
      createdWebSockets.push(mockWebSocket);
      Object.assign(this, mockWebSocket);
      return mockWebSocket;
    }) as unknown as typeof WebSocket;

    // Add static properties to the mock constructor
    Object.defineProperty(MockWebSocketConstructor, 'CONNECTING', { value: 0 });
    Object.defineProperty(MockWebSocketConstructor, 'OPEN', { value: 1 });
    Object.defineProperty(MockWebSocketConstructor, 'CLOSING', { value: 2 });
    Object.defineProperty(MockWebSocketConstructor, 'CLOSED', { value: 3 });

    // Use vi.stubGlobal to mock WebSocket (handles read-only globals)
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

  describe('Connection Deduplication', () => {
    it('should share a single connection for multiple subscribers to the same URL', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber1: Subscriber = {
        id: generateSubscriberId(),
        onOpen: vi.fn(),
        onMessage: vi.fn(),
      };

      const subscriber2: Subscriber = {
        id: generateSubscriberId(),
        onOpen: vi.fn(),
        onMessage: vi.fn(),
      };

      // Subscribe first subscriber
      manager.subscribe(url, subscriber1, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // Subscribe second subscriber to same URL
      manager.subscribe(url, subscriber2, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // Should only create ONE WebSocket connection
      expect(createdWebSockets.length).toBe(1);
      expect(manager.getSubscriberCount(url)).toBe(2);
    });

    it('should create separate connections for different URLs', async () => {
      const url1 = 'ws://localhost:8000/ws/events';
      const url2 = 'ws://localhost:8000/ws/system';

      const subscriber1: Subscriber = {
        id: generateSubscriberId(),
        onOpen: vi.fn(),
      };

      const subscriber2: Subscriber = {
        id: generateSubscriberId(),
        onOpen: vi.fn(),
      };

      manager.subscribe(url1, subscriber1, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      manager.subscribe(url2, subscriber2, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // Should create TWO WebSocket connections
      expect(createdWebSockets.length).toBe(2);
      expect(manager.getSubscriberCount(url1)).toBe(1);
      expect(manager.getSubscriberCount(url2)).toBe(1);
    });

    it('should notify new subscriber immediately if connection is already open', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber1: Subscriber = {
        id: generateSubscriberId(),
        onOpen: vi.fn(),
      };

      const subscriber2: Subscriber = {
        id: generateSubscriberId(),
        onOpen: vi.fn(),
      };

      // First subscriber connects
      manager.subscribe(url, subscriber1, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      expect(subscriber1.onOpen).toHaveBeenCalledTimes(1);

      // Second subscriber should be notified immediately since connection is open
      manager.subscribe(url, subscriber2, defaultConfig);

      expect(subscriber2.onOpen).toHaveBeenCalledTimes(1);
    });
  });

  describe('Reference Counting', () => {
    it('should track subscriber count correctly', () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber1: Subscriber = { id: generateSubscriberId() };
      const subscriber2: Subscriber = { id: generateSubscriberId() };
      const subscriber3: Subscriber = { id: generateSubscriberId() };

      manager.subscribe(url, subscriber1, defaultConfig);
      expect(manager.getSubscriberCount(url)).toBe(1);

      manager.subscribe(url, subscriber2, defaultConfig);
      expect(manager.getSubscriberCount(url)).toBe(2);

      manager.subscribe(url, subscriber3, defaultConfig);
      expect(manager.getSubscriberCount(url)).toBe(3);
    });

    it('should decrement subscriber count on unsubscribe', () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber1: Subscriber = { id: generateSubscriberId() };
      const subscriber2: Subscriber = { id: generateSubscriberId() };

      const unsubscribe1 = manager.subscribe(url, subscriber1, defaultConfig);
      const unsubscribe2 = manager.subscribe(url, subscriber2, defaultConfig);

      expect(manager.getSubscriberCount(url)).toBe(2);

      unsubscribe1();
      expect(manager.getSubscriberCount(url)).toBe(1);

      unsubscribe2();
      expect(manager.getSubscriberCount(url)).toBe(0);
    });

    it('should close connection when last subscriber unsubscribes', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber1: Subscriber = { id: generateSubscriberId() };
      const subscriber2: Subscriber = { id: generateSubscriberId() };

      const unsubscribe1 = manager.subscribe(url, subscriber1, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      const unsubscribe2 = manager.subscribe(url, subscriber2, defaultConfig);

      expect(manager.hasConnection(url)).toBe(true);

      unsubscribe1();
      expect(manager.hasConnection(url)).toBe(true); // Still has one subscriber

      unsubscribe2();
      expect(manager.hasConnection(url)).toBe(false); // No more subscribers, connection closed
    });

    it('should keep connection open while at least one subscriber remains', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber1: Subscriber = { id: generateSubscriberId() };
      const subscriber2: Subscriber = { id: generateSubscriberId() };
      const subscriber3: Subscriber = { id: generateSubscriberId() };

      const unsubscribe1 = manager.subscribe(url, subscriber1, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      manager.subscribe(url, subscriber2, defaultConfig);
      manager.subscribe(url, subscriber3, defaultConfig);

      const ws = createdWebSockets[0];
      expect(ws.readyState).toBe(WebSocket.OPEN);

      // Unsubscribe first two
      unsubscribe1();
      expect(manager.hasConnection(url)).toBe(true);

      // Connection should still be open
      expect(createdWebSockets.length).toBe(1);
    });
  });

  describe('Message Broadcasting', () => {
    it('should broadcast messages to all subscribers', async () => {
      const url = 'ws://localhost:8000/ws/events';
      const testMessage = { type: 'test', data: 'hello' };

      const subscriber1: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
      };

      const subscriber2: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
      };

      manager.subscribe(url, subscriber1, defaultConfig);
      manager.subscribe(url, subscriber2, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // Simulate receiving a message
      mockWebSocket?.simulateMessage(testMessage);

      expect(subscriber1.onMessage).toHaveBeenCalledWith(testMessage);
      expect(subscriber2.onMessage).toHaveBeenCalledWith(testMessage);
    });

    it('should not send messages to unsubscribed subscribers', async () => {
      const url = 'ws://localhost:8000/ws/events';
      const testMessage = { type: 'test', data: 'hello' };

      const subscriber1: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
      };

      const subscriber2: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
      };

      manager.subscribe(url, subscriber1, defaultConfig);
      const unsubscribe2 = manager.subscribe(url, subscriber2, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // Unsubscribe second subscriber
      unsubscribe2();

      // Simulate receiving a message
      mockWebSocket?.simulateMessage(testMessage);

      expect(subscriber1.onMessage).toHaveBeenCalledWith(testMessage);
      expect(subscriber2.onMessage).not.toHaveBeenCalled();
    });
  });

  describe('Heartbeat Handling', () => {
    it('should respond to heartbeat with pong when autoRespondToHeartbeat is true', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onHeartbeat: vi.fn(),
      };

      manager.subscribe(url, subscriber, { ...defaultConfig, autoRespondToHeartbeat: true });
      await vi.advanceTimersByTimeAsync(10);

      // Simulate heartbeat
      mockWebSocket?.simulateMessage({ type: 'ping' });

      expect(subscriber.onHeartbeat).toHaveBeenCalled();
      expect(mockWebSocket?.sentMessages).toContain(JSON.stringify({ type: 'pong' }));
    });

    it('should not respond to heartbeat when autoRespondToHeartbeat is false', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onHeartbeat: vi.fn(),
      };

      manager.subscribe(url, subscriber, { ...defaultConfig, autoRespondToHeartbeat: false });
      await vi.advanceTimersByTimeAsync(10);

      // Simulate heartbeat
      mockWebSocket?.simulateMessage({ type: 'ping' });

      expect(subscriber.onHeartbeat).toHaveBeenCalled();
      expect(mockWebSocket?.sentMessages).not.toContain(JSON.stringify({ type: 'pong' }));
    });

    it('should not pass heartbeat messages to onMessage handlers', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber: Subscriber = {
        id: generateSubscriberId(),
        onMessage: vi.fn(),
        onHeartbeat: vi.fn(),
      };

      manager.subscribe(url, subscriber, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // Simulate heartbeat
      mockWebSocket?.simulateMessage({ type: 'ping' });

      expect(subscriber.onHeartbeat).toHaveBeenCalled();
      expect(subscriber.onMessage).not.toHaveBeenCalled();
    });
  });

  describe('Connection State', () => {
    it('should return correct connection state', async () => {
      const url = 'ws://localhost:8000/ws/events';

      // Before subscribing
      let state = manager.getConnectionState(url);
      expect(state.isConnected).toBe(false);
      expect(state.reconnectCount).toBe(0);
      expect(state.hasExhaustedRetries).toBe(false);

      const subscriber: Subscriber = { id: generateSubscriberId() };
      manager.subscribe(url, subscriber, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      // After connecting
      state = manager.getConnectionState(url);
      expect(state.isConnected).toBe(true);
      expect(state.reconnectCount).toBe(0);
    });
  });

  describe('Send Messages', () => {
    it('should send messages through the shared connection', async () => {
      const url = 'ws://localhost:8000/ws/events';

      const subscriber: Subscriber = { id: generateSubscriberId() };
      manager.subscribe(url, subscriber, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      const result = manager.send(url, { action: 'test' });

      expect(result).toBe(true);
      expect(mockWebSocket?.sentMessages).toContain(JSON.stringify({ action: 'test' }));
    });

    it('should return false when sending to non-existent connection', () => {
      const result = manager.send('ws://nonexistent', { action: 'test' });
      expect(result).toBe(false);
    });
  });

  describe('Cleanup', () => {
    it('should clean up all connections on clearAll', async () => {
      const url1 = 'ws://localhost:8000/ws/events';
      const url2 = 'ws://localhost:8000/ws/system';

      manager.subscribe(url1, { id: generateSubscriberId() }, defaultConfig);
      manager.subscribe(url2, { id: generateSubscriberId() }, defaultConfig);
      await vi.advanceTimersByTimeAsync(10);

      expect(manager.hasConnection(url1)).toBe(true);
      expect(manager.hasConnection(url2)).toBe(true);

      manager.clearAll();

      expect(manager.hasConnection(url1)).toBe(false);
      expect(manager.hasConnection(url2)).toBe(false);
    });
  });
});

describe('generateSubscriberId', () => {
  beforeEach(() => {
    resetSubscriberCounter();
  });

  it('should generate unique IDs', () => {
    const id1 = generateSubscriberId();
    const id2 = generateSubscriberId();
    const id3 = generateSubscriberId();

    expect(id1).not.toBe(id2);
    expect(id2).not.toBe(id3);
    expect(id1).not.toBe(id3);
  });

  it('should include incrementing counter', () => {
    const id1 = generateSubscriberId();
    const id2 = generateSubscriberId();

    expect(id1).toMatch(/ws-sub-1-/);
    expect(id2).toMatch(/ws-sub-2-/);
  });
});

describe('Singleton webSocketManager', () => {
  beforeEach(() => {
    webSocketManager.reset();
  });

  it('should be a singleton instance', () => {
    expect(webSocketManager).toBeInstanceOf(WebSocketManager);
  });
});

describe('generateMessageId', () => {
  it('should generate unique message IDs', () => {
    const id1 = generateMessageId();
    const id2 = generateMessageId();
    const id3 = generateMessageId();

    expect(id1).not.toBe(id2);
    expect(id2).not.toBe(id3);
    expect(id1).not.toBe(id3);
  });

  it('should match the expected format', () => {
    const id = generateMessageId();

    // Format: msg-{timestamp_base36}-{random_5chars}
    expect(id).toMatch(/^msg-[a-z0-9]+-[a-z0-9]+$/);
    expect(id.startsWith('msg-')).toBe(true);
  });

  it('should include timestamp component', () => {
    const beforeTime = Date.now().toString(36);
    const id = generateMessageId();
    const afterTime = Date.now().toString(36);

    // Extract timestamp from ID (second segment)
    const timestampPart = id.split('-')[1];

    // Timestamp should be between before and after times
    expect(timestampPart.length).toBeGreaterThanOrEqual(beforeTime.length - 1);
    expect(timestampPart.length).toBeLessThanOrEqual(afterTime.length + 1);
  });
});

describe('generateConnectionId', () => {
  it('should generate unique connection IDs', () => {
    const id1 = generateConnectionId();
    const id2 = generateConnectionId();
    const id3 = generateConnectionId();

    expect(id1).not.toBe(id2);
    expect(id2).not.toBe(id3);
    expect(id1).not.toBe(id3);
  });

  it('should match the expected format', () => {
    const id = generateConnectionId();

    // Format: ws-{timestamp_base36}-{random_5chars}
    expect(id).toMatch(/^ws-[a-z0-9]+-[a-z0-9]+$/);
    expect(id.startsWith('ws-')).toBe(true);
  });

  it('should be different from message IDs', () => {
    const connectionId = generateConnectionId();
    const messageId = generateMessageId();

    expect(connectionId.startsWith('ws-')).toBe(true);
    expect(messageId.startsWith('msg-')).toBe(true);
    expect(connectionId).not.toBe(messageId);
  });
});

describe('Connection ID tracking', () => {
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

  it('should include connectionId in connection state after connecting', async () => {
    const url = 'ws://localhost:8000/ws/events';

    const subscriber: Subscriber = {
      id: generateSubscriberId(),
      onOpen: vi.fn(),
    };

    manager.subscribe(url, subscriber, defaultConfig);
    await vi.advanceTimersByTimeAsync(10);

    const state = manager.getConnectionState(url);

    expect(state.connectionId).toBeTruthy();
    expect(state.connectionId).toMatch(/^ws-[a-z0-9]+-[a-z0-9]+$/);
    expect(state.isConnected).toBe(true);
  });

  it('should generate new connectionId on reconnection', async () => {
    const url = 'ws://localhost:8000/ws/events';
    const connectionIds: string[] = [];

    const subscriber: Subscriber = {
      id: generateSubscriberId(),
      onOpen: () => {
        const state = manager.getConnectionState(url);
        connectionIds.push(state.connectionId);
      },
    };

    manager.subscribe(url, subscriber, defaultConfig);
    await vi.advanceTimersByTimeAsync(10);

    // Simulate disconnect
    mockWebSocket?.close();
    await vi.advanceTimersByTimeAsync(10);

    // Wait for reconnection
    await vi.advanceTimersByTimeAsync(1500);
    await vi.advanceTimersByTimeAsync(10);

    // Should have two different connection IDs
    expect(connectionIds.length).toBe(2);
    expect(connectionIds[0]).not.toBe(connectionIds[1]);
  });

  it('should include lastPongTime in connection state', async () => {
    const url = 'ws://localhost:8000/ws/events';

    const subscriber: Subscriber = {
      id: generateSubscriberId(),
      onHeartbeat: vi.fn(),
    };

    manager.subscribe(url, subscriber, defaultConfig);
    await vi.advanceTimersByTimeAsync(10);

    // Initial state should have lastPongTime set on connection
    const initialState = manager.getConnectionState(url);
    expect(initialState.lastPongTime).toBeDefined();
    expect(initialState.lastPongTime).not.toBeNull();

    // Simulate heartbeat
    mockWebSocket?.simulateMessage({ type: 'ping' });

    const stateAfterHeartbeat = manager.getConnectionState(url);
    expect(stateAfterHeartbeat.lastPongTime).toBeDefined();
    expect(stateAfterHeartbeat.lastPongTime).not.toBeNull();
  });
});
