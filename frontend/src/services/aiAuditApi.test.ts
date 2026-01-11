/**
 * Unit tests for AI Audit API Client
 *
 * Tests all 15 AI Audit API endpoints with comprehensive coverage
 * of success cases, error handling, and edge cases.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  AiAuditApiError,
  getEventAudit,
  evaluateEvent,
  getAuditStats,
  getLeaderboard,
  getRecommendations,
  triggerBatchAudit,
  getAllPrompts,
  testPrompt,
  getPromptsHistory,
  importPrompts,
  exportPrompts,
  getModelPrompt,
  updateModelPrompt,
  getPromptConfig,
  updatePromptConfig,
  type EventAuditResponse,
  type AuditStatsResponse,
  type LeaderboardResponse,
  type RecommendationsResponse,
  type BatchAuditResponse,
  type AllPromptsResponse,
  type PromptTestResponse,
  type AllPromptsHistoryResponse,
  type PromptImportResponse,
  type PromptExportResponse,
  type ModelPromptResponse,
  type PromptUpdateResponse,
  type PromptConfigResponse,
  type ModelContributions,
  type QualityScores,
  type PromptImprovements,
} from './aiAuditApi';

// ============================================================================
// Mock Data
// ============================================================================

const mockModelContributions: ModelContributions = {
  rtdetr: true,
  florence: true,
  clip: false,
  violence: true,
  clothing: false,
  vehicle: true,
  pet: false,
  weather: true,
  image_quality: true,
  zones: false,
  baseline: true,
  cross_camera: false,
};

const mockQualityScores: QualityScores = {
  context_usage: 4,
  reasoning_coherence: 5,
  risk_justification: 4,
  consistency: 3,
  overall: 4,
};

const mockPromptImprovements: PromptImprovements = {
  missing_context: ['time of day context', 'historical patterns'],
  confusing_sections: ['risk threshold guidance'],
  unused_data: ['weather data'],
  format_suggestions: ['structure risk factors as bullet points'],
  model_gaps: ['facial recognition'],
};

const mockEventAudit: EventAuditResponse = {
  id: 1,
  event_id: 42,
  audited_at: '2026-01-01T10:00:00Z',
  is_fully_evaluated: true,
  contributions: mockModelContributions,
  prompt_length: 2500,
  prompt_token_estimate: 625,
  enrichment_utilization: 0.85,
  scores: mockQualityScores,
  consistency_risk_score: 72,
  consistency_diff: 3,
  self_eval_critique: 'The analysis was thorough but missed some temporal patterns.',
  improvements: mockPromptImprovements,
};

const mockAuditStats: AuditStatsResponse = {
  total_events: 150,
  audited_events: 120,
  fully_evaluated_events: 80,
  avg_quality_score: 4.2,
  avg_consistency_rate: 0.92,
  avg_enrichment_utilization: 0.78,
  model_contribution_rates: {
    rtdetr: 1.0,
    florence: 0.85,
    clip: 0.65,
    violence: 0.45,
  },
  audits_by_day: [
    { date: '2026-01-01', count: 15 },
    { date: '2026-01-02', count: 22 },
    { date: '2026-01-03', count: 18 },
  ],
};

const mockLeaderboardResponse: LeaderboardResponse = {
  entries: [
    { model_name: 'rtdetr', contribution_rate: 1.0, quality_correlation: 0.85, event_count: 150 },
    { model_name: 'image_quality', contribution_rate: 0.95, quality_correlation: 0.72, event_count: 142 },
    { model_name: 'weather', contribution_rate: 0.9, quality_correlation: null, event_count: 135 },
  ],
  period_days: 7,
};

const mockRecommendationsResponse: RecommendationsResponse = {
  recommendations: [
    {
      category: 'missing_context',
      suggestion: 'Add time of day context to improve temporal pattern recognition',
      frequency: 45,
      priority: 'high',
    },
    {
      category: 'model_gaps',
      suggestion: 'Consider adding facial recognition for person identification',
      frequency: 32,
      priority: 'medium',
    },
  ],
  total_events_analyzed: 120,
};

const mockBatchAuditResponse: BatchAuditResponse = {
  queued_count: 50,
  message: 'Successfully processed 50 events for audit evaluation',
};

const mockAllPromptsResponse: AllPromptsResponse = {
  prompts: {
    nemotron: {
      model_name: 'nemotron',
      config: { system_prompt: 'You are a security AI...', temperature: 0.7 },
      version: 3,
      updated_at: '2026-01-03T10:30:00Z',
    },
    florence2: {
      model_name: 'florence2',
      config: { vqa_queries: ['What is this?'] },
      version: 1,
      updated_at: '2026-01-01T08:00:00Z',
    },
  },
};

const mockPromptTestResponse: PromptTestResponse = {
  before: {
    score: 65,
    risk_level: 'medium',
    summary: 'Person detected at front door',
  },
  after: {
    score: 45,
    risk_level: 'low',
    summary: 'Delivery person detected at front door',
  },
  improved: true,
  inference_time_ms: 1250,
};

const mockPromptsHistoryResponse: AllPromptsHistoryResponse = {
  nemotron: {
    model_name: 'nemotron',
    versions: [
      {
        version: 3,
        config: { system_prompt: '...', temperature: 0.8 },
        created_at: '2026-01-03T10:30:00Z',
        created_by: 'admin',
        description: 'Added weather context',
      },
      {
        version: 2,
        config: { system_prompt: '...', temperature: 0.7 },
        created_at: '2026-01-02T14:00:00Z',
        created_by: 'system',
        description: null,
      },
    ],
    total_versions: 3,
  },
};

const mockPromptImportResponse: PromptImportResponse = {
  imported_count: 2,
  skipped_count: 1,
  errors: [],
  message: 'Imported 2 model(s), skipped 1 (already exist)',
};

const mockPromptExportResponse: PromptExportResponse = {
  exported_at: '2026-01-03T10:30:00Z',
  version: '1.0',
  prompts: {
    nemotron: { system_prompt: '...', temperature: 0.7 },
    florence2: { vqa_queries: ['What is this?'] },
  },
};

const mockModelPromptResponse: ModelPromptResponse = {
  model_name: 'nemotron',
  config: { system_prompt: '...', temperature: 0.7 },
  version: 3,
  updated_at: '2026-01-03T10:30:00Z',
};

const mockPromptUpdateResponse: PromptUpdateResponse = {
  model_name: 'nemotron',
  version: 4,
  message: 'Configuration updated to version 4',
  config: { system_prompt: 'Updated...', temperature: 0.8 },
};

const mockPromptConfigResponse: PromptConfigResponse = {
  model: 'nemotron',
  systemPrompt: 'You are a home security AI assistant...',
  temperature: 0.7,
  maxTokens: 2048,
  version: 3,
  updatedAt: '2026-01-03T10:30:00Z',
};

// ============================================================================
// Helper Functions
// ============================================================================

function createMockResponse<T>(data: T, status = 200, statusText = 'OK'): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    json: () => Promise.resolve(data),
    headers: new Headers({ 'Content-Type': 'application/json' }),
  } as Response;
}

function createMockErrorResponse(status: number, statusText: string, detail?: string): Response {
  const errorBody = detail ? { detail } : null;
  return {
    ok: false,
    status,
    statusText,
    json: () => Promise.resolve(errorBody),
    headers: new Headers({ 'Content-Type': 'application/json' }),
  } as Response;
}

// ============================================================================
// AiAuditApiError Tests
// ============================================================================

describe('AiAuditApiError', () => {
  it('creates an error with status and message', () => {
    const error = new AiAuditApiError(404, 'Not Found');
    expect(error.name).toBe('AiAuditApiError');
    expect(error.status).toBe(404);
    expect(error.message).toBe('Not Found');
    expect(error.data).toBeUndefined();
  });

  it('creates an error with additional data', () => {
    const data = { field: 'event_id', reason: 'invalid' };
    const error = new AiAuditApiError(400, 'Bad Request', data);
    expect(error.status).toBe(400);
    expect(error.message).toBe('Bad Request');
    expect(error.data).toEqual(data);
  });

  it('extends Error properly', () => {
    const error = new AiAuditApiError(500, 'Server Error');
    expect(error instanceof Error).toBe(true);
    expect(error instanceof AiAuditApiError).toBe(true);
  });
});

// ============================================================================
// Endpoint 1: getEventAudit Tests
// ============================================================================

describe('getEventAudit', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches event audit successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventAudit));

    const result = await getEventAudit(42);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/events/42', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockEventAudit);
    expect(result.event_id).toBe(42);
  });

  it('returns all audit fields correctly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventAudit));

    const result = await getEventAudit(42);

    expect(result.contributions.rtdetr).toBe(true);
    expect(result.scores.overall).toBe(4);
    expect(result.improvements.missing_context).toContain('time of day context');
  });

  it('throws AiAuditApiError on 404 not found', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(404, 'Not Found', 'Event audit not found')
    );

    await expect(getEventAudit(999)).rejects.toThrow(AiAuditApiError);
    await expect(getEventAudit(999)).rejects.toMatchObject({
      status: 404,
      message: 'Event audit not found',
    });
  });

  it('throws AiAuditApiError on network error', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Network failure'));

    await expect(getEventAudit(42)).rejects.toThrow(AiAuditApiError);
    await expect(getEventAudit(42)).rejects.toMatchObject({
      status: 0,
      message: 'Network failure',
    });
  });
});

// ============================================================================
// Endpoint 2: evaluateEvent Tests
// ============================================================================

describe('evaluateEvent', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('triggers evaluation without force parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventAudit));

    const result = await evaluateEvent(42);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/events/42/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockEventAudit);
  });

  it('triggers evaluation with force=true', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventAudit));

    await evaluateEvent(42, true);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/events/42/evaluate?force=true', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('triggers evaluation with force=false (no query param)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventAudit));

    await evaluateEvent(42, false);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/events/42/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('throws AiAuditApiError on 404 not found', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(404, 'Not Found', 'Event not found')
    );

    await expect(evaluateEvent(999)).rejects.toThrow(AiAuditApiError);
  });
});

// ============================================================================
// Endpoint 3: getAuditStats Tests
// ============================================================================

describe('getAuditStats', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches audit stats without parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    const result = await getAuditStats();

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/stats', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockAuditStats);
  });

  it('fetches audit stats with days parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    await getAuditStats(14);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/stats?days=14', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('fetches audit stats with camera_id parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    await getAuditStats(undefined, 'front-door');

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/stats?camera_id=front-door', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('fetches audit stats with both parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    await getAuditStats(30, 'backyard');

    const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(calledUrl).toContain('days=30');
    expect(calledUrl).toContain('camera_id=backyard');
  });
});

// ============================================================================
// Endpoint 4: getLeaderboard Tests
// ============================================================================

describe('getLeaderboard', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches leaderboard without parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLeaderboardResponse));

    const result = await getLeaderboard();

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/leaderboard', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockLeaderboardResponse);
  });

  it('fetches leaderboard with days parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLeaderboardResponse));

    await getLeaderboard(30);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/leaderboard?days=30', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('handles entries with null quality_correlation', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLeaderboardResponse));

    const result = await getLeaderboard();

    const weatherEntry = result.entries.find((e) => e.model_name === 'weather');
    expect(weatherEntry?.quality_correlation).toBeNull();
  });
});

// ============================================================================
// Endpoint 5: getRecommendations Tests
// ============================================================================

describe('getRecommendations', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches recommendations without parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockRecommendationsResponse));

    const result = await getRecommendations();

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/recommendations', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockRecommendationsResponse);
  });

  it('fetches recommendations with days parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockRecommendationsResponse));

    await getRecommendations(14);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/recommendations?days=14', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('returns prioritized recommendations', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockRecommendationsResponse));

    const result = await getRecommendations();

    const highPriority = result.recommendations.filter((r) => r.priority === 'high');
    expect(highPriority).toHaveLength(1);
  });
});

// ============================================================================
// Endpoint 6: triggerBatchAudit Tests
// ============================================================================

describe('triggerBatchAudit', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('triggers batch audit without parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockBatchAuditResponse));

    const result = await triggerBatchAudit();

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/batch', {
      method: 'POST',
      body: JSON.stringify({}),
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockBatchAuditResponse);
  });

  it('triggers batch audit with all parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockBatchAuditResponse));

    await triggerBatchAudit({
      limit: 200,
      min_risk_score: 75,
      force_reevaluate: true,
    });

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/batch', {
      method: 'POST',
      body: JSON.stringify({ limit: 200, min_risk_score: 75, force_reevaluate: true }),
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('handles zero events queued', async () => {
    const noEventsResponse: BatchAuditResponse = {
      queued_count: 0,
      message: 'No events found matching criteria',
    };

    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(noEventsResponse));

    const result = await triggerBatchAudit();

    expect(result.queued_count).toBe(0);
  });
});

// ============================================================================
// Endpoint 7: getAllPrompts Tests
// ============================================================================

describe('getAllPrompts', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches all prompts successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAllPromptsResponse));

    const result = await getAllPrompts();

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/prompts', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockAllPromptsResponse);
    expect(result.prompts.nemotron.version).toBe(3);
  });
});

// ============================================================================
// Endpoint 8: testPrompt Tests
// ============================================================================

describe('testPrompt', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('tests prompt configuration successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockPromptTestResponse));

    const result = await testPrompt({
      model: 'nemotron',
      config: { system_prompt: 'Test prompt', temperature: 0.8 },
      event_id: 12345,
    });

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/prompts/test', {
      method: 'POST',
      body: JSON.stringify({
        model: 'nemotron',
        config: { system_prompt: 'Test prompt', temperature: 0.8 },
        event_id: 12345,
      }),
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.improved).toBe(true);
    expect(result.before.score).toBe(65);
    expect(result.after.score).toBe(45);
  });

  it('throws on invalid model', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(404, 'Not Found', 'Model not found')
    );

    await expect(
      testPrompt({
        model: 'nemotron',
        config: {},
        event_id: 12345,
      })
    ).rejects.toThrow(AiAuditApiError);
  });
});

// ============================================================================
// Endpoint 9: getPromptsHistory Tests
// ============================================================================

describe('getPromptsHistory', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches prompt history without parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockPromptsHistoryResponse));

    const result = await getPromptsHistory();

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/prompts/history', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.nemotron.total_versions).toBe(3);
  });

  it('fetches prompt history with limit parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockPromptsHistoryResponse));

    await getPromptsHistory(20);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/prompts/history?limit=20', {
      headers: { 'Content-Type': 'application/json' },
    });
  });
});

// ============================================================================
// Endpoint 10: importPrompts Tests
// ============================================================================

describe('importPrompts', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('imports prompts successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockPromptImportResponse));

    const result = await importPrompts({
      prompts: {
        nemotron: { system_prompt: '...', temperature: 0.7 },
      },
      overwrite: true,
    });

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/prompts/import', {
      method: 'POST',
      body: JSON.stringify({
        prompts: { nemotron: { system_prompt: '...', temperature: 0.7 } },
        overwrite: true,
      }),
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.imported_count).toBe(2);
  });

  it('throws on empty prompts', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(400, 'Bad Request', 'No prompts provided for import')
    );

    await expect(
      importPrompts({ prompts: {} })
    ).rejects.toMatchObject({
      status: 400,
      message: 'No prompts provided for import',
    });
  });
});

// ============================================================================
// Endpoint 11: exportPrompts Tests
// ============================================================================

describe('exportPrompts', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('exports prompts successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockPromptExportResponse));

    const result = await exportPrompts();

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/prompts/export', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.version).toBe('1.0');
    expect(result.prompts).toHaveProperty('nemotron');
  });
});

// ============================================================================
// Endpoint 12: getModelPrompt Tests
// ============================================================================

describe('getModelPrompt', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches model prompt successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockModelPromptResponse));

    const result = await getModelPrompt('nemotron');

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/prompts/nemotron', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.model_name).toBe('nemotron');
    expect(result.version).toBe(3);
  });

  it('throws on invalid model', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(404, 'Not Found', 'Model not found')
    );

    await expect(getModelPrompt('nemotron')).rejects.toMatchObject({
      status: 404,
    });
  });
});

// ============================================================================
// Endpoint 13: updateModelPrompt Tests
// ============================================================================

describe('updateModelPrompt', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('updates model prompt successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockPromptUpdateResponse));

    const result = await updateModelPrompt('nemotron', {
      config: { system_prompt: 'Updated...', temperature: 0.8 },
      description: 'Added weather context',
    });

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/prompts/nemotron', {
      method: 'PUT',
      body: JSON.stringify({
        config: { system_prompt: 'Updated...', temperature: 0.8 },
        description: 'Added weather context',
      }),
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.version).toBe(4);
    expect(result.message).toContain('version 4');
  });

  it('throws on invalid configuration', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(400, 'Bad Request', 'Invalid configuration')
    );

    await expect(
      updateModelPrompt('nemotron', { config: {} })
    ).rejects.toMatchObject({
      status: 400,
    });
  });
});

// ============================================================================
// Endpoint 14: getPromptConfig Tests
// ============================================================================

describe('getPromptConfig', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches prompt config successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockPromptConfigResponse));

    const result = await getPromptConfig('nemotron');

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/prompt-config/nemotron', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.model).toBe('nemotron');
    expect(result.temperature).toBe(0.7);
    expect(result.maxTokens).toBe(2048);
  });

  it('throws on model not found', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(404, 'Not Found', "No configuration found for model 'invalid'")
    );

    await expect(getPromptConfig('nemotron')).rejects.toMatchObject({
      status: 404,
    });
  });
});

// ============================================================================
// Endpoint 15: updatePromptConfig Tests
// ============================================================================

describe('updatePromptConfig', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('updates prompt config successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockPromptConfigResponse));

    const result = await updatePromptConfig('nemotron', {
      systemPrompt: 'You are a home security AI assistant...',
      temperature: 0.7,
      maxTokens: 2048,
    });

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/prompt-config/nemotron', {
      method: 'PUT',
      body: JSON.stringify({
        systemPrompt: 'You are a home security AI assistant...',
        temperature: 0.7,
        maxTokens: 2048,
      }),
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.version).toBe(3);
  });

  it('creates new config if not exists', async () => {
    const newConfig: PromptConfigResponse = {
      ...mockPromptConfigResponse,
      version: 1,
    };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(newConfig));

    const result = await updatePromptConfig('florence-2', {
      systemPrompt: 'New config...',
      temperature: 0.5,
      maxTokens: 1024,
    });

    expect(result.version).toBe(1);
  });
});

// ============================================================================
// Error Handling Tests
// ============================================================================

describe('Error Handling', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('handles error response with string body', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.resolve('Simple error message'),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    await expect(getEventAudit(42)).rejects.toMatchObject({
      status: 400,
      message: 'Simple error message',
    });
  });

  it('handles error response with non-JSON body', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.reject(new Error('Not JSON')),
      headers: new Headers({ 'Content-Type': 'text/html' }),
    } as Response);

    await expect(getEventAudit(42)).rejects.toMatchObject({
      status: 500,
      message: 'HTTP 500: Internal Server Error',
    });
  });

  it('handles network timeout', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Request timeout'));

    await expect(getEventAudit(42)).rejects.toMatchObject({
      status: 0,
      message: 'Request timeout',
    });
  });

  it('handles fetch rejection with non-Error object', async () => {
    vi.mocked(fetch).mockRejectedValue('String error');

    await expect(getEventAudit(42)).rejects.toMatchObject({
      status: 0,
      message: 'Network request failed',
    });
  });

  it('handles JSON parse error', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: () => Promise.reject(new Error('Invalid JSON')),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    await expect(getEventAudit(42)).rejects.toMatchObject({
      status: 200,
      message: 'Failed to parse response JSON',
    });
  });

  it('preserves AiAuditApiError when re-thrown', async () => {
    const originalError = new AiAuditApiError(404, 'Not found', { id: 42 });
    vi.mocked(fetch).mockRejectedValue(originalError);

    await expect(getEventAudit(42)).rejects.toMatchObject({
      status: 404,
      message: 'Not found',
      data: { id: 42 },
    });
  });
});

// ============================================================================
// Query Parameter Edge Cases
// ============================================================================

describe('Query Parameter Edge Cases', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('handles days=0 parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    await getAuditStats(0);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/stats?days=0', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('handles empty camera_id (falsy)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    await getAuditStats(7, '');

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/stats?days=7', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('handles min_risk_score=0 in batch audit', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockBatchAuditResponse));

    await triggerBatchAudit({ min_risk_score: 0 });

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/batch', {
      method: 'POST',
      body: JSON.stringify({ min_risk_score: 0 }),
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('handles force_reevaluate=false explicitly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockBatchAuditResponse));

    await triggerBatchAudit({ force_reevaluate: false });

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/batch', {
      method: 'POST',
      body: JSON.stringify({ force_reevaluate: false }),
      headers: { 'Content-Type': 'application/json' },
    });
  });
});
