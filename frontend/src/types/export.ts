/**
 * Export Types
 *
 * Types for export job tracking and progress monitoring.
 * Supports background export jobs with real-time progress updates.
 *
 * @see backend/api/schemas/export.py - Backend Pydantic schemas
 * @see NEM-2385, NEM-2386
 */

// ============================================================================
// Enums
// ============================================================================

/**
 * Export job status values.
 *
 * Represents the lifecycle of an export job:
 * pending -> running -> completed | failed
 */
export type ExportJobStatus = 'pending' | 'running' | 'completed' | 'failed';

/**
 * Types of data exports available.
 */
export type ExportType = 'events' | 'alerts' | 'full_backup';

/**
 * Supported export file formats.
 */
export type ExportFormat = 'csv' | 'json' | 'zip' | 'excel';

// ============================================================================
// Request Types
// ============================================================================

/**
 * Parameters for creating a new export job.
 */
export interface ExportJobCreateParams {
  /** Type of data to export */
  export_type?: ExportType;
  /** Output file format */
  export_format?: ExportFormat;
  /** Filter by camera ID */
  camera_id?: string | null;
  /** Filter by risk level */
  risk_level?: string | null;
  /** Filter events starting from this date (ISO format) */
  start_date?: string | null;
  /** Filter events ending before this date (ISO format) */
  end_date?: string | null;
  /** Filter by reviewed status */
  reviewed?: boolean | null;
}

// ============================================================================
// Response Types
// ============================================================================

/**
 * Response when starting a new export job.
 */
export interface ExportJobStartResponse {
  /** Unique job identifier for tracking progress */
  job_id: string;
  /** Initial job status (always pending) */
  status: ExportJobStatus;
  /** Human-readable status message */
  message: string;
}

/**
 * Progress information for an export job.
 */
export interface ExportJobProgress {
  /** Total items to process (null if unknown) */
  total_items: number | null;
  /** Number of items processed so far */
  processed_items: number;
  /** Progress percentage (0-100) */
  progress_percent: number;
  /** Current processing step description */
  current_step: string | null;
  /** Estimated completion time (ISO format) */
  estimated_completion: string | null;
}

/**
 * Result information for a completed export.
 */
export interface ExportJobResult {
  /** Download path for the exported file */
  output_path: string | null;
  /** File size in bytes */
  output_size_bytes: number | null;
  /** Number of records exported */
  event_count: number;
  /** Export format used */
  format: string;
}

/**
 * Full export job response with status, progress, and result.
 */
export interface ExportJob {
  /** Unique export job identifier */
  id: string;
  /** Current job status */
  status: ExportJobStatus;
  /** Type of export */
  export_type: string;
  /** Export file format */
  export_format: string;
  /** Progress information */
  progress: ExportJobProgress;
  /** Job creation timestamp */
  created_at: string;
  /** Job start timestamp */
  started_at: string | null;
  /** Job completion timestamp */
  completed_at: string | null;
  /** Export result (populated when completed) */
  result: ExportJobResult | null;
  /** Error message (populated when failed) */
  error_message: string | null;
}

/**
 * Pagination metadata for list responses.
 */
export interface ExportPaginationMeta {
  /** Total number of items */
  total: number;
  /** Number of items per page */
  limit: number;
  /** Number of items skipped */
  offset: number;
  /** Cursor for next page (optional) */
  cursor: string | null;
  /** Cursor for next page (optional) */
  next_cursor: string | null;
  /** Whether there are more items */
  has_more: boolean;
}

/**
 * Paginated list of export jobs.
 */
export interface ExportJobListResponse {
  /** List of export jobs */
  items: ExportJob[];
  /** Pagination metadata */
  pagination: ExportPaginationMeta;
}

/**
 * Response when cancelling an export job.
 */
export interface ExportJobCancelResponse {
  /** Job ID that was cancelled */
  job_id: string;
  /** New job status after cancellation */
  status: ExportJobStatus;
  /** Cancellation status message */
  message: string;
  /** Whether cancellation was successful */
  cancelled: boolean;
}

/**
 * Export file download metadata.
 */
export interface ExportDownloadInfo {
  /** Whether the file is ready for download */
  ready: boolean;
  /** Exported filename */
  filename: string | null;
  /** MIME type of the file */
  content_type: string | null;
  /** File size in bytes */
  size_bytes: number | null;
  /** URL to download the file */
  download_url: string | null;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Check if an export job is in a terminal state (completed or failed).
 */
export function isExportJobComplete(job: ExportJob): boolean {
  return job.status === 'completed' || job.status === 'failed';
}

/**
 * Check if an export job is currently running.
 */
export function isExportJobRunning(job: ExportJob): boolean {
  return job.status === 'running';
}

/**
 * Check if an export job is pending (waiting to start).
 */
export function isExportJobPending(job: ExportJob): boolean {
  return job.status === 'pending';
}

/**
 * Check if an export job has failed.
 */
export function isExportJobFailed(job: ExportJob): boolean {
  return job.status === 'failed';
}

/**
 * Format bytes to human-readable string.
 */
export function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === 0) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const base = 1024;
  const index = Math.floor(Math.log(bytes) / Math.log(base));
  const size = bytes / Math.pow(base, index);

  return `${size.toFixed(index > 0 ? 1 : 0)} ${units[index]}`;
}

/**
 * Calculate estimated time remaining based on progress.
 */
export function calculateTimeRemaining(
  startedAt: string | null,
  progressPercent: number
): string | null {
  if (!startedAt || progressPercent <= 0 || progressPercent >= 100) {
    return null;
  }

  const elapsed = Date.now() - new Date(startedAt).getTime();
  const estimatedTotal = (elapsed / progressPercent) * 100;
  const remaining = estimatedTotal - elapsed;

  if (remaining <= 0) return null;

  const minutes = Math.ceil(remaining / 60000);
  if (minutes === 1) return '~1 min remaining';
  if (minutes < 60) return `~${minutes} min remaining`;

  const hours = Math.ceil(minutes / 60);
  if (hours === 1) return '~1 hour remaining';
  return `~${hours} hours remaining`;
}
