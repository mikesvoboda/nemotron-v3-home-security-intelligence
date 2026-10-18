import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import {
  ConnectionStatusContext,
  type BackendSystemStatus,
  type ChannelStatus,
  type ConnectionState,
  type ConnectionStatusSummary,
  type UseConnectionStatusReturn,
} from './useConnectionStatus';
import {
  AUTH_TERMINAL_CLOSE_CODES,
  generateSubscriberId,
  webSocketManager,
} from './webSocketManager';
import { buildWebSocketOptions, fetchHealth, fetchEvents } from '../services/api';

import type { SecurityEvent } from './useEventStream';

// Backend WebSocket message envelope structure
interface BackendEventMessage {
  type: 'event';
  data: SecurityEvent;
}

const MAX_EVENTS = 100;

/**
 * Type guard to check if data is a valid SecurityEvent
 */
function isSecurityEvent(data: unknown): data is SecurityEvent {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const obj = data as Record<string, unknown>;
  return (
    ('id' in obj || 'event_id' in obj) &&
    'camera_id' in obj &&
    'risk_score' in obj &&
    'risk_level' in obj &&
    'summary' in obj
  );
}

/**
 * Type guard to check if message is a backend event message envelope
 */
function isBackendEventMessage(data: unknown): data is BackendEventMessage {
  if (!data || typeof data !== 'object') {
    return false;
  }
  const msg = data as Record<string, unknown>;
  return msg.type === 'event' && isSecurityEvent(msg.data);
}

function isBackendSystemStatus(data: unknown): data is BackendSystemStatus {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const msg = data as Record<string, unknown>;

  return (
    msg.type === 'system_status' &&
    typeof msg.data === 'object' &&
    msg.data !== null &&
    typeof msg.timestamp === 'string' &&
    'gpu' in msg.data &&
    'cameras' in msg.data &&
    'health' in msg.data
  );
}

// REST API polling interval when WebSocket fails
// Use shorter interval (5 seconds) during fallback for faster data updates
// and quicker detection of backend recovery
const FALLBACK_POLLING_INTERVAL = 5000;

/**
 * The schedule this provider asks the manager for. [r204]: these are the
 * values `useWebSocketStatus` carried as defaults before its socket code was
 * deleted, and they match every other production subscriber on these two URLs
 * (`usePrometheusAlertWebSocket`, `useVerdictEngineStatus`, … all pass
 * 1000/15) — which matters because the manager keeps ONE config per URL, the
 * first subscriber's, and React mounts child effects before parent effects.
 *
 * `maxReconnectAttempts: 15` is load-bearing beyond the schedule: the banner
 * renders `eventsChannel.maxReconnectAttempts +
 * systemChannel.maxReconnectAttempts` (Layout.tsx) — the "Attempt n/30" that
 * golden/shell/ws-status.spec.ts pins.
 */
const CHANNEL_CONNECTION = {
  reconnect: true,
  reconnectInterval: 1000,
  maxReconnectAttempts: 15,
  connectionTimeout: 10000,
  autoRespondToHeartbeat: true,
} as const;

/** Close codes that mean "your credential was refused". NOT re-declared here:
 * `webSocketManager` already owns the set (`AUTH_TERMINAL_CLOSE_CODES`,
 * webSocketManager.ts:155, a wire contract with the backend's
 * `auth.py WS_CLOSE_AUTH_REQUIRED`), and the manager's own `onclose` decides
 * the terminal rule from it. Importing it keeps the surface's label and the
 * transport's decision reading one list, so a future code added to the
 * transport cannot leave this hook describing that close as a generic failure. */

/** What the manager observation for one channel feeds into the summary. */
interface ChannelObservation {
  state: ConnectionState;
  reconnectAttempts: number;
  lastMessageTime: Date | null;
  hasExhaustedRetries: boolean;
  authRequired: boolean;
}

/**
 * Subscribe to one channel through the shared `webSocketManager` and project
 * the manager's callbacks onto a `ChannelStatus`.
 *
 * [r204] box 1: this replaced the second socket implementation
 * (`useWebSocketStatus`, whose `new WebSocket` and hand-rolled backoff are
 * deleted). The manager owns the transport — one connection per URL, shared
 * with every other hook on the same URL, its own byte-identical
 * `calculateBackoffDelay` (30 s cap, ≤25 % jitter — so the recovery-leg timing
 * golden/shell/ws-status.spec.ts budgets against is unchanged), and its
 * terminal-auth rule. This function opens nothing; it only translates.
 *
 * Message-shape note: the manager routes heartbeat frames to `onHeartbeat` and
 * never to `onMessage` (it answers them with a pong itself), while the deleted
 * hook passed every frame — heartbeats included — to `onMessage` and stamped
 * `lastMessageTime` from each. Stamping in both places below is what keeps the
 * tooltip's "Just now / Ns ago" (WebSocketStatus.tsx's `formatTimeSince`)
 * ticking exactly as F-007 reads it; `onOpen` deliberately does NOT stamp,
 * because the deleted hook never did either and `/ws/events` legitimately
 * reads "No messages yet" until a detection broadcasts. The payloads
 * themselves are unaffected: this channel's handlers type-guard on `type`, and
 * a heartbeat frame was never a `type: 'event'`.
 */
function useChannelStatus(
  url: string,
  protocols: string[] | undefined,
  channelName: string,
  onMessage: (data: unknown) => void,
  onMaxRetriesExhausted: () => void,
  retryToken: number
): ChannelStatus {
  const [observation, setObservation] = useState<ChannelObservation>({
    state: 'disconnected',
    reconnectAttempts: 0,
    lastMessageTime: null,
    hasExhaustedRetries: false,
    authRequired: false,
  });

  // Callbacks behind refs so the subscriber object never needs to be re-created
  // when a handler identity changes — the house pattern from useWebSocket.ts,
  // and it matters here because re-subscribing would churn the manager's
  // refcount on a URL that other hooks share.
  const onMessageRef = useRef(onMessage);
  const onMaxRetriesExhaustedRef = useRef(onMaxRetriesExhausted);
  useEffect(() => {
    onMessageRef.current = onMessage;
    onMaxRetriesExhaustedRef.current = onMaxRetriesExhausted;
  });

  // Dependency on the protocols' CONTENTS, not array identity:
  // buildWebSocketOptions returns a fresh array every render, so depending on
  // the array would resubscribe on every parent state change (useWebSocket.ts's
  // F1.3 comment is the original record of why).
  const protocolsKey = protocols?.length ? protocols.join(',') : undefined;

  useEffect(() => {
    const offeredProtocols = protocolsKey?.split(',');

    // The manager reports liveness, not a four-state lifecycle, so the close
    // handler has to infer "still trying" vs "stopped". The signal is whether
    // the attempt count ADVANCED on this close: the manager increments
    // `reconnectAttempts` only in the branch that schedules a retry, and it
    // does so before notifying subscribers (its own ordering comment), so a
    // close that raised the count has a retry queued and a close that did not
    // is a close it gave up on — the terminal-auth case (no increment) and the
    // exhausted case (count already at the max) both land there. Reading the
    // delta rather than comparing the count to the max is what keeps this
    // hook's states identical to the deleted hook's, which flipped to 'failed'
    // one close LATER than a `count >= max` test taken at notify time would.
    const applyClose = (authRequired: boolean) => {
      const managerState = webSocketManager.getConnectionState(url);
      setObservation((prev) => {
        const rescheduled = managerState.reconnectCount > prev.reconnectAttempts;
        return {
          state: authRequired || !rescheduled ? 'failed' : 'reconnecting',
          reconnectAttempts: managerState.reconnectCount,
          lastMessageTime: prev.lastMessageTime,
          // The manager fires `onMaxRetriesExhausted` alongside the final
          // close; that callback owns the flag. Here the close only proves
          // exhaustion when it stopped without a reschedule and the socket is
          // genuinely down — which is also the terminal-auth case, where
          // "exhausted" would be a lie about what happened, so authRequired
          // deliberately does not set it.
          hasExhaustedRetries:
            prev.hasExhaustedRetries ||
            (!authRequired && !rescheduled && !managerState.isConnected),
          authRequired,
        };
      });
    };

    const unsubscribe = webSocketManager.subscribe(
      url,
      {
        id: generateSubscriberId(),
        onOpen: () => {
          const managerState = webSocketManager.getConnectionState(url);
          setObservation({
            state: 'connected',
            reconnectAttempts: managerState.reconnectCount,
            lastMessageTime: null,
            hasExhaustedRetries: false,
            authRequired: false,
          });
        },
        // The manager forwards the CloseEvent verbatim to subscribers BEFORE
        // deciding about reconnection, so an auth refusal is visible here as
        // the code itself — that read is the whole terminal-auth rule for this
        // surface (box 2: a 4001 shows as such and is not retried).
        onClose: (event?: CloseEvent) => {
          applyClose(
            typeof event?.code === 'number' && AUTH_TERMINAL_CLOSE_CODES.includes(event.code)
          );
        },
        onMessage: (data) => {
          setObservation((prev) => ({ ...prev, lastMessageTime: new Date() }));
          onMessageRef.current?.(data);
        },
        onHeartbeat: () => {
          // Keep "last message" fresh on heartbeats — see the function
          // comment's message-shape note.
          setObservation((prev) => ({ ...prev, lastMessageTime: new Date() }));
        },
        onError: () => {
          // The manager logs the error and the close that follows carries the
          // state; the deleted hook forwarded it to an `onError` no consumer
          // here used. Kept as a no-op subscriber member so the shape is
          // explicit rather than missing.
        },
        onMaxRetriesExhausted: () => {
          setObservation((prev) => ({
            ...prev,
            state: 'failed',
            hasExhaustedRetries: true,
          }));
          onMaxRetriesExhaustedRef.current?.();
        },
      },
      {
        ...CHANNEL_CONNECTION,
        protocols: offeredProtocols,
      }
    );

    return () => {
      unsubscribe();
    };
    // channelName is display-only metadata (it names the row in the tooltip),
    // not a subscription input, so it is deliberately not a dependency.
  }, [url, protocolsKey]);

  // A manual retry clears the terminal flags, matching the deleted hook's
  // `connect()`, which called `setHasExhaustedRetries(false)` before
  // re-handshaking. The attempt count is the manager's to reset (its
  // `reconnect()` does exactly that) and the state is left alone — the close
  // handler sets it from what the fresh handshake actually did, and inventing a
  // 'connecting' value here would be a fifth state the union forbids.
  useEffect(() => {
    if (retryToken === 0) return;
    setObservation((prev) => ({ ...prev, hasExhaustedRetries: false, authRequired: false }));
  }, [retryToken]);

  // Memoized (the deleted hook rebuilt this literal every render, which made
  // the summary memo below rebuild too): the manager only pushes on
  // open/close/message, so between those the channels — and therefore the
  // context value — keep their identity and consumers skip the re-render.
  return useMemo(
    () => ({
      name: channelName,
      state: observation.state,
      reconnectAttempts: observation.reconnectAttempts,
      maxReconnectAttempts: CHANNEL_CONNECTION.maxReconnectAttempts,
      lastMessageTime: observation.lastMessageTime,
      hasExhaustedRetries: observation.hasExhaustedRetries,
      authRequired: observation.authRequired,
    }),
    [channelName, observation]
  );
}

/**
 * Mounts the app's ONE Events/System status subscription and shares it with
 * every consumer through `useConnectionStatus`.
 *
 * [r204] box 1: before this provider, `useConnectionStatus()` built a session
 * per call, and the shell has two callers (Layout.tsx, Header.tsx), so the
 * mounted app ran four independent reconnect state machines over two URLs —
 * four schedulers whose slowest member the status surfaces had to wait on —
 * each pair opening its own sockets through `useWebSocketStatus` and so
 * bypassing `webSocketManager`'s share-by-URL, heartbeat handling and
 * terminal-auth rule entirely. The manager already shared one connection per
 * URL for every other hook (`useWebSocket.ts` is the model); this provider puts
 * the status path on the same rails, so the whole app agrees about what
 * "connected" means and the transport's constructor call lives in exactly one
 * file. (Deliberately not spelled as the grep pattern here: this module's own
 * prose would then show up in the Done-when census it is describing.)
 *
 * Mount position matters: this provider sits inside `<ProtectedRoute>` in
 * App.tsx, which is the precondition the manager's terminal-close note states
 * ("recovery after a auth close is React's — every WS hook mounts inside
 * <ProtectedRoute>, so a login remounts it"). A provider ABOVE the gate would
 * hold a socket that stays closed until manual reload after a 4001; that is the
 * exact case the manager's comment warns about, so the position is part of the
 * design, not a layout preference.
 */
export function ConnectionStatusProvider({ children }: { children: ReactNode }) {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [systemStatus, setSystemStatus] = useState<BackendSystemStatus | null>(null);
  const [isPollingFallback, setIsPollingFallback] = useState(false);
  const [disconnectedSince, setDisconnectedSince] = useState<Date | null>(null);
  // Bumped by `retryConnection` so each channel can clear a terminal claim
  // (exhausted / authRequired) the moment the user asks for a fresh handshake.
  const [retryToken, setRetryToken] = useState(0);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastEventIdRef = useRef<string | number | null>(null);

  const handleEventMessage = useCallback((data: unknown) => {
    if (isBackendEventMessage(data)) {
      const event = data.data;
      setEvents((prevEvents) => {
        const newEvents = [event, ...prevEvents];
        return newEvents.slice(0, MAX_EVENTS);
      });
    }
  }, []);

  const handleSystemMessage = useCallback((data: unknown) => {
    if (isBackendSystemStatus(data)) {
      setSystemStatus(data);
    }
  }, []);

  // Track if we should trigger reconnect after successful health check
  const shouldAutoReconnectRef = useRef(false);

  // REST API polling fallback function
  /* v8 ignore start -- polling fallback is triggered by onMaxRetriesExhausted which requires
   * real WebSocket connection exhaustion. Mock setup cannot reliably trigger this callback. */
  const pollRestApi = useCallback(async () => {
    try {
      // Fetch health status
      const health = await fetchHealth();

      // If health check succeeds during polling fallback, backend is back online
      // Set flag to trigger WebSocket reconnection
      if (health.status === 'healthy' || health.status === 'degraded') {
        shouldAutoReconnectRef.current = true;
      }

      // Get GPU status safely
      const gpuService = health.services?.gpu;
      const gpuIsHealthy = gpuService?.status === 'healthy';

      // Convert health response to BackendSystemStatus format
      // Map the health status to valid values
      const healthValue =
        health.status === 'healthy' || health.status === 'degraded' || health.status === 'unhealthy'
          ? health.status
          : 'unhealthy';

      const healthStatus: BackendSystemStatus = {
        type: 'system_status',
        data: {
          gpu: {
            utilization: gpuIsHealthy ? 50 : null,
            memory_used: null,
            memory_total: null,
            temperature: null,
            inference_fps: null,
          },
          cameras: {
            active: 0,
            total: 0,
          },
          queue: {
            pending: 0,
            processing: 0,
          },
          health: healthValue,
        },
        timestamp: new Date().toISOString(),
      };
      setSystemStatus(healthStatus);

      // Fetch recent events
      const eventsResponse = await fetchEvents({ limit: 20 });
      if (eventsResponse.items && eventsResponse.items.length > 0) {
        // Only add new events we haven't seen
        const newEvents = eventsResponse.items.filter(
          (event) => event.id !== lastEventIdRef.current
        );
        if (newEvents.length > 0) {
          lastEventIdRef.current = eventsResponse.items[0].id;
          setEvents((prevEvents) => {
            // Convert Event to SecurityEvent format
            const securityEvents: SecurityEvent[] = newEvents.map((e) => {
              // Validate risk_level is a valid value — but "not a level I
              // recognise" is NOT "low" (D11). null is the unknown the
              // SecurityEventData contract declares, and renderers branch on
              // it; folding it into 'low' is the same lie as `?? 0` below it.
              const validRiskLevels = ['low', 'medium', 'high', 'critical'] as const;
              type RiskLevel = (typeof validRiskLevels)[number];
              const riskLevel: RiskLevel | null = validRiskLevels.includes(
                e.risk_level as RiskLevel
              )
                ? (e.risk_level as RiskLevel)
                : null;

              return {
                id: e.id,
                event_id: e.id,
                camera_id: e.camera_id,
                // D11: no score = verification_failed/never-verified, not a 0.
                // The sibling WS path (`handleEventMessage`) already stores the
                // payload verbatim; this REST mapper must not invent a number
                // the WS path would never invent.
                risk_score: e.risk_score ?? null,
                risk_level: riskLevel,
                summary: e.summary ?? '',
                timestamp: e.started_at,
                started_at: e.started_at,
              };
            });
            const combined = [...securityEvents, ...prevEvents];
            // Deduplicate by id
            const unique = combined.filter(
              (event, index, self) => index === self.findIndex((ev) => ev.id === event.id)
            );
            return unique.slice(0, MAX_EVENTS);
          });
        }
      }
    } catch {
      // Polling failure is expected when server is down - silently ignore
      shouldAutoReconnectRef.current = false;
    }
  }, []);
  /* v8 ignore stop */

  // Reference to retry function (will be set once the channels exist)
  const retryConnectionRef = useRef<(() => void) | null>(null);

  // Start/stop polling based on WebSocket state
  /* v8 ignore start -- part of polling fallback system, requires onMaxRetriesExhausted trigger */
  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current) return; // Already polling

    setIsPollingFallback(true);
    shouldAutoReconnectRef.current = false;

    // Immediate first poll
    void pollRestApi();

    // Set up interval with shorter polling during fallback (5s instead of 30s)
    // This provides faster data updates and quicker backend recovery detection
    pollingIntervalRef.current = setInterval(() => {
      void pollRestApi();

      // If health check succeeded, trigger WebSocket reconnection
      if (shouldAutoReconnectRef.current && retryConnectionRef.current) {
        shouldAutoReconnectRef.current = false;
        retryConnectionRef.current();
      }
    }, FALLBACK_POLLING_INTERVAL);
  }, [pollRestApi]);

  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
      setIsPollingFallback(false);
      shouldAutoReconnectRef.current = false;
    }
  }, []);
  /* v8 ignore stop */

  // Build WebSocket options using helper (respects VITE_WS_BASE_URL)
  // SECURITY (ruling 44): browsers open this socket cookie-authenticated; no key
  const eventsWsOptions = buildWebSocketOptions('/ws/events');
  const systemWsOptions = buildWebSocketOptions('/ws/system');

  const eventsChannel = useChannelStatus(
    eventsWsOptions.url,
    eventsWsOptions.protocols,
    'Events',
    handleEventMessage,
    startPolling,
    retryToken
  );

  const systemChannel = useChannelStatus(
    systemWsOptions.url,
    systemWsOptions.protocols,
    'System',
    handleSystemMessage,
    startPolling,
    retryToken
  );

  // Stop polling when WebSocket reconnects
  useEffect(() => {
    if (eventsChannel.state === 'connected' || systemChannel.state === 'connected') {
      stopPolling();
    }
  }, [eventsChannel.state, systemChannel.state, stopPolling]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  // Track when disconnection started
  useEffect(() => {
    const isConnected = eventsChannel.state === 'connected' && systemChannel.state === 'connected';

    if (isConnected) {
      // Clear disconnection time when reconnected
      setDisconnectedSince(null);
    } else if (disconnectedSince === null) {
      // Set disconnection time when first disconnected
      setDisconnectedSince(new Date());
    }
    // Note: We intentionally don't include disconnectedSince in deps to avoid resetting
    // the timestamp on every render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventsChannel.state, systemChannel.state]);

  const clearEvents = useCallback(() => {
    setEvents([]);
    lastEventIdRef.current = null;
  }, []);

  // Manual retry: ask the manager to re-handshake both channels. On a
  // terminal-auth close this is the user-facing half of the recovery the
  // manager deliberately leaves to React (its `authRefused` note): a re-login
  // remounts this provider inside <ProtectedRoute>, and the Retry button covers
  // a credential that refreshed without a remount. `reconnect()` is a no-op
  // while refCount is 0 and it resets the attempt count, so a manual retry
  // gets a full schedule rather than resuming the exhausted one — which is
  // box 2's "keeps its meaning": retryConnection still means "try again".
  const retryConnection = useCallback(() => {
    stopPolling();
    webSocketManager.reconnect(eventsWsOptions.url);
    webSocketManager.reconnect(systemWsOptions.url);
    // Bumping the token is what tells each channel to drop a stale
    // exhausted/authRequired claim while the fresh handshake is in flight.
    setRetryToken((n) => n + 1);
  }, [stopPolling, eventsWsOptions.url, systemWsOptions.url]);

  // Update ref so auto-reconnect can access this function
  useEffect(() => {
    retryConnectionRef.current = retryConnection;
  }, [retryConnection]);

  const summary = useMemo((): ConnectionStatusSummary => {
    const anyReconnecting =
      eventsChannel.state === 'reconnecting' || systemChannel.state === 'reconnecting';
    const allConnected = eventsChannel.state === 'connected' && systemChannel.state === 'connected';
    const hasExhaustedRetries =
      eventsChannel.hasExhaustedRetries || systemChannel.hasExhaustedRetries;
    const allFailed = eventsChannel.state === 'failed' && systemChannel.state === 'failed';
    const anyFailed = eventsChannel.state === 'failed' || systemChannel.state === 'failed';

    let overallState: ConnectionState;
    if (allConnected) {
      overallState = 'connected';
    } else if (anyFailed) {
      overallState = 'failed';
    } else if (anyReconnecting) {
      overallState = 'reconnecting';
    } else {
      overallState = 'disconnected';
    }

    return {
      eventsChannel,
      systemChannel,
      overallState,
      anyReconnecting,
      allConnected,
      totalReconnectAttempts: eventsChannel.reconnectAttempts + systemChannel.reconnectAttempts,
      hasExhaustedRetries,
      allFailed,
      authRequired: Boolean(eventsChannel.authRequired || systemChannel.authRequired),
      disconnectedSince,
    };
  }, [eventsChannel, systemChannel, disconnectedSince]);

  const value = useMemo<UseConnectionStatusReturn>(
    () => ({
      summary,
      events,
      systemStatus,
      clearEvents,
      isPollingFallback,
      retryConnection,
    }),
    [summary, events, systemStatus, clearEvents, isPollingFallback, retryConnection]
  );

  return (
    <ConnectionStatusContext.Provider value={value}>{children}</ConnectionStatusContext.Provider>
  );
}
