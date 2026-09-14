/**
 * Backup/Restore Types
 *
 * Types for the backup and restore feature, enabling full system backup
 * export and restore functionality.
 *
 * @see backend/api/schemas/backup.py - Backend Pydantic schemas
 * @see docs/plans/interfaces/backup-restore-interfaces.md - Interface definitions
 * @see NEM-3566
 */

// ============================================================================
// Status Enums
// ============================================================================

/**
 * Backup job status values.
 * Matches backend BackupJobStatus enum.
 */
export type BackupJobStatus = 'pending' | 'running' | 'completed' | 'failed';

/**
 * Restore job status values.
 * Matches backend RestoreJobStatus enum.
 */
export type RestoreJobStatus = 'pending' | 'validating' | 'restoring' | 'completed' | 'failed';

// ============================================================================
// Backup Manifest (stored in backup ZIP)
// ============================================================================

/**
 * Information about a single backup content type.
 */
export interface BackupContentInfo {
  /** Number of records */
  count: number;
  /** SHA256 checksum of the JSON file */
  checksum: string;
}

/**
 * Manifest file stored inside backup ZIP.
 * Contains metadata about the backup contents.
 */
export interface BackupManifest {
  /** Unique backup identifier */
  backup_id: string;
  /** Backup format version (e.g., '1.0') */
  version: string;
  /** Backup creation timestamp (ISO 8601 string) */
  created_at: string;
  /** Application version, or null if not recorded */
  app_version: string | null;
  /** Map of content type to info (events, alerts, cameras, etc.) */
  contents: Record<string, BackupContentInfo>;
}

// ============================================================================
// Backup Job Types
// ============================================================================

/**
 * Progress information for a backup job.
 */
export interface BackupJobProgress {
  /** Total tables to export */
  total_tables: number;
  /** Tables exported so far */
  completed_tables: number;
  /** Progress percentage (0-100) */
  progress_percent: number;
  /** Current step description, or null if not started */
  current_step: string | null;
}

/**
 * Full status response for a backup job.
 */
export interface BackupJob {
  /** Unique backup job identifier */
  id: string;
  /** Current job status */
  status: BackupJobStatus;
  /** Progress information */
  progress: BackupJobProgress;

  // Timing
  /** Job creation timestamp (ISO 8601 string) */
  created_at: string;
  /** Job start timestamp, or null if not started */
  started_at: string | null;
  /** Job completion timestamp, or null if not completed */
  completed_at: string | null;

  // Result (on completion)
  /** Download path for backup file, or null if not completed */
  file_path: string | null;
  /** Backup file size in bytes, or null if not completed */
  file_size_bytes: number | null;
  /** Backup manifest, or null if not completed */
  manifest: BackupManifest | null;

  // Error (on failure)
  /** Error message if failed, or null otherwise */
  error_message: string | null;
}

/**
 * Summary item for backup list.
 */
export interface BackupListItem {
  /** Backup ID */
  id: string;
  /** Creation timestamp (ISO 8601 string) */
  created_at: string;
  /** File size in bytes */
  file_size_bytes: number;
  /** Job status */
  status: BackupJobStatus;
  /** Download URL if completed, or null otherwise */
  download_url: string | null;
}

/**
 * Response for listing available backups.
 */
export interface BackupListResponse {
  /** List of backup items */
  backups: BackupListItem[];
  /** Total number of backups */
  total: number;
}

// ============================================================================
// Restore Job Types
// ============================================================================

/**
 * Progress information for a restore job.
 */
export interface RestoreJobProgress {
  /** Total tables to restore */
  total_tables: number;
  /** Tables restored so far */
  completed_tables: number;
  /** Progress percentage (0-100) */
  progress_percent: number;
  /** Current step description, or null if not started */
  current_step: string | null;
}

/**
 * Full status response for a restore job.
 */
export interface RestoreJob {
  /** Unique restore job identifier */
  id: string;
  /** Current job status */
  status: RestoreJobStatus;
  /** Progress information */
  progress: RestoreJobProgress;

  // Source backup info
  /** Source backup ID from manifest, or null if not yet parsed */
  backup_id: string | null;
  /** When source backup was created, or null if not yet parsed */
  backup_created_at: string | null;

  // Timing
  /** Job creation timestamp (ISO 8601 string) */
  created_at: string;
  /** Job start timestamp, or null if not started */
  started_at: string | null;
  /** Job completion timestamp, or null if not completed */
  completed_at: string | null;

  // Result (on completion)
  /** Count of restored items per table, or null if not completed */
  items_restored: Record<string, number> | null;

  // Error (on failure)
  /** Error message if failed, or null otherwise */
  error_message: string | null;
}

// ============================================================================
// API Request/Response Types
// ============================================================================

/**
 * Response when creating a backup job.
 */
export interface BackupJobStartResponse {
  /** Unique job identifier */
  job_id: string;
  /** Initial status (typically 'pending') */
  status: BackupJobStatus;
  /** Human-readable message */
  message: string;
}

/**
 * Response when starting a restore job.
 */
export interface RestoreJobStartResponse {
  /** Unique restore job identifier */
  job_id: string;
  /** Initial status (typically 'pending') */
  status: RestoreJobStatus;
  /** Human-readable message */
  message: string;
}

/**
 * Response when deleting a backup.
 */
export interface BackupDeleteResponse {
  /** Whether the backup was deleted */
  deleted: boolean;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for BackupJob objects.
 *
 * @example
 * ```ts
 * if (isBackupJob(data)) {
 *   console.log(data.status);
 * }
 * ```
 */
export function isBackupJob(obj: unknown): obj is BackupJob {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'id' in obj &&
    'status' in obj &&
    'progress' in obj &&
    'created_at' in obj
  );
}

/**
 * Type guard for RestoreJob objects.
 *
 * @example
 * ```ts
 * if (isRestoreJob(data)) {
 *   console.log(data.status);
 * }
 * ```
 */
export function isRestoreJob(obj: unknown): obj is RestoreJob {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'id' in obj &&
    'status' in obj &&
    'progress' in obj &&
    'created_at' in obj &&
    'items_restored' in obj
  );
}

// ============================================================================
// Status Helpers
// ============================================================================

/**
 * Check if a backup job is complete (either completed or failed).
 */
export function isBackupJobComplete(job: BackupJob): boolean {
  return job.status === 'completed' || job.status === 'failed';
}

/**
 * Check if a backup job is currently running.
 */
export function isBackupJobRunning(job: BackupJob): boolean {
  return job.status === 'running';
}

/**
 * Check if a backup job is pending.
 */
export function isBackupJobPending(job: BackupJob): boolean {
  return job.status === 'pending';
}

/**
 * Check if a backup job has failed.
 */
export function isBackupJobFailed(job: BackupJob): boolean {
  return job.status === 'failed';
}

/**
 * Check if a restore job is complete (either completed or failed).
 */
export function isRestoreJobComplete(job: RestoreJob): boolean {
  return job.status === 'completed' || job.status === 'failed';
}

/**
 * Check if a restore job is currently in progress (validating or restoring).
 */
export function isRestoreJobInProgress(job: RestoreJob): boolean {
  return job.status === 'validating' || job.status === 'restoring';
}

/**
 * Check if a restore job is pending.
 */
export function isRestoreJobPending(job: RestoreJob): boolean {
  return job.status === 'pending';
}

/**
 * Check if a restore job has failed.
 */
export function isRestoreJobFailed(job: RestoreJob): boolean {
  return job.status === 'failed';
}
