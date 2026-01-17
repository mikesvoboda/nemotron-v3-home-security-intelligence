/**
 * JobHistoryTimeline - Collapsible job state transition timeline
 *
 * Displays a vertical timeline of all state transitions for a job,
 * wrapped in a collapsible section. Shows a summary badge when collapsed.
 *
 * @module components/jobs/JobHistoryTimeline
 */

import { clsx } from 'clsx';
import { History, AlertCircle } from 'lucide-react';


import StatusDot from './StatusDot';
import TimelineEntry from './TimelineEntry';
import { useJobHistoryQuery } from '../../hooks/useJobHistoryQuery';
import CollapsibleSection from '../system/CollapsibleSection';

import type React from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the JobHistoryTimeline component
 */
export interface JobHistoryTimelineProps {
  /** The job ID to display history for */
  jobId: string;
  /** Whether to start expanded */
  defaultOpen?: boolean;
  /** Optional additional CSS classes */
  className?: string;
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Loading skeleton for the timeline
 */
function TimelineLoading(): React.ReactElement {
  return (
    <div data-testid="timeline-loading" className="animate-pulse space-y-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex items-start gap-3">
          <div className="h-4 w-4 rounded-full bg-gray-700" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-24 rounded bg-gray-700" />
            <div className="h-3 w-40 rounded bg-gray-700" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Empty state when no history exists
 */
function EmptyHistory(): React.ReactElement {
  return (
    <div className="py-4 text-center text-gray-500">
      <History className="mx-auto h-8 w-8 mb-2 opacity-50" />
      <p>No history available for this job.</p>
    </div>
  );
}

/**
 * Error state display
 */
function HistoryError({ error }: { error: Error }): React.ReactElement {
  return (
    <div className="py-4 text-center text-red-400">
      <AlertCircle className="mx-auto h-8 w-8 mb-2" />
      <p>Failed to load job history</p>
      <p className="mt-1 text-sm text-gray-500">{error.message}</p>
    </div>
  );
}

/**
 * Summary badge showing transition count and status
 */
function SummaryBadge({
  transitionCount,
  currentStatus,
}: {
  transitionCount: number;
  currentStatus: string | null;
}): React.ReactElement {
  return (
    <div className="flex items-center gap-2">
      <span className="text-gray-400">{transitionCount} transitions</span>
      {currentStatus && (
        <>
          <span className="text-gray-600">|</span>
          <span className="flex items-center gap-1.5">
            <StatusDot status={currentStatus} size="sm" />
            <span className="capitalize text-gray-400">{currentStatus}</span>
          </span>
        </>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * JobHistoryTimeline displays a collapsible vertical timeline of job state transitions.
 *
 * Features:
 * - Fetches job history using the useJobHistoryQuery hook
 * - Collapsible section with summary badge
 * - Shows all state transitions in chronological order
 * - Handles loading, empty, and error states
 *
 * @example
 * ```tsx
 * <JobHistoryTimeline jobId="142" />
 * <JobHistoryTimeline jobId="142" defaultOpen />
 * ```
 */
export default function JobHistoryTimeline({
  jobId,
  defaultOpen = false,
  className,
}: JobHistoryTimelineProps): React.ReactElement {
  const { transitions, currentStatus, isLoading, isError, error } =
    useJobHistoryQuery(jobId);

  // Render content based on state
  const renderContent = (): React.ReactElement => {
    if (isLoading) {
      return <TimelineLoading />;
    }

    if (isError && error) {
      return <HistoryError error={error} />;
    }

    if (!transitions || transitions.length === 0) {
      return <EmptyHistory />;
    }

    return (
      <div className="space-y-0" data-testid="job-history-timeline">
        {transitions.map((transition, index) => (
          <TimelineEntry
            key={`${transition.at}-${transition.to}`}
            transition={{
              from: transition.from ?? null,
              to: transition.to,
              at: transition.at,
              triggered_by: transition.triggered_by,
              details: transition.details ?? null,
            }}
            isLast={index === transitions.length - 1}
          />
        ))}
      </div>
    );
  };

  return (
    <CollapsibleSection
      title="History"
      icon={<History className="h-5 w-5 text-gray-400" />}
      defaultOpen={defaultOpen}
      summary={
        !isLoading && transitions && transitions.length > 0 ? (
          <SummaryBadge
            transitionCount={transitions.length}
            currentStatus={currentStatus}
          />
        ) : undefined
      }
      className={clsx('border border-gray-800 rounded-lg', className)}
      data-testid="job-history-section"
    >
      {renderContent()}
    </CollapsibleSection>
  );
}
