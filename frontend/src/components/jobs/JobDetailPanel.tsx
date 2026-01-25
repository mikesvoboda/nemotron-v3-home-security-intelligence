/**
 * JobDetailPanel - Detail panel for a selected job
 *
 * Displays detailed information about a selected job including
 * job header with status and progress, metadata, retry info, and real-time logs.
 *
 * Enhanced to support both JobResponse (basic) and JobDetailResponse (full details)
 * with additional fields like current_step, retry info, queue_name, and priority.
 *
 * UI Design:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │ Export #142                                                     │
 * │ Status: ● Processing (67%)                                      │
 * │ ███████████████████████████░░░░░░░░░░░░░░                       │
 * │ Current Step: Exporting events batch 5 of 10...                 │
 * ├─────────────────────────────────────────────────────────────────┤
 * │ Started: 2 minutes ago (10:30:00 AM)                            │
 * │ Type: Export | Queue: high_priority | Priority: Normal          │
 * │ Retry: Attempt 2 of 3 | Next retry: in 5 minutes                │
 * ├─────────────────────────────────────────────────────────────────┤
 * │ Logs                                            [Auto-scroll ✓] │
 * │ ┌─────────────────────────────────────────────────────────────┐ │
 * │ │ 10:30:00 INFO  Starting export...                           │ │
 * │ │ 10:31:45 WARN  Slow query detected                          │ │
 * │ │ 10:32:00 ERROR Connection timeout                           │ │
 * │ └─────────────────────────────────────────────────────────────┘ │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * NEM-2710, NEM-3593
 */

import { Loader2, FileText, RefreshCw, AlertCircle, ExternalLink } from 'lucide-react';
import { useState } from 'react';

import JobErrorModal from './JobErrorModal';
import JobHeader from './JobHeader';
import JobLogsViewer from './JobLogsViewer';
import JobMetadata from './JobMetadata';
import {
  isJobDetailResponse,
  getPriorityLabel,
  formatRetryInfo,
  hasRetryInfo,
  hasErrorTraceback,
  getShortErrorMessage,
} from '../../types/job';

import type { JobResponse, JobDetailResponse } from '../../services/api';
import type { Job } from '../../types/job';

export interface JobDetailPanelProps {
  /** Selected job to display, or null for placeholder state */
  job: JobResponse | JobDetailResponse | null;
  /** Whether job data is loading */
  isLoading?: boolean;
  /** Whether to show the logs viewer */
  showLogs?: boolean;
}

/**
 * Format relative time from now to a future date.
 */
function formatTimeUntil(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();

  if (diffMs <= 0) return 'now';

  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);

  if (diffMinutes < 1) {
    return `in ${diffSeconds} seconds`;
  }
  if (diffHours < 1) {
    return diffMinutes === 1 ? 'in 1 minute' : `in ${diffMinutes} minutes`;
  }
  return diffHours === 1 ? 'in 1 hour' : `in ${diffHours} hours`;
}

/**
 * Get job ID from either response type.
 */
function getJobId(job: Job): string {
  if (isJobDetailResponse(job)) {
    return job.id;
  }
  return job.job_id;
}

export default function JobDetailPanel({
  job,
  isLoading = false,
  showLogs = true,
}: JobDetailPanelProps) {
  const [isErrorModalOpen, setIsErrorModalOpen] = useState(false);

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

  // Check if we have detailed job info
  const isDetailed = isJobDetailResponse(job);

  // Extract fields based on job type
  const jobId = getJobId(job);
  const currentStep = isDetailed ? job.progress.current_step : null;
  const queueName = isDetailed ? job.queue_name : null;
  const priority = isDetailed ? job.priority : null;
  const retryInfo = isDetailed ? job.retry_info : null;
  const hasRetry = job && hasRetryInfo(job);
  const failedAt = isDetailed ? job.timing.completed_at : job.completed_at;

  // Error info - check if we have a multi-line error (traceback)
  const errorMessage = job.error ?? null;
  const hasTraceback = job && hasErrorTraceback(job);
  const shortError = getShortErrorMessage(errorMessage);

  return (
    <div
      data-testid="job-detail-panel"
      className="flex h-full flex-col overflow-hidden rounded-lg border border-gray-800 bg-[#1F1F1F]"
    >
      {/* Fixed Header Section */}
      <div className="shrink-0 p-6 pb-0">
        {/* Job Header with title, status, progress */}
        <JobHeader job={job} />

        {/* Current Step (if available) */}
        {currentStep && (
          <div data-testid="current-step" className="mt-3 flex items-center gap-2 text-sm">
            <Loader2 className="h-4 w-4 animate-spin text-[#76B900]" />
            <span className="text-gray-400">Current step:</span>
            <span className="text-gray-300">{currentStep}</span>
          </div>
        )}

        {/* Job Metadata with timestamps and details */}
        <JobMetadata job={job} />

        {/* Enhanced Metadata Section (for JobDetailResponse) */}
        {isDetailed && (
          <div
            data-testid="enhanced-metadata"
            className="space-y-2 border-b border-gray-800 py-4 text-sm"
          >
            {/* Queue and Priority */}
            <div className="flex flex-wrap items-center gap-4">
              {queueName && (
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">Queue:</span>
                  <span className="rounded bg-gray-800 px-2 py-0.5 text-xs font-medium text-gray-300">
                    {queueName}
                  </span>
                </div>
              )}
              {priority !== null && (
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">Priority:</span>
                  <span className="text-gray-300">{getPriorityLabel(priority)}</span>
                </div>
              )}
            </div>

            {/* Retry Info */}
            {hasRetry && retryInfo && (
              <div
                data-testid="retry-info"
                className="flex flex-wrap items-center gap-4 rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-3"
              >
                <div className="flex items-center gap-2">
                  <RefreshCw className="h-4 w-4 text-yellow-400" />
                  <span className="text-yellow-400">{formatRetryInfo(retryInfo)}</span>
                </div>
                {retryInfo.next_retry_at && (
                  <div className="text-sm text-yellow-300/80">
                    Next retry: {formatTimeUntil(retryInfo.next_retry_at)}
                  </div>
                )}
                {retryInfo.previous_errors && retryInfo.previous_errors.length > 0 && (
                  <div className="w-full text-sm text-yellow-300/60">
                    Previous errors: {retryInfo.previous_errors.length}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Error Section with View Details button */}
        {errorMessage && (
          <div
            data-testid="error-section"
            className="mt-3 rounded-lg border border-red-500/20 bg-red-500/10 p-4"
          >
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-red-400">Error</span>
                  {hasTraceback && (
                    <button
                      onClick={() => setIsErrorModalOpen(true)}
                      data-testid="view-error-details-button"
                      className="flex items-center gap-1 text-xs text-red-400 transition-colors hover:text-red-300"
                    >
                      View Details
                      <ExternalLink className="h-3 w-3" />
                    </button>
                  )}
                </div>
                <p className="mt-1 text-sm text-red-300">{shortError}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Scrollable Logs Section */}
      {showLogs && (
        <div className="min-h-0 flex-1 p-6 pt-4">
          <JobLogsViewer
            jobId={jobId}
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

      {/* Error Modal */}
      {errorMessage && (
        <JobErrorModal
          isOpen={isErrorModalOpen}
          onClose={() => setIsErrorModalOpen(false)}
          jobId={jobId}
          jobType={job.job_type}
          errorMessage={errorMessage}
          errorTraceback={hasTraceback ? errorMessage : null}
          failedAt={failedAt}
          attemptNumber={retryInfo?.attempt_number}
        />
      )}
    </div>
  );
}
