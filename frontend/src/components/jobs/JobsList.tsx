/**
 * JobsList - List of background jobs
 *
 * Displays a scrollable list of jobs with selection support.
 */

import JobsListItem from './JobsListItem';

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
  return (
    <div data-testid="jobs-list" className="flex-1 overflow-y-auto">
      {jobs.map((job) => (
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
