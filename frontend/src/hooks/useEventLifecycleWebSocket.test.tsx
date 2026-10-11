/**
 * Tests for useEventLifecycleWebSocket (added by F1.3).
 *
 * This hook joined the credential path in e0cd9333: with no explicit `url` it
 * now resolves through buildWebSocketOptions (VITE_WS_BASE_URL or the page
 * origin). Ruling 44: the browser builder attaches no credential subprotocol —
 * the socket rides the session cookie — while an explicit `url` option still
 * wins. Its removed
 * DEFAULT_WS_URL hardcoded ws://localhost:8000 — invisible to nginx in a
 * deployed stack — and CI's Test Coverage Gate named this missing test file
 * at PR #6922's head. Beyond the wiring, the suite covers the message
 * contract: type-guarded dispatch to the per-type callbacks and the React
 * Query invalidation that keeps the events caches fresh.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useEventLifecycleWebSocket } from './useEventLifecycleWebSocket';
import { eventsQueryKeys } from './useEventsQuery';
import { recentEventsQueryKeys } from './useRecentEventsQuery';

import type { UseWebSocketReturn, WebSocketOptions } from './useWebSocket';
import type { ReactNode } from 'react';

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

// Spread the actual module underneath: the hook's sibling imports
// (./useEventsQuery, ./useRecentEventsQuery) also import from services/api,
// and they must keep finding their real exports. Only the builder is swapped.
vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/api')>()),
  buildWebSocketOptions: mocks.buildWebSocketOptions,
}));

vi.mock('../services/logger', () => ({
  logger: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

const createdPayload = {
  id: 7,
  event_id: 70,
  batch_id: 'batch-a',
  camera_id: 'cam-1',
  risk_score: 0.8,
  risk_level: 'high' as const,
  summary: 'motion at door',
  reasoning: 'weapon-like shape',
};

function wrap(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('useEventLifecycleWebSocket', () => {
  let queryClient: QueryClient;
  let invalidateSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mocks.wsOptions = undefined;
    mocks.deliver = undefined;
    mocks.buildWebSocketOptions.mockReset();
    mocks.buildWebSocketOptions.mockReturnValue({
      url: 'ws://stack.example.test/ws/events',
    });
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
  });

  describe('socket wiring (F1.3 path, ruling-44 credential-free)', () => {
    it('asks buildWebSocketOptions for /ws/events when no url is given', () => {
      renderHook(() => useEventLifecycleWebSocket(), { wrapper: wrap(queryClient) });
      expect(mocks.buildWebSocketOptions).toHaveBeenCalledWith('/ws/events');
    });

    it('forwards the builder url with no minted credential', () => {
      // Pre-fix the socket hit localhost:8000 directly, bypassing nginx.
      // Ruling 44: the browser builder attaches no protocol — cookie auth.
      renderHook(() => useEventLifecycleWebSocket(), { wrapper: wrap(queryClient) });
      expect(mocks.wsOptions).toMatchObject({
        url: 'ws://stack.example.test/ws/events',
        reconnect: true,
      });
      expect(mocks.wsOptions?.protocols).toBeUndefined();
    });

    it('an explicit url option wins and the builder is not consulted', () => {
      renderHook(() => useEventLifecycleWebSocket({ url: 'ws://explicit.test/ws/events' }), {
        wrapper: wrap(queryClient),
      });
      expect(mocks.buildWebSocketOptions).not.toHaveBeenCalled();
      expect(mocks.wsOptions).toMatchObject({
        url: 'ws://explicit.test/ws/events',
        protocols: undefined,
      });
    });

    it('an explicit url plus explicit protocols forwards both', () => {
      renderHook(
        () =>
          useEventLifecycleWebSocket({
            url: 'ws://explicit.test/ws/events',
            protocols: ['messaging.v1'],
          }),
        { wrapper: wrap(queryClient) }
      );
      expect(mocks.wsOptions).toMatchObject({
        url: 'ws://explicit.test/ws/events',
        protocols: ['messaging.v1'],
      });
    });
  });

  describe('lifecycle dispatch', () => {
    it('routes event.created to onEventCreated and onAnyEventLifecycle', () => {
      const onEventCreated = vi.fn();
      const onAnyEventLifecycle = vi.fn();
      const { result } = renderHook(
        () => useEventLifecycleWebSocket({ onEventCreated, onAnyEventLifecycle }),
        { wrapper: wrap(queryClient) }
      );

      act(() => mocks.deliver?.({ type: 'event.created', data: createdPayload }));

      expect(onEventCreated).toHaveBeenCalledWith(createdPayload);
      expect(onAnyEventLifecycle).toHaveBeenCalledWith('event.created', createdPayload);
      expect(result.current.lastEventType).toBe('event.created');
      expect(result.current.lastEventPayload).toEqual(createdPayload);
    });

    it('routes event.updated to onEventUpdated', () => {
      const onEventUpdated = vi.fn();
      const { result } = renderHook(() => useEventLifecycleWebSocket({ onEventUpdated }), {
        wrapper: wrap(queryClient),
      });

      const payload = { id: 7, updated_fields: ['risk_score'], risk_score: 0.95 };
      act(() => mocks.deliver?.({ type: 'event.updated', data: payload }));

      expect(onEventUpdated).toHaveBeenCalledWith(payload);
      expect(result.current.lastEventType).toBe('event.updated');
    });

    it('routes event.deleted to onEventDeleted', () => {
      const onEventDeleted = vi.fn();
      const { result } = renderHook(() => useEventLifecycleWebSocket({ onEventDeleted }), {
        wrapper: wrap(queryClient),
      });

      const payload = { id: 7, reason: 'retention' };
      act(() => mocks.deliver?.({ type: 'event.deleted', data: payload }));

      expect(onEventDeleted).toHaveBeenCalledWith(payload);
      expect(result.current.lastEventType).toBe('event.deleted');
    });

    it('ignores malformed messages without touching state', () => {
      const onEventCreated = vi.fn();
      const { result } = renderHook(() => useEventLifecycleWebSocket({ onEventCreated }), {
        wrapper: wrap(queryClient),
      });

      act(() => mocks.deliver?.({ type: 'event.created' })); // no data
      act(() => mocks.deliver?.({ type: 'unrelated.message', data: { id: 1 } }));

      expect(onEventCreated).not.toHaveBeenCalled();
      expect(result.current.lastEventType).toBeNull();
      expect(result.current.lastEventPayload).toBeNull();
    });

    it('invalidates both events caches on a lifecycle message', () => {
      renderHook(() => useEventLifecycleWebSocket(), { wrapper: wrap(queryClient) });

      act(() => mocks.deliver?.({ type: 'event.created', data: createdPayload }));

      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: eventsQueryKeys.all });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: recentEventsQueryKeys.all });
    });

    it('autoInvalidateCache: false skips the invalidation', () => {
      renderHook(() => useEventLifecycleWebSocket({ autoInvalidateCache: false }), {
        wrapper: wrap(queryClient),
      });

      act(() => mocks.deliver?.({ type: 'event.created', data: createdPayload }));

      expect(invalidateSpy).not.toHaveBeenCalled();
    });
  });
});
