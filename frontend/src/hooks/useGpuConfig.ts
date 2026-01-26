/**
 * TanStack Query hooks for GPU Configuration management
 *
 * This module provides hooks for fetching and mutating GPU configuration data
 * using TanStack Query. It includes:
 *
 * Queries:
 * - useGpus: Fetch detected GPU devices
 * - useGpuConfig: Fetch current GPU configuration
 * - useGpuStatus: Fetch AI service status with polling support
 *
 * Mutations:
 * - useUpdateGpuConfig: Update GPU assignments and strategy
 * - useApplyGpuConfig: Apply config and restart services
 * - useDetectGpus: Re-scan for GPU devices
 * - usePreviewStrategy: Preview auto-assignment for a strategy
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with automatic cache invalidation
 * - Configurable polling for status monitoring
 * - Proper error handling
 *
 * @module hooks/useGpuConfig
 * @see docs/plans/2025-01-23-multi-gpu-support-design.md - Design document
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import * as gpuConfigApi from '../services/gpuConfigApi';
import { DEFAULT_STALE_TIME, REALTIME_STALE_TIME } from '../services/queryClient';

import type {
  GpuDevice,
  GpuListResponse,
  GpuConfig,
  GpuConfigUpdateRequest,
  GpuConfigUpdateResponse,
  GpuApplyResult,
  GpuStatusResponse,
  StrategyPreviewResponse,
  AiService,
  AiServicesResponse,
  ServiceHealthStatus,
  ServiceHealthResponse,
} from '../services/gpuConfigApi';

// Re-export types for convenience
export type {
  GpuDevice,
  GpuListResponse,
  GpuConfig,
  GpuConfigUpdateRequest,
  GpuConfigUpdateResponse,
  GpuApplyResult,
  GpuStatusResponse,
  StrategyPreviewResponse,
  GpuAssignment,
  ServiceStatus,
  AiService,
  AiServicesResponse,
  ServiceHealthStatus,
  ServiceHealthResponse,
} from '../services/gpuConfigApi';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query keys for GPU configuration queries.
 * Follows the hierarchical pattern for cache invalidation.
 */
export const GPU_QUERY_KEYS = {
  /** Base key for all GPU queries - use for bulk invalidation */
  all: ['gpu'] as const,
  /** GPU device list */
  gpus: ['gpu', 'devices'] as const,
  /** GPU configuration */
  config: ['gpu', 'config'] as const,
  /** AI service status (apply operation status) */
  status: ['gpu', 'status'] as const,
  /** AI service health (comprehensive health with GPU assignments) */
  serviceHealth: ['gpu', 'service-health'] as const,
  /** AI services list */
  aiServices: ['gpu', 'ai-services'] as const,
  /** Strategy preview */
  preview: (strategy: string) => ['gpu', 'preview', strategy] as const,
} as const;

// ============================================================================
// useGpus - Fetch detected GPU devices
// ============================================================================

/**
 * Options for configuring the useGpus hook.
 */
export interface UseGpusOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * @default false
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useGpus hook.
 */
export interface UseGpusReturn {
  /** GPU devices data */
  data: GpuListResponse | undefined;
  /** List of GPU devices (convenience accessor) */
  gpus: GpuDevice[];
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
 * Hook to fetch detected GPU devices using TanStack Query.
 *
 * Returns the list of GPUs available on the system with their
 * hardware specifications and current VRAM utilization.
 *
 * @param options - Configuration options
 * @returns GPU devices and query state
 *
 * @example
 * ```tsx
 * const { gpus, isLoading, error } = useGpus();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div>
 *     {gpus.map(gpu => (
 *       <GpuCard key={gpu.index} gpu={gpu} />
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useGpus(options: UseGpusOptions = {}): UseGpusReturn {
  const { enabled = true, staleTime = REALTIME_STALE_TIME, refetchInterval = false } = options;

  const query = useQuery({
    queryKey: GPU_QUERY_KEYS.gpus,
    queryFn: gpuConfigApi.getGpus,
    enabled,
    staleTime,
    refetchInterval,
    retry: 1,
  });

  return {
    data: query.data,
    gpus: query.data?.gpus ?? [],
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useGpuConfig - Fetch current GPU configuration
// ============================================================================

/**
 * Options for configuring the useGpuConfig hook.
 */
export interface UseGpuConfigOptions {
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
 * Return type for the useGpuConfig hook.
 */
export interface UseGpuConfigReturn {
  /** GPU configuration data */
  data: GpuConfig | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch current GPU configuration using TanStack Query.
 *
 * Returns the current GPU assignment strategy, all service-to-GPU
 * mappings, and available strategies.
 *
 * @param options - Configuration options
 * @returns GPU configuration and query state
 *
 * @example
 * ```tsx
 * const { data: config, isLoading } = useGpuConfig();
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <div>
 *     <p>Strategy: {config?.strategy}</p>
 *     <AssignmentTable assignments={config?.assignments ?? []} />
 *   </div>
 * );
 * ```
 */
export function useGpuConfig(options: UseGpuConfigOptions = {}): UseGpuConfigReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: GPU_QUERY_KEYS.config,
    queryFn: gpuConfigApi.getGpuConfig,
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
// useGpuStatus - Fetch AI service status with polling
// ============================================================================

/**
 * Options for configuring the useGpuStatus hook.
 */
export interface UseGpuStatusOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds. Set to false to disable polling.
   * @default 2000 (2 seconds) when enabled is true
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useGpuStatus hook.
 */
export interface UseGpuStatusReturn {
  /** Service status data */
  data: GpuStatusResponse | undefined;
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
 * Hook to fetch AI service status with optional polling using TanStack Query.
 *
 * Returns the status of all AI services including container status,
 * health check results, and restart progress. Enables 2-second polling
 * by default for monitoring service restarts.
 *
 * @param enabled - Whether to enable the query and polling (default: true)
 * @returns Service status and query state
 *
 * @example
 * ```tsx
 * // Poll while applying config
 * const [isApplying, setIsApplying] = useState(false);
 * const { data: status, isLoading } = useGpuStatus(isApplying);
 *
 * const allHealthy = status?.services.every(s => s.health === 'healthy');
 *
 * useEffect(() => {
 *   if (isApplying && allHealthy) {
 *     setIsApplying(false);
 *     toast.success('All services restarted successfully');
 *   }
 * }, [isApplying, allHealthy]);
 * ```
 */
export function useGpuStatus(enabled: boolean = true): UseGpuStatusReturn {
  const query = useQuery({
    queryKey: GPU_QUERY_KEYS.status,
    queryFn: gpuConfigApi.getGpuStatus,
    enabled,
    staleTime: REALTIME_STALE_TIME,
    refetchInterval: enabled ? 2000 : false,
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
// useUpdateGpuConfig - Update GPU assignments and strategy
// ============================================================================

/**
 * Return type for the useUpdateGpuConfig hook.
 */
export interface UseUpdateGpuConfigReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<GpuConfigUpdateResponse, Error, GpuConfigUpdateRequest>>;
  /** Convenience method to update config */
  updateConfig: (config: GpuConfigUpdateRequest) => Promise<GpuConfigUpdateResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for updating GPU configuration.
 *
 * Automatically invalidates the config query on success.
 * Does NOT restart services - use useApplyGpuConfig after updating.
 *
 * @returns Mutation for updating GPU config
 *
 * @example
 * ```tsx
 * const { updateConfig, isLoading } = useUpdateGpuConfig();
 *
 * const handleSave = async () => {
 *   const result = await updateConfig({
 *     strategy: 'manual',
 *     assignments: [
 *       { service: 'ai-llm', gpu_index: 0 },
 *       { service: 'ai-enrichment', gpu_index: 1 }
 *     ]
 *   });
 *   if (result.warnings.length > 0) {
 *     toast.warning(result.warnings.join('\n'));
 *   }
 * };
 * ```
 */
export function useUpdateGpuConfig(): UseUpdateGpuConfigReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: gpuConfigApi.updateGpuConfig,
    onSuccess: () => {
      // Invalidate config query to refetch with new values
      void queryClient.invalidateQueries({
        queryKey: GPU_QUERY_KEYS.config,
      });
    },
  });

  return {
    mutation,
    updateConfig: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useApplyGpuConfig - Apply config and restart services
// ============================================================================

/**
 * Return type for the useApplyGpuConfig hook.
 */
export interface UseApplyGpuConfigReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<GpuApplyResult, Error, void>>;
  /** Convenience method to apply config */
  applyConfig: () => Promise<GpuApplyResult>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for applying GPU configuration and restarting services.
 *
 * Automatically invalidates the status query on success to trigger
 * immediate status polling.
 *
 * @returns Mutation for applying GPU config
 *
 * @example
 * ```tsx
 * const { applyConfig, isLoading } = useApplyGpuConfig();
 *
 * const handleApply = async () => {
 *   const result = await applyConfig();
 *   if (result.success) {
 *     toast.success(`Restarted: ${result.restarted.join(', ')}`);
 *   } else {
 *     toast.error(`Failed: ${result.failed.join(', ')}`);
 *   }
 * };
 * ```
 */
export function useApplyGpuConfig(): UseApplyGpuConfigReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: gpuConfigApi.applyGpuConfig,
    onSuccess: () => {
      // Invalidate status query to trigger immediate refetch
      void queryClient.invalidateQueries({
        queryKey: GPU_QUERY_KEYS.status,
      });
    },
  });

  return {
    mutation,
    applyConfig: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useDetectGpus - Re-scan for GPU devices
// ============================================================================

/**
 * Return type for the useDetectGpus hook.
 */
export interface UseDetectGpusReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<GpuListResponse, Error, void>>;
  /** Convenience method to detect GPUs */
  detect: () => Promise<GpuListResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for re-detecting GPUs on the system.
 *
 * Automatically invalidates the gpus query on success to refresh
 * the GPU list.
 *
 * @returns Mutation for detecting GPUs
 *
 * @example
 * ```tsx
 * const { detect, isLoading } = useDetectGpus();
 *
 * const handleRescan = async () => {
 *   const { gpus } = await detect();
 *   toast.success(`Detected ${gpus.length} GPUs`);
 * };
 * ```
 */
export function useDetectGpus(): UseDetectGpusReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: gpuConfigApi.detectGpus,
    onSuccess: () => {
      // Invalidate gpus query to refresh the list
      void queryClient.invalidateQueries({
        queryKey: GPU_QUERY_KEYS.gpus,
      });
    },
  });

  return {
    mutation,
    detect: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// usePreviewStrategy - Preview auto-assignment for a strategy
// ============================================================================

/**
 * Return type for the usePreviewStrategy hook.
 */
export interface UsePreviewStrategyReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<StrategyPreviewResponse, Error, string>>;
  /** Convenience method to preview a strategy */
  preview: (strategy: string) => Promise<StrategyPreviewResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
  /** The preview data from the last successful mutation */
  data: StrategyPreviewResponse | undefined;
}

/**
 * Hook providing mutation for previewing strategy auto-assignment.
 *
 * Returns what assignments would be made for a given strategy
 * without actually changing the configuration.
 *
 * @returns Mutation for previewing strategy
 *
 * @example
 * ```tsx
 * const { preview, isLoading, data } = usePreviewStrategy();
 *
 * const handleStrategyChange = async (strategy: string) => {
 *   const result = await preview(strategy);
 *   // Show proposed assignments to user before confirming
 *   setProposedAssignments(result.proposed_assignments);
 * };
 * ```
 */
export function usePreviewStrategy(): UsePreviewStrategyReturn {
  const mutation = useMutation({
    mutationFn: gpuConfigApi.previewStrategy,
  });

  return {
    mutation,
    preview: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
    data: mutation.data,
  };
}

// ============================================================================
// useAiServices - Fetch available AI services with VRAM requirements
// ============================================================================

/**
 * Options for configuring the useAiServices hook.
 */
export interface UseAiServicesOptions {
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
 * Return type for the useAiServices hook.
 */
export interface UseAiServicesReturn {
  /** AI services response data */
  data: AiServicesResponse | undefined;
  /** List of AI services (convenience accessor) */
  services: AiService[];
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch available AI services with VRAM requirements.
 *
 * Returns the list of AI services that can be assigned to GPUs,
 * including their display names, descriptions, and VRAM requirements.
 *
 * @param options - Configuration options
 * @returns AI services and query state
 *
 * @example
 * ```tsx
 * const { services, isLoading, error } = useAiServices();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div>
 *     {services.map(service => (
 *       <ServiceCard key={service.name} service={service} />
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useAiServices(options: UseAiServicesOptions = {}): UseAiServicesReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: GPU_QUERY_KEYS.aiServices,
    queryFn: gpuConfigApi.getAiServices,
    enabled,
    staleTime,
    retry: 1,
  });

  return {
    data: query.data,
    services: query.data?.services ?? [],
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useServiceHealth - Fetch AI service health with GPU assignments
// ============================================================================

/**
 * Options for configuring the useServiceHealth hook.
 */
export interface UseServiceHealthOptions {
  /**
   * Whether to enable the query and polling.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds. Set to false to disable polling.
   * @default 2000 (2 seconds) when enabled is true
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useServiceHealth hook.
 */
export interface UseServiceHealthReturn {
  /** Service health response data */
  data: ServiceHealthResponse | undefined;
  /** List of service health statuses (convenience accessor) */
  services: ServiceHealthStatus[];
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
 * Hook to fetch AI service health status with GPU assignments.
 *
 * Returns comprehensive health information for all AI services including
 * container status, health check result, GPU assignment, and restart status.
 * Enables 2-second polling by default for real-time monitoring.
 *
 * This hook is designed for the GpuSettingsPage to display service health
 * and detect when services have finished restarting.
 *
 * @param enabled - Whether to enable the query and polling (default: true)
 * @returns Service health status and query state
 *
 * @example
 * ```tsx
 * // Poll while applying config
 * const [isApplying, setIsApplying] = useState(false);
 * const { services, isLoading } = useServiceHealth(isApplying);
 *
 * const allHealthy = services.every(s => s.health === 'healthy');
 * const noneRestarting = services.every(s => !s.restart_status);
 *
 * useEffect(() => {
 *   if (isApplying && allHealthy && noneRestarting) {
 *     setIsApplying(false);
 *     toast.success('All services restarted successfully');
 *   }
 * }, [isApplying, allHealthy, noneRestarting]);
 * ```
 */
export function useServiceHealth(enabled: boolean = true): UseServiceHealthReturn {
  const query = useQuery({
    queryKey: GPU_QUERY_KEYS.serviceHealth,
    queryFn: gpuConfigApi.getServiceHealth,
    enabled,
    staleTime: REALTIME_STALE_TIME,
    refetchInterval: enabled ? 2000 : false,
    retry: 1,
  });

  return {
    data: query.data,
    services: query.data?.services ?? [],
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}
