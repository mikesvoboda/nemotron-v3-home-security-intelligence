/**
 * JobsListItem - Individual job item in the jobs list
 *
 * Displays job summary information including status, type, and progress.
 */

import { formatDistanceToNow } from 'date-fns';
import { CheckCircle, Loader2, XCircle, Circle } from 'lucide-react';

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

export default function JobsListItem({ job, isSelected = false, onClick }: JobsListItemProps) {
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
        isSelected ? 'bg-[#76B900]/10 border-l-2 border-l-[#76B900]' : ''
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
        {job.message && (
          <p className="mt-1 truncate text-xs text-gray-400">{job.message}</p>
        )}
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
}
