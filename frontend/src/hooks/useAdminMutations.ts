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

import { useMutation, useQueryClient } from '@tanstack/react-query';

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
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: seedCameras,
    onSuccess: () => {
      // Invalidate camera queries to reflect new data
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
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
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: seedEvents,
    onSuccess: () => {
      // Invalidate event and detection queries to reflect new data
      void queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.detections.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.stats });
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
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: clearSeededData,
    onSuccess: () => {
      // Invalidate all data queries after cleanup
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.detections.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.stats });
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.storage });
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
 * const { seedCameras, seedEvents, seedPipelineLatency, clearSeededData } = useAdminMutations();
 *
 * // Seed cameras
 * seedCameras.mutate({ count: 5 });
 *
 * // Clear all data
 * clearSeededData.mutate({ confirm: 'DELETE_ALL_DATA' });
 * ```
 */
export function useAdminMutations() {
  const seedCameras = useSeedCamerasMutation();
  const seedEvents = useSeedEventsMutation();
  const seedPipelineLatency = useSeedPipelineLatencyMutation();
  const clearSeededData = useClearSeededDataMutation();

  return {
    seedCameras,
    seedEvents,
    seedPipelineLatency,
    clearSeededData,
  };
}

// Types are exported directly from their interface definitions above
