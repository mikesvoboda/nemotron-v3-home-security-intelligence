/**
 * JobsListItem - Individual job item in the jobs list
 *
 * Displays job summary information including status, type, and progress.
 *
 * Performance optimization: Uses React.memo with custom equality function
 * that ignores callback props (onClick) since those typically have stable
 * behavior even when references change. This prevents unnecessary re-renders
 * when the parent component re-renders.
 *
 * @see NEM-3424 - Standardize React.memo usage with custom equality
 */

import { formatDistanceToNow } from 'date-fns';
import { CheckCircle, Loader2, XCircle, Circle } from 'lucide-react';
import { memo } from 'react';

import type { JobResponse, JobStatusEnum } from '../../services/api';

export interface JobsListItemProps {
  /** Job data to display */
  job: JobResponse;
  /** Whether this job is currently selected */
  isSelected?: boolean;
  /** Callback when job is clicked */
  onClick?: (jobId: string) => void;
}

/**
 * Get status icon based on job status
 */
function getStatusIcon(status: JobStatusEnum) {
  switch (status) {
    case 'running':
      return <Loader2 className="h-4 w-4 animate-spin text-blue-400" />;
    case 'completed':
      return <CheckCircle className="h-4 w-4 text-green-400" />;
    case 'failed':
      return <XCircle className="h-4 w-4 text-red-400" />;
    case 'pending':
    default:
      return <Circle className="h-4 w-4 text-gray-400" />;
  }
}

/**
 * Get status text color based on job status
 */
function getStatusColor(status: JobStatusEnum): string {
  switch (status) {
    case 'running':
      return 'text-blue-400';
    case 'completed':
      return 'text-green-400';
    case 'failed':
      return 'text-red-400';
    case 'pending':
    default:
      return 'text-gray-400';
  }
}

/**
 * Format job type for display
 */
function formatJobType(jobType: string): string {
  return jobType.charAt(0).toUpperCase() + jobType.slice(1);
}

/**
 * Custom equality function for JobsListItem props.
 *
 * Compares job data properties that affect rendering while ignoring
 * callback props that typically have stable behavior.
 *
 * This is more specific than listItemPropsComparator because we need
 * to handle the nested `job` object.
 */
function jobsListItemPropsAreEqual(
  prevProps: JobsListItemProps,
  nextProps: JobsListItemProps
): boolean {
  // Compare isSelected directly
  if (prevProps.isSelected !== nextProps.isSelected) {
    return false;
  }

  // Compare job object properties that affect rendering
  const prevJob = prevProps.job;
  const nextJob = nextProps.job;

  return (
    prevJob.job_id === nextJob.job_id &&
    prevJob.status === nextJob.status &&
    prevJob.job_type === nextJob.job_type &&
    prevJob.progress === nextJob.progress &&
    prevJob.message === nextJob.message &&
    prevJob.created_at === nextJob.created_at
  );
  // Note: onClick is intentionally ignored - it may have a new reference
  // on each parent render but the behavior is typically stable
}

const JobsListItem = memo(function JobsListItem({
  job,
  isSelected = false,
  onClick,
}: JobsListItemProps) {
  const handleClick = () => {
    onClick?.(job.job_id);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick?.(job.job_id);
    }
  };

  const timeAgo = formatDistanceToNow(new Date(job.created_at), { addSuffix: true });

  return (
    <div
      data-testid={`job-item-${job.job_id}`}
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={`cursor-pointer border-b border-gray-800 p-4 transition-colors hover:bg-gray-800/50 ${
        isSelected ? 'border-l-2 border-l-[#76B900] bg-[#76B900]/10' : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          {getStatusIcon(job.status)}
          <span className={`text-sm font-medium capitalize ${getStatusColor(job.status)}`}>
            {job.status}
          </span>
        </div>
        <span className="text-xs text-gray-500">{timeAgo}</span>
      </div>

      <div className="mt-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">{formatJobType(job.job_type)}</span>
          <span className="text-xs text-gray-500">#{job.job_id.slice(-6)}</span>
        </div>
        {job.message && <p className="mt-1 truncate text-xs text-gray-400">{job.message}</p>}
      </div>

      {/* Progress bar for running jobs */}
      {job.status === 'running' && job.progress > 0 && (
        <div className="mt-2">
          <div className="h-1 w-full overflow-hidden rounded-full bg-gray-700">
            <div
              className="h-full bg-blue-400 transition-all duration-300"
              style={{ width: `${job.progress}%` }}
            />
          </div>
          <span className="mt-1 text-xs text-gray-500">{job.progress}%</span>
        </div>
      )}
    </div>
  );
}, jobsListItemPropsAreEqual);

export default JobsListItem;
