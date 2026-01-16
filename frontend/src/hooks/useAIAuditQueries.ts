/**
 * TanStack Query hooks for AI Audit data management
 *
 * This module provides hooks for fetching and mutating AI audit data using
 * TanStack Query. It includes:
 *
 * Queries:
 * - useAIAuditStats: Fetch aggregate audit statistics
 * - useAIAuditLeaderboard: Fetch model rankings/leaderboard
 * - useAIAuditRecommendations: Fetch prompt improvement recommendations
 * - useAIAuditEventQuery: Fetch audit for specific event
 * - useAIAuditPromptsQuery: Fetch all prompts
 * - useAIAuditPromptHistoryQuery: Fetch prompt version history
 *
 * Mutations:
 * - useEvaluateEventMutation: Trigger evaluation for an event
 * - useBatchAuditMutation: Trigger batch processing
 * - useTestPromptMutation: A/B test prompts
 * - useUpdatePromptMutation: Update a prompt
 * - useImportPromptsMutation: Import prompt configs
 * - useExportPromptsMutation: Export prompt configs
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with automatic cache invalidation
 * - Optimistic updates support
 * - Background refetching
 *
 * @module hooks/useAIAuditQueries
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchAuditStats,
  fetchLeaderboard,
  fetchRecommendations,
  fetchEventAudit,
  triggerEvaluation,
  triggerBatchAudit,
  type AuditStats,
  type LeaderboardResponse,
  type RecommendationsResponse,
  type EventAudit,
  type BatchAuditResponse,
} from '../services/auditApi';
import {
  fetchAllPrompts,
  fetchPromptHistory,
  updatePromptForModel,
  testPrompt,
  importPrompts,
  exportPrompts,
} from '../services/promptManagementApi';
import { queryKeys, DEFAULT_STALE_TIME, STATIC_STALE_TIME } from '../services/queryClient';

import type {
  AIModelEnum,
  AllPromptsResponse,
  PromptHistoryResponse,
  ModelPromptConfig,
  PromptTestRequest,
  PromptTestResult,
  PromptsImportRequest,
  PromptsImportResponse,
  PromptsExportResponse,
  PromptUpdateRequest,
} from '../types/promptManagement';

// ============================================================================
// Query Key Extensions
// ============================================================================

/**
 * Extended query keys for AI audit queries.
 * These extend the base queryKeys from queryClient.ts.
 */
export const aiAuditQueryKeys = {
  /** Base key for all AI audit queries */
  all: ['ai', 'audit'] as const,

  /** Audit statistics */
  stats: (params?: { days?: number; camera_id?: string }) =>
    params
      ? ([...aiAuditQueryKeys.all, 'stats', params] as const)
      : ([...aiAuditQueryKeys.all, 'stats'] as const),

  /** Model leaderboard */
  leaderboard: (params?: { days?: number }) =>
    params
      ? ([...aiAuditQueryKeys.all, 'leaderboard', params] as const)
      : ([...aiAuditQueryKeys.all, 'leaderboard'] as const),

  /** Recommendations */
  recommendations: (params?: { days?: number }) =>
    params
      ? ([...aiAuditQueryKeys.all, 'recommendations', params] as const)
      : ([...aiAuditQueryKeys.all, 'recommendations'] as const),

  /** Event audit */
  event: (eventId: number) => [...aiAuditQueryKeys.all, 'event', eventId] as const,

  /** Prompt management */
  prompts: {
    /** All prompts */
    all: ['ai', 'prompts'] as const,
    /** Prompt history */
    history: (model?: AIModelEnum) =>
      model
        ? (['ai', 'prompts', 'history', model] as const)
        : (['ai', 'prompts', 'history'] as const),
  },
};

// ============================================================================
// useAIAuditStats - Fetch aggregate audit statistics
// ============================================================================

/**
 * Options for configuring the useAIAuditStats hook
 */
export interface UseAIAuditStatsOptions {
  /**
   * Number of days to include in statistics (1-90).
   * @default 7
   */
  days?: number;

  /**
   * Optional camera ID to filter stats.
   */
  cameraId?: string;

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
 * Return type for the useAIAuditStats hook
 */
export interface UseAIAuditStatsReturn {
  /** Audit statistics data */
  data: AuditStats | undefined;
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
 * Hook to fetch aggregate AI audit statistics using TanStack Query.
 *
 * @param options - Configuration options
 * @returns Audit statistics and query state
 *
 * @example
 * ```tsx
 * const { data: stats, isLoading, error } = useAIAuditStats({ days: 7 });
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div>
 *     <p>Total Events: {stats?.total_events}</p>
 *     <p>Avg Quality: {stats?.avg_quality_score}</p>
 *   </div>
 * );
 * ```
 */
export function useAIAuditStats(options: UseAIAuditStatsOptions = {}): UseAIAuditStatsReturn {
  const {
    days,
    cameraId,
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
    refetchInterval = false,
  } = options;

  const queryParams = useMemo(
    () => (days !== undefined || cameraId ? { days, camera_id: cameraId } : undefined),
    [days, cameraId]
  );

  const query = useQuery({
    queryKey: queryKeys.ai.audit.stats(queryParams),
    queryFn: () => fetchAuditStats(days, cameraId),
    enabled,
    staleTime,
    refetchInterval,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useAIAuditLeaderboard - Fetch model rankings/leaderboard
// ============================================================================

/**
 * Options for configuring the useAIAuditLeaderboard hook
 */
export interface UseAIAuditLeaderboardOptions {
  /**
   * Number of days to include (1-90).
   * @default 7
   */
  days?: number;

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
 * Return type for the useAIAuditLeaderboard hook
 */
export interface UseAIAuditLeaderboardReturn {
  /** Leaderboard data */
  data: LeaderboardResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch AI model leaderboard using TanStack Query.
 *
 * @param options - Configuration options
 * @returns Leaderboard data and query state
 *
 * @example
 * ```tsx
 * const { data: leaderboard, isLoading } = useAIAuditLeaderboard({ days: 30 });
 *
 * return (
 *   <ul>
 *     {leaderboard?.entries.map(entry => (
 *       <li key={entry.model_name}>
 *         {entry.model_name}: {(entry.contribution_rate * 100).toFixed(1)}%
 *       </li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useAIAuditLeaderboard(
  options: UseAIAuditLeaderboardOptions = {}
): UseAIAuditLeaderboardReturn {
  const { days, enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const queryParams = useMemo(() => (days !== undefined ? { days } : undefined), [days]);

  const query = useQuery({
    queryKey: queryKeys.ai.audit.leaderboard(queryParams),
    queryFn: () => fetchLeaderboard(days),
    enabled,
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
// useAIAuditRecommendations - Fetch prompt improvement recommendations
// ============================================================================

/**
 * Options for configuring the useAIAuditRecommendations hook
 */
export interface UseAIAuditRecommendationsOptions {
  /**
   * Number of days to analyze (1-90).
   * @default 7
   */
  days?: number;

  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default STATIC_STALE_TIME (5 minutes) - recommendations don't change often
   */
  staleTime?: number;
}

/**
 * Return type for the useAIAuditRecommendations hook
 */
export interface UseAIAuditRecommendationsReturn {
  /** Recommendations data */
  data: RecommendationsResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch AI prompt improvement recommendations using TanStack Query.
 *
 * @param options - Configuration options
 * @returns Recommendations data and query state
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useAIAuditRecommendations({ days: 14 });
 *
 * return (
 *   <ul>
 *     {data?.recommendations.map((rec, i) => (
 *       <li key={i}>
 *         [{rec.priority}] {rec.category}: {rec.suggestion}
 *       </li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useAIAuditRecommendations(
  options: UseAIAuditRecommendationsOptions = {}
): UseAIAuditRecommendationsReturn {
  const { days, enabled = true, staleTime = STATIC_STALE_TIME } = options;

  const queryParams = useMemo(() => (days !== undefined ? { days } : undefined), [days]);

  const query = useQuery({
    queryKey: queryKeys.ai.audit.recommendations(queryParams),
    queryFn: () => fetchRecommendations(days),
    enabled,
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
// useAIAuditEventQuery - Fetch audit for specific event
// ============================================================================

/**
 * Options for configuring the useAIAuditEventQuery hook
 */
export interface UseAIAuditEventQueryOptions {
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
 * Return type for the useAIAuditEventQuery hook
 */
export interface UseAIAuditEventQueryReturn {
  /** Event audit data */
  data: EventAudit | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch audit information for a specific event using TanStack Query.
 *
 * @param eventId - The ID of the event to get audit for, or undefined to disable
 * @param options - Configuration options
 * @returns Event audit data and query state
 *
 * @example
 * ```tsx
 * const { data: audit, isLoading } = useAIAuditEventQuery(eventId);
 *
 * if (!audit) return null;
 *
 * return (
 *   <div>
 *     <p>Quality Score: {audit.scores.overall}</p>
 *     <p>Enrichment Utilization: {(audit.enrichment_utilization * 100).toFixed(1)}%</p>
 *   </div>
 * );
 * ```
 */
export function useAIAuditEventQuery(
  eventId: number | undefined,
  options: UseAIAuditEventQueryOptions = {}
): UseAIAuditEventQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.ai.audit.event(eventId ?? 0),
    queryFn: () => {
      if (eventId === undefined) {
        throw new Error('Event ID is required');
      }
      return fetchEventAudit(eventId);
    },
    enabled: enabled && eventId !== undefined,
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
// useAIAuditPromptsQuery - Fetch all prompts
// ============================================================================

/**
 * Options for configuring the useAIAuditPromptsQuery hook
 */
export interface UseAIAuditPromptsQueryOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default STATIC_STALE_TIME (5 minutes) - prompts don't change often
   */
  staleTime?: number;
}

/**
 * Return type for the useAIAuditPromptsQuery hook
 */
export interface UseAIAuditPromptsQueryReturn {
  /** All prompts data */
  data: AllPromptsResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch all AI prompt configurations using TanStack Query.
 *
 * @param options - Configuration options
 * @returns All prompts data and query state
 *
 * @example
 * ```tsx
 * const { data: prompts, isLoading } = useAIAuditPromptsQuery();
 *
 * return (
 *   <div>
 *     {Object.entries(prompts?.prompts ?? {}).map(([model, config]) => (
 *       <div key={model}>{model}: {JSON.stringify(config)}</div>
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useAIAuditPromptsQuery(
  options: UseAIAuditPromptsQueryOptions = {}
): UseAIAuditPromptsQueryReturn {
  const { enabled = true, staleTime = STATIC_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.ai.prompts.all,
    queryFn: fetchAllPrompts,
    enabled,
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
// useAIAuditPromptHistoryQuery - Fetch prompt version history
// ============================================================================

/**
 * Options for configuring the useAIAuditPromptHistoryQuery hook
 */
export interface UseAIAuditPromptHistoryQueryOptions {
  /**
   * Optional model filter.
   */
  model?: AIModelEnum;

  /**
   * Maximum results to return (1-100).
   * @default 50
   */
  limit?: number;

  /**
   * @deprecated Use cursor parameter instead for better performance with large datasets.
   * Offset for pagination.
   * @default 0
   */
  offset?: number;

  /**
   * Cursor for pagination. Pass the `next_cursor` value from the previous response.
   * Recommended over offset pagination for better performance.
   */
  cursor?: string;

  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default STATIC_STALE_TIME (5 minutes)
   */
  staleTime?: number;
}

/**
 * Return type for the useAIAuditPromptHistoryQuery hook
 */
export interface UseAIAuditPromptHistoryQueryReturn {
  /** Prompt history data */
  data: PromptHistoryResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch prompt version history using TanStack Query.
 *
 * @param options - Configuration options
 * @returns Prompt history data and query state
 *
 * @example
 * ```tsx
 * const { data: history, isLoading } = useAIAuditPromptHistoryQuery({
 *   model: AIModelEnum.NEMOTRON,
 *   limit: 10,
 * });
 *
 * return (
 *   <ul>
 *     {history?.versions.map(version => (
 *       <li key={version.id}>
 *         v{version.version}: {version.change_description}
 *       </li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useAIAuditPromptHistoryQuery(
  options: UseAIAuditPromptHistoryQueryOptions = {}
): UseAIAuditPromptHistoryQueryReturn {
  const {
    model,
    limit = 50,
    offset,
    cursor,
    enabled = true,
    staleTime = STATIC_STALE_TIME,
  } = options;

  const query = useQuery({
    queryKey: queryKeys.ai.prompts.history(model),
    queryFn: () => fetchPromptHistory(model, { limit, offset, cursor }),
    enabled,
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
// useEvaluateEventMutation - Trigger evaluation for an event
// ============================================================================

/**
 * Variables for the evaluate event mutation
 */
export interface EvaluateEventVariables {
  /** Event ID to evaluate */
  eventId: number;
  /** If true, re-evaluate even if already evaluated */
  force?: boolean;
}

/**
 * Return type for the useEvaluateEventMutation hook
 */
export interface UseEvaluateEventMutationReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<EventAudit, Error, EvaluateEventVariables>>;
  /** Convenience method to trigger evaluation */
  evaluate: (variables: EvaluateEventVariables) => Promise<EventAudit>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for triggering event evaluation.
 *
 * Automatically invalidates the event audit query on success.
 *
 * @returns Mutation for evaluating an event
 *
 * @example
 * ```tsx
 * const { evaluate, isLoading } = useEvaluateEventMutation();
 *
 * const handleEvaluate = async () => {
 *   await evaluate({ eventId: 123, force: true });
 * };
 * ```
 */
export function useEvaluateEventMutation(): UseEvaluateEventMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: ({ eventId, force }: EvaluateEventVariables) => triggerEvaluation(eventId, force),
    onSuccess: (_data, variables) => {
      // Invalidate the specific event audit query
      void queryClient.invalidateQueries({
        queryKey: queryKeys.ai.audit.event(variables.eventId),
      });
      // Also invalidate stats since evaluation might affect them
      void queryClient.invalidateQueries({
        queryKey: aiAuditQueryKeys.all,
      });
    },
  });

  return {
    mutation,
    evaluate: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useBatchAuditMutation - Trigger batch processing
// ============================================================================

/**
 * Variables for the batch audit mutation
 */
export interface BatchAuditVariables {
  /** Maximum number of events to process (1-1000) */
  limit?: number;
  /** Minimum risk score filter (0-100) */
  minRiskScore?: number;
  /** Whether to re-evaluate already evaluated events */
  forceReevaluate?: boolean;
}

/**
 * Return type for the useBatchAuditMutation hook
 */
export interface UseBatchAuditMutationReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<BatchAuditResponse, Error, BatchAuditVariables>>;
  /** Convenience method to trigger batch audit */
  triggerBatch: (variables: BatchAuditVariables) => Promise<BatchAuditResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for triggering batch audit processing.
 *
 * Automatically invalidates all audit queries on success.
 *
 * @returns Mutation for batch audit processing
 *
 * @example
 * ```tsx
 * const { triggerBatch, isLoading } = useBatchAuditMutation();
 *
 * const handleBatch = async () => {
 *   const result = await triggerBatch({ limit: 100, minRiskScore: 50 });
 *   console.log(`Processed ${result.queued_count} events`);
 * };
 * ```
 */
export function useBatchAuditMutation(): UseBatchAuditMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: ({ limit, minRiskScore, forceReevaluate }: BatchAuditVariables = {}) =>
      triggerBatchAudit(limit, minRiskScore, forceReevaluate),
    onSuccess: () => {
      // Invalidate all audit queries since batch affects everything
      void queryClient.invalidateQueries({
        queryKey: aiAuditQueryKeys.all,
      });
    },
  });

  return {
    mutation,
    triggerBatch: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useTestPromptMutation - A/B test prompts
// ============================================================================

/**
 * Return type for the useTestPromptMutation hook
 */
export interface UseTestPromptMutationReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<PromptTestResult, Error, PromptTestRequest>>;
  /** Convenience method to test a prompt */
  test: (request: PromptTestRequest) => Promise<PromptTestResult>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for A/B testing prompts.
 *
 * Does not invalidate any queries since testing doesn't change stored data.
 *
 * @returns Mutation for testing prompts
 *
 * @example
 * ```tsx
 * const { test, isLoading } = useTestPromptMutation();
 *
 * const handleTest = async () => {
 *   const result = await test({
 *     model: AIModelEnum.NEMOTRON,
 *     config: { system_prompt: 'New prompt...' },
 *     event_id: 123,
 *   });
 *   console.log(`Improved: ${result.improved}`);
 * };
 * ```
 */
export function useTestPromptMutation(): UseTestPromptMutationReturn {
  const mutation = useMutation({
    mutationFn: (request: PromptTestRequest) => testPrompt(request),
  });

  return {
    mutation,
    test: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useUpdatePromptMutation - Update a prompt
// ============================================================================

/**
 * Variables for the update prompt mutation
 */
export interface UpdatePromptVariables {
  /** Model to update */
  model: AIModelEnum;
  /** Update request with new config */
  request: PromptUpdateRequest;
}

/**
 * Return type for the useUpdatePromptMutation hook
 */
export interface UseUpdatePromptMutationReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<ModelPromptConfig, Error, UpdatePromptVariables>>;
  /** Convenience method to update a prompt */
  update: (variables: UpdatePromptVariables) => Promise<ModelPromptConfig>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for updating a prompt configuration.
 *
 * Automatically invalidates prompt queries on success.
 *
 * @returns Mutation for updating prompts
 *
 * @example
 * ```tsx
 * const { update, isLoading } = useUpdatePromptMutation();
 *
 * const handleUpdate = async () => {
 *   await update({
 *     model: AIModelEnum.NEMOTRON,
 *     request: {
 *       config: { system_prompt: 'Updated prompt...' },
 *       change_description: 'Improved risk detection',
 *     },
 *   });
 * };
 * ```
 */
export function useUpdatePromptMutation(): UseUpdatePromptMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: ({ model, request }: UpdatePromptVariables) => updatePromptForModel(model, request),
    onSuccess: (_data, variables) => {
      // Invalidate all prompts query
      void queryClient.invalidateQueries({
        queryKey: queryKeys.ai.prompts.all,
      });
      // Invalidate specific model prompt
      void queryClient.invalidateQueries({
        queryKey: queryKeys.ai.prompts.model(variables.model),
      });
      // Invalidate prompt history
      void queryClient.invalidateQueries({
        queryKey: queryKeys.ai.prompts.history(variables.model),
      });
    },
  });

  return {
    mutation,
    update: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useImportPromptsMutation - Import prompt configs
// ============================================================================

/**
 * Return type for the useImportPromptsMutation hook
 */
export interface UseImportPromptsMutationReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<PromptsImportResponse, Error, PromptsImportRequest>>;
  /** Convenience method to import prompts */
  importPrompts: (request: PromptsImportRequest) => Promise<PromptsImportResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for importing prompt configurations.
 *
 * Automatically invalidates all prompt queries on success.
 *
 * @returns Mutation for importing prompts
 *
 * @example
 * ```tsx
 * const { importPrompts, isLoading } = useImportPromptsMutation();
 *
 * const handleImport = async (data: PromptsImportRequest) => {
 *   const result = await importPrompts(data);
 *   console.log(`Imported: ${result.imported_models.join(', ')}`);
 * };
 * ```
 */
export function useImportPromptsMutation(): UseImportPromptsMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (request: PromptsImportRequest) => importPrompts(request),
    onSuccess: () => {
      // Invalidate all prompt queries
      void queryClient.invalidateQueries({
        queryKey: queryKeys.ai.prompts.all,
      });
      // Invalidate all prompt history
      void queryClient.invalidateQueries({
        queryKey: aiAuditQueryKeys.prompts.history(),
      });
    },
  });

  return {
    mutation,
    importPrompts: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useExportPromptsMutation - Export prompt configs
// ============================================================================

/**
 * Return type for the useExportPromptsMutation hook
 */
export interface UseExportPromptsMutationReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<PromptsExportResponse, Error, void>>;
  /** Convenience method to export prompts */
  exportPrompts: () => Promise<PromptsExportResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
  /** The export data if successful */
  data: PromptsExportResponse | undefined;
}

/**
 * Hook providing mutation for exporting prompt configurations.
 *
 * Note: This is a mutation rather than a query because it's typically
 * triggered by user action (download button) rather than data display.
 *
 * @returns Mutation for exporting prompts
 *
 * @example
 * ```tsx
 * const { exportPrompts, isLoading, data } = useExportPromptsMutation();
 *
 * const handleExport = async () => {
 *   const result = await exportPrompts();
 *   const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
 *   // Download blob...
 * };
 * ```
 */
export function useExportPromptsMutation(): UseExportPromptsMutationReturn {
  const mutation = useMutation({
    mutationFn: () => exportPrompts(),
  });

  return {
    mutation,
    exportPrompts: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
    data: mutation.data,
  };
}
