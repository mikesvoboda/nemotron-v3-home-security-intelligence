/**
 * Tests for useRecentThreats (added by F1.3, alongside the hook's rewire).
 *
 * The F1.3 angle first: this hook used to hardcode its socket at
 * `ws://localhost:8000/ws/events` off a VITE_WS_URL variable no deployment
 * docs define, so in a running stack the socket bypassed nginx — and nothing
 * tested the hook, so nothing noticed (CI's Test Coverage Gate named that
 * missing file at PR #6922's head). The rewired path (commit e0cd9333) takes
 * its url from buildWebSocketOptions; ruling 44 means the browser builder
 * attaches no credential subprotocol (the session cookie authenticates), so
 * these tests pin the url forwarding and the absence of any minted protocol,
 * then cover the hook's own message contract.
 *
 * The builder itself is unit-tested in services/api.test.ts; here it is
 * mocked so the assertion is exactly "the hook forwards what it was given".
 */
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useRecentThreats } from './useRecentThreats';

import type { UseWebSocketReturn, WebSocketOptions } from './useWebSocket';

const mocks = vi.hoisted(() => ({
  wsOptions: undefined as WebSocketOptions | undefined,
  deliver: undefined as ((data: unknown) => void) | undefined,
  buildWebSocketOptions: vi.fn<(endpoint: string) => { url: string; protocols?: string[] }>(),
}));

vi.mock('./useWebSocket', () => ({
  useWebSocket: vi.fn((options: WebSocketOptions): UseWebSocketReturn => {
    mocks.wsOptions = options;
    mocks.deliver = options.onMessage;
    return {
      isConnected: true,
      lastMessage: null,
      send: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
      hasExhaustedRetries: false,
      reconnectCount: 0,
      lastHeartbeat: null,
      connectionId: 'test-connection',
    };
  }),
}));

// The hook imports the builder via the '@/services/api' alias; mocking the
// same specifier the source uses keeps resolution unambiguous. The actual
// module is spread underneath so any other module that joins the import
// graph later still finds its real exports — only the builder is swapped.
vi.mock('@/services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/api')>()),
  buildWebSocketOptions: mocks.buildWebSocketOptions,
}));

vi.mock('@/services/logger', () => ({
  logger: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

/** Envelope shaped like backend/api's threat_detected broadcast. */
function threatMessage(overrides: Record<string, unknown> = {}): unknown {
  return {
    type: 'threat_detected',
    data: {
      id: 'threat-1',
      event_id: 'event-1',
      weapon_type: 'weapon',
      camera_name: 'front-door',
      timestamp: new Date().toISOString(),
      confidence: 0.92,
      ...overrides,
    },
  };
}

function hoursAgoISO(hours: number): string {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
}

describe('useRecentThreats', () => {
  beforeEach(() => {
    mocks.wsOptions = undefined;
    mocks.deliver = undefined;
    mocks.buildWebSocketOptions.mockReset();
    mocks.buildWebSocketOptions.mockReturnValue({
      url: 'ws://stack.example.test/ws/events',
    });
  });

  describe('socket wiring (F1.3 path, ruling-44 credential-free)', () => {
    it('asks buildWebSocketOptions for the /ws/events endpoint', () => {
      renderHook(() => useRecentThreats());
      expect(mocks.buildWebSocketOptions).toHaveBeenCalledWith('/ws/events');
    });

    it('forwards the builder url to useWebSocket with NO credential', () => {
      // Pre-F1.3 this failed: url was the hardcoded
      // ws://localhost:8000/ws/events (bypassing nginx). Post ruling 44 the
      // builder mints no protocol at all — the socket is cookie-authenticated.
      renderHook(() => useRecentThreats());
      expect(mocks.wsOptions).toMatchObject({
        url: 'ws://stack.example.test/ws/events',
        reconnect: true,
      });
      expect(mocks.wsOptions?.protocols).toBeUndefined();
    });
  });

  describe('message handling', () => {
    it('starts empty', () => {
      const { result } = renderHook(() => useRecentThreats());
      expect(result.current.threats).toEqual([]);
      expect(result.current.count).toBe(0);
      expect(result.current.hasNewThreat).toBe(false);
    });

    it('converts a threat_detected envelope to the camelCase shape', () => {
      const onNewThreat = vi.fn();
      const { result } = renderHook(() => useRecentThreats({ onNewThreat }));

      act(() => mocks.deliver?.(threatMessage()));

      expect(result.current.threats).toHaveLength(1);
      expect(result.current.threats[0]).toMatchObject({
        id: 'threat-1',
        eventId: 'event-1',
        weaponType: 'weapon',
        cameraName: 'front-door',
        confidence: 0.92,
      });
      expect(result.current.count).toBe(1);
      expect(result.current.hasNewThreat).toBe(true);
      expect(onNewThreat).toHaveBeenCalledWith(expect.objectContaining({ id: 'threat-1' }));
    });

    it('ignores envelopes that are not threat messages or fail the type guard', () => {
      const { result } = renderHook(() => useRecentThreats());

      act(() => mocks.deliver?.({ type: 'event.created', data: { id: 1 } }));
      // Same type, but confidence is missing → isThreatMessage must reject it.
      act(() => {
        const { confidence: _confidence, ...withoutConfidence } = (
          threatMessage() as { data: Record<string, unknown> }
        ).data;
        mocks.deliver?.({ type: 'threat_detected', data: withoutConfidence });
      });

      expect(result.current.threats).toEqual([]);
      expect(result.current.hasNewThreat).toBe(false);
    });

    it('drops duplicate threat ids', () => {
      const { result } = renderHook(() => useRecentThreats());

      act(() => mocks.deliver?.(threatMessage()));
      act(() => mocks.deliver?.(threatMessage()));

      expect(result.current.threats).toHaveLength(1);
    });

    it('excludes threats outside the maxAgeHours window', () => {
      const { result } = renderHook(() => useRecentThreats({ maxAgeHours: 24 }));

      // 25h old on a 24h window: rejected at insert time by filterByAge.
      act(() => mocks.deliver?.(threatMessage({ id: 'old', timestamp: hoursAgoISO(25) })));
      expect(result.current.threats).toEqual([]);

      act(() => mocks.deliver?.(threatMessage({ id: 'fresh', timestamp: hoursAgoISO(1) })));
      expect(result.current.threats.map((t) => t.id)).toEqual(['fresh']);
    });

    it('clearNewThreatFlag resets the animation flag', () => {
      const { result } = renderHook(() => useRecentThreats());

      act(() => mocks.deliver?.(threatMessage()));
      expect(result.current.hasNewThreat).toBe(true);

      act(() => result.current.clearNewThreatFlag());
      expect(result.current.hasNewThreat).toBe(false);
    });
  });
});
