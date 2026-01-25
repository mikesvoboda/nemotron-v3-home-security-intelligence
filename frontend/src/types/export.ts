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
 * Available export column names.
 */
export type ExportColumnName =
  | 'event_id'
  | 'camera_name'
  | 'started_at'
  | 'ended_at'
  | 'risk_score'
  | 'risk_level'
  | 'summary'
  | 'detection_count'
  | 'reviewed'
  | 'object_types'
  | 'reasoning';

/**
 * Export column definition with field name and display label.
 */
export interface ExportColumnDefinition {
  /** Field name used in the export data */
  field: ExportColumnName;
  /** Human-readable display label */
  label: string;
  /** Description of the column */
  description: string;
}

/**
 * All available export columns with metadata.
 */
export const EXPORT_COLUMNS: ExportColumnDefinition[] = [
  { field: 'event_id', label: 'Event ID', description: 'Unique identifier for the event' },
  { field: 'camera_name', label: 'Camera', description: 'Name of the camera that captured the event' },
  { field: 'started_at', label: 'Started At', description: 'When the event started' },
  { field: 'ended_at', label: 'Ended At', description: 'When the event ended' },
  { field: 'risk_score', label: 'Risk Score', description: 'Numeric risk score (0-100)' },
  { field: 'risk_level', label: 'Risk Level', description: 'Risk level category (low/medium/high/critical)' },
  { field: 'summary', label: 'Summary', description: 'AI-generated summary of the event' },
  { field: 'detection_count', label: 'Detections', description: 'Number of detections in the event' },
  { field: 'reviewed', label: 'Reviewed', description: 'Whether the event has been reviewed' },
  { field: 'object_types', label: 'Object Types', description: 'Types of objects detected' },
  { field: 'reasoning', label: 'Reasoning', description: 'AI reasoning for the risk assessment' },
];

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
  /** List of column field names to include (null for all) */
  columns?: ExportColumnName[] | null;
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
 * Filter parameters used for an export job.
 */
export interface ExportFilterParams {
  /** Camera ID filter */
  camera_id: string | null;
  /** Risk level filter */
  risk_level: string | null;
  /** Start date filter (ISO format) */
  start_date: string | null;
  /** End date filter (ISO format) */
  end_date: string | null;
  /** Reviewed status filter */
  reviewed: boolean | null;
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
  /** Filter parameters used (JSON string, parse with parseFilterParams) */
  filter_params: string | null;
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

/**
 * Parse filter parameters from JSON string.
 */
export function parseFilterParams(filterParams: string | null): ExportFilterParams | null {
  if (!filterParams) return null;
  try {
    return JSON.parse(filterParams) as ExportFilterParams;
  } catch {
    return null;
  }
}

/**
 * Format filter parameters for display.
 */
export function formatFilterParams(filterParams: string | null): string[] {
  const params = parseFilterParams(filterParams);
  if (!params) return [];

  const filters: string[] = [];

  if (params.camera_id) {
    filters.push(`Camera: ${params.camera_id}`);
  }
  if (params.risk_level) {
    filters.push(`Risk: ${params.risk_level}`);
  }
  if (params.start_date) {
    filters.push(`From: ${new Date(params.start_date).toLocaleDateString()}`);
  }
  if (params.end_date) {
    filters.push(`To: ${new Date(params.end_date).toLocaleDateString()}`);
  }
  if (params.reviewed !== null) {
    filters.push(params.reviewed ? 'Reviewed only' : 'Unreviewed only');
  }

  return filters;
}

/**
 * Calculate export job duration in seconds.
 */
export function calculateDuration(startedAt: string | null, completedAt: string | null): number | null {
  if (!startedAt) return null;
  const endTime = completedAt ? new Date(completedAt).getTime() : Date.now();
  const startTime = new Date(startedAt).getTime();
  return Math.round((endTime - startTime) / 1000);
}

/**
 * Format duration for display.
 */
export function formatDuration(seconds: number | null): string {
  if (seconds === null) return '';
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}
