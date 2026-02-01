/**
 * Unit tests for Model Zoo API Client
 *
 * Tests all Model Zoo API endpoints with comprehensive coverage
 * of success cases, error handling, and edge cases.
 *
 * TDD RED PHASE: These tests will fail until the backend is implemented.
 *
 * @see NEM-4788
 * @see docs/plans/2025-01-31-model-zoo-management-design.md
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  ModelZooApiError,
  listModels,
  getVRAMSummary,
  loadModel,
  unloadModel,
  reloadModel,
  unloadAllModels,
  type ModelListResponse,
  type VRAMSummaryResponse,
  type LoadModelResponse,
  type UnloadModelResponse,
  type UnloadAllResponse,
  type ModelStatus,
  type GpuVRAMInfo,
} from './modelZooApi';

// ============================================================================
// Mock Data
// ============================================================================

const mockModelLoaded: ModelStatus = {
  name: 'threat-detection-yolov8n',
  category: 'detection',
  estimated_vram_mb: 300,
  enabled: true,
  service: 'ai-enrichment-light',
  gpu_id: 1,
  runtime: {
    loaded: true,
    actual_vram_mb: 287,
    last_used: '2026-01-31T10:30:00Z',
    load_count: 5,
  },
};

const mockModelUnloaded: ModelStatus = {
  name: 'vehicle-segment-classification',
  category: 'classification',
  estimated_vram_mb: 1500,
  enabled: true,
  service: 'ai-enrichment',
  gpu_id: 0,
  runtime: {
    loaded: false,
    actual_vram_mb: null,
    last_used: null,
    load_count: 0,
  },
};

const mockModelDisabled: ModelStatus = {
  name: 'fashion-clip',
  category: 'classification',
  estimated_vram_mb: 800,
  enabled: false,
  service: 'ai-enrichment',
  gpu_id: 0,
  runtime: null,
};

const mockModelListResponse: ModelListResponse = {
  models: [mockModelLoaded, mockModelUnloaded, mockModelDisabled],
  service_status: {
    'ai-enrichment': 'healthy',
    'ai-enrichment-light': 'healthy',
  },
};

const mockGpuVRAMInfo0: GpuVRAMInfo = {
  gpu_id: 0,
  service: 'ai-enrichment',
  budget_mb: 6800,
  used_mb: 2100,
  available_mb: 4700,
  utilization_percent: 30.9,
  loaded_models: ['fashion-clip', 'vehicle-segment-classification'],
};

const mockGpuVRAMInfo1: GpuVRAMInfo = {
  gpu_id: 1,
  service: 'ai-enrichment-light',
  budget_mb: 1200,
  used_mb: 450,
  available_mb: 750,
  utilization_percent: 37.5,
  loaded_models: ['threat-detection-yolov8n', 'osnet-x0-25'],
};

const mockVRAMSummaryResponse: VRAMSummaryResponse = {
  gpus: [mockGpuVRAMInfo0, mockGpuVRAMInfo1],
  totals: {
    budget_mb: 8000,
    used_mb: 2550,
    available_mb: 5450,
    model_count: 4,
  },
};

const mockLoadModelResponse: LoadModelResponse = {
  success: true,
  model_name: 'threat-detection-yolov8n',
  service: 'ai-enrichment-light',
  gpu_id: 1,
  load_time_ms: 1250,
  vram_mb: 287,
};

const mockUnloadModelResponse: UnloadModelResponse = {
  success: true,
  model_name: 'threat-detection-yolov8n',
  freed_vram_mb: 287,
};

const mockUnloadAllResponse: UnloadAllResponse = {
  success: true,
  unloaded_count: 4,
  total_freed_vram_mb: 2550,
  errors: [],
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
// ModelZooApiError Tests
// ============================================================================

describe('ModelZooApiError', () => {
  it('creates an error with status and message', () => {
    const error = new ModelZooApiError(404, 'Model not found');
    expect(error.name).toBe('ModelZooApiError');
    expect(error.status).toBe(404);
    expect(error.message).toBe('Model not found');
    expect(error.data).toBeUndefined();
  });

  it('creates an error with additional data', () => {
    const data = { model: 'threat-detection', reason: 'not enabled' };
    const error = new ModelZooApiError(400, 'Bad Request', data);
    expect(error.status).toBe(400);
    expect(error.message).toBe('Bad Request');
    expect(error.data).toEqual(data);
  });

  it('extends Error properly', () => {
    const error = new ModelZooApiError(500, 'Server Error');
    expect(error instanceof Error).toBe(true);
    expect(error instanceof ModelZooApiError).toBe(true);
  });

  it('creates an error with status 0 for network errors', () => {
    const error = new ModelZooApiError(0, 'Network failure');
    expect(error.status).toBe(0);
    expect(error.message).toBe('Network failure');
  });
});

// ============================================================================
// listModels Tests
// ============================================================================

describe('listModels', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('calls correct endpoint', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockModelListResponse));

    await listModels();

    expect(fetch).toHaveBeenCalledWith('/api/system/models', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('returns model list successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockModelListResponse));

    const result = await listModels();

    expect(result.models).toHaveLength(3);
    expect(result.service_status['ai-enrichment']).toBe('healthy');
  });

  it('returns models with runtime state', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockModelListResponse));

    const result = await listModels();

    const loadedModel = result.models.find((m) => m.name === 'threat-detection-yolov8n');
    expect(loadedModel?.runtime?.loaded).toBe(true);
    expect(loadedModel?.runtime?.actual_vram_mb).toBe(287);
    expect(loadedModel?.runtime?.load_count).toBe(5);
  });

  it('returns models without runtime state when service is down', async () => {
    const responseWithNullRuntime: ModelListResponse = {
      ...mockModelListResponse,
      models: [mockModelDisabled],
      service_status: {
        'ai-enrichment': 'unhealthy',
        'ai-enrichment-light': 'healthy',
      },
    };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(responseWithNullRuntime));

    const result = await listModels();

    expect(result.models[0].runtime).toBeNull();
    expect(result.service_status['ai-enrichment']).toBe('unhealthy');
  });

  it('handles empty model list', async () => {
    const emptyResponse: ModelListResponse = {
      models: [],
      service_status: {},
    };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(emptyResponse));

    const result = await listModels();

    expect(result.models).toHaveLength(0);
  });

  it('throws ModelZooApiError on 500 server error', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(500, 'Internal Server Error', 'Failed to fetch models')
    );

    await expect(listModels()).rejects.toThrow(ModelZooApiError);
    await expect(listModels()).rejects.toMatchObject({
      status: 500,
      message: 'Failed to fetch models',
    });
  });

  it('throws ModelZooApiError on network error', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Network failure'));

    await expect(listModels()).rejects.toThrow(ModelZooApiError);
    await expect(listModels()).rejects.toMatchObject({
      status: 0,
      message: 'Network failure',
    });
  });
});

// ============================================================================
// getVRAMSummary Tests
// ============================================================================

describe('getVRAMSummary', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('calls correct endpoint', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockVRAMSummaryResponse));

    await getVRAMSummary();

    expect(fetch).toHaveBeenCalledWith('/api/system/models/vram-summary', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('returns per-GPU VRAM breakdown', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockVRAMSummaryResponse));

    const result = await getVRAMSummary();

    expect(result.gpus).toHaveLength(2);
    expect(result.gpus[0].gpu_id).toBe(0);
    expect(result.gpus[0].service).toBe('ai-enrichment');
    expect(result.gpus[0].budget_mb).toBe(6800);
  });

  it('returns VRAM totals', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockVRAMSummaryResponse));

    const result = await getVRAMSummary();

    expect(result.totals.budget_mb).toBe(8000);
    expect(result.totals.used_mb).toBe(2550);
    expect(result.totals.model_count).toBe(4);
  });

  it('returns loaded model names per GPU', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockVRAMSummaryResponse));

    const result = await getVRAMSummary();

    expect(result.gpus[0].loaded_models).toContain('fashion-clip');
    expect(result.gpus[1].loaded_models).toContain('threat-detection-yolov8n');
  });

  it('returns utilization percentage', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockVRAMSummaryResponse));

    const result = await getVRAMSummary();

    expect(result.gpus[0].utilization_percent).toBeCloseTo(30.9, 1);
    expect(result.gpus[1].utilization_percent).toBeCloseTo(37.5, 1);
  });

  it('throws ModelZooApiError on 500 server error', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(500, 'Internal Server Error', 'Failed to get VRAM summary')
    );

    await expect(getVRAMSummary()).rejects.toThrow(ModelZooApiError);
    await expect(getVRAMSummary()).rejects.toMatchObject({
      status: 500,
      message: 'Failed to get VRAM summary',
    });
  });

  it('throws ModelZooApiError on network error', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Connection refused'));

    await expect(getVRAMSummary()).rejects.toMatchObject({
      status: 0,
      message: 'Connection refused',
    });
  });
});

// ============================================================================
// loadModel Tests
// ============================================================================

describe('loadModel', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('calls POST with model name', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLoadModelResponse));

    await loadModel('threat-detection-yolov8n');

    expect(fetch).toHaveBeenCalledWith('/api/system/models/threat-detection-yolov8n/load', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('returns load result with timing info', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLoadModelResponse));

    const result = await loadModel('threat-detection-yolov8n');

    expect(result.success).toBe(true);
    expect(result.model_name).toBe('threat-detection-yolov8n');
    expect(result.load_time_ms).toBe(1250);
    expect(result.vram_mb).toBe(287);
  });

  it('returns service and GPU info', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLoadModelResponse));

    const result = await loadModel('threat-detection-yolov8n');

    expect(result.service).toBe('ai-enrichment-light');
    expect(result.gpu_id).toBe(1);
  });

  it('encodes model name in URL', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLoadModelResponse));

    await loadModel('model with spaces');

    expect(fetch).toHaveBeenCalledWith('/api/system/models/model%20with%20spaces/load', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('throws ModelZooApiError on 404 model not found', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(404, 'Not Found', 'Model not found: unknown-model')
    );

    await expect(loadModel('unknown-model')).rejects.toThrow(ModelZooApiError);
    await expect(loadModel('unknown-model')).rejects.toMatchObject({
      status: 404,
      message: 'Model not found: unknown-model',
    });
  });

  it('throws ModelZooApiError on 400 model disabled', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(400, 'Bad Request', 'Model is disabled: fashion-clip')
    );

    await expect(loadModel('fashion-clip')).rejects.toMatchObject({
      status: 400,
      message: 'Model is disabled: fashion-clip',
    });
  });

  it('throws ModelZooApiError on 503 service unavailable', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(503, 'Service Unavailable', 'Enrichment service is down')
    );

    await expect(loadModel('threat-detection-yolov8n')).rejects.toMatchObject({
      status: 503,
      message: 'Enrichment service is down',
    });
  });
});

// ============================================================================
// unloadModel Tests
// ============================================================================

describe('unloadModel', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('calls POST with model name', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockUnloadModelResponse));

    await unloadModel('threat-detection-yolov8n');

    expect(fetch).toHaveBeenCalledWith('/api/system/models/threat-detection-yolov8n/unload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('returns unload result with freed VRAM', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockUnloadModelResponse));

    const result = await unloadModel('threat-detection-yolov8n');

    expect(result.success).toBe(true);
    expect(result.model_name).toBe('threat-detection-yolov8n');
    expect(result.freed_vram_mb).toBe(287);
  });

  it('encodes model name in URL', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockUnloadModelResponse));

    await unloadModel('model-with-special-chars');

    expect(fetch).toHaveBeenCalledWith('/api/system/models/model-with-special-chars/unload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('throws ModelZooApiError on 404 model not found', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(404, 'Not Found', 'Model not found: unknown-model')
    );

    await expect(unloadModel('unknown-model')).rejects.toMatchObject({
      status: 404,
      message: 'Model not found: unknown-model',
    });
  });

  it('handles unloading already unloaded model', async () => {
    const alreadyUnloadedResponse: UnloadModelResponse = {
      success: true,
      model_name: 'vehicle-segment-classification',
      freed_vram_mb: 0,
    };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(alreadyUnloadedResponse));

    const result = await unloadModel('vehicle-segment-classification');

    expect(result.success).toBe(true);
    expect(result.freed_vram_mb).toBe(0);
  });
});

// ============================================================================
// reloadModel Tests
// ============================================================================

describe('reloadModel', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('calls POST with model name on reload endpoint', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLoadModelResponse));

    await reloadModel('threat-detection-yolov8n');

    expect(fetch).toHaveBeenCalledWith('/api/system/models/threat-detection-yolov8n/reload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('returns load result after reload', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockLoadModelResponse));

    const result = await reloadModel('threat-detection-yolov8n');

    expect(result.success).toBe(true);
    expect(result.load_time_ms).toBe(1250);
  });
});

// ============================================================================
// unloadAllModels Tests
// ============================================================================

describe('unloadAllModels', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('calls POST on unload-all endpoint', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockUnloadAllResponse));

    await unloadAllModels();

    expect(fetch).toHaveBeenCalledWith('/api/system/models/unload-all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('returns unload count and total freed VRAM', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockUnloadAllResponse));

    const result = await unloadAllModels();

    expect(result.success).toBe(true);
    expect(result.unloaded_count).toBe(4);
    expect(result.total_freed_vram_mb).toBe(2550);
    expect(result.errors).toHaveLength(0);
  });

  it('returns partial success with errors', async () => {
    const partialResponse: UnloadAllResponse = {
      success: false,
      unloaded_count: 3,
      total_freed_vram_mb: 2000,
      errors: ['Failed to unload threat-detection-yolov8n: model in use'],
    };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(partialResponse));

    const result = await unloadAllModels();

    expect(result.success).toBe(false);
    expect(result.unloaded_count).toBe(3);
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0]).toContain('model in use');
  });

  it('handles no models to unload', async () => {
    const noModelsResponse: UnloadAllResponse = {
      success: true,
      unloaded_count: 0,
      total_freed_vram_mb: 0,
      errors: [],
    };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(noModelsResponse));

    const result = await unloadAllModels();

    expect(result.success).toBe(true);
    expect(result.unloaded_count).toBe(0);
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

  it('handles error responses correctly', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(422, 'Unprocessable Entity', 'Invalid model name')
    );

    await expect(listModels()).rejects.toMatchObject({
      status: 422,
      message: 'Invalid model name',
    });
  });

  it('handles error response with string body', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.resolve('Simple error message'),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    await expect(listModels()).rejects.toMatchObject({
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

    await expect(listModels()).rejects.toMatchObject({
      status: 500,
      message: 'HTTP 500: Internal Server Error',
    });
  });

  it('handles network timeout', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Request timeout'));

    await expect(listModels()).rejects.toMatchObject({
      status: 0,
      message: 'Request timeout',
    });
  });

  it('handles fetch rejection with non-Error object', async () => {
    vi.mocked(fetch).mockRejectedValue('String error');

    await expect(listModels()).rejects.toMatchObject({
      status: 0,
      message: 'Network request failed',
    });
  });

  it('handles JSON parse error on success response', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: () => Promise.reject(new Error('Invalid JSON')),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    await expect(listModels()).rejects.toMatchObject({
      status: 200,
      message: 'Failed to parse response JSON',
    });
  });

  it('preserves ModelZooApiError when re-thrown', async () => {
    const originalError = new ModelZooApiError(404, 'Model not found', { model: 'test' });
    vi.mocked(fetch).mockRejectedValue(originalError);

    await expect(listModels()).rejects.toMatchObject({
      status: 404,
      message: 'Model not found',
      data: { model: 'test' },
    });
  });

  it('handles error response with detail field', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      json: () => Promise.resolve({ detail: 'Validation failed: model_name required' }),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    await expect(listModels()).rejects.toMatchObject({
      status: 422,
      message: 'Validation failed: model_name required',
    });
  });

  it('handles error response with object body but no detail', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.resolve({ error: 'something went wrong', code: 'ERR001' }),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    await expect(listModels()).rejects.toMatchObject({
      status: 400,
      message: 'HTTP 400: Bad Request',
      data: { error: 'something went wrong', code: 'ERR001' },
    });
  });
});

// ============================================================================
// API Key Header Tests
// ============================================================================

describe('API Key Header', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('includes Content-Type header in requests', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockModelListResponse));

    await listModels();

    expect(fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      })
    );
  });
});
