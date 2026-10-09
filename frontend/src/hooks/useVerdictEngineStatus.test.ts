/**
 * useVerdictEngineStatus tests (F1.2, UR-18).
 *
 * Pins the two-state contract from 20-frontend.md F1.2:
 * - initial state comes from B1.4's readiness field (GET /api/system/health/ready
 *   -> verdict_engine), NOT from the socket (the WS event fires only on
 *   transitions and can never supply first-paint state);
 * - later state comes from system.verdict_engine_status_changed events on
 *   /ws/system, whose envelope is {type, data:{state, previous_state, since,
 *   reason, source, timestamp}} (backend emitter re-wraps payloads under
 *   `data` for the system channel).
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useVerdictEngineStatus } from './useVerdictEngineStatus';
import { mockReadinessResponse } from '../mocks/handlers';
import { server } from '../mocks/server';

// Capture the hook's live onMessage callback the way SummaryCardsIntegration.test.tsx does.
let mockOnMessage: ((data: unknown) => void) | undefined;
let mockIsConnected = true;

vi.mock('./useWebSocket', () => ({
  useWebSocket: vi.fn((options: { onMessage?: (data: unknown) => void }) => {
    mockOnMessage = options?.onMessage;
    return {
      isConnected: mockIsConnected,
      lastMessage: null,
      send: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
      hasExhaustedRetries: false,
      reconnectCount: 0,
      lastHeartbeat: null,
    };
  }),
}));

function readinessWith(overrides: Record<string, unknown>) {
  return { ...mockReadinessResponse, ...overrides };
}

function wsTransition(overrides: Record<string, unknown> = {}) {
  return {
    type: 'system.verdict_engine_status_changed',
    data: {
      state: 'unavailable',
      previous_state: 'available',
      since: '2026-10-08T12:00:00Z',
      reason: 'ConnectError: connection refused',
      source: 'health_probe',
      timestamp: '2026-10-08T12:00:01Z',
      ...overrides,
    },
  };
}

describe('useVerdictEngineStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockOnMessage = undefined;
    mockIsConnected = true;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initial state from the readiness field', () => {
    it('seeds an unavailable engine from GET /api/system/health/ready', async () => {
      server.use(
        http.get('/api/system/health/ready', () =>
          HttpResponse.json(
            readinessWith({
              verdict_engine: {
                state: 'unavailable',
                since: '2026-10-08T11:00:00Z',
                reason: 'ConnectError: connection refused',
              },
            })
          )
        )
      );

      const { result } = renderHook(() => useVerdictEngineStatus({ pollIntervalMs: 0 }));

      await waitFor(() => expect(result.current.loaded).toBe(true));
      expect(result.current.state).toBe('unavailable');
      expect(result.current.since).toBe('2026-10-08T11:00:00Z');
      expect(result.current.reason).toBe('ConnectError: connection refused');
    });

    it('seeds an available engine and reports no banner state', async () => {
      // Default handlers serve verdict_engine.state === 'available'.
      const { result } = renderHook(() => useVerdictEngineStatus({ pollIntervalMs: 0 }));

      await waitFor(() => expect(result.current.loaded).toBe(true));
      expect(result.current.state).toBe('available');
      expect(result.current.reason).toBeNull();
    });

    it('stays out of the banner path when the readiness fetch fails', async () => {
      // 404: a 4xx that fetchWithRetry does NOT backoff-retry (api.ts shouldRetry
      // comment), so the hook's catch path settles within the waitFor window.
      server.use(
        http.get('/api/system/health/ready', () =>
          HttpResponse.json({ detail: 'nope' }, { status: 404 })
        )
      );

      const { result } = renderHook(() => useVerdictEngineStatus({ pollIntervalMs: 0 }));

      await waitFor(() => expect(result.current.loaded).toBe(true));
      // Honest unknown, not a false alarm: unknown renders a warning, not the alarm.
      expect(result.current.state).toBe('unknown');
      expect(result.current.isDown).toBe(false);
    });

    it('drops the stale transition time when a later readiness read fails', async () => {
      // Regression guard: `since` is the last TRANSITION time, normally hours
      // old. If a failed read left it in place, the banner would print
      // "unavailable for <hours>" for an engine the probe only failed to
      // reach. A probe that cannot answer cannot say since-when, so the catch
      // path must null it alongside the honest unknown.
      //
      // Same hook instance across both reads (a fresh mount starts with
      // since=null, which would pass without the fix). Real timers + a short
      // interval, per the polling case below: MSW delivery rides setImmediate,
      // which fake timers freeze.
      let failTheRead = false;
      server.use(
        http.get('/api/system/health/ready', () =>
          failTheRead
            ? HttpResponse.json({ detail: 'nope' }, { status: 404 })
            : HttpResponse.json(
                readinessWith({
                  verdict_engine: {
                    state: 'available',
                    since: '2026-10-08T02:00:00Z',
                    reason: null,
                  },
                })
              )
        )
      );

      const { result } = renderHook(() => useVerdictEngineStatus({ pollIntervalMs: 100 }));
      await waitFor(() => expect(result.current.since).toBe('2026-10-08T02:00:00Z'));

      failTheRead = true;

      await waitFor(() => expect(result.current.state).toBe('unknown'), { timeout: 3000 });
      expect(result.current.since).toBeNull();
    });
  });

  describe('transitions over /ws/system', () => {
    it('flips to unavailable on a transition event', async () => {
      const { result } = renderHook(() => useVerdictEngineStatus({ pollIntervalMs: 0 }));
      await waitFor(() => expect(result.current.loaded).toBe(true));

      act(() => {
        mockOnMessage?.(wsTransition());
      });

      expect(result.current.state).toBe('unavailable');
      expect(result.current.isDown).toBe(true);
      expect(result.current.since).toBe('2026-10-08T12:00:00Z');
      expect(result.current.reason).toBe('ConnectError: connection refused');
    });

    it('clears back to available when the engine recovers', async () => {
      server.use(
        http.get('/api/system/health/ready', () =>
          HttpResponse.json(
            readinessWith({
              verdict_engine: { state: 'unavailable', since: '2026-10-08T11:00:00Z', reason: 'x' },
            })
          )
        )
      );
      const { result } = renderHook(() => useVerdictEngineStatus({ pollIntervalMs: 0 }));
      await waitFor(() => expect(result.current.isDown).toBe(true));

      act(() => {
        mockOnMessage?.(
          wsTransition({
            state: 'available',
            previous_state: 'unavailable',
            since: '2026-10-08T12:30:00Z',
            reason: null,
          })
        );
      });

      expect(result.current.state).toBe('available');
      expect(result.current.isDown).toBe(false);
      expect(result.current.reason).toBeNull();
    });

    it('ignores messages for other event types and malformed envelopes', async () => {
      const { result } = renderHook(() => useVerdictEngineStatus({ pollIntervalMs: 0 }));
      await waitFor(() => expect(result.current.loaded).toBe(true));
      const before = result.current.state;

      act(() => {
        mockOnMessage?.({ type: 'system.health_changed', data: { health: 'unhealthy' } });
        // Envelope without data (the /ws/events flat shape must not leak here).
        mockOnMessage?.({ type: 'system.verdict_engine_status_changed', state: 'unavailable' });
        // data without a valid state string.
        mockOnMessage?.({ type: 'system.verdict_engine_status_changed', data: { since: 'x' } });
      });

      expect(result.current.state).toBe(before);
      expect(result.current.loaded).toBe(true);
    });

    it('tracks the unknown state as a warning, not the alarm', async () => {
      const { result } = renderHook(() => useVerdictEngineStatus({ pollIntervalMs: 0 }));
      await waitFor(() => expect(result.current.loaded).toBe(true));

      act(() => {
        mockOnMessage?.(
          wsTransition({
            state: 'unknown',
            reason: 'probe timeout: no response in 5s',
          })
        );
      });

      expect(result.current.state).toBe('unknown');
      expect(result.current.isDown).toBe(false);
      expect(result.current.reason).toBe('probe timeout: no response in 5s');
    });
  });

  describe('polling convergence (missed transitions)', () => {
    it('re-reads readiness on the interval so missed transitions cannot wedge the banner', async () => {
      // Real timers with a short interval: MSW's interceptor delivery rides on
      // setImmediate, which fake timers freeze — a fake-timer poll hangs here.
      const fetchSpy = vi.fn();
      server.use(
        http.get('/api/system/health/ready', () => {
          fetchSpy();
          return HttpResponse.json(mockReadinessResponse);
        })
      );

      const { result } = renderHook(() => useVerdictEngineStatus({ pollIntervalMs: 200 }));
      await waitFor(() => expect(result.current.loaded).toBe(true));
      const initialCalls = fetchSpy.mock.calls.length;
      expect(initialCalls).toBeGreaterThanOrEqual(1);

      await waitFor(() => expect(fetchSpy.mock.calls.length).toBeGreaterThan(initialCalls), {
        timeout: 2000,
      });
    });
  });
});
