/**
 * Unit tests for GPU Configuration API Client (F-176, F-178, F-182).
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  GpuConfigApiError,
  getGpus,
  getGpuConfig,
  previewStrategy,
  type GpuListResponse,
  type GpuConfig,
  type StrategyPreviewResponse,
  type GpuDevice,
  type GpuAssignment,
} from './gpuConfigApi';

const mockGpuDevice: GpuDevice = {
  index: 0,
  name: 'NVIDIA RTX A5500',
  vram_total_mb: 24576,
  vram_used_mb: 8192,
  compute_capability: '8.6',
};

const mockGpuDevice2: GpuDevice = {
  index: 1,
  name: 'NVIDIA RTX A4000',
  vram_total_mb: 16384,
  vram_used_mb: 4096,
  compute_capability: '8.6',
};

const mockGpuListResponse: GpuListResponse = {
  gpus: [mockGpuDevice, mockGpuDevice2],
};

const mockGpuAssignment: GpuAssignment = {
  service: 'ai-llm',
  gpu_index: 0,
  vram_budget_override: null,
};

const mockGpuAssignment2: GpuAssignment = {
  service: 'ai-yolo26',
  gpu_index: 1,
  vram_budget_override: 3.5,
};

const mockGpuConfig: GpuConfig = {
  strategy: 'isolation_first',
  assignments: [mockGpuAssignment, mockGpuAssignment2],
  updated_at: '2026-01-23T10:30:00Z',
};

const mockStrategyPreviewResponse: StrategyPreviewResponse = {
  strategy: 'balanced',
  proposed_assignments: [
    { service: 'ai-llm', gpu_index: 0, vram_budget_override: null },
    { service: 'ai-yolo26', gpu_index: 1, vram_budget_override: null },
    { service: 'ai-enrichment', gpu_index: 0, vram_budget_override: 2.5 },
  ],
  warnings: [],
};

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

describe('GpuConfigApiError', () => {
  it('creates an error with status and message', () => {
    const error = new GpuConfigApiError(404, 'Not Found');
    expect(error.name).toBe('GpuConfigApiError');
    expect(error.status).toBe(404);
    expect(error.message).toBe('Not Found');
    expect(error.data).toBeUndefined();
  });

  it('creates an error with additional data', () => {
    const data = { field: 'gpu_index', reason: 'invalid' };
    const error = new GpuConfigApiError(400, 'Bad Request', data);
    expect(error.status).toBe(400);
    expect(error.message).toBe('Bad Request');
    expect(error.data).toEqual(data);
  });

  it('extends Error properly', () => {
    const error = new GpuConfigApiError(500, 'Server Error');
    expect(error instanceof Error).toBe(true);
    expect(error instanceof GpuConfigApiError).toBe(true);
  });

  it('creates an error with status 0 for network errors', () => {
    const error = new GpuConfigApiError(0, 'Network failure');
    expect(error.status).toBe(0);
    expect(error.message).toBe('Network failure');
  });
});

describe('getGpus', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches GPU list successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuListResponse));

    const result = await getGpus();

    expect(fetch).toHaveBeenCalledWith('/api/system/gpus', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockGpuListResponse);
    expect(result.gpus).toHaveLength(2);
  });

  it('returns GPU device details correctly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuListResponse));

    const result = await getGpus();

    expect(result.gpus[0].index).toBe(0);
    expect(result.gpus[0].name).toBe('NVIDIA RTX A5500');
    expect(result.gpus[0].vram_total_mb).toBe(24576);
    expect(result.gpus[0].vram_used_mb).toBe(8192);
    expect(result.gpus[0].compute_capability).toBe('8.6');
  });

  it('handles empty GPU list', async () => {
    const emptyResponse: GpuListResponse = { gpus: [] };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(emptyResponse));

    const result = await getGpus();

    expect(result.gpus).toHaveLength(0);
  });

  it('throws GpuConfigApiError on 500 server error', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(500, 'Internal Server Error', 'GPU detection failed')
    );

    await expect(getGpus()).rejects.toThrow(GpuConfigApiError);
    await expect(getGpus()).rejects.toMatchObject({
      status: 500,
      message: 'GPU detection failed',
    });
  });

  it('throws GpuConfigApiError on network error', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Network failure'));

    await expect(getGpus()).rejects.toThrow(GpuConfigApiError);
    await expect(getGpus()).rejects.toMatchObject({
      status: 0,
      message: 'Network failure',
    });
  });
});

describe('getGpuConfig', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches GPU configuration successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuConfig));

    const result = await getGpuConfig();

    expect(fetch).toHaveBeenCalledWith('/api/system/gpu-config', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result).toEqual(mockGpuConfig);
  });

  it('returns configuration details correctly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuConfig));

    const result = await getGpuConfig();

    expect(result.strategy).toBe('isolation_first');
    expect(result.assignments).toHaveLength(2);
    expect(result.updated_at).toBe('2026-01-23T10:30:00Z');
  });

  it('returns assignment details correctly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuConfig));

    const result = await getGpuConfig();

    const llmAssignment = result.assignments.find((a) => a.service === 'ai-llm');
    expect(llmAssignment?.gpu_index).toBe(0);
    expect(llmAssignment?.vram_budget_override).toBeNull();

    const detectorAssignment = result.assignments.find((a) => a.service === 'ai-yolo26');
    expect(detectorAssignment?.vram_budget_override).toBe(3.5);
  });

  it('throws GpuConfigApiError on 404 not found', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(404, 'Not Found', 'Configuration not found')
    );

    await expect(getGpuConfig()).rejects.toThrow(GpuConfigApiError);
    await expect(getGpuConfig()).rejects.toMatchObject({
      status: 404,
      message: 'Configuration not found',
    });
  });

  it('throws GpuConfigApiError on network error', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Connection refused'));

    await expect(getGpuConfig()).rejects.toThrow(GpuConfigApiError);
    await expect(getGpuConfig()).rejects.toMatchObject({
      status: 0,
      message: 'Connection refused',
    });
  });
});

describe('previewStrategy', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('previews isolation_first strategy', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockStrategyPreviewResponse));

    const result = await previewStrategy('isolation_first');

    expect(fetch).toHaveBeenCalledWith('/api/system/gpu-config/preview?strategy=isolation_first', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.proposed_assignments).toHaveLength(3);
  });

  it('previews vram_balanced strategy', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockStrategyPreviewResponse));

    await previewStrategy('vram_balanced');

    expect(fetch).toHaveBeenCalledWith('/api/system/gpu-config/preview?strategy=vram_balanced', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('previews auto strategy', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockStrategyPreviewResponse));

    await previewStrategy('auto');

    expect(fetch).toHaveBeenCalledWith('/api/system/gpu-config/preview?strategy=auto', {
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('previews manual strategy', async () => {
    const manualPreview: StrategyPreviewResponse = {
      strategy: 'manual',
      proposed_assignments: [],
      warnings: [],
    };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(manualPreview));

    const result = await previewStrategy('manual');

    expect(result.proposed_assignments).toHaveLength(0);
  });

  it('returns proposed assignments with vram_budget_override', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockStrategyPreviewResponse));

    const result = await previewStrategy('isolation_first');

    const enrichmentAssignment = result.proposed_assignments.find(
      (a) => a.service === 'ai-enrichment'
    );
    expect(enrichmentAssignment?.vram_budget_override).toBe(2.5);
  });

  it('throws GpuConfigApiError on 400 invalid strategy', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(400, 'Bad Request', 'Invalid strategy: unknown_strategy')
    );

    await expect(previewStrategy('unknown_strategy')).rejects.toThrow(GpuConfigApiError);
    await expect(previewStrategy('unknown_strategy')).rejects.toMatchObject({
      status: 400,
      message: 'Invalid strategy: unknown_strategy',
    });
  });

  it('throws GpuConfigApiError on 500 server error', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(500, 'Internal Server Error', 'Failed to compute assignments')
    );

    await expect(previewStrategy('auto')).rejects.toMatchObject({
      status: 500,
      message: 'Failed to compute assignments',
    });
  });

  it('handles strategy with special characters in URL encoding', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockStrategyPreviewResponse));

    await previewStrategy('test strategy');

    expect(fetch).toHaveBeenCalledWith(
      '/api/system/gpu-config/preview?strategy=test+strategy',
      expect.any(Object)
    );
  });
});

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

    await expect(getGpus()).rejects.toMatchObject({
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

    await expect(getGpus()).rejects.toMatchObject({
      status: 500,
      message: 'HTTP 500: Internal Server Error',
    });
  });

  it('handles network timeout', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Request timeout'));

    await expect(getGpus()).rejects.toMatchObject({
      status: 0,
      message: 'Request timeout',
    });
  });

  it('handles fetch rejection with non-Error object', async () => {
    vi.mocked(fetch).mockRejectedValue('String error');

    await expect(getGpus()).rejects.toMatchObject({
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

    await expect(getGpus()).rejects.toMatchObject({
      status: 200,
      message: 'Failed to parse response JSON',
    });
  });

  it('preserves GpuConfigApiError when re-thrown', async () => {
    const originalError = new GpuConfigApiError(404, 'Not found', { id: 42 });
    vi.mocked(fetch).mockRejectedValue(originalError);

    await expect(getGpus()).rejects.toMatchObject({
      status: 404,
      message: 'Not found',
      data: { id: 42 },
    });
  });

  it('handles error response with detail field', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      json: () => Promise.resolve({ detail: 'Validation failed: gpu_index must be >= 0' }),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    } as Response);

    await expect(getGpus()).rejects.toMatchObject({
      status: 422,
      message: 'Validation failed: gpu_index must be >= 0',
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

    await expect(getGpus()).rejects.toMatchObject({
      status: 400,
      message: 'HTTP 400: Bad Request',
      data: { error: 'something went wrong', code: 'ERR001' },
    });
  });
});

describe('API Key Header', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('includes Content-Type header in requests', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuListResponse));

    await getGpus();

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
