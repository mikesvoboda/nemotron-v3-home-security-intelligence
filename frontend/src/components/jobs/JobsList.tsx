/**
 * JobsList - List of background jobs
 *
 * Displays a scrollable list of jobs with selection support.
 * Uses useDeferredList for performance optimization with large job lists (NEM-3750).
 */

import JobsListItem from './JobsListItem';
import { useDeferredList } from '../../hooks/useDeferredList';

import type { JobResponse } from '../../services/api';

export interface JobsListProps {
  /** List of jobs to display */
  jobs: JobResponse[];
  /** Currently selected job ID */
  selectedJobId?: string | null;
  /** Callback when a job is selected */
  onSelectJob?: (jobId: string) => void;
}

export default function JobsList({ jobs, selectedJobId, onSelectJob }: JobsListProps) {
  // Use deferred list for performance optimization with large job lists (NEM-3750)
  // This prevents UI blocking when rendering/updating large numbers of jobs
  const { deferredItems: deferredJobs, isStale } = useDeferredList({
    items: jobs,
    deferThreshold: 50, // Start deferring at 50+ jobs
  });

  return (
    <div
      data-testid="jobs-list"
      className={`flex-1 overflow-y-auto ${isStale ? 'opacity-70 transition-opacity' : ''}`}
    >
      {deferredJobs.map((job) => (
        <JobsListItem
          key={job.job_id}
          job={job}
          isSelected={selectedJobId === job.job_id}
          onClick={onSelectJob}
        />
      ))}
    </div>
  );
}
