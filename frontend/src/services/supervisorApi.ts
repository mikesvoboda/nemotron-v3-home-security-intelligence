/**
 * Supervisor API Client
 *
 * Provides typed fetch wrappers for supervisor worker management endpoints including:
 * - Fetching supervisor status and worker list
 * - Starting, stopping, and restarting workers
 * - Resetting worker restart counts
 * - Fetching restart history
 *
 * @see backend/api/routes/supervisor.py - Backend implementation
 */

import { fetchApi } from './api';

import type {
  RestartHistoryResponse,
  UseRestartHistoryOptions,
} from '../hooks/useRestartHistory';
import type { SupervisorStatus } from '../hooks/useSupervisorStatus';
import type { WorkerControlResponse } from '../hooks/useWorkerActions';


/**
 * Fetch the current supervisor status including all worker statuses.
 *
 * @returns SupervisorStatus containing running state, worker count, and worker details
 * @throws Error on network or server errors
 *
 * @example
 * ```typescript
 * const status = await fetchSupervisorStatus();
 * console.log(`Supervisor running: ${status.running}`);
 * status.workers.forEach(w => console.log(`${w.name}: ${w.status}`));
 * ```
 */
export async function fetchSupervisorStatus(): Promise<SupervisorStatus> {
  return fetchApi<SupervisorStatus>('/api/system/supervisor');
}

/**
 * Start a stopped worker.
 *
 * @param name - The worker name to start
 * @returns WorkerControlResponse with success status and message
 * @throws Error if worker not found or already running
 *
 * @example
 * ```typescript
 * const result = await startWorker('file_watcher');
 * if (result.success) {
 *   console.log(`Worker ${result.worker_name} started`);
 * }
 * ```
 */
export async function startWorker(name: string): Promise<WorkerControlResponse> {
  return fetchApi<WorkerControlResponse>(
    `/api/system/supervisor/workers/${name}/start`,
    { method: 'POST' }
  );
}

/**
 * Stop a running worker.
 *
 * @param name - The worker name to stop
 * @returns WorkerControlResponse with success status and message
 * @throws Error if worker not found or already stopped
 *
 * @example
 * ```typescript
 * const result = await stopWorker('detection_worker');
 * if (result.success) {
 *   console.log(`Worker ${result.worker_name} stopped`);
 * }
 * ```
 */
export async function stopWorker(name: string): Promise<WorkerControlResponse> {
  return fetchApi<WorkerControlResponse>(
    `/api/system/supervisor/workers/${name}/stop`,
    { method: 'POST' }
  );
}

/**
 * Restart a worker (stop and start).
 *
 * @param name - The worker name to restart
 * @returns WorkerControlResponse with success status and message
 * @throws Error if worker not found
 *
 * @example
 * ```typescript
 * const result = await restartWorker('file_watcher');
 * if (result.success) {
 *   console.log(`Worker ${result.worker_name} restarted`);
 * }
 * ```
 */
export async function restartWorker(
  name: string
): Promise<WorkerControlResponse> {
  return fetchApi<WorkerControlResponse>(
    `/api/system/supervisor/workers/${name}/restart`,
    { method: 'POST' }
  );
}

/**
 * Reset the restart count for a failed worker.
 *
 * This allows a failed worker (that has exceeded max restarts) to be
 * restarted again.
 *
 * @param name - The worker name to reset
 * @returns WorkerControlResponse with success status and message
 * @throws Error if worker not found or not in failed state
 *
 * @example
 * ```typescript
 * const result = await resetWorkerRestartCount('detection_worker');
 * if (result.success) {
 *   console.log(`Worker ${result.worker_name} restart count reset`);
 * }
 * ```
 */
export async function resetWorkerRestartCount(
  name: string
): Promise<WorkerControlResponse> {
  return fetchApi<WorkerControlResponse>(
    `/api/system/supervisor/reset/${name}`,
    { method: 'POST' }
  );
}

/**
 * Fetch restart history for workers.
 *
 * @param options - Optional filtering and pagination options
 * @param options.workerName - Filter by specific worker name
 * @param options.limit - Maximum number of items to return
 * @param options.offset - Number of items to skip for pagination
 * @returns RestartHistoryResponse with items and pagination info
 * @throws Error on network or server errors
 *
 * @example
 * ```typescript
 * // Fetch all history
 * const history = await fetchRestartHistory();
 *
 * // Fetch with pagination
 * const page2 = await fetchRestartHistory({ limit: 20, offset: 20 });
 *
 * // Fetch for specific worker
 * const workerHistory = await fetchRestartHistory({ workerName: 'file_watcher' });
 * ```
 */
export async function fetchRestartHistory(
  options?: UseRestartHistoryOptions
): Promise<RestartHistoryResponse> {
  const params = new URLSearchParams();

  if (options?.workerName) {
    params.append('workerName', options.workerName);
  }
  if (options?.limit !== undefined) {
    params.append('limit', String(options.limit));
  }
  if (options?.offset !== undefined) {
    params.append('offset', String(options.offset));
  }

  const queryString = params.toString();
  const endpoint = queryString
    ? `/api/system/supervisor/restart-history?${queryString}`
    : '/api/system/supervisor/restart-history';

  return fetchApi<RestartHistoryResponse>(endpoint);
}
