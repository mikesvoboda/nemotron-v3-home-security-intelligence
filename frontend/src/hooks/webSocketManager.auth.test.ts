/**
 * F1.3: the WebSocket manager attaches the credential.
 *
 * Two defects, both measured at origin/main e9ec74ef:
 *
 * 1. `webSocketManager.connect` calls `new WebSocket(wsUrl)` with one argument
 *    (webSocketManager.ts:477) — the `api-key.{key}` subprotocol that
 *    `buildWebSocketOptions` mints (api.ts:995-999) and 18 hooks pass down
 *    through `useWebSocket` is dropped on the floor (useWebSocket.ts:19
 *    admits it: "protocols are not yet supported by the manager"). Only
 *    useWebSocketStatus.ts:138 ever honors them. So every manager-routed
 *    socket connects unauthenticated in an API-key deployment.
 *
 * 2. B1.5's gate answers an uncredentialed handshake by accepting and then
 *    closing 4001 "Authentication required"
 *    (backend/api/middleware/auth.py:400-404). A retrying client re-sends the
 *    same failing handshake 15 times (~8 min of backoff, useWebSocket.ts:68-70).
 *    An auth refusal is deterministic: retrying is noise, not recovery.
 */
import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useWebSocket } from './useWebSocket';
import { WebSocketManager, type ConnectionConfig } from './webSocketManager';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  protocols: string[] | undefined;
  readyState = 0; // CONNECTING
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url: string, protocols?: string[] | string) {
    this.url = url;
    this.protocols =
      protocols === undefined ? undefined : Array.isArray(protocols) ? protocols : [protocols];
    MockWebSocket.instances.push(this);
  }

  send(): void {}
  close(): void {
    this.readyState = 3;
  }

  /** Drive the manager's onclose with a specific close code. */
  simulateClose(code: number, reason = ''): void {
    this.readyState = 3;
    this.onclose?.({ code, reason, wasClean: false } as CloseEvent);
  }

  open(): void {
    this.readyState = 1;
    this.onopen?.({} as Event);
  }
}

const config: ConnectionConfig = {
  reconnect: true,
  reconnectInterval: 100,
  maxReconnectAttempts: 5,
  connectionTimeout: 0,
  autoRespondToHeartbeat: true,
};

describe('WebSocket manager attaches the credential (F1.3)', () => {
  let manager: WebSocketManager;

  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
    manager = new WebSocketManager();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('passes the protocols to the WebSocket constructor', () => {
    manager.subscribe(
      'ws://localhost/ws/events',
      { id: 'sub-1' },
      { ...config, protocols: ['api-key.testkey'] }
    );

    const socket = MockWebSocket.instances[0];
    expect(socket).toBeDefined();
    expect(socket.protocols).toEqual(['api-key.testkey']);
  });

  it('constructs without a protocols argument when none is configured', () => {
    manager.subscribe('ws://localhost/ws/events', { id: 'sub-2' }, config);

    expect(MockWebSocket.instances[0].protocols).toBeUndefined();
  });

  it('stops reconnecting when B1.5 closes the handshake with 4001', async () => {
    vi.useFakeTimers();
    manager.subscribe('ws://localhost/ws/events', { id: 'sub-3' }, config);

    MockWebSocket.instances[0].simulateClose(4001, 'Authentication required');
    expect(MockWebSocket.instances.length).toBe(1); // the refusal itself is terminal

    await vi.advanceTimersByTimeAsync(10_000);
    expect(MockWebSocket.instances.length).toBe(1); // no retry storm

    vi.useRealTimers();
  });

  it('still reconnects an ordinary drop', async () => {
    vi.useFakeTimers();
    manager.subscribe('ws://localhost/ws/events', { id: 'sub-4' }, config);

    MockWebSocket.instances[0].simulateClose(1006, '');
    await vi.advanceTimersByTimeAsync(2_000);
    expect(MockWebSocket.instances.length).toBe(2);

    vi.useRealTimers();
  });

  it('carries the close code to subscribers so a hook can tell auth from noise', () => {
    const onClose = vi.fn();
    manager.subscribe('ws://localhost/ws/events', { id: 'sub-5', onClose }, config);

    MockWebSocket.instances[0].simulateClose(4001, 'Authentication required');

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onClose.mock.calls[0][0]).toMatchObject({ code: 4001 });
  });

  it('useWebSocket forwards its protocols option to the manager', async () => {
    const { rerender } = renderHook(() =>
      useWebSocket({
        url: 'ws://localhost/ws/events',
        protocols: ['api-key.hookkey'],
        reconnect: false,
      })
    );

    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1));
    expect(MockWebSocket.instances[0].protocols).toEqual(['api-key.hookkey']);

    // The array above is rebuilt every render (that is what the hooks do —
    // buildWebSocketOptions returns a fresh one). The connection must depend
    // on its CONTENTS, not identity, or every parent state change would
    // disconnect and resubscribe the socket.
    rerender();
    expect(MockWebSocket.instances.length).toBe(1);
  });
});
