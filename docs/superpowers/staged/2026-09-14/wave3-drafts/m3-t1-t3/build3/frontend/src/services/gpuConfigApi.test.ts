/**
 * Unit tests for GPU Configuration API Client
 *
 * Tests all GPU Configuration API endpoints with comprehensive coverage
 * of success cases, error handling, and edge cases.
 *
 * @see NEM-3322
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  GpuConfigApiError,
  getGpus,
  getGpuConfig,
  updateGpuConfig,
  applyGpuConfig,
  getGpuStatus,
  detectGpus,
  previewStrategy,
  type GpuListResponse,
  type GpuConfig,
  type GpuConfigUpdateResponse,
  type GpuApplyResult,
  type GpuStatusResponse,
  type StrategyPreviewResponse,
  type GpuDevice,
  type GpuAssignment,
  type ServiceStatus,
} from './gpuConfigApi';

// ============================================================================
// Mock Data
// ============================================================================

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

const mockGpuConfigUpdateResponse: GpuConfigUpdateResponse = {
  success: true,
  warnings: [],
};

const mockGpuConfigUpdateResponseWithWarnings: GpuConfigUpdateResponse = {
  success: true,
  warnings: ['GPU 0 VRAM budget exceeds available VRAM', 'Service ai-enrichment not assigned'],
};

const mockGpuApplyResult: GpuApplyResult = {
  success: true,
  warnings: [],
  restarted_services: ['ai-llm', 'ai-yolo26'],
  service_statuses: [
    { service: 'ai-llm', status: 'running', message: null },
    { service: 'ai-yolo26', status: 'running', message: null },
  ],
};

const mockGpuApplyResultWithFailures: GpuApplyResult = {
  success: false,
  warnings: ['Container restart timed out for ai-yolo26'],
  restarted_services: ['ai-llm'],
  service_statuses: [
    { service: 'ai-llm', status: 'running', message: null },
    { service: 'ai-yolo26', status: 'error', message: 'Container restart timed out' },
  ],
};

const mockServiceStatus: ServiceStatus = {
  service: 'ai-llm',
  status: 'running',
  message: null,
};

const mockServiceStatus2: ServiceStatus = {
  service: 'ai-yolo26',
  status: 'running',
  message: null,
};

const mockServiceStatusRestarting: ServiceStatus = {
  service: 'ai-llm',
  status: 'starting',
  message: 'Waiting for restart',
};

const mockGpuStatusResponse: GpuStatusResponse = {
  in_progress: false,
  services_pending: [],
  services_completed: ['ai-llm', 'ai-yolo26'],
  service_statuses: [mockServiceStatus, mockServiceStatus2],
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
// GpuConfigApiError Tests
// ============================================================================

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

// ============================================================================
// getGpus Tests
// ============================================================================

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

// ============================================================================
// getGpuConfig Tests
// ============================================================================

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

// ============================================================================
// updateGpuConfig Tests
// ============================================================================

describe('updateGpuConfig', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('updates GPU configuration with strategy only', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuConfigUpdateResponse));

    const result = await updateGpuConfig({ strategy: 'vram_balanced' });

    expect(fetch).toHaveBeenCalledWith('/api/system/gpu-config', {
      method: 'PUT',
      body: JSON.stringify({ strategy: 'vram_balanced' }),
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.success).toBe(true);
    expect(result.warnings).toHaveLength(0);
  });

  it('updates GPU configuration with assignments only', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuConfigUpdateResponse));

    const assignments = [
      { service: 'ai-llm', gpu_index: 0, vram_budget_override: null },
      { service: 'ai-yolo26', gpu_index: 1, vram_budget_override: 4.0 },
    ];
    const result = await updateGpuConfig({ assignments });

    expect(fetch).toHaveBeenCalledWith('/api/system/gpu-config', {
      method: 'PUT',
      body: JSON.stringify({ assignments }),
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.success).toBe(true);
  });

  it('updates GPU configuration with both strategy and assignments', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuConfigUpdateResponse));

    const config = {
      strategy: 'manual',
      assignments: [{ service: 'ai-llm', gpu_index: 0, vram_budget_override: null }],
    };
    const result = await updateGpuConfig(config);

    expect(fetch).toHaveBeenCalledWith('/api/system/gpu-config', {
      method: 'PUT',
      body: JSON.stringify(config),
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.success).toBe(true);
  });

  it('returns warnings when configuration has issues', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      createMockResponse(mockGpuConfigUpdateResponseWithWarnings)
    );

    const result = await updateGpuConfig({ strategy: 'manual' });

    expect(result.success).toBe(true);
    expect(result.warnings).toHaveLength(2);
    expect(result.warnings).toContain('GPU 0 VRAM budget exceeds available VRAM');
  });

  it('throws GpuConfigApiError on 400 validation error', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(400, 'Bad Request', 'Invalid GPU index')
    );

    await expect(updateGpuConfig({ strategy: 'invalid' })).rejects.toThrow(GpuConfigApiError);
    await expect(updateGpuConfig({ strategy: 'invalid' })).rejects.toMatchObject({
      status: 400,
      message: 'Invalid GPU index',
    });
  });

  it('throws GpuConfigApiError on 422 unprocessable entity', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(422, 'Unprocessable Entity', 'GPU 2 does not exist')
    );

    await expect(
      updateGpuConfig({
        assignments: [{ service: 'ai-llm', gpu_index: 2, vram_budget_override: null }],
      })
    ).rejects.toMatchObject({
      status: 422,
      message: 'GPU 2 does not exist',
    });
  });

  it('handles empty update request', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuConfigUpdateResponse));

    const result = await updateGpuConfig({});

    expect(fetch).toHaveBeenCalledWith('/api/system/gpu-config', {
      method: 'PUT',
      body: JSON.stringify({}),
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.success).toBe(true);
  });
});

// ============================================================================
// applyGpuConfig Tests
// ============================================================================

describe('applyGpuConfig', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('applies GPU configuration successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuApplyResult));

    const result = await applyGpuConfig();

    expect(fetch).toHaveBeenCalledWith('/api/system/gpu-config/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.success).toBe(true);
    expect(result.restarted_services).toContain('ai-llm');
    expect(result.restarted_services).toContain('ai-yolo26');
    expect(result.service_statuses).toHaveLength(2);
  });

  it('returns partial success with failed restarts', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuApplyResultWithFailures));

    const result = await applyGpuConfig();

    expect(result.success).toBe(false);
    expect(result.restarted_services).toContain('ai-llm');
    const failedService = result.service_statuses.find((s) => s.status === 'error');
    expect(failedService?.service).toBe('ai-yolo26');
    expect(result.warnings).toContain('Container restart timed out for ai-yolo26');
  });

  it('handles no services to restart', async () => {
    const noRestartResult: GpuApplyResult = {
      success: true,
      warnings: ['No services required restart'],
      restarted_services: [],
      service_statuses: [],
    };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(noRestartResult));

    const result = await applyGpuConfig();

    expect(result.success).toBe(true);
    expect(result.restarted_services).toHaveLength(0);
  });

  it('throws GpuConfigApiError on 500 server error', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(500, 'Internal Server Error', 'Docker daemon unavailable')
    );

    await expect(applyGpuConfig()).rejects.toThrow(GpuConfigApiError);
    await expect(applyGpuConfig()).rejects.toMatchObject({
      status: 500,
      message: 'Docker daemon unavailable',
    });
  });

  it('throws GpuConfigApiError on 503 service unavailable', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(503, 'Service Unavailable', 'System is busy')
    );

    await expect(applyGpuConfig()).rejects.toMatchObject({
      status: 503,
      message: 'System is busy',
    });
  });
});

// ============================================================================
// getGpuStatus Tests
// ============================================================================

describe('getGpuStatus', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches GPU status successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuStatusResponse));

    const result = await getGpuStatus();

    expect(fetch).toHaveBeenCalledWith('/api/system/gpu-config/status', {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.service_statuses).toHaveLength(2);
  });

  it('returns service status details correctly', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuStatusResponse));

    const result = await getGpuStatus();

    const llmService = result.service_statuses.find((s) => s.service === 'ai-llm');
    expect(llmService?.status).toBe('running');
    expect(llmService?.message).toBeNull();
  });

  it('returns starting service status', async () => {
    const startingResponse: GpuStatusResponse = {
      in_progress: true,
      services_pending: ['ai-llm'],
      services_completed: [],
      service_statuses: [mockServiceStatusRestarting],
    };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(startingResponse));

    const result = await getGpuStatus();

    expect(result.service_statuses[0].status).toBe('starting');
    expect(result.in_progress).toBe(true);
    expect(result.services_pending).toContain('ai-llm');
  });

  it('handles service with status message', async () => {
    const serviceWithMessage: ServiceStatus = {
      service: 'ai-enrichment',
      status: 'stopped',
      message: 'Container exited with code 1',
    };
    const response: GpuStatusResponse = {
      in_progress: false,
      services_pending: [],
      services_completed: ['ai-enrichment'],
      service_statuses: [serviceWithMessage],
    };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(response));

    const result = await getGpuStatus();

    expect(result.service_statuses[0].message).toBe('Container exited with code 1');
  });

  it('throws GpuConfigApiError on 500 server error', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(500, 'Internal Server Error', 'Failed to query containers')
    );

    await expect(getGpuStatus()).rejects.toThrow(GpuConfigApiError);
    await expect(getGpuStatus()).rejects.toMatchObject({
      status: 500,
      message: 'Failed to query containers',
    });
  });

  it('throws GpuConfigApiError on network error', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Request timeout'));

    await expect(getGpuStatus()).rejects.toMatchObject({
      status: 0,
      message: 'Request timeout',
    });
  });
});

// ============================================================================
// detectGpus Tests
// ============================================================================

describe('detectGpus', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('detects GPUs successfully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(mockGpuListResponse));

    const result = await detectGpus();

    expect(fetch).toHaveBeenCalledWith('/api/system/gpu-config/detect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    expect(result.gpus).toHaveLength(2);
  });

  it('handles detection returning single GPU', async () => {
    const singleGpuResponse: GpuListResponse = { gpus: [mockGpuDevice] };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(singleGpuResponse));

    const result = await detectGpus();

    expect(result.gpus).toHaveLength(1);
    expect(result.gpus[0].name).toBe('NVIDIA RTX A5500');
  });

  it('handles detection returning no GPUs', async () => {
    const noGpuResponse: GpuListResponse = { gpus: [] };
    vi.mocked(fetch).mockResolvedValueOnce(createMockResponse(noGpuResponse));

    const result = await detectGpus();

    expect(result.gpus).toHaveLength(0);
  });

  it('throws GpuConfigApiError on 500 detection failure', async () => {
    vi.mocked(fetch).mockResolvedValue(
      createMockErrorResponse(500, 'Internal Server Error', 'NVIDIA driver not found')
    );

    await expect(detectGpus()).rejects.toThrow(GpuConfigApiError);
    await expect(detectGpus()).rejects.toMatchObject({
      status: 500,
      message: 'NVIDIA driver not found',
    });
  });

  it('throws GpuConfigApiError on network error', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Connection reset'));

    await expect(detectGpus()).rejects.toMatchObject({
      status: 0,
      message: 'Connection reset',
    });
  });
});

// ============================================================================
// previewStrategy Tests
// ============================================================================

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
