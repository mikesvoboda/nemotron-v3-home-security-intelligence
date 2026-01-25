/**
 * JobMetadata - Displays job metadata including timestamps and type
 *
 * UI Design:
 * ├─────────────────────────────────────────────────────────────────┤
 * │ Started: 2 minutes ago (10:30:00 AM)                            │
 * │ Type: Export | Target: events.csv | Created by: System          │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * NEM-2710
 */

import { clsx } from 'clsx';
import { Clock, AlertCircle } from 'lucide-react';
import { memo } from 'react';

import type { JobResponse } from '../../services/api';

export interface JobMetadataProps {
  /** The job to display metadata for */
  job: JobResponse;
}

/**
 * Format relative time from a date.
 */
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 10) {
    return 'just now';
  }
  if (diffSeconds < 60) {
    return `${diffSeconds} seconds ago`;
  }
  if (diffMinutes < 60) {
    return diffMinutes === 1 ? '1 minute ago' : `${diffMinutes} minutes ago`;
  }
  if (diffHours < 24) {
    return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
  }
  return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;
}

/**
 * Format absolute time for display.
 */
function formatAbsoluteTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
}

/**
 * Format duration between two timestamps.
 */
function formatDuration(startString: string, endString: string): string {
  const start = new Date(startString);
  const end = new Date(endString);
  const diffMs = end.getTime() - start.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);

  if (diffMinutes < 1) {
    return `${diffSeconds} seconds`;
  }
  if (diffHours < 1) {
    return diffMinutes === 1 ? '1 minute' : `${diffMinutes} minutes`;
  }
  const remainingMinutes = diffMinutes % 60;
  if (remainingMinutes === 0) {
    return diffHours === 1 ? '1 hour' : `${diffHours} hours`;
  }
  return `${diffHours}h ${remainingMinutes}m`;
}

/**
 * Format job type for display.
 */
function formatJobType(jobType: string): string {
  return jobType.charAt(0).toUpperCase() + jobType.slice(1);
}

interface MetadataItemProps {
  label: string;
  children: React.ReactNode;
  testId?: string;
  className?: string;
}

function MetadataItem({ label, children, testId, className }: MetadataItemProps) {
  return (
    <div
      data-testid={testId || `metadata-item-${label.toLowerCase()}`}
      className={clsx('flex items-center gap-2 text-sm', className)}
    >
      <span className="text-gray-500">{label}:</span>
      <span className="text-gray-300">{children}</span>
    </div>
  );
}

/**
 * JobMetadata displays job timestamps, type, and other metadata.
 *
 * @param props - Component props
 * @returns Metadata section for job detail panel
 *
 * @example
 * <JobMetadata job={{
 *   job_type: 'export',
 *   status: 'running',
 *   created_at: '2024-01-15T10:28:00Z',
 *   started_at: '2024-01-15T10:30:00Z',
 *   completed_at: null,
 *   message: 'Processing events',
 *   error: null,
 *   ...
 * }} />
 */
const JobMetadata = memo(function JobMetadata({ job }: JobMetadataProps) {
  const { job_type, status, created_at, started_at, completed_at, message, error } = job;

  const isCompleted = status === 'completed' || status === 'failed';
  const showDuration = isCompleted && started_at && completed_at;

  return (
    <div data-testid="job-metadata" className="space-y-3 border-b border-gray-800 py-4">
      {/* Type */}
      <MetadataItem label="Type">
        <span data-testid="job-type">{formatJobType(job_type)}</span>
      </MetadataItem>

      {/* Created */}
      <MetadataItem label="Created">
        <Clock className="h-3.5 w-3.5 text-gray-500" />
        <span>
          {formatRelativeTime(created_at)} ({formatAbsoluteTime(created_at)})
        </span>
      </MetadataItem>

      {/* Started */}
      <MetadataItem label="Started">
        {started_at ? (
          <>
            <span>{formatRelativeTime(started_at)}</span>
            <span className="text-gray-500">({formatAbsoluteTime(started_at)})</span>
          </>
        ) : (
          <span className="italic text-gray-500">Not started</span>
        )}
      </MetadataItem>

      {/* Completed */}
      {isCompleted && completed_at && (
        <MetadataItem label="Completed" testId="metadata-item-completed">
          <span>{formatRelativeTime(completed_at)}</span>
          <span className="text-gray-500">({formatAbsoluteTime(completed_at)})</span>
        </MetadataItem>
      )}

      {/* Duration */}
      {showDuration && (
        <MetadataItem label="Duration">
          <span>{formatDuration(started_at, completed_at)}</span>
        </MetadataItem>
      )}

      {/* Message */}
      {message && (
        <div data-testid="message-section" className="pt-2">
          <MetadataItem label="Status">
            <span>{message}</span>
          </MetadataItem>
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          data-testid="error-section"
          className="mt-3 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-red-400"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="text-sm font-medium">Error</span>
          </div>
          <p className="mt-1 text-sm text-red-300">{error}</p>
        </div>
      )}
    </div>
  );
});

export default JobMetadata;
