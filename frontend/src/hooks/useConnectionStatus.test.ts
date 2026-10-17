/**
 * [r204] rewrote this hook's session source: it used to BUILD a pair of
 * sockets per call (through `useWebSocketStatus`, whose transport is deleted),
 * and now READS the one session `ConnectionStatusProvider` holds on
 * `webSocketManager`.
 *
 * Two consequences for this file, both load-bearing:
 *
 * 1. Every case renders through the provider now (`renderStatus()` below),
 *    because the hook is a reader. That is what makes the 24 pre-existing
 *    assertions still meaningful: they describe what the surfaces see, and
 *    those are the behaviours the package required to survive the move.
 * 2. The WebSocket stub below is now the MANAGER's socket, not the hook's. So
 *    the counts in these tests are manager-level: one construction per URL
 *    however many consumers subscribe. The `[r204]` block at the bottom pins
 *    exactly that, plus the terminal-auth rule the manager owns and the deleted
 *    hook did not have.
 */
import { render, renderHook, act, cleanup } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { ConnectionStatusProvider } from './ConnectionStatusProvider';
import { useConnectionStatus } from './useConnectionStatus';
import { webSocketManager } from './webSocketManager';

// Mock the api module
vi.mock('../services/api', () => ({
  buildWebSocketOptions: (path: string) => ({ url: `ws://localhost${path}`, protocols: undefined }),
  fetchHealth: vi.fn().mockResolvedValue({
    status: 'healthy',
    services: { gpu: { status: 'healthy' } },
  }),
  fetchEvents: vi.fn().mockResolvedValue({ events: [], total: 0, page: 1, page_size: 20 }),
}));

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  /** Frames the client wrote, newest last. The manager writes heartbeats'
   * replies here (`autoRespondToHeartbeat`); the deleted hook never wrote
   * anything, so this is the one wire-level difference [r204] introduces. */
  sentFrames: string[] = [];
  /** Manager assigns `ws.binaryType` for the compressed-frame path. */
  binaryType: BinaryType = 'blob';

  constructor(url: string) {
    this.url = url;
    // Simulate async connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 0);
  }

  send(data?: string) {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
    if (typeof data === 'string') {
      this.sentFrames.push(data);
    }
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  simulateMessage(data: unknown) {
    if (this.onmessage) {
      // The manager's onmessage parses the frame itself, so the stub has to
      // hand it a wire string rather than an object.
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }

  /** Drive the manager's onclose with a specific code. 1006 is "closed
   * abnormally, no status received" — what a dropped connection actually
   * reports, and what an argumentless `CloseEvent` does NOT report (its code is
   * 0, which the browser reserves for "never opened"). */
  simulateClose(code = 1006, reason = '') {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ code, reason, wasClean: false } as CloseEvent);
  }
}

/** The manager is a module singleton (that sharing is the point of [r204]), so
 * these cases have to reset it explicitly — an empty singleton map is the
 * fixture's equivalent of a fresh page load. `reset()` also resets the
 * subscriber-id counter, keeping ids stable across cases. */
function freshManager(): void {
  webSocketManager.reset();
}

/** Every case renders through the provider, because since [r204] the hook only
 * reads a session. `createElement` rather than JSX: this file is a `.ts`. */
function Wrapper({ children }: { children: ReactNode }) {
  return createElement(ConnectionStatusProvider, null, children);
}

function renderStatus() {
  return renderHook(() => useConnectionStatus(), { wrapper: Wrapper });
}

describe('useConnectionStatus', () => {
  let mockWsInstances: MockWebSocket[] = [];

  /** Constructions for one channel URL — the census the [r204] witnesses use,
   * because "did it retry?" and "does everyone share one?" are both questions
   * about how many sockets a given URL got. */
  const socketsFor = (path: string) =>
    mockWsInstances.filter((ws) => ws.url === `ws://localhost${path}`);

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockWsInstances = [];
    freshManager();

    // Mock WebSocket constructor
    vi.stubGlobal(
      'WebSocket',
      class extends MockWebSocket {
        constructor(url: string) {
          super(url);
          mockWsInstances.push(this);
        }
      }
    );
  });

  afterEach(() => {
    // Order matters: unmount first (the provider's cleanup unsubscribes, which
    // is what closes the manager's connections), then drop the singleton's
    // map so a later case never sees this one's sockets.
    cleanup();
    freshManager();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    mockWsInstances = [];
  });

  /** Advance past the manager's backoff for `attempt`s at 1 s base (30 s cap,
   * ≤25 % jitter), so "no new socket appeared" means no retry was scheduled. */
  async function letItRetry(): Promise<void> {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });
  }

  it('initializes with two channel statuses', () => {
    const { result } = renderStatus();

    expect(result.current.summary.eventsChannel.name).toBe('Events');
    expect(result.current.summary.systemChannel.name).toBe('System');
  });

  it('creates two WebSocket connections', async () => {
    renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Sorted rather than positional: which socket the manager constructs first
    // is an accident of provider render order, and nothing downstream reads it.
    expect(mockWsInstances.map((ws) => ws.url).sort()).toEqual([
      'ws://localhost/ws/events',
      'ws://localhost/ws/system',
    ]);
  });

  it('reports allConnected when both channels are connected', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(result.current.summary.allConnected).toBe(true);
  });

  it('reports overallState as connected when both channels are connected', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(result.current.summary.overallState).toBe('connected');
  });

  it('reports overallState as reconnecting when either channel is reconnecting', async () => {
    const { result } = renderStatus();

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Close one connection to trigger reconnecting
    act(() => {
      mockWsInstances[0].simulateClose();
    });

    expect(result.current.summary.anyReconnecting).toBe(true);
    expect(result.current.summary.overallState).toBe('reconnecting');
  });

  it('computes totalReconnectAttempts from both channels', async () => {
    const { result } = renderStatus();

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Close both to trigger reconnecting
    act(() => {
      mockWsInstances[0].simulateClose();
      mockWsInstances[1].simulateClose();
    });

    expect(result.current.summary.totalReconnectAttempts).toBe(2); // 1 each
  });

  it('handles event messages and adds to events array', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send event message through events channel
    const eventMessage = {
      type: 'event',
      data: {
        id: '123',
        camera_id: 'cam1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test event',
      },
    };

    act(() => {
      mockWsInstances[0].simulateMessage(eventMessage);
    });

    expect(result.current.events.length).toBe(1);
    expect(result.current.events[0].id).toBe('123');
    expect(result.current.events[0].summary).toBe('Test event');
  });

  it('handles system status messages', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send system status message through system channel
    const systemMessage = {
      type: 'system_status',
      data: {
        gpu: {
          utilization: 45,
          memory_used: 8192,
          memory_total: 24576,
          temperature: 65,
          inference_fps: 30.5,
        },
        cameras: {
          active: 3,
          total: 5,
        },
        queue: {
          pending: 2,
          processing: 1,
        },
        health: 'healthy',
      },
      timestamp: '2025-12-30T10:00:00Z',
    };

    act(() => {
      mockWsInstances[1].simulateMessage(systemMessage);
    });

    expect(result.current.systemStatus).not.toBeNull();
    expect(result.current.systemStatus?.data.health).toBe('healthy');
    expect(result.current.systemStatus?.data.gpu.utilization).toBe(45);
  });

  /**
   * [r204] behaviour note, pinned rather than assumed: a `{type:'ping'}` frame
   * is a heartbeat, and the manager routes heartbeats to `onHeartbeat` (and
   * answers them itself) instead of `onMessage`, which the deleted hook did not
   * do. The two claims that matter — the frame is not a SecurityEvent, and it
   * still counts as liveness — both hold on the new path, so both are asserted.
   * The third assertion is the new wire traffic: the manager's pong.
   */
  it('treats an events-channel ping as liveness, not an event', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send non-event message
    const pingMessage = { type: 'ping' };

    expect(result.current.summary.eventsChannel.lastMessageTime).toBeNull();

    act(() => {
      mockWsInstances[0].simulateMessage(pingMessage);
    });

    expect(result.current.events.length).toBe(0);
    expect(result.current.summary.eventsChannel.lastMessageTime).not.toBeNull();
    expect(socketsFor('/ws/events')[0].sentFrames).toContain('{"type":"pong"}');
  });

  it('treats a system-channel ping as liveness, not a status', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send non-system_status message
    const pingMessage = { type: 'ping' };

    act(() => {
      mockWsInstances[1].simulateMessage(pingMessage);
    });

    expect(result.current.systemStatus).toBeNull();
    expect(result.current.summary.systemChannel.lastMessageTime).not.toBeNull();
  });

  it('limits events array to 100 items', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Add 105 events
    for (let i = 0; i < 105; i++) {
      const eventMessage = {
        type: 'event',
        data: {
          id: `${i}`,
          camera_id: 'cam1',
          risk_score: 50,
          risk_level: 'medium',
          summary: `Event ${i}`,
        },
      };

      act(() => {
        mockWsInstances[0].simulateMessage(eventMessage);
      });
    }

    expect(result.current.events.length).toBe(100);
    // Newest event should be first
    expect(result.current.events[0].id).toBe('104');
  });

  it('provides clearEvents function', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Add some events
    const eventMessage = {
      type: 'event',
      data: {
        id: '1',
        camera_id: 'cam1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Test',
      },
    };

    act(() => {
      mockWsInstances[0].simulateMessage(eventMessage);
    });

    expect(result.current.events.length).toBe(1);

    // Clear events
    act(() => {
      result.current.clearEvents();
    });

    expect(result.current.events.length).toBe(0);
  });

  it('validates event message structure', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send incomplete event (missing required fields)
    const incompleteEvent = {
      type: 'event',
      data: {
        id: '1',
        // Missing camera_id, risk_score, risk_level, summary
      },
    };

    act(() => {
      mockWsInstances[0].simulateMessage(incompleteEvent);
    });

    // Should not add invalid event
    expect(result.current.events.length).toBe(0);
  });

  it('validates system status message structure', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send incomplete system status
    const incompleteStatus = {
      type: 'system_status',
      data: {
        // Missing required fields
      },
    };

    act(() => {
      mockWsInstances[1].simulateMessage(incompleteStatus);
    });

    // Should not update with invalid status
    expect(result.current.systemStatus).toBeNull();
  });

  it('initializes isPollingFallback as false', () => {
    const { result } = renderStatus();

    expect(result.current.isPollingFallback).toBe(false);
  });

  it('provides retryConnection function', () => {
    const { result } = renderStatus();

    expect(typeof result.current.retryConnection).toBe('function');
  });

  it('retryConnection triggers new connections', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    const initialInstances = mockWsInstances.length;

    // Close connections
    act(() => {
      mockWsInstances.forEach((ws) => ws.simulateClose());
    });

    // Call retry
    act(() => {
      result.current.retryConnection();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Should have created new connections
    expect(mockWsInstances.length).toBeGreaterThanOrEqual(initialInstances);
  });

  it('handles event_id field as fallback for id', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send event with event_id instead of id
    const eventMessage = {
      type: 'event',
      data: {
        event_id: 'evt123',
        camera_id: 'cam1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Test event',
      },
    };

    act(() => {
      mockWsInstances[0].simulateMessage(eventMessage);
    });

    expect(result.current.events.length).toBe(1);
  });

  it('handles null data in type guard checks', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send null. The manager parses the frame before handing it over, so the
    // stub writes the wire text `null` — the parse genuinely produces null and
    // the hook's guard is what is under test.
    act(() => {
      mockWsInstances[0].onmessage?.(new MessageEvent('message', { data: 'null' }));
    });

    expect(result.current.events.length).toBe(0);

    // Send undefined-like object
    act(() => {
      mockWsInstances[1].simulateMessage({ type: 'system_status', data: null });
    });

    expect(result.current.systemStatus).toBeNull();
  });

  it('handles system status without timestamp', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send system status missing timestamp
    const systemMessage = {
      type: 'system_status',
      data: {
        gpu: { utilization: 45 },
        cameras: { active: 3, total: 5 },
        health: 'healthy',
      },
      // Missing timestamp
    };

    act(() => {
      mockWsInstances[1].simulateMessage(systemMessage);
    });

    // Should not update without timestamp
    expect(result.current.systemStatus).toBeNull();
  });

  it('handles non-object data gracefully', async () => {
    const { result } = renderStatus();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send string
    act(() => {
      mockWsInstances[0].simulateMessage('invalid');
    });

    expect(result.current.events.length).toBe(0);

    // Send number
    act(() => {
      mockWsInstances[1].simulateMessage(123);
    });

    expect(result.current.systemStatus).toBeNull();
  });

  describe('[r204] one connection owner', () => {
    /**
     * The regression this package exists for: the shell has two
     * `useConnectionStatus` consumers (Layout.tsx:38, Header.tsx:171), and each
     * used to own its own pair of sockets — four connections and four backoff
     * schedulers over two URLs. Modelled here as two sibling sessions, which is
     * the shape the shell had; the manager is what collapses them.
     */
    it('holds one manager connection per channel across every consumer', async () => {
      function StatusConsumer() {
        useConnectionStatus();
        return null;
      }

      render(
        createElement(
          'div',
          null,
          createElement(ConnectionStatusProvider, null, createElement(StatusConsumer)),
          createElement(ConnectionStatusProvider, null, createElement(StatusConsumer))
        )
      );

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      // Two sessions, still one socket per URL...
      expect(mockWsInstances.length).toBe(2);
      expect(socketsFor('/ws/events').length).toBe(1);
      expect(socketsFor('/ws/system').length).toBe(1);
      // ...and both sessions are genuinely registered on it, so a close
      // notifies both rather than one being left showing a stale "connected".
      expect(webSocketManager.getSubscriberCount('ws://localhost/ws/events')).toBe(2);
      expect(webSocketManager.getSubscriberCount('ws://localhost/ws/system')).toBe(2);
    });

    it('unmounting every consumer closes the manager connection', async () => {
      const { unmount } = renderStatus();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });
      expect(webSocketManager.hasConnection('ws://localhost/ws/events')).toBe(true);

      unmount();

      // The manager drops the entry when refCount hits 0, so no orphan socket
      // (and no reconnect timer) outlives the shell. This is also why an
      // unmount cannot produce a phantom retry against a dead session.
      expect(webSocketManager.hasConnection('ws://localhost/ws/events')).toBe(false);
      expect(webSocketManager.hasConnection('ws://localhost/ws/system')).toBe(false);
    });

    /**
     * Box 3's third witness, and box 2's display rule. B1.5's gate answers an
     * uncredentialed handshake with 4001 (auth.py's `WS_CLOSE_AUTH_REQUIRED`);
     * webSocketManager.auth.test.ts already proves the TRANSPORT stops there.
     * This is the other half: what the status surface does with that close.
     */
    it('shows a 4001 close as an auth refusal and stops reconnecting on the status path', async () => {
      const { result } = renderStatus();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      act(() => {
        socketsFor('/ws/events')[0].simulateClose(4001, 'Authentication required');
      });

      // Named as an auth refusal, not as a generic failure...
      expect(result.current.summary.eventsChannel.authRequired).toBe(true);
      expect(result.current.summary.eventsChannel.state).toBe('failed');
      expect(result.current.summary.authRequired).toBe(true);
      // ..."exhausted retries" would be a false statement about what happened,
      // so it stays false even though the surface is showing a failed state.
      expect(result.current.summary.eventsChannel.hasExhaustedRetries).toBe(false);
      // The other channel is untouched by a per-channel refusal.
      expect(result.current.summary.systemChannel.state).toBe('connected');

      const socketsAfterRefusal = mockWsInstances.length;
      await letItRetry();

      // No retry storm: two full minutes of fake clock covers the whole 15-step
      // backoff (30 s cap), so a scheduled retry would have constructed here.
      expect(mockWsInstances.length).toBe(socketsAfterRefusal);
      expect(result.current.summary.eventsChannel.authRequired).toBe(true);
      /**
       * And no REST fallback: the manager fires `onMaxRetriesExhausted` — which
       * is what starts polling — only in its exhausted-attempts branch, not on
       * an auth refusal. So the surface must not begin hammering `/health` and
       * `/events` with a credential the gate already refused.
       */
      expect(result.current.isPollingFallback).toBe(false);
    });

    /**
     * The control for the case above. "No new socket" only means "it stopped"
     * if the same fixture produces a new socket when the close was ordinary —
     * otherwise a broken stub would pass the 4001 witness for free.
     */
    it('still retries an ordinary close on the status path', async () => {
      const { result } = renderStatus();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      act(() => {
        socketsFor('/ws/events')[0].simulateClose(1006);
      });
      expect(result.current.summary.eventsChannel.state).toBe('reconnecting');

      const socketsBeforeRetry = mockWsInstances.length;
      await letItRetry();

      expect(mockWsInstances.length).toBeGreaterThan(socketsBeforeRetry);
      // ...and the fresh handshake clears the refusal label back to connected.
      expect(result.current.summary.eventsChannel.state).toBe('connected');
      expect(result.current.summary.eventsChannel.authRequired).toBe(false);
    });

    it('retryConnection re-handshakes after a terminal auth close', async () => {
      const { result } = renderStatus();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      act(() => {
        socketsFor('/ws/events')[0].simulateClose(4001, 'Authentication required');
      });
      expect(result.current.summary.eventsChannel.authRequired).toBe(true);

      // The Retry button is the user-facing half of the recovery the manager
      // deliberately leaves to React (its `authRefused` note): the transport
      // will not retry a refusal on its own, so a manual retry must.
      act(() => {
        result.current.retryConnection();
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      expect(socketsFor('/ws/events').length).toBe(2);
      expect(result.current.summary.eventsChannel.authRequired).toBe(false);
      expect(result.current.summary.eventsChannel.state).toBe('connected');
    });
  });

  describe('auto-recovery from polling fallback', () => {
    it('uses 5 second polling interval during fallback mode', async () => {
      // This test verifies the FALLBACK_POLLING_INTERVAL constant is 5000ms
      // We can't easily test the actual interval without exposing internals,
      // so we verify behavior: after exhausting retries, polling should use shorter interval
      const { result } = renderStatus();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      // The hook should use 15 reconnect attempts by default now
      expect(result.current.summary.eventsChannel.maxReconnectAttempts).toBe(15);
      expect(result.current.summary.systemChannel.maxReconnectAttempts).toBe(15);
    });

    it('provides isPollingFallback state that indicates fallback mode', () => {
      const { result } = renderStatus();

      // Initially not in polling fallback
      expect(result.current.isPollingFallback).toBe(false);
    });

    it('retryConnection can be called to attempt WebSocket reconnection', async () => {
      const { result } = renderStatus();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      // Close connections to simulate failure
      act(() => {
        mockWsInstances.forEach((ws) => ws.simulateClose());
      });

      // Store instance count before retry
      const instancesBefore = mockWsInstances.length;

      // Call retry
      act(() => {
        result.current.retryConnection();
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      // Should have attempted to create new WebSocket connections
      expect(mockWsInstances.length).toBeGreaterThan(instancesBefore);
    });
  });
});
