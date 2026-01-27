/**
 * useAdminMutations - React Query mutations for admin seed/cleanup operations
 *
 * Provides mutations for the Developer Tools page to seed test data
 * and cleanup seeded data.
 *
 * Endpoints:
 * - POST /api/admin/seed/cameras - Seed test cameras
 * - POST /api/admin/seed/events - Seed test events
 * - POST /api/admin/seed/pipeline-latency - Seed pipeline latency data
 * - DELETE /api/admin/seed/clear - Clear all seeded data
 *
 * @module hooks/useAdminMutations
 */

import { useMutation } from '@tanstack/react-query';

import { queryKeys } from '../services/queryClient';

// ============================================================================
// Type Definitions (matching backend schemas)
// ============================================================================

/**
 * Request schema for seeding cameras
 */
export interface SeedCamerasRequest {
  /** Number of cameras to create (1-6) */
  count: number;
  /** Remove existing cameras first */
  clear_existing?: boolean;
  /** Create camera folders on filesystem */
  create_folders?: boolean;
}

/**
 * Response schema for seed cameras endpoint
 */
export interface SeedCamerasResponse {
  /** Created cameras */
  cameras: Record<string, unknown>[];
  /** Number of cameras cleared */
  cleared: number;
  /** Number of cameras created */
  created: number;
}

/**
 * Request schema for seeding events
 */
export interface SeedEventsRequest {
  /** Number of events to create (1-100) */
  count: number;
  /** Remove existing events and detections */
  clear_existing?: boolean;
}

/**
 * Response schema for seed events endpoint
 */
export interface SeedEventsResponse {
  /** Number of detections cleared */
  detections_cleared: number;
  /** Number of detections created */
  detections_created: number;
  /** Number of events cleared */
  events_cleared: number;
  /** Number of events created */
  events_created: number;
}

/**
 * Request schema for seeding pipeline latency data
 */
export interface SeedPipelineLatencyRequest {
  /** Number of latency samples to generate per stage (10-1000) */
  num_samples?: number;
  /** Time span in hours for the generated samples (1-168) */
  time_span_hours?: number;
}

/**
 * Response schema for seed pipeline latency endpoint
 */
export interface SeedPipelineLatencyResponse {
  /** Success message */
  message: string;
  /** Number of samples generated per stage */
  samples_per_stage: number;
  /** Names of stages that were seeded */
  stages_seeded: string[];
  /** Time span in hours for the generated samples */
  time_span_hours: number;
}

/**
 * Request schema for clearing data - requires confirmation
 */
export interface ClearDataRequest {
  /** Must be exactly 'DELETE_ALL_DATA' to confirm deletion */
  confirm: string;
}

/**
 * Response schema for clear data endpoint
 */
export interface ClearDataResponse {
  /** Number of cameras cleared */
  cameras_cleared: number;
  /** Number of detections cleared */
  detections_cleared: number;
  /** Number of events cleared */
  events_cleared: number;
}

// Re-export with more descriptive names for the UI
export type ClearSeededDataRequest = ClearDataRequest;
export type ClearSeededDataResponse = ClearDataResponse;

/**
 * Request schema for orphan cleanup endpoint
 */
export interface OrphanCleanupRequest {
  /** If True, only report what would be deleted without actually deleting */
  dry_run?: boolean;
  /** Minimum age in hours before a file can be deleted (1-720) */
  min_age_hours?: number;
  /** Maximum gigabytes to delete in one run (0.1-100) */
  max_delete_gb?: number;
}

/**
 * Response schema for orphan cleanup endpoint
 */
export interface OrphanCleanupResponse {
  /** Number of files scanned */
  scanned_files: number;
  /** Number of orphaned files found */
  orphaned_files: number;
  /** Number of files deleted */
  deleted_files: number;
  /** Bytes deleted */
  deleted_bytes: number;
  /** Human-readable bytes deleted */
  deleted_bytes_formatted: string;
  /** Number of failed deletions */
  failed_count: number;
  /** List of failed file paths */
  failed_deletions: string[];
  /** Duration in seconds */
  duration_seconds: number;
  /** Whether this was a dry run */
  dry_run: boolean;
  /** Files skipped due to being too young */
  skipped_young: number;
  /** Files skipped due to size limit */
  skipped_size_limit: number;
}

/**
 * Response schema for cache clear endpoint
 */
export interface ClearCacheResponse {
  /** Number of cache keys cleared */
  keys_cleared: number;
  /** Cache types that were cleared */
  cache_types: string[];
  /** Duration in seconds */
  duration_seconds: number;
  /** Summary message */
  message: string;
}

/**
 * Response schema for queue flush endpoint
 */
export interface FlushQueuesResponse {
  /** Names of queues that were flushed */
  queues_flushed: string[];
  /** Items cleared per queue */
  items_cleared: Record<string, number>;
  /** Duration in seconds */
  duration_seconds: number;
  /** Summary message */
  message: string;
}

// ============================================================================
// API Functions
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

/**
 * Build headers for API requests
 */
function buildHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

/**
 * Handle API response and extract error message on failure
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorBody = (await response.json()) as { detail?: string };
      if (errorBody.detail) {
        errorMessage = errorBody.detail;
      }
    } catch {
      // Use default error message if JSON parsing fails
    }
    throw new Error(errorMessage);
  }
  return response.json() as Promise<T>;
}

/**
 * Seed test cameras into the database
 */
async function seedCameras(params: SeedCamerasRequest): Promise<SeedCamerasResponse> {
  const response = await fetch(`${BASE_URL}/api/admin/seed/cameras`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(params),
  });
  return handleResponse<SeedCamerasResponse>(response);
}

/**
 * Seed test events into the database
 */
async function seedEvents(params: SeedEventsRequest): Promise<SeedEventsResponse> {
  const response = await fetch(`${BASE_URL}/api/admin/seed/events`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(params),
  });
  return handleResponse<SeedEventsResponse>(response);
}

/**
 * Seed pipeline latency data
 */
async function seedPipelineLatency(
  params: SeedPipelineLatencyRequest
): Promise<SeedPipelineLatencyResponse> {
  const response = await fetch(`${BASE_URL}/api/admin/seed/pipeline-latency`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(params),
  });
  return handleResponse<SeedPipelineLatencyResponse>(response);
}

/**
 * Clear all seeded data (requires confirmation)
 */
async function clearSeededData(params: ClearDataRequest): Promise<ClearDataResponse> {
  const response = await fetch(`${BASE_URL}/api/admin/seed/clear`, {
    method: 'DELETE',
    headers: buildHeaders(),
    body: JSON.stringify(params),
  });
  return handleResponse<ClearDataResponse>(response);
}

/**
 * Run orphan cleanup to find and delete orphaned files
 */
async function runOrphanCleanup(params: OrphanCleanupRequest): Promise<OrphanCleanupResponse> {
  const response = await fetch(`${BASE_URL}/api/admin/cleanup/orphans`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(params),
  });
  return handleResponse<OrphanCleanupResponse>(response);
}

/**
 * Clear all cached data from Redis
 */
async function clearCache(): Promise<ClearCacheResponse> {
  const response = await fetch(`${BASE_URL}/api/admin/maintenance/clear-cache`, {
    method: 'POST',
    headers: buildHeaders(),
  });
  return handleResponse<ClearCacheResponse>(response);
}

/**
 * Flush all processing queues in Redis
 */
async function flushQueues(): Promise<FlushQueuesResponse> {
  const response = await fetch(`${BASE_URL}/api/admin/maintenance/flush-queues`, {
    method: 'POST',
    headers: buildHeaders(),
  });
  return handleResponse<FlushQueuesResponse>(response);
}

// ============================================================================
// Mutation Hooks
// ============================================================================

/**
 * Mutation hook for seeding test cameras
 *
 * @example
 * ```tsx
 * const { mutate, isLoading, error } = useSeedCamerasMutation();
 * mutate({ count: 5, clear_existing: false });
 * ```
 */
export function useSeedCamerasMutation() {
  return useMutation({
    mutationFn: seedCameras,
    onSuccess: (_data, _variables, _context, { client }) => {
      // Invalidate camera queries to reflect new data
      void client.invalidateQueries({ queryKey: queryKeys.cameras.all });
    },
  });
}

/**
 * Mutation hook for seeding test events
 *
 * @example
 * ```tsx
 * const { mutate, isLoading, error } = useSeedEventsMutation();
 * mutate({ count: 100, clear_existing: false });
 * ```
 */
export function useSeedEventsMutation() {
  return useMutation({
    mutationFn: seedEvents,
    onSuccess: (_data, _variables, _context, { client }) => {
      // Invalidate event and detection queries to reflect new data
      void client.invalidateQueries({ queryKey: queryKeys.events.all });
      void client.invalidateQueries({ queryKey: queryKeys.detections.all });
      void client.invalidateQueries({ queryKey: queryKeys.system.stats });
    },
  });
}

/**
 * Mutation hook for seeding pipeline latency data
 *
 * @example
 * ```tsx
 * const { mutate, isLoading, error } = useSeedPipelineLatencyMutation();
 * mutate({ num_samples: 100, time_span_hours: 24 });
 * ```
 */
export function useSeedPipelineLatencyMutation() {
  return useMutation({
    mutationFn: seedPipelineLatency,
    // Pipeline latency is stored in memory, no queries to invalidate
  });
}

/**
 * Mutation hook for clearing all seeded data
 *
 * DANGER: This permanently deletes data. Requires confirmation string.
 *
 * @example
 * ```tsx
 * const { mutate, isLoading, error } = useClearSeededDataMutation();
 * mutate({ confirm: 'DELETE_ALL_DATA' });
 * ```
 */
export function useClearSeededDataMutation() {
  return useMutation({
    mutationFn: clearSeededData,
    onSuccess: (_data, _variables, _context, { client }) => {
      // Invalidate all data queries after cleanup
      void client.invalidateQueries({ queryKey: queryKeys.cameras.all });
      void client.invalidateQueries({ queryKey: queryKeys.events.all });
      void client.invalidateQueries({ queryKey: queryKeys.detections.all });
      void client.invalidateQueries({ queryKey: queryKeys.system.stats });
      void client.invalidateQueries({ queryKey: queryKeys.system.storage });
    },
  });
}

/**
 * Mutation hook for running orphan cleanup
 *
 * @example
 * ```tsx
 * const { mutate, isPending, error } = useOrphanCleanupMutation();
 * mutate({ dry_run: false, min_age_hours: 24 });
 * ```
 */
export function useOrphanCleanupMutation() {
  return useMutation({
    mutationFn: runOrphanCleanup,
    onSuccess: (_data, _variables, _context, { client }) => {
      // Invalidate storage stats after cleanup
      void client.invalidateQueries({ queryKey: queryKeys.system.storage });
    },
  });
}

/**
 * Mutation hook for clearing all cached data
 *
 * @example
 * ```tsx
 * const { mutate, isPending, error } = useClearCacheMutation();
 * mutate();
 * ```
 */
export function useClearCacheMutation() {
  return useMutation({
    mutationFn: clearCache,
    onSuccess: (_data, _variables, _context, { client }) => {
      // Invalidate all queries to refetch fresh data
      void client.invalidateQueries();
    },
  });
}

/**
 * Mutation hook for flushing all processing queues
 *
 * @example
 * ```tsx
 * const { mutate, isPending, error } = useFlushQueuesMutation();
 * mutate();
 * ```
 */
export function useFlushQueuesMutation() {
  return useMutation({
    mutationFn: flushQueues,
    onSuccess: (_data, _variables, _context, { client }) => {
      // Invalidate system stats after queue flush
      void client.invalidateQueries({ queryKey: queryKeys.system.stats });
    },
  });
}

// ============================================================================
// Combined Hook
// ============================================================================

/**
 * Combined hook returning all admin mutations
 *
 * Provides a convenient way to access all admin mutation hooks in one call.
 *
 * @example
 * ```tsx
 * const { seedCameras, seedEvents, seedPipelineLatency, clearSeededData, orphanCleanup, clearCache, flushQueues } = useAdminMutations();
 *
 * // Seed cameras
 * seedCameras.mutate({ count: 5 });
 *
 * // Clear all data
 * clearSeededData.mutate({ confirm: 'DELETE_ALL_DATA' });
 *
 * // Maintenance operations
 * orphanCleanup.mutate({ dry_run: false });
 * clearCache.mutate();
 * flushQueues.mutate();
 * ```
 */
export function useAdminMutations() {
  const seedCameras = useSeedCamerasMutation();
  const seedEvents = useSeedEventsMutation();
  const seedPipelineLatency = useSeedPipelineLatencyMutation();
  const clearSeededData = useClearSeededDataMutation();
  const orphanCleanup = useOrphanCleanupMutation();
  const clearCache = useClearCacheMutation();
  const flushQueues = useFlushQueuesMutation();

  return {
    seedCameras,
    seedEvents,
    seedPipelineLatency,
    clearSeededData,
    // Maintenance operations
    orphanCleanup,
    clearCache,
    flushQueues,
  };
}

// Types are exported directly from their interface definitions above
