/**
 * StatusDot - Visual indicator for job status in timeline
 *
 * Displays a colored dot based on job status following the design spec:
 * - pending/queued: Gray outline (ring)
 * - processing/running: Blue pulsing
 * - completed: Green filled
 * - failed: Red filled
 * - cancelled: Yellow filled
 *
 * @module components/jobs/StatusDot
 */

import { clsx } from 'clsx';

import type React from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Recognized job statuses for styling
 */
export type JobStatus =
  | 'pending'
  | 'queued'
  | 'processing'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

/**
 * Props for the StatusDot component
 */
export interface StatusDotProps {
  /** The job status to display */
  status: string;
  /** Optional additional CSS classes */
  className?: string;
  /** Size variant */
  size?: 'sm' | 'lg';
}

// ============================================================================
// Status Configuration
// ============================================================================

/**
 * Map of status to Tailwind color classes
 */
const statusColors: Record<JobStatus, string> = {
  pending: 'bg-gray-400',
  queued: 'bg-gray-400',
  processing: 'bg-blue-500',
  running: 'bg-blue-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  cancelled: 'bg-yellow-500',
};

/**
 * Statuses that represent pending/waiting states (show as outline)
 */
const pendingStatuses = new Set<string>(['pending', 'queued']);

/**
 * Statuses that represent active processing (show animation)
 */
const processingStatuses = new Set<string>(['processing', 'running']);

/**
 * Statuses that represent final states (filled dot)
 */
const finalStatuses = new Set<string>(['completed', 'failed', 'cancelled']);

// ============================================================================
// Component
// ============================================================================

/**
 * StatusDot renders a colored dot indicating job status.
 *
 * The dot style varies based on status:
 * - Pending states: Gray ring outline
 * - Processing states: Blue pulsing dot
 * - Final states: Filled colored dot
 *
 * @example
 * ```tsx
 * <StatusDot status="completed" />
 * <StatusDot status="processing" size="lg" />
 * ```
 */
export default function StatusDot({
  status,
  className,
  size = 'sm',
}: StatusDotProps): React.ReactElement {
  // Determine the color class
  const colorClass = statusColors[status as JobStatus] ?? 'bg-gray-400';

  // Determine the dot style
  const isPending = pendingStatuses.has(status);
  const isProcessing = processingStatuses.has(status);
  const isFinal = finalStatuses.has(status);

  // Size classes
  const sizeClasses = size === 'lg' ? 'h-4 w-4' : 'h-3 w-3';

  return (
    <span
      data-testid="status-dot"
      role="img"
      aria-label={`Status: ${status}`}
      className={clsx(
        'inline-block rounded-full flex-shrink-0',
        sizeClasses,
        colorClass,
        {
          // Pending states: ring outline style
          'ring-2 ring-current bg-transparent': isPending,
          // Processing states: pulsing animation
          'animate-pulse': isProcessing,
          // Final states get no extra styling (just filled)
        },
        // Don't apply ring for final or processing states
        !isPending && !isFinal && !isProcessing && 'ring-2 ring-current bg-transparent',
        className
      )}
    />
  );
}
