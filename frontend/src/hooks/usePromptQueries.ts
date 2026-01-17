/**
 * usePromptQueries - TanStack Query hooks for prompt management
 *
 * Provides hooks for fetching and mutating AI model prompt configurations
 * using TanStack Query. Supports:
 * - usePromptConfig: Fetch current config for a model
 * - usePromptHistory: Fetch version history for a model
 * - useUpdatePromptConfig: Update config for a model
 * - useRestorePromptVersion: Restore a previous version
 *
 * @see NEM-2697 - Build Prompt Management page
 * @module hooks/usePromptQueries
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchPromptForModel,
  fetchPromptHistory,
  updatePromptForModel,
  restorePromptVersion,
  type PromptHistoryOptions,
} from '../services/promptManagementApi';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

import type {
  AIModelEnum,
  ModelPromptConfig,
  PromptHistoryResponse,
  PromptRestoreResponse,
  PromptUpdateRequest,
} from '../types/promptManagement';

// ============================================================================
// usePromptConfig - Fetch current config for a model
// ============================================================================

/**
 * Options for configuring the usePromptConfig hook
 */
export interface UsePromptConfigOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default false
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the usePromptConfig hook
 */
export interface UsePromptConfigReturn {
  /** Current prompt configuration */
  data: ModelPromptConfig | undefined;
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
 * Hook to fetch the current prompt configuration for a model.
 *
 * @param model - The AI model to fetch configuration for
 * @param options - Configuration options
 * @returns Config data and query state
 *
 * @example
 * ```tsx
 * const { data: config, isLoading, error } = usePromptConfig(AIModelEnum.NEMOTRON);
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 * if (!config) return null;
 *
 * return <PromptEditor config={config} />;
 * ```
 */
export function usePromptConfig(
  model: AIModelEnum,
  options: UsePromptConfigOptions = {}
): UsePromptConfigReturn {
  const { enabled = true, refetchInterval = false, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.ai.prompts.model(model),
    queryFn: () => fetchPromptForModel(model),
    enabled,
    refetchInterval,
    staleTime,
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
// usePromptHistory - Fetch version history for a model
// ============================================================================

/**
 * Options for configuring the usePromptHistory hook
 */
export interface UsePromptHistoryOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Maximum number of versions to fetch per page.
   * @default 50
   */
  limit?: number;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the usePromptHistory hook
 */
export interface UsePromptHistoryReturn {
  /** Version history response */
  data: PromptHistoryResponse | undefined;
  /** List of versions, empty array if not yet fetched */
  versions: PromptHistoryResponse['versions'];
  /** Total count of versions */
  totalCount: number;
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
 * Hook to fetch version history for a model's prompt configuration.
 *
 * @param model - The AI model to fetch history for
 * @param options - Configuration options
 * @returns History data and query state
 *
 * @example
 * ```tsx
 * const { versions, totalCount, isLoading } = usePromptHistory(AIModelEnum.NEMOTRON);
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <ul>
 *     {versions.map(v => (
 *       <li key={v.id}>Version {v.version}: {v.change_description}</li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function usePromptHistory(
  model: AIModelEnum,
  options: UsePromptHistoryOptions = {}
): UsePromptHistoryReturn {
  const { enabled = true, limit = 50, staleTime = DEFAULT_STALE_TIME } = options;

  const historyOptions: PromptHistoryOptions = { limit };

  const query = useQuery({
    queryKey: [...queryKeys.ai.prompts.history(model), { limit }],
    queryFn: () => fetchPromptHistory(model, historyOptions),
    enabled,
    staleTime,
    retry: 1,
  });

  const versions = useMemo(() => query.data?.versions ?? [], [query.data]);
  const totalCount = query.data?.total_count ?? 0;

  return {
    data: query.data,
    versions,
    totalCount,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useUpdatePromptConfig - Update config for a model
// ============================================================================

/**
 * Variables for updating prompt configuration
 */
export interface UpdatePromptConfigVariables {
  /** The model to update */
  model: AIModelEnum;
  /** The update request containing new config */
  request: PromptUpdateRequest;
}

/**
 * Return type for the useUpdatePromptConfig hook
 */
export interface UseUpdatePromptConfigReturn {
  /** Mutation function to update config */
  mutate: (variables: UpdatePromptConfigVariables) => void;
  /** Async mutation function to update config */
  mutateAsync: (variables: UpdatePromptConfigVariables) => Promise<ModelPromptConfig>;
  /** Whether the mutation is in progress */
  isPending: boolean;
  /** Whether the mutation was successful */
  isSuccess: boolean;
  /** Whether the mutation failed */
  isError: boolean;
  /** Error object if the mutation failed */
  error: Error | null;
  /** The result data if successful */
  data: ModelPromptConfig | undefined;
  /** Reset the mutation state */
  reset: () => void;
}

/**
 * Hook providing mutation for updating prompt configuration.
 *
 * Automatically invalidates the config and history queries on success.
 *
 * @returns Mutation object for updating prompt config
 *
 * @example
 * ```tsx
 * const { mutateAsync, isPending } = useUpdatePromptConfig();
 *
 * const handleSave = async () => {
 *   await mutateAsync({
 *     model: AIModelEnum.NEMOTRON,
 *     request: {
 *       config: { system_prompt: 'New prompt' },
 *       change_description: 'Updated prompt',
 *     },
 *   });
 * };
 * ```
 */
export function useUpdatePromptConfig(): UseUpdatePromptConfigReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: ({ model, request }: UpdatePromptConfigVariables) =>
      updatePromptForModel(model, request),

    onSuccess: (_data, variables) => {
      // Invalidate config and history for the updated model
      void queryClient.invalidateQueries({
        queryKey: queryKeys.ai.prompts.model(variables.model),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.ai.prompts.history(variables.model),
      });
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    data: mutation.data,
    reset: mutation.reset,
  };
}

// ============================================================================
// useRestorePromptVersion - Restore a previous version
// ============================================================================

/**
 * Return type for the useRestorePromptVersion hook
 */
export interface UseRestorePromptVersionReturn {
  /** Mutation function to restore a version */
  mutate: (versionId: number) => void;
  /** Async mutation function to restore a version */
  mutateAsync: (versionId: number) => Promise<PromptRestoreResponse>;
  /** Whether the mutation is in progress */
  isPending: boolean;
  /** Whether the mutation was successful */
  isSuccess: boolean;
  /** Whether the mutation failed */
  isError: boolean;
  /** Error object if the mutation failed */
  error: Error | null;
  /** The result data if successful */
  data: PromptRestoreResponse | undefined;
  /** Reset the mutation state */
  reset: () => void;
}

/**
 * Hook providing mutation for restoring a previous prompt version.
 *
 * Automatically invalidates all prompt queries on success.
 *
 * @returns Mutation object for restoring prompt version
 *
 * @example
 * ```tsx
 * const { mutateAsync, isPending } = useRestorePromptVersion();
 *
 * const handleRestore = async (versionId: number) => {
 *   const result = await mutateAsync(versionId);
 *   console.log(`Restored to version ${result.new_version}`);
 * };
 * ```
 */
export function useRestorePromptVersion(): UseRestorePromptVersionReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (versionId: number) => restorePromptVersion(versionId),

    onSuccess: (data) => {
      // Invalidate config and history for the restored model
      void queryClient.invalidateQueries({
        queryKey: queryKeys.ai.prompts.model(data.model),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.ai.prompts.history(data.model),
      });
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    data: mutation.data,
    reset: mutation.reset,
  };
}
