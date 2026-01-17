/**
 * JobDetailPanel - Detail panel for a selected job
 *
 * Displays detailed information about a selected job including
 * job header with status and progress, metadata, and real-time logs.
 *
 * UI Design:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │ Export #142                                                     │
 * │ Status: ● Processing (67%)                                      │
 * │ ███████████████████████████░░░░░░░░░░░░░░                       │
 * ├─────────────────────────────────────────────────────────────────┤
 * │ Started: 2 minutes ago (10:30:00 AM)                            │
 * │ Type: Export | Target: events.csv | Created by: System          │
 * ├─────────────────────────────────────────────────────────────────┤
 * │ Logs                                            [Auto-scroll ✓] │
 * │ ┌─────────────────────────────────────────────────────────────┐ │
 * │ │ 10:30:00 INFO  Starting export...                           │ │
 * │ │ 10:31:45 WARN  Slow query detected                          │ │
 * │ │ 10:32:00 ERROR Connection timeout                           │ │
 * │ └─────────────────────────────────────────────────────────────┘ │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * NEM-2710
 */

import { Loader2, FileText } from 'lucide-react';

import JobHeader from './JobHeader';
import JobLogsViewer from './JobLogsViewer';
import JobMetadata from './JobMetadata';

import type { JobResponse } from '../../services/api';

export interface JobDetailPanelProps {
  /** Selected job to display, or null for placeholder state */
  job: JobResponse | null;
  /** Whether job data is loading */
  isLoading?: boolean;
  /** Whether to show the logs viewer */
  showLogs?: boolean;
}

export default function JobDetailPanel({
  job,
  isLoading = false,
  showLogs = true,
}: JobDetailPanelProps) {
  // Placeholder state when no job is selected
  if (!job && !isLoading) {
    return (
      <div
        data-testid="job-detail-panel"
        className="flex h-full items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]"
      >
        <div className="text-center">
          <FileText className="mx-auto mb-4 h-12 w-12 text-gray-600" />
          <p className="text-gray-400">Select a job to view details</p>
        </div>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div
        data-testid="job-detail-panel"
        className="flex h-full items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F]"
      >
        <div className="text-center">
          <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin text-[#76B900]" />
          <p className="text-gray-400">Loading job details...</p>
        </div>
      </div>
    );
  }

  if (!job) return null;

  // Determine if logs streaming should be enabled
  const isJobActive = job.status === 'running' || job.status === 'pending';

  return (
    <div
      data-testid="job-detail-panel"
      className="flex h-full flex-col overflow-hidden rounded-lg border border-gray-800 bg-[#1F1F1F]"
    >
      {/* Fixed Header Section */}
      <div className="shrink-0 p-6 pb-0">
        {/* Job Header with title, status, progress */}
        <JobHeader job={job} />

        {/* Job Metadata with timestamps and details */}
        <JobMetadata job={job} />
      </div>

      {/* Scrollable Logs Section */}
      {showLogs && (
        <div className="min-h-0 flex-1 p-6 pt-4">
          <JobLogsViewer
            jobId={job.job_id}
            enabled={isJobActive}
            maxHeight={400}
            className="h-full"
          />
        </div>
      )}

      {/* Result (if completed and has result data) */}
      {job.result !== null && (
        <div className="shrink-0 border-t border-gray-800 p-6">
          <h3 className="mb-2 text-sm font-medium text-gray-400">Result</h3>
          <pre className="max-h-40 overflow-auto rounded-lg bg-gray-800 p-4 text-xs text-gray-300">
            {JSON.stringify(job.result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
