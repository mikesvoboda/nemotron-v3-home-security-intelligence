/**
 * useDetections - TanStack Query hooks for detection data management
 *
 * This module provides hooks for fetching detection data using TanStack Query:
 * - useDetectionsListQuery: Fetch detections with filtering
 * - useDetectionDetailQuery: Fetch a single detection by ID
 * - useDetectionSearchQuery: Search detections with full-text search
 * - useDetectionLabelsQuery: Fetch available labels with counts
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with automatic cache invalidation
 * - Background refetching
 * - Cursor-based pagination support
 *
 * @module hooks/useDetections
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchDetections,
  fetchDetection,
  searchDetections,
  fetchDetectionLabels,
  type DetectionsListParams,
  type DetectionSearchParams,
  type DetectionSearchResponse,
  type DetectionLabelsResponse,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

import type { Detection, DetectionListResponse } from '../types/generated';

// ============================================================================
// useDetectionsListQuery - Fetch detections with filtering
// ============================================================================

/**
 * Filters for querying detections
 */
export interface DetectionFilters {
  /** Filter by camera ID */
  camera_id?: string;
  /** Filter by object type (e.g., person, car, truck) */
  object_type?: string;
  /** Filter detections after this date (ISO format) */
  start_date?: string;
  /** Filter detections before this date (ISO format) */
  end_date?: string;
  /** Minimum confidence score (0-1) */
  min_confidence?: number;
  /** Filter by labels (NEM-3641). Detections must have ALL specified labels. */
  labels?: string[];
  /** Filter by media type: 'image' or 'video' (NEM-3642) */
  media_type?: 'image' | 'video';
}

/**
 * Options for configuring the useDetectionsListQuery hook
 */
export interface UseDetectionsListQueryOptions {
  /** Filter parameters */
  filters?: DetectionFilters;
  /** Maximum number of results per page */
  limit?: number;
  /** Cursor for pagination */
  cursor?: string;
  /** Whether to enable the query */
  enabled?: boolean;
  /** Refetch interval in milliseconds */
  refetchInterval?: number | false;
  /** Custom stale time in milliseconds */
  staleTime?: number;
}

/**
 * Return type for the useDetectionsListQuery hook
 */
export interface UseDetectionsListQueryReturn {
  /** List of detections */
  detections: Detection[];
  /** Response data including pagination */
  data: DetectionListResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isFetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether there are more results */
  hasMore: boolean;
  /** Cursor for next page */
  nextCursor: string | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch detections with optional filtering.
 */
export function useDetectionsListQuery(
  options: UseDetectionsListQueryOptions = {}
): UseDetectionsListQueryReturn {
  const {
    filters,
    limit = 50,
    cursor,
    enabled = true,
    refetchInterval = false,
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  const queryParams: DetectionsListParams = {
    ...filters,
    limit,
    cursor,
  };

  const query = useQuery({
    queryKey: queryKeys.detections.list({ ...filters, limit, cursor }),
    queryFn: () => fetchDetections(queryParams),
    enabled,
    refetchInterval,
    staleTime,
    retry: 1,
  });

  const detections = useMemo(() => query.data?.items ?? [], [query.data?.items]);

  return {
    detections,
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    hasMore: query.data?.pagination.has_more ?? false,
    nextCursor: query.data?.pagination.next_cursor ?? null,
    refetch: query.refetch,
  };
}

// ============================================================================
// useDetectionDetailQuery - Fetch single detection by ID
// ============================================================================

export interface UseDetectionDetailQueryOptions {
  enabled?: boolean;
  staleTime?: number;
}

export interface UseDetectionDetailQueryReturn {
  data: Detection | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

export function useDetectionDetailQuery(
  detectionId: number | undefined,
  options: UseDetectionDetailQueryOptions = {}
): UseDetectionDetailQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.detections.detail(detectionId ?? 0),
    queryFn: () => {
      if (detectionId === undefined) {
        throw new Error('Detection ID is required');
      }
      return fetchDetection(detectionId);
    },
    enabled: enabled && detectionId !== undefined,
    staleTime,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useDetectionSearchQuery - Search detections with full-text search
// ============================================================================

export interface DetectionSearchFilters {
  query: string;
  labels?: string[];
  min_confidence?: number;
  camera_id?: string;
  start_date?: string;
  end_date?: string;
}

export interface UseDetectionSearchQueryOptions {
  params: DetectionSearchFilters;
  limit?: number;
  offset?: number;
  enabled?: boolean;
  staleTime?: number;
}

export interface UseDetectionSearchQueryReturn {
  results: DetectionSearchResponse['results'];
  data: DetectionSearchResponse | undefined;
  isLoading: boolean;
  isFetching: boolean;
  error: Error | null;
  totalCount: number;
  refetch: () => Promise<unknown>;
}

export function useDetectionSearchQuery(
  options: UseDetectionSearchQueryOptions
): UseDetectionSearchQueryReturn {
  const {
    params,
    limit = 50,
    offset = 0,
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  const searchParams: DetectionSearchParams = {
    ...params,
    limit,
    offset,
  };

  const query = useQuery({
    queryKey: queryKeys.detections.search({ ...params, limit, offset }),
    queryFn: () => searchDetections(searchParams),
    enabled: enabled && params.query.length > 0,
    staleTime,
    retry: 1,
  });

  const results = useMemo(() => query.data?.results ?? [], [query.data?.results]);

  return {
    results,
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    totalCount: query.data?.total_count ?? 0,
    refetch: query.refetch,
  };
}

// ============================================================================
// useDetectionLabelsQuery - Fetch available labels with counts
// ============================================================================

export interface UseDetectionLabelsQueryOptions {
  enabled?: boolean;
  staleTime?: number;
}

export interface UseDetectionLabelsQueryReturn {
  labels: DetectionLabelsResponse['labels'];
  data: DetectionLabelsResponse | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

export function useDetectionLabelsQuery(
  options: UseDetectionLabelsQueryOptions = {}
): UseDetectionLabelsQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.detections.labels,
    queryFn: fetchDetectionLabels,
    enabled,
    staleTime,
    retry: 1,
  });

  const labels = useMemo(() => query.data?.labels ?? [], [query.data?.labels]);

  return {
    labels,
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}
