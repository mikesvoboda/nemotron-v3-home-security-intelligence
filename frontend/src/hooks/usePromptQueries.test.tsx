/**
 * Tests for usePromptQueries hooks
 *
 * Tests the TanStack Query hooks for prompt management:
 * - usePromptConfig
 * - usePromptHistory
 * - useUpdatePromptConfig
 * - useRestorePromptVersion
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';


import {
  usePromptConfig,
  usePromptHistory,
  useUpdatePromptConfig,
  useRestorePromptVersion,
} from './usePromptQueries';
import * as promptApi from '../services/promptManagementApi';
import { AIModelEnum } from '../types/promptManagement';

import type {
  ModelPromptConfig,
  PromptHistoryResponse,
  PromptRestoreResponse,
} from '../types/promptManagement';
import type { ReactNode } from 'react';

// ============================================================================
// Mock Data
// ============================================================================

const mockNemotronConfig: ModelPromptConfig = {
  model: AIModelEnum.NEMOTRON,
  config: {
    system_prompt: 'You are an AI security analyst.',
    temperature: 0.7,
  },
  version: 5,
  created_at: '2026-01-07T12:00:00Z',
  created_by: 'admin',
  change_description: 'Improved risk scoring',
};

const mockHistory: PromptHistoryResponse = {
  versions: [
    {
      id: 10,
      model: AIModelEnum.NEMOTRON,
      version: 5,
      created_at: '2026-01-07T10:00:00Z',
      created_by: 'admin',
      change_description: 'Improved risk scoring',
      is_active: true,
    },
    {
      id: 9,
      model: AIModelEnum.NEMOTRON,
      version: 4,
      created_at: '2026-01-06T15:30:00Z',
      created_by: 'admin',
      change_description: 'Updated context',
      is_active: false,
    },
  ],
  total_count: 2,
};

const mockRestoreResponse: PromptRestoreResponse = {
  restored_version: 4,
  model: AIModelEnum.NEMOTRON,
  new_version: 6,
  message: 'Successfully restored version 4 as new version 6',
};

// ============================================================================
// Mocks
// ============================================================================

vi.mock('../services/promptManagementApi', () => ({
  fetchPromptForModel: vi.fn(),
  fetchPromptHistory: vi.fn(),
  updatePromptForModel: vi.fn(),
  restorePromptVersion: vi.fn(),
}));

// ============================================================================
// Test Utils
// ============================================================================

function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
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

describe('usePromptConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches config for the specified model', async () => {
    (promptApi.fetchPromptForModel as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockNemotronConfig
    );

    const { result } = renderHook(() => usePromptConfig(AIModelEnum.NEMOTRON), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(promptApi.fetchPromptForModel).toHaveBeenCalledWith(AIModelEnum.NEMOTRON);
    expect(result.current.data).toEqual(mockNemotronConfig);
    expect(result.current.error).toBeNull();
  });

  it('returns error when fetch fails', async () => {
    const error = new Error('Failed to fetch');
    (promptApi.fetchPromptForModel as ReturnType<typeof vi.fn>).mockRejectedValue(error);

    const { result } = renderHook(() => usePromptConfig(AIModelEnum.NEMOTRON), {
      wrapper: createTestWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.isLoading).toBe(false);
      },
      { timeout: 3000 }
    );

    expect(result.current.error).toBeTruthy();
    expect(result.current.data).toBeUndefined();
  });

  it('does not fetch when disabled', async () => {
    const { result } = renderHook(
      () => usePromptConfig(AIModelEnum.NEMOTRON, { enabled: false }),
      { wrapper: createTestWrapper() }
    );

    // Wait a bit to ensure no fetch happens
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(promptApi.fetchPromptForModel).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
  });
});

describe('usePromptHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches history for the specified model', async () => {
    (promptApi.fetchPromptHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

    const { result } = renderHook(() => usePromptHistory(AIModelEnum.NEMOTRON), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(promptApi.fetchPromptHistory).toHaveBeenCalledWith(AIModelEnum.NEMOTRON, { limit: 50 });
    expect(result.current.versions).toEqual(mockHistory.versions);
    expect(result.current.totalCount).toBe(2);
  });

  it('returns empty versions when not yet fetched', () => {
    // Use mockReturnValue with a pending promise instead of mockImplementation
    // to avoid no-misused-promises error
    (promptApi.fetchPromptHistory as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise<PromptHistoryResponse>(() => {}) // Never resolves
    );

    const { result } = renderHook(() => usePromptHistory(AIModelEnum.NEMOTRON), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.versions).toEqual([]);
    expect(result.current.totalCount).toBe(0);
  });

  it('passes custom limit option', async () => {
    (promptApi.fetchPromptHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

    renderHook(() => usePromptHistory(AIModelEnum.NEMOTRON, { limit: 10 }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(promptApi.fetchPromptHistory).toHaveBeenCalledWith(AIModelEnum.NEMOTRON, {
        limit: 10,
      });
    });
  });
});

describe('useUpdatePromptConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('updates config and returns new version', async () => {
    const updatedConfig: ModelPromptConfig = {
      ...mockNemotronConfig,
      version: 6,
      change_description: 'New update',
    };
    (promptApi.updatePromptForModel as ReturnType<typeof vi.fn>).mockResolvedValue(updatedConfig);

    const { result } = renderHook(() => useUpdatePromptConfig(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isPending).toBe(false);

    result.current.mutate({
      model: AIModelEnum.NEMOTRON,
      request: {
        config: { system_prompt: 'Updated prompt' },
        change_description: 'New update',
      },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(promptApi.updatePromptForModel).toHaveBeenCalledWith(AIModelEnum.NEMOTRON, {
      config: { system_prompt: 'Updated prompt' },
      change_description: 'New update',
    });
    expect(result.current.data).toEqual(updatedConfig);
  });

  it('returns error when update fails', async () => {
    const error = new Error('Update failed');
    (promptApi.updatePromptForModel as ReturnType<typeof vi.fn>).mockRejectedValue(error);

    const { result } = renderHook(() => useUpdatePromptConfig(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({
      model: AIModelEnum.NEMOTRON,
      request: { config: { system_prompt: 'Bad prompt' } },
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeTruthy();
  });

  it('supports mutateAsync', async () => {
    const updatedConfig: ModelPromptConfig = {
      ...mockNemotronConfig,
      version: 6,
    };
    (promptApi.updatePromptForModel as ReturnType<typeof vi.fn>).mockResolvedValue(updatedConfig);

    const { result } = renderHook(() => useUpdatePromptConfig(), {
      wrapper: createTestWrapper(),
    });

    const response = await result.current.mutateAsync({
      model: AIModelEnum.NEMOTRON,
      request: { config: { system_prompt: 'Async prompt' } },
    });

    expect(response).toEqual(updatedConfig);
  });
});

describe('useRestorePromptVersion', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('restores a version and returns result', async () => {
    (promptApi.restorePromptVersion as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockRestoreResponse
    );

    const { result } = renderHook(() => useRestorePromptVersion(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate(9);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(promptApi.restorePromptVersion).toHaveBeenCalledWith(9);
    expect(result.current.data).toEqual(mockRestoreResponse);
  });

  it('returns error when restore fails', async () => {
    const error = new Error('Version not found');
    (promptApi.restorePromptVersion as ReturnType<typeof vi.fn>).mockRejectedValue(error);

    const { result } = renderHook(() => useRestorePromptVersion(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate(999);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeTruthy();
  });

  it('supports mutateAsync', async () => {
    (promptApi.restorePromptVersion as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockRestoreResponse
    );

    const { result } = renderHook(() => useRestorePromptVersion(), {
      wrapper: createTestWrapper(),
    });

    const response = await result.current.mutateAsync(9);

    expect(response).toEqual(mockRestoreResponse);
  });

  it('can reset mutation state', async () => {
    (promptApi.restorePromptVersion as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockRestoreResponse
    );

    const { result } = renderHook(() => useRestorePromptVersion(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate(9);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    result.current.reset();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(false);
      expect(result.current.data).toBeUndefined();
    });
  });
});
