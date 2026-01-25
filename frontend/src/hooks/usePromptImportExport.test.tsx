/**
 * Tests for usePromptImportExport hooks
 *
 * Tests the export, import preview, and import hooks
 * for prompt management.
 *
 * @see NEM-2699 - Implement prompt import/export with preview diffs
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useExportPrompts, useImportPreview, useImportPrompts } from './usePromptImportExport';
import * as promptApi from '../services/promptManagementApi';

import type {
  PromptsExportResponse,
  PromptsImportPreviewResponse,
  PromptsImportResponse,
} from '../types/promptManagement';
import type { ReactNode } from 'react';

// ============================================================================
// Mocks
// ============================================================================

vi.mock('../services/promptManagementApi', () => ({
  exportPrompts: vi.fn(),
  previewImportPrompts: vi.fn(),
  importPrompts: vi.fn(),
}));

// ============================================================================
// Mock Data
// ============================================================================

const mockExportResponse: PromptsExportResponse = {
  version: '1.0',
  exported_at: '2026-01-17T10:30:00Z',
  prompts: {
    nemotron: { system_prompt: 'Test', temperature: 0.7 },
  },
};

const mockPreviewResponse: PromptsImportPreviewResponse = {
  version: '1.0',
  valid: true,
  validation_errors: [],
  diffs: [
    {
      model: 'nemotron',
      has_changes: true,
      current_version: 5,
      current_config: { temperature: 0.7 },
      imported_config: { temperature: 0.8 },
      changes: ['temperature: 0.7 -> 0.8'],
    },
  ],
  total_changes: 1,
  unknown_models: [],
};

const mockImportResponse: PromptsImportResponse = {
  imported_models: ['nemotron'],
  skipped_models: [],
  new_versions: { nemotron: 6 },
  message: 'Successfully imported 1 model configuration',
};

// ============================================================================
// Test Utils
// ============================================================================

function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return function TestWrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('useExportPrompts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (promptApi.exportPrompts as ReturnType<typeof vi.fn>).mockResolvedValue(mockExportResponse);

    // Mock URL methods only (not DOM methods to avoid breaking test environment)
    URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    URL.revokeObjectURL = vi.fn();
  });

  it('returns initial state correctly', () => {
    const { result } = renderHook(() => useExportPrompts(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isExporting).toBe(false);
    expect(result.current.error).toBe(null);
  });

  it('exports prompts successfully', async () => {
    const mockCreateObjectURL = vi.fn(() => 'blob:mock-url');
    const mockRevokeObjectURL = vi.fn();
    URL.createObjectURL = mockCreateObjectURL;
    URL.revokeObjectURL = mockRevokeObjectURL;

    const { result } = renderHook(() => useExportPrompts(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      await result.current.exportAndDownload();
    });

    expect(promptApi.exportPrompts).toHaveBeenCalled();
    expect(mockCreateObjectURL).toHaveBeenCalled();
    expect(mockRevokeObjectURL).toHaveBeenCalled();
  });

  it('handles export error', async () => {
    const error = new Error('Export failed');
    (promptApi.exportPrompts as ReturnType<typeof vi.fn>).mockRejectedValue(error);

    const { result } = renderHook(() => useExportPrompts(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      try {
        await result.current.exportAndDownload();
      } catch {
        // Expected error
      }
    });

    expect(result.current.error).toEqual(error);
  });

  it('resets error on resetError call', async () => {
    const error = new Error('Export failed');
    (promptApi.exportPrompts as ReturnType<typeof vi.fn>).mockRejectedValue(error);

    const { result } = renderHook(() => useExportPrompts(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      try {
        await result.current.exportAndDownload();
      } catch {
        // Expected error
      }
    });

    expect(result.current.error).not.toBe(null);

    act(() => {
      result.current.resetError();
    });

    expect(result.current.error).toBe(null);
  });
});

describe('useImportPreview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (promptApi.previewImportPrompts as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockPreviewResponse
    );
  });

  it('returns initial state correctly', () => {
    const { result } = renderHook(() => useImportPreview(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.previewData).toBe(null);
    expect(result.current.isPending).toBe(false);
    expect(result.current.error).toBe(null);
  });

  it('previews import from request', async () => {
    const { result } = renderHook(() => useImportPreview(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        version: '1.0',
        prompts: { nemotron: { temperature: 0.8 } },
      });
    });

    await waitFor(() => {
      expect(result.current.previewData).toEqual(mockPreviewResponse);
    });

    expect(promptApi.previewImportPrompts).toHaveBeenCalledWith({
      version: '1.0',
      prompts: { nemotron: { temperature: 0.8 } },
    });
  });

  it('previews import from file', async () => {
    const { result } = renderHook(() => useImportPreview(), {
      wrapper: createTestWrapper(),
    });

    // Create a mock file with text() method
    const fileContent = JSON.stringify({
      version: '1.0',
      prompts: { nemotron: { temperature: 0.8 } },
    });
    const testFile = {
      name: 'test.json',
      type: 'application/json',
      text: vi.fn().mockResolvedValue(fileContent),
    } as unknown as File;

    await act(async () => {
      await result.current.previewFromFile(testFile);
    });

    await waitFor(() => {
      expect(result.current.previewData).toEqual(mockPreviewResponse);
    });
  });

  it('handles invalid JSON file', async () => {
    const { result } = renderHook(() => useImportPreview(), {
      wrapper: createTestWrapper(),
    });

    // Create a mock file with invalid JSON content
    const invalidFile = {
      name: 'invalid.json',
      type: 'application/json',
      text: vi.fn().mockResolvedValue('not valid json'),
    } as unknown as File;

    await act(async () => {
      try {
        await result.current.previewFromFile(invalidFile);
        // If we get here, the test should fail
        expect.fail('Expected error to be thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect((error as Error).message).toContain('Invalid JSON file');
      }
    });
  });

  it('clears preview data', async () => {
    const { result } = renderHook(() => useImportPreview(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        version: '1.0',
        prompts: { nemotron: { temperature: 0.8 } },
      });
    });

    await waitFor(() => {
      expect(result.current.previewData).not.toBe(null);
    });

    act(() => {
      result.current.clearPreview();
    });

    expect(result.current.previewData).toBe(null);
  });
});

describe('useImportPrompts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (promptApi.importPrompts as ReturnType<typeof vi.fn>).mockResolvedValue(mockImportResponse);
  });

  it('returns initial state correctly', () => {
    const { result } = renderHook(() => useImportPrompts(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isPending).toBe(false);
    expect(result.current.isSuccess).toBe(false);
    expect(result.current.isError).toBe(false);
    expect(result.current.data).toBe(undefined);
  });

  it('imports prompts successfully', async () => {
    const { result } = renderHook(() => useImportPrompts(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        version: '1.0',
        prompts: { nemotron: { temperature: 0.8 } },
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toEqual(mockImportResponse);
    });
  });

  it('imports from preview data', async () => {
    const { result } = renderHook(() => useImportPrompts(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      await result.current.importFromPreview(mockPreviewResponse);
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(promptApi.importPrompts).toHaveBeenCalledWith({
      version: '1.0',
      prompts: { nemotron: { temperature: 0.8 } },
    });
  });

  it('handles import error', async () => {
    const error = new Error('Import failed');
    (promptApi.importPrompts as ReturnType<typeof vi.fn>).mockRejectedValue(error);

    const { result } = renderHook(() => useImportPrompts(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      try {
        await result.current.mutateAsync({
          version: '1.0',
          prompts: { nemotron: { temperature: 0.8 } },
        });
      } catch {
        // Expected error
      }
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
      expect(result.current.error).toEqual(error);
    });
  });

  it('resets mutation state', async () => {
    const { result } = renderHook(() => useImportPrompts(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        version: '1.0',
        prompts: { nemotron: { temperature: 0.8 } },
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    act(() => {
      result.current.reset();
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(false);
      expect(result.current.data).toBe(undefined);
    });
  });
});
