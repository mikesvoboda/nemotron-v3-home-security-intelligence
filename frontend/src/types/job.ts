/**
 * Job Types - Extended types for job tracking and display
 *
 * These types supplement the generated API types with frontend-specific
 * type definitions and utilities for job management.
 *
 * @module types/job
 * @see NEM-3593
 */

import type {
  JobResponse,
  JobDetailResponse,
  JobStatusEnum,
  components,
} from './generated';

// Re-export generated types for convenience
export type { JobResponse, JobDetailResponse, JobStatusEnum };

// Extract nested types from components
export type JobRetryInfo = components['schemas']['JobRetryInfo'];
export type JobProgressDetail = components['schemas']['JobProgressDetail'];
export type JobTiming = components['schemas']['JobTiming'];
export type JobMetadata = components['schemas']['JobMetadata'];

/**
 * Full Job type combining list and detail response fields.
 * This is a union type that works for both list items and detail views.
 *
 * Use this when you need a flexible type that can handle both
 * JobResponse (from list endpoints) and JobDetailResponse (from detail endpoint).
 */
export type Job = JobResponse | JobDetailResponse;

/**
 * Job type as displayed in the UI, with normalized field names.
 *
 * This interface provides a consistent structure for job display,
 * mapping from both JobResponse and JobDetailResponse fields.
 */
export interface JobDisplayData {
  /** Unique job identifier */
  id: string;
  /** Type of job (e.g., 'export', 'cleanup', 'backup', 'import') */
  job_type: string;
  /** Current job status */
  status: JobStatusEnum;
  /** Name of the queue this job is assigned to (if available) */
  queue_name?: string | null;
  /** Job priority (0 = highest, 4 = lowest) */
  priority?: number;
  /** ISO timestamp when job was created */
  created_at: string;
  /** ISO timestamp when job started running */
  started_at?: string | null;
  /** ISO timestamp when job finished */
  completed_at?: string | null;
  /** Progress percentage (0-100) */
  progress_percent: number;
  /** Description of current processing step */
  current_step?: string | null;
  /** Job result data (if completed) */
  result?: unknown;
  /** Error message (if failed) */
  error_message?: string | null;
  /** Full error traceback for debugging */
  error_traceback?: string | null;
  /** Current attempt number (for retries) */
  attempt_number?: number;
  /** Maximum number of retry attempts */
  max_attempts?: number;
  /** ISO timestamp for next retry attempt */
  next_retry_at?: string | null;
  /** Human-readable status message */
  message?: string | null;
}

/**
 * Convert a JobResponse to JobDisplayData.
 * JobResponse has simpler fields from the list endpoint.
 */
export function jobResponseToDisplayData(job: JobResponse): JobDisplayData {
  return {
    id: job.job_id,
    job_type: job.job_type,
    status: job.status,
    created_at: job.created_at,
    started_at: job.started_at,
    completed_at: job.completed_at,
    progress_percent: job.progress,
    error_message: job.error,
    result: job.result,
    message: job.message,
  };
}

/**
 * Convert a JobDetailResponse to JobDisplayData.
 * JobDetailResponse has more detailed fields from the detail endpoint.
 */
export function jobDetailToDisplayData(job: JobDetailResponse): JobDisplayData {
  return {
    id: job.id,
    job_type: job.job_type,
    status: job.status,
    queue_name: job.queue_name,
    priority: job.priority,
    created_at: job.timing.created_at,
    started_at: job.timing.started_at,
    completed_at: job.timing.completed_at,
    progress_percent: job.progress.percent,
    current_step: job.progress.current_step,
    error_message: job.error,
    result: job.result,
    attempt_number: job.retry_info.attempt_number,
    max_attempts: job.retry_info.max_attempts,
    next_retry_at: job.retry_info.next_retry_at,
  };
}

/**
 * Type guard to check if a job is a JobDetailResponse.
 */
export function isJobDetailResponse(job: Job): job is JobDetailResponse {
  return 'timing' in job && 'retry_info' in job && 'progress' in job && typeof job.progress === 'object';
}

/**
 * Type guard to check if a job is a JobResponse.
 */
export function isJobResponse(job: Job): job is JobResponse {
  return 'job_id' in job && 'progress' in job && typeof job.progress === 'number';
}

/**
 * Convert any Job type to JobDisplayData.
 */
export function toJobDisplayData(job: Job): JobDisplayData {
  if (isJobDetailResponse(job)) {
    return jobDetailToDisplayData(job);
  }
  return jobResponseToDisplayData(job);
}

/**
 * Check if a job has retry information.
 */
export function hasRetryInfo(job: Job): boolean {
  return isJobDetailResponse(job) && job.retry_info.max_attempts > 1;
}

/**
 * Check if a job can be retried (failed and has remaining attempts).
 */
export function canRetry(job: Job): boolean {
  if (!isJobDetailResponse(job)) return false;
  return (
    job.status === 'failed' && job.retry_info.attempt_number < job.retry_info.max_attempts
  );
}

/**
 * Check if a job has a detailed error traceback.
 * Note: Traceback is only available in JobDetailResponse through the error field.
 */
export function hasErrorTraceback(job: Job): boolean {
  return !!job.error && job.error.includes('\n');
}

/**
 * Format retry info for display.
 */
export function formatRetryInfo(retryInfo: JobRetryInfo): string {
  return `Attempt ${retryInfo.attempt_number} of ${retryInfo.max_attempts}`;
}

/**
 * Get the short error message (first line only).
 */
export function getShortErrorMessage(error: string | null | undefined): string | null {
  if (!error) return null;
  const firstLine = error.split('\n')[0];
  return firstLine.length > 100 ? `${firstLine.substring(0, 100)}...` : firstLine;
}

/**
 * Priority level labels for display.
 */
export const PRIORITY_LABELS: Record<number, string> = {
  0: 'Highest',
  1: 'High',
  2: 'Normal',
  3: 'Low',
  4: 'Lowest',
};

/**
 * Get priority label for a priority value.
 */
export function getPriorityLabel(priority: number): string {
  return PRIORITY_LABELS[priority] ?? `Priority ${priority}`;
}
