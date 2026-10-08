/**
 * useVerdictEngineStatus - verdict-engine (ai-vlm) availability for the F1.2 banner
 *
 * F1.2 (UR-18): reads the state from B1.4's readiness field on load
 * (GET /api/system/health/ready -> verdict_engine, always present on
 * ReadinessResponse) and from system.verdict_engine_status_changed
 * WebSocket events afterwards. The WS event fires ONLY on transitions
 * (backend/services/verdict_engine_status.py), so it can never supply
 * first-paint state — HTTP seeds, the socket updates.
 *
 * The readiness poll stays alive while mounted: the event is fire-and-forget
 * (a missed transition during a socket gap would otherwise wedge the banner
 * on a stale state until the next transition), and the backend caches the
 * probe for HEALTH_CACHE_TTL_SECONDS (15 s), so a 15 s poll is cheap.
 *
 * Envelope on /ws/system is {type, data:{...}}: the backend emitter re-wraps
 * payloads under `data` for the system channel
 * (backend/services/websocket_emitter.py _dispatch_to_system_broadcaster).
 *
 * @module hooks/useVerdictEngineStatus
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions, fetchReadiness } from '../services/api';
import { logger } from '../services/logger';
import { isHeartbeatMessage, isErrorMessage } from '../types/websocket';

import type {
  VerdictEngineState,
  VerdictEngineStatusChangedPayload,
} from '../types/websocket-events';

export type { VerdictEngineState } from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/** Options for configuring the useVerdictEngineStatus hook */
export interface UseVerdictEngineStatusOptions {
  /**
   * Whether to enable the WebSocket connection and readiness polling.
   * @default true
   */
  enabled?: boolean;

  /**
   * Readiness re-read interval in ms. 0 disables polling (state then moves
   * only on WS transitions — tests use this; production keeps the default).
   * @default 15000
   */
  pollIntervalMs?: number;
}

/** Return type for the useVerdictEngineStatus hook */
export interface UseVerdictEngineStatusReturn {
  /** Engine state; 'unknown' until first data, or when the probe cannot tell */
  state: VerdictEngineState;
  /** ISO time the state last TRANSITIONED (survives the readiness cache) */
  since: string | null;
  /** Engine's error string while unavailable/unknown; null while available */
  reason: string | null;
  /** True once the first readiness read has settled (success or failure) */
  loaded: boolean;
  /** True only for the alarm state ('unavailable') — drives the banner */
  isDown: boolean;
  /** Whether the /ws/system socket is connected */
  isConnected: boolean;
}

/** Default poll cadence: the backend caches the probe for 15 s anyway. */
const DEFAULT_POLL_INTERVAL_MS = 15000;

// ============================================================================
// Type Guard
// ============================================================================

const VERDICT_ENGINE_STATES = ['available', 'unavailable', 'unknown'] as const;

/**
 * Type guard for system.verdict_engine_status_changed messages ({type, data}).
 */
export function isVerdictEngineStatusChangedMessage(
  value: unknown
): value is { type: 'system.verdict_engine_status_changed'; data: VerdictEngineStatusChangedPayload } {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const msg = value as Record<string, unknown>;
  if (msg.type !== 'system.verdict_engine_status_changed') {
    return false;
  }

  if (!msg.data || typeof msg.data !== 'object') {
    return false;
  }

  const data = msg.data as Record<string, unknown>;
  return (
    typeof data.state === 'string' &&
    (VERDICT_ENGINE_STATES as readonly string[]).includes(data.state) &&
    typeof data.since === 'string'
  );
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Tracks verdict-engine (ai-vlm) availability for the persistent banner.
 *
 * @example
 * ```tsx
 * const { state, since, reason, isDown } = useVerdictEngineStatus();
 * {isDown && <VerdictEngineStatusBanner state={state} since={since} reason={reason} />}
 * ```
 */
export function useVerdictEngineStatus(
  options: UseVerdictEngineStatusOptions = {}
): UseVerdictEngineStatusReturn {
  const { enabled = true, pollIntervalMs = DEFAULT_POLL_INTERVAL_MS } = options;

  const [state, setState] = useState<VerdictEngineState>('unknown');
  const [since, setSince] = useState<string | null>(null);
  const [reason, setReason] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const applyVerdict = useCallback((next: VerdictEngineStatusChangedPayload | {
    state: VerdictEngineState;
    since: string | null;
    reason: string | null;
  }) => {
    if (!isMountedRef.current) {
      return;
    }
    setState(next.state);
    setSince(next.since ?? null);
    setReason(next.reason ?? null);
  }, []);

  // Initial state (and convergence): B1.4's readiness field.
  useEffect(() => {
    if (!enabled) {
      return;
    }

    let cancelled = false;

    const readReadiness = async () => {
      try {
        const readiness = await fetchReadiness();
        if (cancelled || !isMountedRef.current) {
          return;
        }
        const verdict = readiness.verdict_engine;
        setState(verdict.state);
        setSince(verdict.since ?? null);
        setReason(verdict.reason ?? null);
        setLoaded(true);
      } catch (error) {
        if (cancelled || !isMountedRef.current) {
          return;
        }
        // Honest unknown: a failed probe read is not evidence the engine is down.
        logger.debug('Verdict-engine readiness read failed', {
          component: 'useVerdictEngineStatus',
          error: String(error),
        });
        setState('unknown');
        setReason('readiness probe unavailable');
        setLoaded(true);
      }
    };

    void readReadiness();

    if (pollIntervalMs > 0) {
      const timer = setInterval(() => void readReadiness(), pollIntervalMs);
      return () => {
        cancelled = true;
        clearInterval(timer);
      };
    }

    return () => {
      cancelled = true;
    };
  }, [enabled, pollIntervalMs]);

  // Transitions: system.verdict_engine_status_changed on /ws/system.
  const handleMessage = useCallback(
    (data: unknown) => {
      if (!isMountedRef.current) {
        return;
      }

      if (isVerdictEngineStatusChangedMessage(data)) {
        const payload = data.data;
        logger.debug('Verdict-engine transition event received', {
          component: 'useVerdictEngineStatus',
          state: payload.state,
          previous_state: payload.previous_state,
          since: payload.since,
        });
        applyVerdict({
          state: payload.state,
          since: payload.since,
          reason: payload.reason ?? null,
        });
        return;
      }

      // Handle other message types (silently ignore)
      if (isHeartbeatMessage(data)) {
        return;
      }

      if (isErrorMessage(data)) {
        logger.warn('Verdict-engine status WebSocket error', {
          component: 'useVerdictEngineStatus',
          message: data.message,
        });
      }
    },
    [applyVerdict]
  );

  const wsOptions = buildWebSocketOptions('/ws/system');

  const { isConnected } = useWebSocket(
    enabled
      ? {
          url: wsOptions.url,
          protocols: wsOptions.protocols,
          onMessage: handleMessage,
          reconnect: true,
          reconnectInterval: 1000,
          reconnectAttempts: 15,
          connectionTimeout: 10000,
          autoRespondToHeartbeat: true,
        }
      : {
          url: wsOptions.url,
          protocols: wsOptions.protocols,
          onMessage: handleMessage,
          reconnect: false,
        }
  );

  return {
    state,
    since,
    reason,
    loaded,
    isDown: state === 'unavailable',
    isConnected,
  };
}

export default useVerdictEngineStatus;
