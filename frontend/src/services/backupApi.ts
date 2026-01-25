/**
 * Backup/Restore API Client
 *
 * Provides typed fetch wrappers for backup/restore REST endpoints including:
 * - Backup creation and status monitoring
 * - Backup file download and deletion
 * - Restore from uploaded backup file
 * - Restore job status monitoring
 *
 * @see backend/api/routes/backup.py - Backend implementation
 * @see docs/plans/interfaces/backup-restore-interfaces.md - Interface definitions
 * @see NEM-3566
 */

import type {
  BackupJob,
  BackupJobStartResponse,
  BackupListResponse,
  RestoreJob,
  RestoreJobStartResponse,
} from '../types/backup';

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;
const API_BASE = '/api/backup';

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for Backup API failures.
 * Includes HTTP status code and parsed error data.
 */
export class BackupApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'BackupApiError';
  }
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Build headers with optional API key authentication.
 */
function buildHeaders(contentType?: string): HeadersInit {
  const headers: Record<string, string> = {};
  if (contentType) {
    headers['Content-Type'] = contentType;
  }
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

/**
 * Handle API response with proper error handling.
 * Parses error details from FastAPI response format.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorData: unknown = undefined;

    try {
      const errorBody: unknown = await response.json();
      if (typeof errorBody === 'object' && errorBody !== null && 'detail' in errorBody) {
        errorMessage = String((errorBody as { detail: unknown }).detail);
        errorData = errorBody;
      } else if (typeof errorBody === 'string') {
        errorMessage = errorBody;
      } else {
        errorData = errorBody;
      }
    } catch {
      // If response body is not JSON, use status text
    }

    throw new BackupApiError(response.status, errorMessage, errorData);
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new BackupApiError(response.status, 'Failed to parse response JSON', error);
  }
}

/**
 * Perform a fetch request to the Backup API with error handling.
 *
 * @param endpoint - API endpoint path (relative to /api/backup)
 * @param options - Optional fetch options
 * @returns Parsed JSON response
 */
async function fetchBackupApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${API_BASE}${endpoint}`;

  const fetchOptions: RequestInit = {
    ...options,
    headers: {
      ...buildHeaders('application/json'),
      ...(options?.headers || {}),
    },
  };

  try {
    const response = await fetch(url, fetchOptions);
    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof BackupApiError) {
      throw error;
    }
    throw new BackupApiError(
      0,
      error instanceof Error ? error.message : 'Network request failed'
    );
  }
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Create a new backup job.
 *
 * Initiates a full system backup that runs in the background.
 * Use getBackupJob() to poll for status updates.
 *
 * @returns Response with job ID and initial status
 * @throws BackupApiError on server errors
 *
 * @example
 * ```typescript
 * const { job_id, status, message } = await createBackup();
 * console.log(`Backup job ${job_id} created with status: ${status}`);
 * ```
 */
export async function createBackup(): Promise<BackupJobStartResponse> {
  return fetchBackupApi<BackupJobStartResponse>('', {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

/**
 * List available backups.
 *
 * Returns all backup jobs with their status and download URLs.
 *
 * @returns List of backups with total count
 * @throws BackupApiError on server errors
 *
 * @example
 * ```typescript
 * const { backups, total } = await listBackups();
 * console.log(`Found ${total} backups`);
 * backups.forEach(b => console.log(`${b.id}: ${b.status}`));
 * ```
 */
export async function listBackups(): Promise<BackupListResponse> {
  return fetchBackupApi<BackupListResponse>('');
}

/**
 * Get backup job status.
 *
 * Returns full job details including progress, timing, and result.
 * Use this to poll for status updates during backup creation.
 *
 * @param jobId - Backup job identifier
 * @returns Full job status response
 * @throws BackupApiError if job not found or on server errors
 *
 * @example
 * ```typescript
 * const job = await getBackupJob(jobId);
 * if (job.status === 'completed') {
 *   console.log(`Backup ready: ${job.file_size_bytes} bytes`);
 * } else if (job.status === 'running') {
 *   console.log(`Progress: ${job.progress.progress_percent}%`);
 * }
 * ```
 */
export async function getBackupJob(jobId: string): Promise<BackupJob> {
  return fetchBackupApi<BackupJob>(`/${encodeURIComponent(jobId)}`);
}

/**
 * Get the download URL for a backup file.
 *
 * Returns the URL that can be used to download the backup ZIP file.
 * Note: This is a synchronous function that constructs the URL.
 *
 * @param jobId - Backup job identifier
 * @returns Full download URL
 *
 * @example
 * ```typescript
 * const url = getBackupDownloadUrl(jobId);
 * // Use in an anchor tag or fetch
 * window.location.href = url;
 * ```
 */
export function getBackupDownloadUrl(jobId: string): string {
  return `${BASE_URL}${API_BASE}/${encodeURIComponent(jobId)}/download`;
}

/**
 * Delete a backup file.
 *
 * Permanently removes the backup file from the server.
 *
 * @param jobId - Backup job identifier
 * @throws BackupApiError if backup not found or on server errors
 *
 * @example
 * ```typescript
 * await deleteBackup(jobId);
 * console.log('Backup deleted');
 * ```
 */
export async function deleteBackup(jobId: string): Promise<void> {
  const url = `${BASE_URL}${API_BASE}/${encodeURIComponent(jobId)}`;

  const response = await fetch(url, {
    method: 'DELETE',
    headers: buildHeaders('application/json'),
  });

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorData: unknown = undefined;

    try {
      const errorBody: unknown = await response.json();
      if (typeof errorBody === 'object' && errorBody !== null && 'detail' in errorBody) {
        errorMessage = String((errorBody as { detail: unknown }).detail);
        errorData = errorBody;
      }
    } catch {
      // If response body is not JSON, use status text
    }

    throw new BackupApiError(response.status, errorMessage, errorData);
  }

  // Response may be empty or return { deleted: true }
  // Either way, if we got here the delete was successful
}

/**
 * Start a restore job from an uploaded backup file.
 *
 * Uploads a backup ZIP file and initiates the restore process.
 * The restore runs in the background - use getRestoreJob() to poll for status.
 *
 * @param file - The backup ZIP file to restore from
 * @returns Response with job ID and initial status
 * @throws BackupApiError on validation errors or server errors
 *
 * @example
 * ```typescript
 * const fileInput = document.querySelector('input[type="file"]');
 * const file = fileInput.files[0];
 *
 * const { job_id, status, message } = await startRestore(file);
 * console.log(`Restore job ${job_id} created: ${message}`);
 * ```
 */
export async function startRestore(file: File): Promise<RestoreJobStartResponse> {
  const url = `${BASE_URL}${API_BASE}/restore`;

  const formData = new FormData();
  formData.append('file', file);

  // Note: Don't set Content-Type header - browser will set it automatically
  // with the correct boundary for multipart/form-data
  const headers: Record<string, string> = {};
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
    });

    return handleResponse<RestoreJobStartResponse>(response);
  } catch (error) {
    if (error instanceof BackupApiError) {
      throw error;
    }
    throw new BackupApiError(
      0,
      error instanceof Error ? error.message : 'Network request failed'
    );
  }
}

/**
 * Get restore job status.
 *
 * Returns full job details including progress, timing, and result.
 * Use this to poll for status updates during restore.
 *
 * @param jobId - Restore job identifier
 * @returns Full job status response
 * @throws BackupApiError if job not found or on server errors
 *
 * @example
 * ```typescript
 * const job = await getRestoreJob(jobId);
 * if (job.status === 'completed') {
 *   console.log('Restore complete:', job.items_restored);
 * } else if (job.status === 'restoring') {
 *   console.log(`Progress: ${job.progress.progress_percent}%`);
 * } else if (job.status === 'validating') {
 *   console.log('Validating backup file...');
 * }
 * ```
 */
export async function getRestoreJob(jobId: string): Promise<RestoreJob> {
  return fetchBackupApi<RestoreJob>(`/restore/${encodeURIComponent(jobId)}`);
}
