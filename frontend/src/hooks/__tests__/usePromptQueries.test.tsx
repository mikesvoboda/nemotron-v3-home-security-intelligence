/**
 * Unit tests for usePromptQueries hooks
 *
 * Tests TanStack Query integration for prompt management:
 * - usePromptConfig: Fetch current prompt config for a model
 * - usePromptHistory: Fetch version history for a model
 * - useUpdatePromptConfig: Update prompt configuration
 * - useRestorePromptVersion: Restore a previous version
 * - usePromptTest: A/B test prompt configuration
 *
 * @module hooks/__tests__/usePromptQueries
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  usePromptConfig,
  usePromptHistory,
  useUpdatePromptConfig,
  useRestorePromptVersion,
  usePromptTest,
  type UsePromptConfigOptions,
  type UsePromptHistoryOptions,
  type UpdatePromptConfigVariables,
  type PromptTestVariables,
} from '../usePromptQueries';

import type {
  AIModelEnum,
  ModelPromptConfig,
  PromptHistoryResponse,
  PromptRestoreResponse,
} from '../../types/promptManagement';

// ============================================================================
// Mock API Functions
// ============================================================================

const mockFetchPromptForModel = vi.fn();
const mockFetchPromptHistory = vi.fn();
const mockUpdatePromptForModel = vi.fn();
const mockRestorePromptVersion = vi.fn();
const mockTestPrompt = vi.fn();

vi.mock('../../services/promptManagementApi', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../services/promptManagementApi')>();
  return {
    ...actual,
    fetchPromptForModel: (...args: unknown[]) => mockFetchPromptForModel(...args),
    fetchPromptHistory: (...args: unknown[]) => mockFetchPromptHistory(...args),
    updatePromptForModel: (...args: unknown[]) => mockUpdatePromptForModel(...args),
    restorePromptVersion: (...args: unknown[]) => mockRestorePromptVersion(...args),
    testPrompt: (...args: unknown[]) => mockTestPrompt(...args),
  };
});

// ============================================================================
// Test Utilities
// ============================================================================

/**
 * Create a test wrapper with a fresh QueryClient for each test.
 * Disables retries and caching to ensure tests are isolated.
 */
function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ============================================================================
// Test Data Fixtures
// ============================================================================

const mockModel: AIModelEnum = 'nemotron' as AIModelEnum;

const mockPromptConfig: ModelPromptConfig = {
  model: mockModel,
  version: 5,
  config: {
    system_prompt: 'You are a security risk analyzer.',
    temperature: 0.7,
    max_tokens: 1024,
  },
  change_description: 'Updated temperature parameter',
} as unknown as ModelPromptConfig;

const mockPromptHistoryResponse = {
  model: mockModel,
  versions: [
    {
      id: 5,
      model: mockModel,
      version: 5,
      created_at: '2026-01-20T10:00:00Z',
      change_description: 'Updated temperature parameter',
    },
    {
      id: 4,
      model: mockModel,
      version: 4,
      created_at: '2026-01-19T14:30:00Z',
      change_description: 'Reduced max_tokens',
    },
    {
      id: 3,
      model: mockModel,
      version: 3,
      created_at: '2026-01-18T09:15:00Z',
      change_description: 'Simplified system prompt',
    },
  ],
  total_count: 3,
} as unknown as PromptHistoryResponse;

const mockRestoreResponse = {
  model: mockModel,
  new_version: 6,
  restored_from_version: 3,
  message: 'Successfully restored to version 3',
} as unknown as PromptRestoreResponse;

const mockTestResponse = {
  before_score: 75,
  after_score: 82,
  before_response: {
    risk_level: 'HIGH',
    reasoning: 'Previous reasoning',
    summary: 'Previous summary',
  },
  after_response: {
    risk_level: 'CRITICAL',
    reasoning: 'New reasoning with improved prompt',
    summary: 'New summary with better analysis',
  },
  test_duration_ms: 1250,
};

// ============================================================================
// Setup/Teardown
// ============================================================================

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchPromptForModel.mockResolvedValue(mockPromptConfig);
  mockFetchPromptHistory.mockResolvedValue(mockPromptHistoryResponse);
  mockUpdatePromptForModel.mockResolvedValue(mockPromptConfig);
  mockRestorePromptVersion.mockResolvedValue(mockRestoreResponse);
  mockTestPrompt.mockResolvedValue(mockTestResponse);
});

// ============================================================================
// usePromptConfig Tests
// ============================================================================

describe('usePromptConfig', () => {
  it('fetches prompt config on mount', async () => {
    const { result } = renderHook(() => usePromptConfig(mockModel), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockPromptConfig);
    expect(mockFetchPromptForModel).toHaveBeenCalledWith(mockModel);
    expect(mockFetchPromptForModel).toHaveBeenCalledTimes(1);
  });

  it('does not fetch when enabled is false', async () => {
    const options: UsePromptConfigOptions = { enabled: false };

    renderHook(() => usePromptConfig(mockModel, options), {
      wrapper: createTestWrapper(),
    });

    // Wait to ensure no fetch happens
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockFetchPromptForModel).not.toHaveBeenCalled();
  });

  it('handles error state', async () => {
    const errorMessage = 'Failed to fetch prompt config';

    // Clear the default mock behavior and set up rejection
    mockFetchPromptForModel.mockClear();
    mockFetchPromptForModel.mockRejectedValue(new Error(errorMessage));

    const { result } = renderHook(() => usePromptConfig(mockModel), {
      wrapper: createTestWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.isLoading).toBe(false);
      },
      { timeout: 2000 }
    );

    expect(result.current.error).toBeTruthy();
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe(errorMessage);
    expect(result.current.data).toBeUndefined();
  });

  it('supports custom stale time', async () => {
    const options: UsePromptConfigOptions = { staleTime: 60000 };

    const { result } = renderHook(() => usePromptConfig(mockModel, options), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockPromptConfig);
  });

  it('supports refetch interval for polling', async () => {
    const options: UsePromptConfigOptions = { refetchInterval: 5000 };

    const { result } = renderHook(() => usePromptConfig(mockModel, options), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockPromptConfig);
  });

  it('provides refetch function', async () => {
    const { result } = renderHook(() => usePromptConfig(mockModel), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetchPromptForModel).toHaveBeenCalledTimes(1);

    // Trigger manual refetch
    await result.current.refetch();

    expect(mockFetchPromptForModel).toHaveBeenCalledTimes(2);
  });

  it('tracks refetching state correctly', async () => {
    const { result } = renderHook(() => usePromptConfig(mockModel), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isRefetching).toBe(false);

    // Trigger refetch and immediately check for refetching state
    const refetchPromise = result.current.refetch();

    // Wait for refetch to complete
    await refetchPromise;

    await waitFor(() => {
      expect(result.current.isRefetching).toBe(false);
    });
  });
});

// ============================================================================
// usePromptHistory Tests
// ============================================================================

describe('usePromptHistory', () => {
  it('fetches prompt history on mount', async () => {
    const { result } = renderHook(() => usePromptHistory(mockModel), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.versions).toEqual([]);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockPromptHistoryResponse);
    expect(result.current.versions).toEqual(mockPromptHistoryResponse.versions);
    expect(result.current.totalCount).toBe(3);
    expect(mockFetchPromptHistory).toHaveBeenCalledWith(mockModel, { limit: 50 });
  });

  it('supports custom limit', async () => {
    const options: UsePromptHistoryOptions = { limit: 10 };

    const { result } = renderHook(() => usePromptHistory(mockModel, options), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetchPromptHistory).toHaveBeenCalledWith(mockModel, { limit: 10 });
  });

  it('does not fetch when enabled is false', async () => {
    const options: UsePromptHistoryOptions = { enabled: false };

    renderHook(() => usePromptHistory(mockModel, options), {
      wrapper: createTestWrapper(),
    });

    // Wait to ensure no fetch happens
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockFetchPromptHistory).not.toHaveBeenCalled();
  });

  it('handles empty history', async () => {
    const emptyResponse = {
      model: mockModel,
      versions: [],
      total_count: 0,
    } as unknown as PromptHistoryResponse;

    mockFetchPromptHistory.mockResolvedValue(emptyResponse);

    const { result } = renderHook(() => usePromptHistory(mockModel), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.versions).toEqual([]);
    expect(result.current.totalCount).toBe(0);
  });

  it('handles error state', async () => {
    const errorMessage = 'Failed to fetch history';

    // Clear the default mock behavior and set up rejection
    mockFetchPromptHistory.mockClear();
    mockFetchPromptHistory.mockRejectedValue(new Error(errorMessage));

    const { result } = renderHook(() => usePromptHistory(mockModel), {
      wrapper: createTestWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.isLoading).toBe(false);
      },
      { timeout: 2000 }
    );

    expect(result.current.error).toBeTruthy();
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe(errorMessage);
    expect(result.current.versions).toEqual([]);
  });

  it('provides refetch function', async () => {
    const { result } = renderHook(() => usePromptHistory(mockModel), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetchPromptHistory).toHaveBeenCalledTimes(1);

    await result.current.refetch();

    expect(mockFetchPromptHistory).toHaveBeenCalledTimes(2);
  });
});

// ============================================================================
// useUpdatePromptConfig Tests
// ============================================================================

describe('useUpdatePromptConfig', () => {
  it('updates prompt config successfully', async () => {
    const { result } = renderHook(() => useUpdatePromptConfig(), {
      wrapper: createTestWrapper(),
    });

    const variables: UpdatePromptConfigVariables = {
      model: mockModel,
      request: {
        config: { temperature: 0.8 },
        change_description: 'Increased temperature',
      },
    };

    result.current.mutate(variables);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockPromptConfig);
    expect(mockUpdatePromptForModel).toHaveBeenCalledWith(
      mockModel,
      variables.request
    );
  });

  it('tracks pending state correctly', async () => {
    mockUpdatePromptForModel.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(() => resolve(mockPromptConfig), 100)
        )
    );

    const { result } = renderHook(() => useUpdatePromptConfig(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isPending).toBe(false);

    result.current.mutate({
      model: mockModel,
      request: {
        config: { temperature: 0.8 },
        change_description: 'Test update',
      },
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('handles error state', async () => {
    const errorMessage = 'Invalid configuration';
    mockUpdatePromptForModel.mockRejectedValue(new Error(errorMessage));

    const { result } = renderHook(() => useUpdatePromptConfig(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({
      model: mockModel,
      request: {
        config: {},
        change_description: 'Test',
      },
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe(errorMessage);
    expect(result.current.data).toBeUndefined();
  });

  it('supports async mutation', async () => {
    const { result } = renderHook(() => useUpdatePromptConfig(), {
      wrapper: createTestWrapper(),
    });

    const response = await result.current.mutateAsync({
      model: mockModel,
      request: {
        config: { temperature: 0.9 },
        change_description: 'Async update',
      },
    });

    expect(response).toEqual(mockPromptConfig);

    // Wait for React state to update
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('resets mutation state', async () => {
    const { result } = renderHook(() => useUpdatePromptConfig(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({
      model: mockModel,
      request: {
        config: {},
        change_description: 'Test',
      },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    result.current.reset();

    // Wait for React state to update after reset
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(false);
    });

    expect(result.current.data).toBeUndefined();
  });

  it('invalidates cache on success', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useUpdatePromptConfig(), { wrapper });

    result.current.mutate({
      model: mockModel,
      request: {
        config: {},
        change_description: 'Test',
      },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Should invalidate both config and history
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// ============================================================================
// useRestorePromptVersion Tests
// ============================================================================

describe('useRestorePromptVersion', () => {
  it('restores prompt version successfully', async () => {
    const { result } = renderHook(() => useRestorePromptVersion(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate(3);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockRestoreResponse);
    expect(mockRestorePromptVersion).toHaveBeenCalledWith(3);
  });

  it('handles error state', async () => {
    const errorMessage = 'Version not found';
    mockRestorePromptVersion.mockRejectedValue(new Error(errorMessage));

    const { result } = renderHook(() => useRestorePromptVersion(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate(999);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe(errorMessage);
  });

  it('supports async mutation', async () => {
    const { result } = renderHook(() => useRestorePromptVersion(), {
      wrapper: createTestWrapper(),
    });

    const response = await result.current.mutateAsync(3);

    expect(response).toEqual(mockRestoreResponse);

    // Wait for React state to update
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('invalidates cache on success', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useRestorePromptVersion(), { wrapper });

    result.current.mutate(3);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Should invalidate both config and history for the restored model
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });

  it('resets mutation state', async () => {
    const { result } = renderHook(() => useRestorePromptVersion(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate(3);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    result.current.reset();

    // Wait for React state to update after reset
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(false);
    });

    expect(result.current.data).toBeUndefined();
  });
});

// ============================================================================
// usePromptTest Tests
// ============================================================================

describe('usePromptTest', () => {
  it('runs A/B test successfully', async () => {
    const { result } = renderHook(() => usePromptTest(), {
      wrapper: createTestWrapper(),
    });

    const variables: PromptTestVariables = {
      model: mockModel,
      config: { temperature: 0.9 },
      eventId: 123,
    };

    result.current.mutate(variables);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toMatchObject({
      riskScore: 82,
      riskLevel: 'CRITICAL',
      reasoning: expect.any(String),
      summary: expect.any(String),
      processingTimeMs: 1250,
    });

    expect(mockTestPrompt).toHaveBeenCalledWith({
      model: mockModel,
      config: variables.config,
      event_id: 123,
    });
  });

  it('transforms snake_case response to camelCase', async () => {
    const { result } = renderHook(() => usePromptTest(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({
      model: mockModel,
      config: {},
      eventId: 123,
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Verify camelCase properties
    expect(result.current.data).toHaveProperty('riskScore');
    expect(result.current.data).toHaveProperty('riskLevel');
    expect(result.current.data).toHaveProperty('processingTimeMs');
    expect(result.current.data).not.toHaveProperty('risk_score');
    expect(result.current.data).not.toHaveProperty('processing_time_ms');
  });

  it('handles missing response fields gracefully', async () => {
    mockTestPrompt.mockResolvedValue({
      test_duration_ms: 500,
    });

    const { result } = renderHook(() => usePromptTest(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({
      model: mockModel,
      config: {},
      eventId: 123,
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toMatchObject({
      riskScore: 0,
      riskLevel: 'unknown',
      reasoning: '',
      summary: '',
      processingTimeMs: 500,
      tokensUsed: 0,
    });
  });

  it('handles error state', async () => {
    const errorMessage = 'Event not found';
    mockTestPrompt.mockRejectedValue(new Error(errorMessage));

    const { result } = renderHook(() => usePromptTest(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({
      model: mockModel,
      config: {},
      eventId: 999,
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe(errorMessage);
  });

  it('supports async mutation', async () => {
    const { result } = renderHook(() => usePromptTest(), {
      wrapper: createTestWrapper(),
    });

    const response = await result.current.mutateAsync({
      model: mockModel,
      config: { temperature: 0.8 },
      eventId: 123,
    });

    expect(response.riskScore).toBe(82);

    // Wait for React state to update
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('does not invalidate cache on success', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => usePromptTest(), { wrapper });

    result.current.mutate({
      model: mockModel,
      config: {},
      eventId: 123,
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Test mutation should not invalidate any queries
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it('resets mutation state', async () => {
    const { result } = renderHook(() => usePromptTest(), {
      wrapper: createTestWrapper(),
    });

    result.current.mutate({
      model: mockModel,
      config: {},
      eventId: 123,
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    result.current.reset();

    // Wait for React state to update after reset
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(false);
    });

    expect(result.current.data).toBeUndefined();
  });
});
