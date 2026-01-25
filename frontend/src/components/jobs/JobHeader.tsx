/**
 * JobHeader - Displays job title, status badge, and progress bar
 *
 * UI Design:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │ Export #142                                                     │
 * │ Status: ● Processing (67%)                                      │
 * │ ███████████████████████████░░░░░░░░░░░░░░                       │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * NEM-2710
 */

import { clsx } from 'clsx';
import { memo } from 'react';

import type { JobResponse, JobStatusEnum } from '../../services/api';

export interface JobHeaderProps {
  /** The job to display header for */
  job: JobResponse;
}

/**
 * Get display name for job type.
 */
function formatJobType(jobType: string): string {
  return jobType.charAt(0).toUpperCase() + jobType.slice(1);
}

/**
 * Extract short ID from job_id (e.g., "export-142" -> "#142").
 */
function formatJobId(jobId: string): string {
  // Try to extract numeric portion
  const match = jobId.match(/(\d+)$/);
  if (match) {
    return `#${match[1]}`;
  }
  // Fall back to showing the full ID
  return jobId;
}

/**
 * Get status badge configuration.
 */
function getStatusConfig(status: JobStatusEnum): {
  label: string;
  colorClass: string;
  dotColorClass: string;
  isAnimated: boolean;
} {
  switch (status) {
    case 'running':
      return {
        label: 'Running',
        colorClass: 'text-blue-400 bg-blue-400/10',
        dotColorClass: 'bg-blue-400',
        isAnimated: true,
      };
    case 'completed':
      return {
        label: 'Completed',
        colorClass: 'text-green-400 bg-green-400/10',
        dotColorClass: 'bg-green-400',
        isAnimated: false,
      };
    case 'failed':
      return {
        label: 'Failed',
        colorClass: 'text-red-400 bg-red-400/10',
        dotColorClass: 'bg-red-400',
        isAnimated: false,
      };
    case 'pending':
    default:
      return {
        label: 'Pending',
        colorClass: 'text-gray-400 bg-gray-400/10',
        dotColorClass: 'bg-gray-400',
        isAnimated: false,
      };
  }
}

/**
 * Get progress bar fill color based on status.
 */
function getProgressFillClass(status: JobStatusEnum): string {
  switch (status) {
    case 'completed':
      return 'bg-green-500';
    case 'failed':
      return 'bg-red-500';
    case 'running':
    default:
      return 'bg-blue-500';
  }
}

/**
 * JobHeader displays job identification, status badge, and progress bar.
 *
 * @param props - Component props
 * @returns Header section for job detail panel
 *
 * @example
 * <JobHeader job={{
 *   job_id: 'export-142',
 *   job_type: 'export',
 *   status: 'running',
 *   progress: 67,
 *   ...
 * }} />
 */
const JobHeader = memo(function JobHeader({ job }: JobHeaderProps) {
  const { job_id, job_type, status, progress } = job;
  const statusConfig = getStatusConfig(status);
  const showProgress = status !== 'pending' && progress >= 0;

  return (
    <div className="border-b border-gray-800 pb-4">
      {/* Title */}
      <h2 className="text-xl font-semibold text-white">
        {formatJobType(job_type)} {formatJobId(job_id)}
      </h2>

      {/* Status badge */}
      <div className="mt-2 flex items-center gap-2">
        <span className="text-sm text-gray-400">Status:</span>
        <span
          data-testid="status-badge"
          className={clsx(
            'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-sm font-medium',
            statusConfig.colorClass
          )}
        >
          <span
            data-testid="status-dot"
            className={clsx(
              'h-2 w-2 rounded-full',
              statusConfig.dotColorClass,
              statusConfig.isAnimated && 'animate-pulse'
            )}
          />
          {statusConfig.label}
          {showProgress && ` (${progress}%)`}
        </span>
      </div>

      {/* Progress bar */}
      {showProgress && (
        <div
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Job progress: ${progress}%`}
          className="mt-3 h-2 w-full overflow-hidden rounded-full bg-gray-700"
        >
          <div
            data-testid="progress-fill"
            className={clsx('h-full transition-all duration-300', getProgressFillClass(status))}
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
});

export default JobHeader;
