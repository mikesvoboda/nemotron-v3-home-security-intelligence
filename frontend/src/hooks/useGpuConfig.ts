/**
 * TanStack Query hooks for GPU Configuration management (F-176, F-178, F-182).
 */

import { useQuery, useMutation } from '@tanstack/react-query';

import * as gpuConfigApi from '../services/gpuConfigApi';
import { DEFAULT_STALE_TIME, REALTIME_STALE_TIME } from '../services/queryClient';

import type {
  GpuDevice,
  GpuListResponse,
  GpuConfig,
  StrategyPreviewResponse,
  AiService,
  AiServicesResponse,
} from '../services/gpuConfigApi';

export type {
  GpuDevice,
  GpuListResponse,
  GpuConfig,
  StrategyPreviewResponse,
  GpuAssignment,
  AiService,
  AiServicesResponse,
} from '../services/gpuConfigApi';

export const GPU_QUERY_KEYS = {
  all: ['gpu'] as const,
  gpus: ['gpu', 'devices'] as const,
  config: ['gpu', 'config'] as const,
  aiServices: ['gpu', 'ai-services'] as const,
  preview: (strategy: string) => ['gpu', 'preview', strategy] as const,
} as const;

export interface UseGpusOptions {
  enabled?: boolean;
  staleTime?: number;
  refetchInterval?: number | false;
}

export interface UseGpusReturn {
  data: GpuListResponse | undefined;
  gpus: GpuDevice[];
  isLoading: boolean;
  isRefetching: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

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

export interface UseGpuConfigOptions {
  enabled?: boolean;
  staleTime?: number;
}

export interface UseGpuConfigReturn {
  data: GpuConfig | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

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

export interface UsePreviewStrategyReturn {
  mutation: ReturnType<typeof useMutation<StrategyPreviewResponse, Error, string>>;
  preview: (strategy: string) => Promise<StrategyPreviewResponse>;
  isLoading: boolean;
  error: Error | null;
  data: StrategyPreviewResponse | undefined;
}

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

export interface UseAiServicesOptions {
  enabled?: boolean;
  staleTime?: number;
}

export interface UseAiServicesReturn {
  data: AiServicesResponse | undefined;
  services: AiService[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

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

export type {
  GpuConfigVersionSummary,
  GpuConfigVersionDetail,
  GpuConfigVersionListResponse,
  GpuConfigAssignmentChange,
  GpuConfigVersionDiffResponse,
  GpuConfigExportData,
} from '../services/gpuConfigApi';

export const GPU_VERSION_QUERY_KEYS = {
  versions: ['gpu', 'versions'] as const,
  version: (id: string) => ['gpu', 'versions', id] as const,
  diff: (from: number, to: number) => ['gpu', 'versions', 'diff', from, to] as const,
} as const;

export interface UseConfigVersionsOptions {
  enabled?: boolean;
  limit?: number;
  offset?: number;
}

export interface UseConfigVersionsReturn {
  data: gpuConfigApi.GpuConfigVersionListResponse | undefined;
  versions: gpuConfigApi.GpuConfigVersionSummary[];
  totalCount: number;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

export function useConfigVersions(options: UseConfigVersionsOptions = {}): UseConfigVersionsReturn {
  const { enabled = true, limit = 20, offset = 0 } = options;

  const query = useQuery({
    queryKey: [...GPU_VERSION_QUERY_KEYS.versions, limit, offset],
    queryFn: () => gpuConfigApi.getConfigVersions(limit, offset),
    enabled,
    staleTime: DEFAULT_STALE_TIME,
    retry: 1,
  });

  return {
    data: query.data,
    versions: query.data?.versions ?? [],
    totalCount: query.data?.total_count ?? 0,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

export interface UseConfigVersionReturn {
  data: gpuConfigApi.GpuConfigVersionDetail | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

export function useConfigVersion(versionId: string | null): UseConfigVersionReturn {
  const query = useQuery({
    queryKey: GPU_VERSION_QUERY_KEYS.version(versionId ?? ''),
    queryFn: () => {
      if (!versionId) throw new Error('Invariant: versionId required');
      return gpuConfigApi.getConfigVersion(versionId);
    },
    enabled: !!versionId,
    staleTime: DEFAULT_STALE_TIME,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

export interface UseConfigVersionDiffReturn {
  data: gpuConfigApi.GpuConfigVersionDiffResponse | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

export function useConfigVersionDiff(
  fromVersion: number | null,
  toVersion: number | null
): UseConfigVersionDiffReturn {
  const query = useQuery({
    queryKey: GPU_VERSION_QUERY_KEYS.diff(fromVersion ?? 0, toVersion ?? 0),
    queryFn: () => {
      if (fromVersion === null || toVersion === null) {
        throw new Error('Invariant: fromVersion and toVersion required');
      }
      return gpuConfigApi.diffConfigVersions(fromVersion, toVersion);
    },
    enabled: fromVersion !== null && toVersion !== null,
    staleTime: DEFAULT_STALE_TIME,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

export interface UseExportConfigReturn {
  exportConfig: (versionId?: string) => Promise<gpuConfigApi.GpuConfigExportData>;
  downloadConfig: (versionId?: string, format?: 'json' | 'yaml') => Promise<void>;
  isLoading: boolean;
  error: Error | null;
}

export function useExportConfig(): UseExportConfigReturn {
  const exportMutation = useMutation({
    mutationFn: (versionId?: string) => gpuConfigApi.exportGpuConfig(versionId),
  });

  const downloadMutation = useMutation({
    mutationFn: ({ versionId, format }: { versionId?: string; format?: 'json' | 'yaml' }) =>
      gpuConfigApi.downloadGpuConfig(versionId, format),
  });

  return {
    exportConfig: exportMutation.mutateAsync,
    downloadConfig: (versionId?: string, format?: 'json' | 'yaml') =>
      downloadMutation.mutateAsync({ versionId, format }),
    isLoading: exportMutation.isPending || downloadMutation.isPending,
    error: exportMutation.error ?? downloadMutation.error,
  };
}
