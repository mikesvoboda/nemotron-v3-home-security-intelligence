/**
 * TanStack Query Hooks for Scheduled Report Management
 *
 * This module provides hooks for fetching and mutating scheduled report data
 * using TanStack Query. It includes:
 *
 * Queries:
 * - useScheduledReportsQuery: Fetch list of scheduled reports
 * - useScheduledReportQuery: Fetch single scheduled report by ID
 *
 * Mutations:
 * - useCreateScheduledReportMutation: Create a new scheduled report
 * - useUpdateScheduledReportMutation: Update an existing scheduled report
 * - useDeleteScheduledReportMutation: Delete a scheduled report
 * - useTriggerScheduledReportMutation: Manually trigger a report
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with automatic cache invalidation
 * - Proper error handling
 * - Optimistic updates where appropriate
 *
 * @module hooks/useScheduledReports
 * @see NEM-3667 - Scheduled Reports Frontend UI
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { DEFAULT_STALE_TIME } from '../services/queryClient';
import * as scheduledReportsApi from '../services/scheduledReportsApi';

import type {
  ScheduledReport,
  ScheduledReportCreate,
  ScheduledReportUpdate,
  ScheduledReportListResponse,
  ScheduledReportRunResponse,
} from '../types/scheduledReport';

// Re-export types for convenience
export type {
  ScheduledReport,
  ScheduledReportCreate,
  ScheduledReportUpdate,
  ScheduledReportListResponse,
  ScheduledReportRunResponse,
} from '../types/scheduledReport';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query keys for scheduled report-related queries.
 * Follows the hierarchical pattern for cache invalidation.
 *
 * @example
 * ```typescript
 * // Invalidate all scheduled report queries
 * queryClient.invalidateQueries({ queryKey: SCHEDULED_REPORT_QUERY_KEYS.all });
 *
 * // Invalidate specific scheduled report
 * queryClient.invalidateQueries({ queryKey: SCHEDULED_REPORT_QUERY_KEYS.detail(1) });
 * ```
 */
export const SCHEDULED_REPORT_QUERY_KEYS = {
  /** Base key for all scheduled report queries - use for bulk invalidation */
  all: ['scheduled-reports'] as const,
  /** Scheduled report list */
  list: ['scheduled-reports', 'list'] as const,
  /** Single scheduled report by ID */
  detail: (id: number) => ['scheduled-reports', 'detail', id] as const,
} as const;

// ============================================================================
// useScheduledReportsQuery - Fetch list of scheduled reports
// ============================================================================

/**
 * Options for configuring the useScheduledReportsQuery hook.
 */
export interface UseScheduledReportsQueryOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * @default false
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useScheduledReportsQuery hook.
 */
export interface UseScheduledReportsQueryReturn {
  /** Scheduled report list response data */
  data: ScheduledReportListResponse | undefined;
  /** List of scheduled reports (convenience accessor) */
  reports: ScheduledReport[];
  /** Total scheduled report count */
  total: number;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch list of scheduled reports using TanStack Query.
 *
 * @param options - Configuration options
 * @returns Scheduled report list and query state
 *
 * @example
 * ```tsx
 * const { reports, isLoading, error } = useScheduledReportsQuery();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div>
 *     {reports.map(report => (
 *       <ReportCard key={report.id} report={report} />
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useScheduledReportsQuery(
  options: UseScheduledReportsQueryOptions = {}
): UseScheduledReportsQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, refetchInterval = false } = options;

  const query = useQuery({
    queryKey: SCHEDULED_REPORT_QUERY_KEYS.list,
    queryFn: scheduledReportsApi.listScheduledReports,
    enabled,
    staleTime,
    refetchInterval,
    retry: 1,
  });

  return {
    data: query.data,
    reports: query.data?.items ?? [],
    total: query.data?.total ?? 0,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useScheduledReportQuery - Fetch single scheduled report by ID
// ============================================================================

/**
 * Options for configuring the useScheduledReportQuery hook.
 */
export interface UseScheduledReportQueryOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useScheduledReportQuery hook.
 */
export interface UseScheduledReportQueryReturn {
  /** Scheduled report data */
  data: ScheduledReport | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch a single scheduled report by ID using TanStack Query.
 *
 * @param id - Scheduled report ID
 * @param options - Configuration options
 * @returns Scheduled report data and query state
 *
 * @example
 * ```tsx
 * const { data: report, isLoading } = useScheduledReportQuery(1);
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <div>
 *     <h1>{report?.name}</h1>
 *     <p>Frequency: {report?.frequency}</p>
 *   </div>
 * );
 * ```
 */
export function useScheduledReportQuery(
  id: number,
  options: UseScheduledReportQueryOptions = {}
): UseScheduledReportQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: SCHEDULED_REPORT_QUERY_KEYS.detail(id),
    queryFn: () => scheduledReportsApi.getScheduledReport(id),
    enabled: enabled && id > 0,
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
// useCreateScheduledReportMutation - Create a new scheduled report
// ============================================================================

/**
 * Return type for the useCreateScheduledReportMutation hook.
 */
export interface UseCreateScheduledReportMutationReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<ScheduledReport, Error, ScheduledReportCreate>>;
  /** Convenience method to create scheduled report */
  createReport: (data: ScheduledReportCreate) => Promise<ScheduledReport>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for creating a new scheduled report.
 *
 * Automatically invalidates the scheduled report list query on success.
 *
 * @returns Mutation for creating scheduled report
 *
 * @example
 * ```tsx
 * const { createReport, isLoading, error } = useCreateScheduledReportMutation();
 *
 * const handleSubmit = async (data: ScheduledReportCreate) => {
 *   try {
 *     const report = await createReport(data);
 *     toast.success(`Report "${report.name}" created!`);
 *   } catch (err) {
 *     toast.error(`Failed to create report: ${err.message}`);
 *   }
 * };
 * ```
 */
export function useCreateScheduledReportMutation(): UseCreateScheduledReportMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: scheduledReportsApi.createScheduledReport,
    onSuccess: () => {
      // Invalidate list query to refetch with new report
      void queryClient.invalidateQueries({
        queryKey: SCHEDULED_REPORT_QUERY_KEYS.list,
      });
    },
  });

  return {
    mutation,
    createReport: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useUpdateScheduledReportMutation - Update an existing scheduled report
// ============================================================================

/**
 * Variables for the update scheduled report mutation.
 */
export interface UpdateScheduledReportVariables {
  /** Scheduled report ID to update */
  id: number;
  /** Fields to update */
  data: ScheduledReportUpdate;
}

/**
 * Return type for the useUpdateScheduledReportMutation hook.
 */
export interface UseUpdateScheduledReportMutationReturn {
  /** The mutation object */
  mutation: ReturnType<
    typeof useMutation<ScheduledReport, Error, UpdateScheduledReportVariables>
  >;
  /** Convenience method to update scheduled report */
  updateReport: (id: number, data: ScheduledReportUpdate) => Promise<ScheduledReport>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for updating an existing scheduled report.
 *
 * Automatically invalidates the scheduled report list and detail queries on success.
 *
 * @returns Mutation for updating scheduled report
 *
 * @example
 * ```tsx
 * const { updateReport, isLoading } = useUpdateScheduledReportMutation();
 *
 * const handleSave = async () => {
 *   await updateReport(reportId, {
 *     name: newName,
 *     enabled: false,
 *   });
 *   toast.success('Report updated!');
 * };
 * ```
 */
export function useUpdateScheduledReportMutation(): UseUpdateScheduledReportMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: ({ id, data }: UpdateScheduledReportVariables) =>
      scheduledReportsApi.updateScheduledReport(id, data),
    onSuccess: (updatedReport) => {
      // Invalidate list query
      void queryClient.invalidateQueries({
        queryKey: SCHEDULED_REPORT_QUERY_KEYS.list,
      });
      // Invalidate specific scheduled report detail query
      void queryClient.invalidateQueries({
        queryKey: SCHEDULED_REPORT_QUERY_KEYS.detail(updatedReport.id),
      });
    },
  });

  return {
    mutation,
    updateReport: (id: number, data: ScheduledReportUpdate) =>
      mutation.mutateAsync({ id, data }),
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useDeleteScheduledReportMutation - Delete a scheduled report
// ============================================================================

/**
 * Return type for the useDeleteScheduledReportMutation hook.
 */
export interface UseDeleteScheduledReportMutationReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<void, Error, number>>;
  /** Convenience method to delete scheduled report */
  deleteReport: (id: number) => Promise<void>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for deleting a scheduled report.
 *
 * Automatically invalidates the scheduled report list query on success.
 *
 * @returns Mutation for deleting scheduled report
 *
 * @example
 * ```tsx
 * const { deleteReport, isLoading } = useDeleteScheduledReportMutation();
 *
 * const handleDelete = async () => {
 *   if (confirm('Delete this report?')) {
 *     await deleteReport(reportId);
 *     toast.success('Report deleted');
 *   }
 * };
 * ```
 */
export function useDeleteScheduledReportMutation(): UseDeleteScheduledReportMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: scheduledReportsApi.deleteScheduledReport,
    onSuccess: (_data, reportId) => {
      // Invalidate list query
      void queryClient.invalidateQueries({
        queryKey: SCHEDULED_REPORT_QUERY_KEYS.list,
      });
      // Remove the specific report from cache
      queryClient.removeQueries({
        queryKey: SCHEDULED_REPORT_QUERY_KEYS.detail(reportId),
      });
    },
  });

  return {
    mutation,
    deleteReport: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useTriggerScheduledReportMutation - Manually trigger a report
// ============================================================================

/**
 * Return type for the useTriggerScheduledReportMutation hook.
 */
export interface UseTriggerScheduledReportMutationReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<ScheduledReportRunResponse, Error, number>>;
  /** Convenience method to trigger scheduled report */
  triggerReport: (id: number) => Promise<ScheduledReportRunResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
  /** The trigger result from the last successful trigger */
  data: ScheduledReportRunResponse | undefined;
}

/**
 * Hook providing mutation for manually triggering a scheduled report.
 *
 * Invalidates the scheduled report list to update last_run_at.
 *
 * @returns Mutation for triggering scheduled report
 *
 * @example
 * ```tsx
 * const { triggerReport, isLoading, data } = useTriggerScheduledReportMutation();
 *
 * const handleTrigger = async () => {
 *   const result = await triggerReport(reportId);
 *   toast.success(`Report triggered: ${result.message}`);
 * };
 * ```
 */
export function useTriggerScheduledReportMutation(): UseTriggerScheduledReportMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: scheduledReportsApi.triggerScheduledReport,
    onSuccess: (_data, reportId) => {
      // Invalidate list query to update last_run_at
      void queryClient.invalidateQueries({
        queryKey: SCHEDULED_REPORT_QUERY_KEYS.list,
      });
      // Invalidate specific report detail
      void queryClient.invalidateQueries({
        queryKey: SCHEDULED_REPORT_QUERY_KEYS.detail(reportId),
      });
    },
  });

  return {
    mutation,
    triggerReport: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
    data: mutation.data,
  };
}
