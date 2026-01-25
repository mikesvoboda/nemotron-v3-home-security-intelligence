/**
 * TimelineEntry - Single entry in the job history timeline
 *
 * Displays a state transition with:
 * - Status dot
 * - Timestamp
 * - Status label with message
 * - Vertical connector line to next entry
 *
 * @module components/jobs/TimelineEntry
 */

import { clsx } from 'clsx';

import StatusDot from './StatusDot';

import type React from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Transition data from the API
 */
export interface Transition {
  /** Previous status (null for initial transition) */
  from: string | null;
  /** New status after transition */
  to: string;
  /** ISO timestamp of the transition */
  at: string;
  /** What triggered the transition (api, worker, system) */
  triggered_by: string;
  /** Additional transition details */
  details: Record<string, unknown> | null;
}

/**
 * Props for the TimelineEntry component
 */
export interface TimelineEntryProps {
  /** The transition to display */
  transition: Transition;
  /** Whether this is the last entry (no connector line) */
  isLast: boolean;
  /** Whether to show the triggered_by attribution */
  showTriggeredBy?: boolean;
  /** Optional additional CSS classes */
  className?: string;
}

// ============================================================================
// Helpers
// ============================================================================

/**
 * Format a timestamp for display in the timeline
 */
function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return isoString;
  }
}

/**
 * Get a human-readable label for a status
 */
function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: 'Pending',
    queued: 'Queued',
    processing: 'Processing',
    running: 'Running',
    completed: 'Completed',
    failed: 'Failed',
    cancelled: 'Cancelled',
  };
  return labels[status] ?? status.charAt(0).toUpperCase() + status.slice(1);
}

/**
 * Get a message describing the transition
 */
function getTransitionMessage(transition: Transition): string {
  const { from, to, details } = transition;

  // Check for custom message in details
  if (details?.message && typeof details.message === 'string') {
    return details.message;
  }

  // Check for error message in failed transitions
  if (details?.error && typeof details.error === 'string') {
    return details.error;
  }

  // Initial transition
  if (from === null) {
    if (to === 'pending' || to === 'queued') {
      return 'Job created';
    }
    return `Job created as ${getStatusLabel(to)}`;
  }

  // State transitions with meaningful messages
  const transitionMessages: Record<string, Record<string, string>> = {
    pending: {
      running: 'Started processing',
      processing: 'Started processing',
      failed: 'Job failed',
      cancelled: 'Job cancelled',
    },
    queued: {
      running: 'Started processing',
      processing: 'Started processing',
      failed: 'Job failed',
      cancelled: 'Job cancelled',
    },
    running: {
      completed: 'Job completed successfully',
      failed: 'Job failed',
      cancelled: 'Job cancelled',
    },
    processing: {
      completed: 'Job completed successfully',
      failed: 'Job failed',
      cancelled: 'Job cancelled',
    },
  };

  return transitionMessages[from]?.[to] ?? `Changed to ${getStatusLabel(to)}`;
}

// ============================================================================
// Component
// ============================================================================

/**
 * TimelineEntry renders a single state transition in the job history timeline.
 *
 * The component displays:
 * - A status dot colored based on the target status
 * - A formatted timestamp
 * - The status label and transition message
 * - A vertical connector line (unless it's the last entry)
 *
 * @example
 * ```tsx
 * <TimelineEntry
 *   transition={{
 *     from: 'pending',
 *     to: 'running',
 *     at: '2026-01-17T10:30:05Z',
 *     triggered_by: 'worker',
 *     details: null,
 *   }}
 *   isLast={false}
 * />
 * ```
 */
export default function TimelineEntry({
  transition,
  isLast,
  showTriggeredBy = false,
  className,
}: TimelineEntryProps): React.ReactElement {
  const { to, at, triggered_by, details } = transition;
  const timestamp = formatTimestamp(at);
  const statusLabel = getStatusLabel(to);
  const message = getTransitionMessage(transition);

  // Check if there's an error to display
  const errorMessage = details?.error && typeof details.error === 'string' ? details.error : null;

  return (
    <div
      data-testid="timeline-entry"
      className={clsx('relative flex items-start gap-3', className)}
    >
      {/* Status dot and connector line */}
      <div className="relative flex flex-col items-center">
        <StatusDot status={to} size="lg" />
        {!isLast && (
          <div
            data-testid="timeline-connector"
            className="absolute left-1/2 top-4 h-full w-0.5 -translate-x-1/2 bg-gray-700"
            aria-hidden="true"
          />
        )}
      </div>

      {/* Entry content */}
      <div className={clsx('flex-1 pb-4', isLast && 'pb-0')}>
        {/* Timestamp and status */}
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-sm text-gray-400">{timestamp}</span>
          <span className="text-sm font-semibold text-white">{statusLabel}</span>
          {showTriggeredBy && (
            <span data-testid="triggered-by" className="text-xs text-gray-500">
              via {triggered_by}
            </span>
          )}
        </div>

        {/* Message */}
        <p className="mt-0.5 text-sm text-gray-400">{message}</p>

        {/* Error details (if different from message) */}
        {errorMessage && errorMessage !== message && (
          <p className="mt-1 text-sm text-red-400">{errorMessage}</p>
        )}
      </div>
    </div>
  );
}
