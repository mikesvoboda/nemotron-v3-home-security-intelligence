import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useAIAuditStats,
  useAIAuditLeaderboard,
  useAIAuditRecommendations,
  useAIAuditEventQuery,
  useAIAuditPromptsQuery,
  useAIAuditPromptHistoryQuery,
  useEvaluateEventMutation,
  useBatchAuditMutation,
  useTestPromptMutation,
  useUpdatePromptMutation,
  useImportPromptsMutation,
  useExportPromptsMutation,
  aiAuditQueryKeys,
} from './useAIAuditQueries';
import * as auditApi from '../services/auditApi';
import * as promptApi from '../services/promptManagementApi';
import { createQueryClient, queryKeys } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';
import { AIModelEnum } from '../types/promptManagement';

import type {
  AuditStats,
  LeaderboardResponse,
  RecommendationsResponse,
  EventAudit,
  BatchAuditResponse,
} from '../services/auditApi';
import type {
  AllPromptsResponse,
  PromptHistoryResponse,
  ModelPromptConfig,
  PromptTestResult,
  PromptsImportResponse,
  PromptsExportResponse,
} from '../types/promptManagement';

// Mock the API modules
vi.mock('../services/auditApi', () => ({
  fetchAuditStats: vi.fn(),
  fetchLeaderboard: vi.fn(),
  fetchRecommendations: vi.fn(),
  fetchEventAudit: vi.fn(),
  triggerEvaluation: vi.fn(),
  triggerBatchAudit: vi.fn(),
}));

vi.mock('../services/promptManagementApi', () => ({
  fetchAllPrompts: vi.fn(),
  fetchPromptHistory: vi.fn(),
  updatePromptForModel: vi.fn(),
  testPrompt: vi.fn(),
  importPrompts: vi.fn(),
  exportPrompts: vi.fn(),
}));

// ============================================================================
// Test Data
// ============================================================================

const mockAuditStats: AuditStats = {
  total_events: 100,
  audited_events: 80,
  fully_evaluated_events: 60,
  avg_quality_score: 4.2,
  avg_consistency_rate: 0.85,
  avg_enrichment_utilization: 0.75,
  model_contribution_rates: {
    rtdetr: 0.95,
    florence: 0.80,
    clip: 0.70,
  },
  audits_by_day: [
    { date: '2025-01-10', count: 10 },
    { date: '2025-01-11', count: 12 },
  ],
};

const mockLeaderboard: LeaderboardResponse = {
  entries: [
    {
      model_name: 'rtdetr',
      contribution_rate: 0.95,
      quality_correlation: 0.85,
      event_count: 95,
    },
    {
      model_name: 'florence',
      contribution_rate: 0.80,
      quality_correlation: 0.72,
      event_count: 80,
    },
  ],
  period_days: 7,
};

const mockRecommendations: RecommendationsResponse = {
  recommendations: [
    {
      category: 'missing_context',
      suggestion: 'Add weather data to prompts',
      frequency: 15,
      priority: 'high',
    },
    {
      category: 'model_gaps',
      suggestion: 'Enable violence detection',
      frequency: 8,
      priority: 'medium',
    },
  ],
  total_events_analyzed: 100,
};

const mockEventAudit: EventAudit = {
  id: 1,
  event_id: 123,
  audited_at: '2025-01-11T10:00:00Z',
  is_fully_evaluated: true,
  contributions: {
    rtdetr: true,
    florence: true,
    clip: false,
    violence: false,
    clothing: false,
    vehicle: true,
    pet: false,
    weather: true,
    image_quality: true,
    zones: true,
    baseline: true,
    cross_camera: false,
  },
  prompt_length: 5000,
  prompt_token_estimate: 1250,
  enrichment_utilization: 0.75,
  scores: {
    context_usage: 4,
    reasoning_coherence: 5,
    risk_justification: 4,
    consistency: 4,
    overall: 4.25,
  },
  consistency_risk_score: 72,
  consistency_diff: 3,
  self_eval_critique: 'Good analysis but could improve...',
  improvements: {
    missing_context: ['weather data'],
    confusing_sections: [],
    unused_data: ['zone B data'],
    format_suggestions: [],
    model_gaps: ['violence detection'],
  },
};

const mockAllPrompts: AllPromptsResponse = {
  version: '1.0.0',
  exported_at: '2025-01-11T10:00:00Z',
  prompts: {
    nemotron: { system_prompt: 'Analyze security...', version: 5 },
    florence2: { queries: ['describe scene'] },
  },
};

const mockPromptHistory: PromptHistoryResponse = {
  versions: [
    {
      id: 5,
      model: AIModelEnum.NEMOTRON,
      version: 5,
      created_at: '2025-01-11T10:00:00Z',
      created_by: 'admin',
      change_description: 'Improved risk detection',
      is_active: true,
    },
    {
      id: 4,
      model: AIModelEnum.NEMOTRON,
      version: 4,
      created_at: '2025-01-10T10:00:00Z',
      change_description: 'Fixed formatting',
      is_active: false,
    },
  ],
  total_count: 5,
};

const mockModelPromptConfig: ModelPromptConfig = {
  model: AIModelEnum.NEMOTRON,
  config: { system_prompt: 'Updated prompt...' },
  version: 6,
  created_at: '2025-01-11T11:00:00Z',
  change_description: 'Test update',
};

const mockTestResult: PromptTestResult = {
  model: AIModelEnum.NEMOTRON,
  before_score: 70,
  after_score: 75,
  before_response: { risk: 70 },
  after_response: { risk: 75 },
  improved: true,
  test_duration_ms: 1500,
};

const mockBatchResponse: BatchAuditResponse = {
  queued_count: 50,
  message: 'Processed 50 events',
};

const mockImportResponse: PromptsImportResponse = {
  imported_models: ['nemotron', 'florence2'],
  skipped_models: [],
  new_versions: { nemotron: 6, florence2: 3 },
  message: 'Import successful',
};

const mockExportResponse: PromptsExportResponse = {
  version: '1.0.0',
  exported_at: '2025-01-11T10:00:00Z',
  prompts: {
    nemotron: { system_prompt: 'Prompt...' },
  },
};

// ============================================================================
// Query Key Tests
// ============================================================================

describe('aiAuditQueryKeys', () => {
  it('creates correct stats query keys', () => {
    expect(aiAuditQueryKeys.all).toEqual(['ai', 'audit']);
    expect(aiAuditQueryKeys.stats()).toEqual(['ai', 'audit', 'stats']);
    expect(aiAuditQueryKeys.stats({ days: 7 })).toEqual(['ai', 'audit', 'stats', { days: 7 }]);
    expect(aiAuditQueryKeys.stats({ days: 7, camera_id: 'cam-1' })).toEqual([
      'ai',
      'audit',
      'stats',
      { days: 7, camera_id: 'cam-1' },
    ]);
  });

  it('creates correct leaderboard query keys', () => {
    expect(aiAuditQueryKeys.leaderboard()).toEqual(['ai', 'audit', 'leaderboard']);
    expect(aiAuditQueryKeys.leaderboard({ days: 30 })).toEqual([
      'ai',
      'audit',
      'leaderboard',
      { days: 30 },
    ]);
  });

  it('creates correct recommendations query keys', () => {
    expect(aiAuditQueryKeys.recommendations()).toEqual(['ai', 'audit', 'recommendations']);
    expect(aiAuditQueryKeys.recommendations({ days: 14 })).toEqual([
      'ai',
      'audit',
      'recommendations',
      { days: 14 },
    ]);
  });

  it('creates correct event query keys', () => {
    expect(aiAuditQueryKeys.event(123)).toEqual(['ai', 'audit', 'event', 123]);
  });

  it('creates correct prompts query keys', () => {
    expect(aiAuditQueryKeys.prompts.all).toEqual(['ai', 'prompts']);
    expect(aiAuditQueryKeys.prompts.history()).toEqual(['ai', 'prompts', 'history']);
    expect(aiAuditQueryKeys.prompts.history(AIModelEnum.NEMOTRON)).toEqual([
      'ai',
      'prompts',
      'history',
      'nemotron',
    ]);
  });
});

// ============================================================================
// useAIAuditStats Tests
// ============================================================================

describe('useAIAuditStats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auditApi.fetchAuditStats as ReturnType<typeof vi.fn>).mockResolvedValue(mockAuditStats);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (auditApi.fetchAuditStats as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAIAuditStats(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (auditApi.fetchAuditStats as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAIAuditStats(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });
  });

  describe('fetching data', () => {
    it('fetches stats on mount', async () => {
      renderHook(() => useAIAuditStats(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(auditApi.fetchAuditStats).toHaveBeenCalledTimes(1);
      });
    });

    it('fetches stats with days parameter', async () => {
      renderHook(() => useAIAuditStats({ days: 14 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(auditApi.fetchAuditStats).toHaveBeenCalledWith(14, undefined);
      });
    });

    it('fetches stats with camera filter', async () => {
      renderHook(() => useAIAuditStats({ days: 7, cameraId: 'cam-1' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(auditApi.fetchAuditStats).toHaveBeenCalledWith(7, 'cam-1');
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useAIAuditStats(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockAuditStats);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useAIAuditStats(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch stats';
      (auditApi.fetchAuditStats as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useAIAuditStats(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useAIAuditStats({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(auditApi.fetchAuditStats).not.toHaveBeenCalled();
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useAIAuditStats(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });
});

// ============================================================================
// useAIAuditLeaderboard Tests
// ============================================================================

describe('useAIAuditLeaderboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auditApi.fetchLeaderboard as ReturnType<typeof vi.fn>).mockResolvedValue(mockLeaderboard);
  });

  it('fetches leaderboard on mount', async () => {
    renderHook(() => useAIAuditLeaderboard(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(auditApi.fetchLeaderboard).toHaveBeenCalledTimes(1);
    });
  });

  it('fetches leaderboard with days parameter', async () => {
    renderHook(() => useAIAuditLeaderboard({ days: 30 }), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(auditApi.fetchLeaderboard).toHaveBeenCalledWith(30);
    });
  });

  it('returns leaderboard data', async () => {
    const { result } = renderHook(() => useAIAuditLeaderboard(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockLeaderboard);
    });
  });

  it('does not fetch when enabled is false', async () => {
    renderHook(() => useAIAuditLeaderboard({ enabled: false }), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(auditApi.fetchLeaderboard).not.toHaveBeenCalled();
  });
});

// ============================================================================
// useAIAuditRecommendations Tests
// ============================================================================

describe('useAIAuditRecommendations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auditApi.fetchRecommendations as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockRecommendations
    );
  });

  it('fetches recommendations on mount', async () => {
    renderHook(() => useAIAuditRecommendations(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(auditApi.fetchRecommendations).toHaveBeenCalledTimes(1);
    });
  });

  it('fetches recommendations with days parameter', async () => {
    renderHook(() => useAIAuditRecommendations({ days: 14 }), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(auditApi.fetchRecommendations).toHaveBeenCalledWith(14);
    });
  });

  it('returns recommendations data', async () => {
    const { result } = renderHook(() => useAIAuditRecommendations(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockRecommendations);
    });
  });
});

// ============================================================================
// useAIAuditEventQuery Tests
// ============================================================================

describe('useAIAuditEventQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auditApi.fetchEventAudit as ReturnType<typeof vi.fn>).mockResolvedValue(mockEventAudit);
  });

  it('fetches event audit by ID', async () => {
    renderHook(() => useAIAuditEventQuery(123), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(auditApi.fetchEventAudit).toHaveBeenCalledWith(123);
    });
  });

  it('returns event audit data', async () => {
    const { result } = renderHook(() => useAIAuditEventQuery(123), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockEventAudit);
    });
  });

  it('does not fetch when eventId is undefined', async () => {
    renderHook(() => useAIAuditEventQuery(undefined), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(auditApi.fetchEventAudit).not.toHaveBeenCalled();
  });

  it('does not fetch when enabled is false', async () => {
    renderHook(() => useAIAuditEventQuery(123, { enabled: false }), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(auditApi.fetchEventAudit).not.toHaveBeenCalled();
  });
});

// ============================================================================
// useAIAuditPromptsQuery Tests
// ============================================================================

describe('useAIAuditPromptsQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (promptApi.fetchAllPrompts as ReturnType<typeof vi.fn>).mockResolvedValue(mockAllPrompts);
  });

  it('fetches all prompts on mount', async () => {
    renderHook(() => useAIAuditPromptsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(promptApi.fetchAllPrompts).toHaveBeenCalledTimes(1);
    });
  });

  it('returns prompts data', async () => {
    const { result } = renderHook(() => useAIAuditPromptsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockAllPrompts);
    });
  });

  it('does not fetch when enabled is false', async () => {
    renderHook(() => useAIAuditPromptsQuery({ enabled: false }), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(promptApi.fetchAllPrompts).not.toHaveBeenCalled();
  });
});

// ============================================================================
// useAIAuditPromptHistoryQuery Tests
// ============================================================================

describe('useAIAuditPromptHistoryQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (promptApi.fetchPromptHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockPromptHistory);
  });

  it('fetches prompt history on mount', async () => {
    renderHook(() => useAIAuditPromptHistoryQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(promptApi.fetchPromptHistory).toHaveBeenCalledTimes(1);
    });
  });

  it('fetches prompt history with model filter', async () => {
    renderHook(() => useAIAuditPromptHistoryQuery({ model: AIModelEnum.NEMOTRON }), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(promptApi.fetchPromptHistory).toHaveBeenCalledWith('nemotron', {
        limit: 50,
        offset: undefined,
        cursor: undefined,
      });
    });
  });

  it('fetches prompt history with pagination', async () => {
    renderHook(() => useAIAuditPromptHistoryQuery({ limit: 10, offset: 20 }), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(promptApi.fetchPromptHistory).toHaveBeenCalledWith(undefined, {
        limit: 10,
        offset: 20,
        cursor: undefined,
      });
    });
  });

  it('fetches prompt history with cursor pagination', async () => {
    renderHook(() => useAIAuditPromptHistoryQuery({ limit: 10, cursor: 'abc123' }), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(promptApi.fetchPromptHistory).toHaveBeenCalledWith(undefined, {
        limit: 10,
        offset: undefined,
        cursor: 'abc123',
      });
    });
  });

  it('returns prompt history data', async () => {
    const { result } = renderHook(() => useAIAuditPromptHistoryQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockPromptHistory);
    });
  });
});

// ============================================================================
// useEvaluateEventMutation Tests
// ============================================================================

describe('useEvaluateEventMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auditApi.triggerEvaluation as ReturnType<typeof vi.fn>).mockResolvedValue(mockEventAudit);
  });

  it('triggers evaluation for an event', async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useEvaluateEventMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.evaluate({ eventId: 123 });
    });

    expect(auditApi.triggerEvaluation).toHaveBeenCalledWith(123, undefined);
  });

  it('triggers evaluation with force flag', async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useEvaluateEventMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.evaluate({ eventId: 123, force: true });
    });

    expect(auditApi.triggerEvaluation).toHaveBeenCalledWith(123, true);
  });

  it('invalidates queries after evaluation', async () => {
    const queryClient = createQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useEvaluateEventMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.evaluate({ eventId: 123 });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.ai.audit.event(123),
    });
  });

  it('tracks loading state', async () => {
    const queryClient = createQueryClient();
    let resolvePromise: (value: EventAudit) => void;
    (auditApi.triggerEvaluation as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise((resolve) => {
        resolvePromise = resolve;
      })
    );

    const { result } = renderHook(() => useEvaluateEventMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    expect(result.current.isLoading).toBe(false);

    act(() => {
      void result.current.evaluate({ eventId: 123 });
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    act(() => {
      resolvePromise!(mockEventAudit);
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });
});

// ============================================================================
// useBatchAuditMutation Tests
// ============================================================================

describe('useBatchAuditMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auditApi.triggerBatchAudit as ReturnType<typeof vi.fn>).mockResolvedValue(mockBatchResponse);
  });

  it('triggers batch audit', async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useBatchAuditMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.triggerBatch({});
    });

    expect(auditApi.triggerBatchAudit).toHaveBeenCalledWith(undefined, undefined, undefined);
  });

  it('triggers batch audit with parameters', async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useBatchAuditMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.triggerBatch({
        limit: 100,
        minRiskScore: 50,
        forceReevaluate: true,
      });
    });

    expect(auditApi.triggerBatchAudit).toHaveBeenCalledWith(100, 50, true);
  });

  it('invalidates audit queries after batch', async () => {
    const queryClient = createQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useBatchAuditMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.triggerBatch({});
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: aiAuditQueryKeys.all,
    });
  });
});

// ============================================================================
// useTestPromptMutation Tests
// ============================================================================

describe('useTestPromptMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (promptApi.testPrompt as ReturnType<typeof vi.fn>).mockResolvedValue(mockTestResult);
  });

  it('tests a prompt', async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useTestPromptMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const testRequest = {
      model: AIModelEnum.NEMOTRON,
      config: { system_prompt: 'Test prompt' },
      event_id: 123,
    };

    await act(async () => {
      await result.current.test(testRequest);
    });

    expect(promptApi.testPrompt).toHaveBeenCalledWith(testRequest);
  });

  it('returns test result', async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useTestPromptMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let testResult: PromptTestResult | undefined;
    await act(async () => {
      testResult = await result.current.test({
        model: AIModelEnum.NEMOTRON,
        config: { system_prompt: 'Test' },
      });
    });

    expect(testResult).toEqual(mockTestResult);
  });
});

// ============================================================================
// useUpdatePromptMutation Tests
// ============================================================================

describe('useUpdatePromptMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (promptApi.updatePromptForModel as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockModelPromptConfig
    );
  });

  it('updates a prompt', async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useUpdatePromptMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.update({
        model: AIModelEnum.NEMOTRON,
        request: {
          config: { system_prompt: 'Updated...' },
          change_description: 'Test change',
        },
      });
    });

    expect(promptApi.updatePromptForModel).toHaveBeenCalledWith('nemotron', {
      config: { system_prompt: 'Updated...' },
      change_description: 'Test change',
    });
  });

  it('invalidates prompt queries after update', async () => {
    const queryClient = createQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useUpdatePromptMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.update({
        model: AIModelEnum.NEMOTRON,
        request: { config: { system_prompt: 'Updated...' } },
      });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.ai.prompts.all,
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.ai.prompts.model('nemotron'),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.ai.prompts.history('nemotron'),
    });
  });
});

// ============================================================================
// useImportPromptsMutation Tests
// ============================================================================

describe('useImportPromptsMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (promptApi.importPrompts as ReturnType<typeof vi.fn>).mockResolvedValue(mockImportResponse);
  });

  it('imports prompts', async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useImportPromptsMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    const importRequest = {
      version: '1.0.0',
      prompts: { nemotron: { system_prompt: 'Imported...' } },
    };

    await act(async () => {
      await result.current.importPrompts(importRequest);
    });

    expect(promptApi.importPrompts).toHaveBeenCalledWith(importRequest);
  });

  it('invalidates prompt queries after import', async () => {
    const queryClient = createQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useImportPromptsMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.importPrompts({
        version: '1.0.0',
        prompts: {},
      });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.ai.prompts.all,
    });
  });
});

// ============================================================================
// useExportPromptsMutation Tests
// ============================================================================

describe('useExportPromptsMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (promptApi.exportPrompts as ReturnType<typeof vi.fn>).mockResolvedValue(mockExportResponse);
  });

  it('exports prompts', async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useExportPromptsMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.exportPrompts();
    });

    expect(promptApi.exportPrompts).toHaveBeenCalledTimes(1);
  });

  it('returns export data', async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useExportPromptsMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    let exportResult: PromptsExportResponse | undefined;
    await act(async () => {
      exportResult = await result.current.exportPrompts();
    });

    expect(exportResult).toEqual(mockExportResponse);
  });

  it('stores export data in mutation result', async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useExportPromptsMutation(), {
      wrapper: createQueryWrapper(queryClient),
    });

    await act(async () => {
      await result.current.exportPrompts();
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockExportResponse);
    });
  });
});
