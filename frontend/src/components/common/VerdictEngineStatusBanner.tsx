/**
 * VerdictEngineStatusBanner - persistent banner for verdict-engine (ai-vlm) downtime
 *
 * F1.2 (UR-18): when the engine is `unavailable`, a persistent banner reads
 * that the verdict engine is unavailable since a time and that new events
 * need review; it clears when the state returns to `available`.
 *
 * Presentational (state arrives via props; Layout owns the data via
 * useVerdictEngineStatus), styled after ConnectionStatusBanner — the closest
 * analog in the house. `unavailable` is the alarm (role=alert, assertive);
 * `unknown` is a warning (role=status, polite) because the backend's honest
 * third state means "the probe could not tell", not "the engine is down".
 * `available` renders nothing.
 */

import { AlertOctagon, AlertTriangle, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { useAnnounce } from '../../hooks/useAnnounce';

import type { VerdictEngineState } from '../../types/websocket-events';

export interface VerdictEngineStatusBannerProps {
  /** Engine state from useVerdictEngineStatus */
  state: VerdictEngineState;
  /** ISO time the state last TRANSITIONED (the banner shows elapsed downtime) */
  since: string | null;
  /** Engine's error string while unavailable/unknown */
  reason: string | null;
  /** Extra classes on the banner container */
  className?: string;
}

interface BannerStyling {
  bgClass: string;
  borderClass: string;
  textClass: string;
  role: 'alert' | 'status';
  ariaLive: 'assertive' | 'polite';
}

const STYLING: Record<VerdictEngineState, BannerStyling> = {
  unavailable: {
    bgClass: 'bg-red-900/30',
    borderClass: 'border-red-500/50',
    textClass: 'text-red-400',
    role: 'alert',
    ariaLive: 'assertive',
  },
  unknown: {
    bgClass: 'bg-yellow-900/30',
    borderClass: 'border-yellow-500/50',
    textClass: 'text-yellow-400',
    role: 'status',
    ariaLive: 'polite',
  },
  available: {
    bgClass: '',
    borderClass: '',
    textClass: '',
    role: 'status',
    ariaLive: 'polite',
  },
};

/** Compact elapsed time since an ISO transition time: "3m", "2h", "1d 4h". */
export function formatSince(since: string, now: Date = new Date()): string {
  const then = new Date(since).getTime();
  if (Number.isNaN(then)) {
    return '';
  }
  const totalSeconds = Math.max(0, Math.floor((now.getTime() - then) / 1000));
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  if (days > 0) {
    return `${days}d ${hours}h`;
  }
  if (hours > 0) {
    return `${hours}h`;
  }
  if (minutes > 0) {
    return `${minutes}m`;
  }
  return '<1m';
}

export function VerdictEngineStatusBanner({
  state,
  since,
  reason,
  className = '',
}: VerdictEngineStatusBannerProps) {
  const [isDismissed, setIsDismissed] = useState(false);
  const { announce } = useAnnounce();
  const previousStateRef = useRef<VerdictEngineState>(state);

  // Announce transitions only, never on first render (ConnectionStatusBanner pattern)
  // Mounting this ref to the first state is also what keeps the banner
  // dismissible: dismissal only clears on an actual state transition.
  useEffect(() => {
    const previous = previousStateRef.current;
    if (previous === state) {
      return;
    }
    previousStateRef.current = state;
    setIsDismissed(false);
    if (state === 'unavailable') {
      announce('Verdict engine unavailable. New events need review.', 'assertive');
    } else if (state === 'unknown') {
      announce('Verdict engine state unknown.', 'polite');
    } else {
      announce('Verdict engine available again.', 'polite');
    }
  }, [state, announce]);

  if (state === 'available' || isDismissed) {
    return null;
  }

  const styling = STYLING[state];
  const Icon = state === 'unavailable' ? AlertOctagon : AlertTriangle;
  const elapsed = since ? formatSince(since) : '';

  return (
    <div
      className={`flex items-center justify-between gap-4 rounded-lg border px-4 py-3 ${styling.bgClass} ${styling.borderClass} ${className}`}
      role={styling.role}
      aria-live={styling.ariaLive}
      data-testid="verdict-engine-banner"
    >
      <div className="flex items-center gap-3">
        <Icon className={`h-5 w-5 shrink-0 ${styling.textClass}`} aria-hidden="true" />
        <div className="flex flex-col gap-0.5">
          <span className={`font-medium ${styling.textClass}`}>
            {state === 'unavailable'
              ? 'Verdict engine unavailable'
              : 'Verdict engine state unknown'}
            {elapsed ? (
              <span data-testid="verdict-engine-since"> — unavailable for {elapsed}</span>
            ) : null}
          </span>
          <span className="text-sm text-gray-300">
            New events need review: without the engine, verifications fall back to
            verification_failed.
          </span>
          {reason ? (
            <span data-testid="verdict-engine-reason" className="text-xs text-gray-400">
              {reason}
            </span>
          ) : null}
        </div>
      </div>
      <button
        type="button"
        onClick={() => setIsDismissed(true)}
        aria-label="Dismiss verdict engine alert"
        className={`shrink-0 rounded p-1 transition-colors hover:bg-white/10 focus:outline-none focus:ring-2 ${
          state === 'unavailable' ? 'focus:ring-red-500/50' : 'focus:ring-yellow-500/50'
        }`}
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

export default VerdictEngineStatusBanner;
