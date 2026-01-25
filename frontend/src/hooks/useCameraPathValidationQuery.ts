/**
 * useCameraPathValidationQuery - TanStack Query hook for camera path validation (NEM-3578)
 *
 * This module provides a hook for fetching camera path validation data using TanStack Query.
 * The path validation endpoint checks all camera folder configurations against the base path
 * and reports issues like missing directories or empty folders.
 *
 * Benefits:
 * - Diagnose "No snapshot available" errors
 * - Validate camera setup before leaving settings
 * - Self-service troubleshooting without server access
 *
 * @module hooks/useCameraPathValidationQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchCameraPathValidation,
  type CameraPathValidationResponse,
  type CameraValidationInfo,
} from '../services/api';
import { queryKeys, STATIC_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useCameraPathValidationQuery hook.
 */
export interface UseCameraPathValidationQueryOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * Path validation data changes rarely, so we use a longer stale time.
   * @default STATIC_STALE_TIME (5 minutes)
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default false
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useCameraPathValidationQuery hook.
 */
export interface UseCameraPathValidationQueryReturn {
  /** Full validation response data, undefined if not yet fetched */
  data: CameraPathValidationResponse | undefined;
  /** List of cameras with valid paths */
  validCameras: CameraValidationInfo[];
  /** List of cameras with validation issues */
  invalidCameras: CameraValidationInfo[];
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether any fetch is in progress (initial or background) */
  isFetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query has errored */
  isError: boolean;
  /** Function to manually trigger a refetch (e.g., after camera config changes) */
  refetch: () => Promise<unknown>;
  /** Total number of cameras validated */
  totalCameras: number;
  /** Number of cameras with valid paths */
  validCount: number;
  /** Number of cameras with validation issues */
  invalidCount: number;
  /** The configured base path for camera folders */
  basePath: string | undefined;
  /** Whether all cameras have valid paths */
  allValid: boolean;
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook to fetch camera path validation results using TanStack Query.
 *
 * Returns validation status for all camera folder paths, identifying
 * cameras with configuration issues like missing directories or empty folders.
 *
 * @param options - Configuration options
 * @returns Camera path validation data and query state
 *
 * @example
 * ```tsx
 * // Basic usage - fetch validation on component mount
 * const {
 *   validCameras,
 *   invalidCameras,
 *   invalidCount,
 *   isLoading,
 *   refetch,
 * } = useCameraPathValidationQuery();
 *
 * if (isLoading) return <Spinner />;
 *
 * if (invalidCount > 0) {
 *   return (
 *     <Alert type="warning">
 *       {invalidCount} camera(s) have path issues:
 *       <ul>
 *         {invalidCameras.map(cam => (
 *           <li key={cam.id}>
 *             {cam.name}: {cam.issues?.join(', ')}
 *           </li>
 *         ))}
 *       </ul>
 *       <button onClick={() => refetch()}>Re-validate</button>
 *     </Alert>
 *   );
 * }
 *
 * return <p>All {validCameras.length} cameras configured correctly!</p>;
 * ```
 *
 * @example
 * ```tsx
 * // Validate on demand (disabled by default)
 * const [shouldValidate, setShouldValidate] = useState(false);
 * const { data, isLoading, refetch } = useCameraPathValidationQuery({
 *   enabled: shouldValidate,
 * });
 *
 * return (
 *   <button
 *     onClick={() => setShouldValidate(true)}
 *     disabled={isLoading}
 *   >
 *     {isLoading ? 'Validating...' : 'Validate Camera Paths'}
 *   </button>
 * );
 * ```
 */
export function useCameraPathValidationQuery(
  options: UseCameraPathValidationQueryOptions = {}
): UseCameraPathValidationQueryReturn {
  const {
    enabled = true,
    staleTime = STATIC_STALE_TIME,
    refetchInterval = false,
  } = options;

  const query = useQuery<CameraPathValidationResponse, Error>({
    queryKey: queryKeys.cameras.pathValidation(),
    queryFn: fetchCameraPathValidation,
    enabled,
    staleTime,
    refetchInterval,
    // Reduced retry since this is a diagnostic endpoint
    retry: 1,
  });

  // Memoize derived values
  const validCameras = useMemo<CameraValidationInfo[]>(
    () => query.data?.valid_cameras ?? [],
    [query.data]
  );

  const invalidCameras = useMemo<CameraValidationInfo[]>(
    () => query.data?.invalid_cameras ?? [],
    [query.data]
  );

  const totalCameras = useMemo(() => query.data?.total_cameras ?? 0, [query.data]);
  const validCount = useMemo(() => query.data?.valid_count ?? 0, [query.data]);
  const invalidCount = useMemo(() => query.data?.invalid_count ?? 0, [query.data]);
  const basePath = useMemo(() => query.data?.base_path, [query.data]);
  const allValid = useMemo(() => invalidCount === 0 && totalCameras > 0, [invalidCount, totalCameras]);

  return {
    data: query.data,
    validCameras,
    invalidCameras,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    totalCameras,
    validCount,
    invalidCount,
    basePath,
    allValid,
  };
}

// Re-export types for convenience
export type { CameraPathValidationResponse, CameraValidationInfo };
