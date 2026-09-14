import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  AuditApiError,
  fetchEventAudit,
  triggerEvaluation,
  fetchAuditStats,
  fetchLeaderboard,
  fetchRecommendations,
  triggerBatchAudit,
  type EventAudit,
  type AuditStats,
  type LeaderboardResponse,
  type RecommendationsResponse,
  type BatchAuditResponse,
  type ModelContributions,
  type QualityScores,
  type PromptImprovements,
} from './auditApi';

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

const mockEventAudit: EventAudit = {
  id: 1,
  event_id: 42,
  audited_at: '2025-01-01T10:00:00Z',
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

const mockAuditStats: AuditStats = {
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
    clothing: 0.3,
    vehicle: 0.55,
    pet: 0.2,
    weather: 0.9,
    image_quality: 0.95,
    zones: 0.4,
    baseline: 0.75,
    cross_camera: 0.25,
  },
  audits_by_day: [
    { date: '2025-01-01', count: 15 },
    { date: '2025-01-02', count: 22 },
    { date: '2025-01-03', count: 18 },
  ],
};

const mockLeaderboardResponse: LeaderboardResponse = {
  entries: [
    { model_name: 'rtdetr', contribution_rate: 1.0, quality_correlation: 0.85, event_count: 150 },
    {
      model_name: 'image_quality',
      contribution_rate: 0.95,
      quality_correlation: 0.72,
      event_count: 142,
    },
    { model_name: 'weather', contribution_rate: 0.9, quality_correlation: null, event_count: 135 },
    {
      model_name: 'florence',
      contribution_rate: 0.85,
      quality_correlation: 0.65,
      event_count: 127,
    },
    {
      model_name: 'baseline',
      contribution_rate: 0.75,
      quality_correlation: 0.58,
      event_count: 112,
    },
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
    {
      category: 'format_suggestions',
      suggestion: 'Structure risk factors as bullet points for clarity',
      frequency: 28,
      priority: 'low',
    },
  ],
  total_events_analyzed: 120,
};

const mockBatchAuditResponse: BatchAuditResponse = {
  queued_count: 50,
  message: 'Successfully queued 50 events for audit processing',
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
// AuditApiError Tests
// ============================================================================

describe('AuditApiError', () => {
  it('creates an error with status and message', () => {
    const error = new AuditApiError(404, 'Not Found');
    expect(error.name).toBe('AuditApiError');
    expect(error.status).toBe(404);
    expect(error.message).toBe('Not Found');
    expect(error.data).toBeUndefined();
  });

  it('creates an error with additional data', () => {
    const data = { field: 'event_id', reason: 'invalid' };
    const error = new AuditApiError(400, 'Bad Request', data);
    expect(error.status).toBe(400);
    expect(error.message).toBe('Bad Request');
    expect(error.data).toEqual(data);
  });

  it('extends Error properly', () => {
    const error = new AuditApiError(500, 'Server Error');
    expect(error instanceof Error).toBe(true);
    expect(error instanceof AuditApiError).toBe(true);
  });
});

// ============================================================================
// fetchEventAudit Tests
// ============================================================================

describe('fetchEventAudit', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches event audit successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventAudit));

    const result = await fetchEventAudit(42);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/events/42', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockEventAudit);
    expect(result.event_id).toBe(42);
    expect(result.is_fully_evaluated).toBe(true);
  });

  it('returns all audit fields correctly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventAudit));

    const result = await fetchEventAudit(42);

    // Check model contributions
    expect(result.contributions.rtdetr).toBe(true);
    expect(result.contributions.clip).toBe(false);

    // Check quality scores
    expect(result.scores.overall).toBe(4);
    expect(result.scores.context_usage).toBe(4);

    // Check prompt improvements
    expect(result.improvements.missing_context).toContain('time of day context');
    expect(result.improvements.model_gaps).toContain('facial recognition');
  });

  it('handles audit with null scores (not yet evaluated)', async () => {
    const partialAudit: EventAudit = {
      ...mockEventAudit,
      is_fully_evaluated: false,
      scores: {
        context_usage: null,
        reasoning_coherence: null,
        risk_justification: null,
        consistency: null,
        overall: null,
      },
      consistency_risk_score: null,
      consistency_diff: null,
      self_eval_critique: null,
    };

    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(partialAudit));

    const result = await fetchEventAudit(42);

    expect(result.is_fully_evaluated).toBe(false);
    expect(result.scores.overall).toBeNull();
    expect(result.consistency_risk_score).toBeNull();
  });

  it('throws AuditApiError on 404 not found', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(404, 'Not Found', 'Event audit not found')
    );

    await expect(fetchEventAudit(999)).rejects.toThrow(AuditApiError);
    await expect(fetchEventAudit(999)).rejects.toMatchObject({
      status: 404,
      message: 'Event audit not found',
    });
  });

  it('throws AuditApiError on network error', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Network failure'));

    await expect(fetchEventAudit(42)).rejects.toThrow(AuditApiError);
    await expect(fetchEventAudit(42)).rejects.toMatchObject({
      status: 0,
      message: 'Network failure',
    });
  });

  it('throws AuditApiError on server error', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(500, 'Internal Server Error', 'Database connection failed')
    );

    await expect(fetchEventAudit(42)).rejects.toThrow(AuditApiError);
    await expect(fetchEventAudit(42)).rejects.toMatchObject({
      status: 500,
      message: 'Database connection failed',
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

    await expect(fetchEventAudit(42)).rejects.toThrow(AuditApiError);
    await expect(fetchEventAudit(42)).rejects.toMatchObject({
      status: 200,
      message: 'Failed to parse response JSON',
    });
  });
});

// ============================================================================
// triggerEvaluation Tests
// ============================================================================

describe('triggerEvaluation', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('triggers evaluation without force parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventAudit));

    const result = await triggerEvaluation(42);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/events/42/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockEventAudit);
  });

  it('triggers evaluation with force=true', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventAudit));

    const result = await triggerEvaluation(42, true);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/events/42/evaluate?force=true', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockEventAudit);
  });

  it('triggers evaluation with force=false (no query param)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockEventAudit));

    await triggerEvaluation(42, false);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/events/42/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('returns updated audit after evaluation', async () => {
    const evaluatedAudit: EventAudit = {
      ...mockEventAudit,
      is_fully_evaluated: true,
      scores: {
        context_usage: 5,
        reasoning_coherence: 4,
        risk_justification: 5,
        consistency: 4,
        overall: 4.5,
      },
    };

    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(evaluatedAudit));

    const result = await triggerEvaluation(42);

    expect(result.is_fully_evaluated).toBe(true);
    expect(result.scores.overall).toBe(4.5);
  });

  it('throws AuditApiError on 404 not found', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(404, 'Not Found', 'Event not found')
    );

    await expect(triggerEvaluation(999)).rejects.toThrow(AuditApiError);
    await expect(triggerEvaluation(999)).rejects.toMatchObject({
      status: 404,
      message: 'Event not found',
    });
  });

  it('throws AuditApiError on 503 service unavailable', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(503, 'Service Unavailable', 'LLM service is busy')
    );

    await expect(triggerEvaluation(42)).rejects.toThrow(AuditApiError);
    await expect(triggerEvaluation(42)).rejects.toMatchObject({
      status: 503,
      message: 'LLM service is busy',
    });
  });
});

// ============================================================================
// fetchAuditStats Tests
// ============================================================================

describe('fetchAuditStats', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches audit stats without parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    const result = await fetchAuditStats();

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/stats', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockAuditStats);
  });

  it('fetches audit stats with days parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    await fetchAuditStats(14);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/stats?days=14', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('fetches audit stats with camera_id parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    await fetchAuditStats(undefined, 'front-door');

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/stats?camera_id=front-door', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('fetches audit stats with both parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    await fetchAuditStats(30, 'backyard');

    const calledUrl = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(calledUrl).toContain('days=30');
    expect(calledUrl).toContain('camera_id=backyard');
  });

  it('returns all stats fields correctly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    const result = await fetchAuditStats();

    expect(result.total_events).toBe(150);
    expect(result.audited_events).toBe(120);
    expect(result.fully_evaluated_events).toBe(80);
    expect(result.avg_quality_score).toBe(4.2);
    expect(result.avg_consistency_rate).toBe(0.92);
    expect(result.model_contribution_rates.rtdetr).toBe(1.0);
    expect(result.audits_by_day).toHaveLength(3);
  });

  it('handles stats with null averages', async () => {
    const statsWithNulls: AuditStats = {
      ...mockAuditStats,
      avg_quality_score: null,
      avg_consistency_rate: null,
      avg_enrichment_utilization: null,
    };

    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(statsWithNulls));

    const result = await fetchAuditStats();

    expect(result.avg_quality_score).toBeNull();
    expect(result.avg_consistency_rate).toBeNull();
  });

  it('throws AuditApiError on server error', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(500, 'Internal Server Error', 'Database query failed')
    );

    await expect(fetchAuditStats()).rejects.toThrow(AuditApiError);
    await expect(fetchAuditStats()).rejects.toMatchObject({
      status: 500,
      message: 'Database query failed',
    });
  });
});

// ============================================================================
// fetchLeaderboard Tests
// ============================================================================

describe('fetchLeaderboard', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches leaderboard without parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLeaderboardResponse));

    const result = await fetchLeaderboard();

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/leaderboard', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockLeaderboardResponse);
  });

  it('fetches leaderboard with days parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLeaderboardResponse));

    await fetchLeaderboard(30);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/leaderboard?days=30', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('returns ranked entries correctly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLeaderboardResponse));

    const result = await fetchLeaderboard();

    expect(result.entries).toHaveLength(5);
    expect(result.entries[0].model_name).toBe('rtdetr');
    expect(result.entries[0].contribution_rate).toBe(1.0);
    expect(result.entries[0].quality_correlation).toBe(0.85);
    expect(result.entries[0].event_count).toBe(150);
    expect(result.period_days).toBe(7);
  });

  it('handles entries with null quality_correlation', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLeaderboardResponse));

    const result = await fetchLeaderboard();

    const weatherEntry = result.entries.find((e) => e.model_name === 'weather');
    expect(weatherEntry?.quality_correlation).toBeNull();
  });

  it('handles empty leaderboard', async () => {
    const emptyLeaderboard: LeaderboardResponse = {
      entries: [],
      period_days: 7,
    };

    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(emptyLeaderboard));

    const result = await fetchLeaderboard();

    expect(result.entries).toEqual([]);
    expect(result.period_days).toBe(7);
  });

  it('throws AuditApiError on server error', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(500, 'Internal Server Error', 'Failed to compute leaderboard')
    );

    await expect(fetchLeaderboard()).rejects.toThrow(AuditApiError);
    await expect(fetchLeaderboard()).rejects.toMatchObject({
      status: 500,
      message: 'Failed to compute leaderboard',
    });
  });
});

// ============================================================================
// fetchRecommendations Tests
// ============================================================================

describe('fetchRecommendations', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches recommendations without parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockRecommendationsResponse));

    const result = await fetchRecommendations();

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/recommendations', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockRecommendationsResponse);
  });

  it('fetches recommendations with days parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockRecommendationsResponse));

    await fetchRecommendations(14);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/recommendations?days=14', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('returns prioritized recommendations correctly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockRecommendationsResponse));

    const result = await fetchRecommendations();

    expect(result.recommendations).toHaveLength(3);
    expect(result.total_events_analyzed).toBe(120);

    const highPriority = result.recommendations.filter((r) => r.priority === 'high');
    expect(highPriority).toHaveLength(1);
    expect(highPriority[0].category).toBe('missing_context');
  });

  it('handles all priority levels', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockRecommendationsResponse));

    const result = await fetchRecommendations();

    const priorities = result.recommendations.map((r) => r.priority);
    expect(priorities).toContain('high');
    expect(priorities).toContain('medium');
    expect(priorities).toContain('low');
  });

  it('handles empty recommendations', async () => {
    const emptyRecommendations: RecommendationsResponse = {
      recommendations: [],
      total_events_analyzed: 0,
    };

    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(emptyRecommendations));

    const result = await fetchRecommendations();

    expect(result.recommendations).toEqual([]);
    expect(result.total_events_analyzed).toBe(0);
  });

  it('throws AuditApiError on server error', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(500, 'Internal Server Error', 'Failed to aggregate recommendations')
    );

    await expect(fetchRecommendations()).rejects.toThrow(AuditApiError);
    await expect(fetchRecommendations()).rejects.toMatchObject({
      status: 500,
      message: 'Failed to aggregate recommendations',
    });
  });
});

// ============================================================================
// triggerBatchAudit Tests
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

  it('triggers batch audit with limit parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockBatchAuditResponse));

    await triggerBatchAudit(100);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/batch', {
      method: 'POST',
      body: JSON.stringify({ limit: 100 }),
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('triggers batch audit with minRiskScore parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockBatchAuditResponse));

    await triggerBatchAudit(undefined, 50);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/batch', {
      method: 'POST',
      body: JSON.stringify({ min_risk_score: 50 }),
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('triggers batch audit with forceReevaluate parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockBatchAuditResponse));

    await triggerBatchAudit(undefined, undefined, true);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/batch', {
      method: 'POST',
      body: JSON.stringify({ force_reevaluate: true }),
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('triggers batch audit with all parameters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockBatchAuditResponse));

    await triggerBatchAudit(200, 75, true);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/batch', {
      method: 'POST',
      body: JSON.stringify({ limit: 200, min_risk_score: 75, force_reevaluate: true }),
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('returns batch response correctly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockBatchAuditResponse));

    const result = await triggerBatchAudit();

    expect(result.queued_count).toBe(50);
    expect(result.message).toBe('Successfully queued 50 events for audit processing');
  });

  it('handles zero events queued', async () => {
    const noEventsResponse: BatchAuditResponse = {
      queued_count: 0,
      message: 'No events match the specified criteria',
    };

    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(noEventsResponse));

    const result = await triggerBatchAudit();

    expect(result.queued_count).toBe(0);
  });

  it('throws AuditApiError on 400 validation error', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(400, 'Bad Request', 'limit must be between 1 and 1000')
    );

    await expect(triggerBatchAudit(5000)).rejects.toThrow(AuditApiError);
    await expect(triggerBatchAudit(5000)).rejects.toMatchObject({
      status: 400,
      message: 'limit must be between 1 and 1000',
    });
  });

  it('throws AuditApiError on 503 service unavailable', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(503, 'Service Unavailable', 'LLM service is overloaded')
    );

    await expect(triggerBatchAudit()).rejects.toThrow(AuditApiError);
    await expect(triggerBatchAudit()).rejects.toMatchObject({
      status: 503,
      message: 'LLM service is overloaded',
    });
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

    await expect(fetchEventAudit(42)).rejects.toThrow(AuditApiError);
    await expect(fetchEventAudit(42)).rejects.toMatchObject({
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

    await expect(fetchEventAudit(42)).rejects.toThrow(AuditApiError);
    await expect(fetchEventAudit(42)).rejects.toMatchObject({
      status: 500,
      message: 'HTTP 500: Internal Server Error',
    });
  });

  it('handles network timeout', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Request timeout'));

    await expect(fetchEventAudit(42)).rejects.toThrow(AuditApiError);
    await expect(fetchEventAudit(42)).rejects.toMatchObject({
      status: 0,
      message: 'Request timeout',
    });
  });

  it('handles fetch rejection with non-Error object', async () => {
    vi.mocked(fetch).mockRejectedValue('String error');

    await expect(fetchEventAudit(42)).rejects.toThrow(AuditApiError);
    await expect(fetchEventAudit(42)).rejects.toMatchObject({
      status: 0,
      message: 'Network request failed',
    });
  });

  it('handles 401 unauthorized', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(401, 'Unauthorized', 'Invalid API key')
    );

    await expect(fetchAuditStats()).rejects.toThrow(AuditApiError);
    await expect(fetchAuditStats()).rejects.toMatchObject({
      status: 401,
      message: 'Invalid API key',
    });
  });

  it('handles 403 forbidden', async () => {
    vi.mocked(fetch).mockResolvedValue(createMockErrorResponse(403, 'Forbidden', 'Access denied'));

    await expect(fetchLeaderboard()).rejects.toThrow(AuditApiError);
    await expect(fetchLeaderboard()).rejects.toMatchObject({
      status: 403,
      message: 'Access denied',
    });
  });

  it('handles error with structured data', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      json: () =>
        Promise.resolve({
          detail: 'Validation failed',
          errors: [{ field: 'days', message: 'must be positive' }],
        }),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    try {
      await fetchAuditStats(-1);
    } catch (error) {
      expect(error).toBeInstanceOf(AuditApiError);
      const auditError = error as AuditApiError;
      expect(auditError.status).toBe(422);
      expect(auditError.message).toBe('Validation failed');
      expect(auditError.data).toHaveProperty('errors');
    }
  });

  it('preserves AuditApiError when re-thrown', async () => {
    const originalError = new AuditApiError(404, 'Not found', { id: 42 });
    vi.mocked(fetch).mockRejectedValue(originalError);

    await expect(fetchEventAudit(42)).rejects.toThrow(AuditApiError);
    await expect(fetchEventAudit(42)).rejects.toMatchObject({
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

    await fetchAuditStats(0);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/stats?days=0', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('handles large days parameter', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    await fetchAuditStats(90);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/stats?days=90', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('handles camera_id with special characters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    await fetchAuditStats(undefined, 'front-door-cam-1');

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/stats?camera_id=front-door-cam-1', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('handles empty camera_id (falsy)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockAuditStats));

    await fetchAuditStats(7, '');

    // Empty string should not be added to query params
    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/stats?days=7', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('handles minRiskScore=0 in batch audit', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockBatchAuditResponse));

    await triggerBatchAudit(undefined, 0);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/batch', {
      method: 'POST',
      body: JSON.stringify({ min_risk_score: 0 }),
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('handles forceReevaluate=false explicitly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockBatchAuditResponse));

    await triggerBatchAudit(undefined, undefined, false);

    expect(fetch).toHaveBeenCalledWith('/api/ai-audit/batch', {
      method: 'POST',
      body: JSON.stringify({ force_reevaluate: false }),
      headers: { 'Content-Type': 'application/json' },
    });
  });
});
