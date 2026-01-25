/**
 * usePromptImportExport - TanStack Query hooks for prompt import/export
 *
 * Provides hooks for exporting and importing AI model prompt configurations:
 * - useExportPrompts: Export all prompts as JSON
 * - useImportPreview: Preview import changes before applying
 * - useImportPrompts: Apply imported configurations
 *
 * @see NEM-2699 - Implement prompt import/export with preview diffs
 * @module hooks/usePromptImportExport
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useCallback, useState } from 'react';

import {
  exportPrompts,
  previewImportPrompts,
  importPrompts,
} from '../services/promptManagementApi';
import { queryKeys } from '../services/queryClient';

import type {
  PromptsExportResponse,
  PromptsImportPreviewRequest,
  PromptsImportPreviewResponse,
  PromptsImportRequest,
  PromptsImportResponse,
} from '../types/promptManagement';

// ============================================================================
// useExportPrompts - Export all prompts as JSON
// ============================================================================

/**
 * Return type for the useExportPrompts hook
 */
export interface UseExportPromptsReturn {
  /** Export prompts and trigger download */
  exportAndDownload: () => Promise<void>;
  /** Whether export is in progress */
  isExporting: boolean;
  /** Error object if export failed */
  error: Error | null;
  /** Reset error state */
  resetError: () => void;
}

/**
 * Hook for exporting all prompt configurations as a JSON file.
 *
 * Creates a downloadable JSON file with the format:
 * prompts-export-YYYY-MM-DD.json
 *
 * @returns Export function and state
 *
 * @example
 * ```tsx
 * const { exportAndDownload, isExporting, error } = useExportPrompts();
 *
 * return (
 *   <Button onClick={exportAndDownload} loading={isExporting}>
 *     Export
 *   </Button>
 * );
 * ```
 */
export function useExportPrompts(): UseExportPromptsReturn {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const exportAndDownload = useCallback(async () => {
    setIsExporting(true);
    setError(null);

    try {
      const data: PromptsExportResponse = await exportPrompts();

      // Create downloadable blob
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);

      // Create and trigger download
      const a = document.createElement('a');
      a.href = url;
      a.download = `prompts-export-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      // Clean up
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to export prompts'));
      throw err;
    } finally {
      setIsExporting(false);
    }
  }, []);

  const resetError = useCallback(() => {
    setError(null);
  }, []);

  return {
    exportAndDownload,
    isExporting,
    error,
    resetError,
  };
}

// ============================================================================
// useImportPreview - Preview import changes before applying
// ============================================================================

/**
 * Return type for the useImportPreview hook
 */
export interface UseImportPreviewReturn {
  /** Preview data from the most recent preview */
  previewData: PromptsImportPreviewResponse | null;
  /** Generate preview from file */
  previewFromFile: (file: File) => Promise<PromptsImportPreviewResponse>;
  /** Mutation function for preview */
  mutate: (request: PromptsImportPreviewRequest) => void;
  /** Async mutation function for preview */
  mutateAsync: (request: PromptsImportPreviewRequest) => Promise<PromptsImportPreviewResponse>;
  /** Whether preview is being generated */
  isPending: boolean;
  /** Error object if preview failed */
  error: Error | null;
  /** Clear the preview data */
  clearPreview: () => void;
  /** Reset the mutation state */
  reset: () => void;
}

/**
 * Hook for previewing import changes before applying them.
 *
 * Parses a JSON file and computes diffs against current configurations.
 *
 * @returns Preview mutation and state
 *
 * @example
 * ```tsx
 * const { previewFromFile, previewData, isPending, error } = useImportPreview();
 *
 * const handleFileSelect = async (file: File) => {
 *   const preview = await previewFromFile(file);
 *   console.log('Changes:', preview.total_changes);
 * };
 * ```
 */
export function useImportPreview(): UseImportPreviewReturn {
  const [previewData, setPreviewData] = useState<PromptsImportPreviewResponse | null>(null);

  const mutation = useMutation({
    mutationFn: (request: PromptsImportPreviewRequest) => previewImportPrompts(request),
    onSuccess: (data) => {
      setPreviewData(data);
    },
  });

  const previewFromFile = useCallback(
    async (file: File): Promise<PromptsImportPreviewResponse> => {
      const text = await file.text();
      let parsed: unknown;

      try {
        parsed = JSON.parse(text);
      } catch {
        throw new Error('Invalid JSON file. Please select a valid prompts export file.');
      }

      // Validate structure
      if (typeof parsed !== 'object' || parsed === null) {
        throw new Error('Invalid file format. Expected a JSON object.');
      }

      const data = parsed as Record<string, unknown>;

      // Extract version and prompts
      const version = (data.version as string) || '1.0';
      const prompts = (data.prompts as Record<string, Record<string, unknown>>) || data;

      // If prompts is empty but we have other keys that look like model configs, use the whole object
      const hasModelKeys = Object.keys(data).some((k) =>
        ['nemotron', 'florence2', 'yolo_world', 'xclip', 'fashion_clip'].includes(k)
      );

      const request: PromptsImportPreviewRequest = {
        version,
        prompts:
          hasModelKeys && Object.keys(prompts).length === 0
            ? (data as Record<string, Record<string, unknown>>)
            : prompts,
      };

      return mutation.mutateAsync(request);
    },
    [mutation]
  );

  const clearPreview = useCallback(() => {
    setPreviewData(null);
    mutation.reset();
  }, [mutation]);

  return {
    previewData,
    previewFromFile,
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    error: mutation.error,
    clearPreview,
    reset: mutation.reset,
  };
}

// ============================================================================
// useImportPrompts - Apply imported configurations
// ============================================================================

/**
 * Return type for the useImportPrompts hook
 */
export interface UseImportPromptsReturn {
  /** Mutation function to import prompts */
  mutate: (request: PromptsImportRequest) => void;
  /** Async mutation function to import prompts */
  mutateAsync: (request: PromptsImportRequest) => Promise<PromptsImportResponse>;
  /** Import from preview data */
  importFromPreview: (previewData: PromptsImportPreviewResponse) => Promise<PromptsImportResponse>;
  /** Whether import is in progress */
  isPending: boolean;
  /** Whether import was successful */
  isSuccess: boolean;
  /** Whether import failed */
  isError: boolean;
  /** Error object if import failed */
  error: Error | null;
  /** The result data if successful */
  data: PromptsImportResponse | undefined;
  /** Reset the mutation state */
  reset: () => void;
}

/**
 * Hook for importing prompt configurations.
 *
 * Automatically invalidates all prompt queries on success.
 *
 * @returns Import mutation and state
 *
 * @example
 * ```tsx
 * const { importFromPreview, isPending, isSuccess } = useImportPrompts();
 *
 * const handleImport = async () => {
 *   const result = await importFromPreview(previewData);
 *   console.log('Imported:', result.imported_models);
 * };
 * ```
 */
export function useImportPrompts(): UseImportPromptsReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (request: PromptsImportRequest) => importPrompts(request),

    onSuccess: () => {
      // Invalidate all prompt-related queries
      void queryClient.invalidateQueries({
        queryKey: queryKeys.ai.prompts.all,
      });
    },
  });

  const importFromPreview = useCallback(
    async (previewData: PromptsImportPreviewResponse): Promise<PromptsImportResponse> => {
      // Build request from preview data
      const prompts: Record<string, Record<string, unknown>> = {};

      for (const diff of previewData.diffs) {
        if (diff.has_changes) {
          prompts[diff.model] = diff.imported_config;
        }
      }

      const request: PromptsImportRequest = {
        version: previewData.version,
        prompts,
      };

      return mutation.mutateAsync(request);
    },
    [mutation]
  );

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    importFromPreview,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    data: mutation.data,
    reset: mutation.reset,
  };
}
