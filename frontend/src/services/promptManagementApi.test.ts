import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  PromptApiError,
  fetchAllPrompts,
  fetchPromptForModel,
  updatePromptForModel,
  fetchPromptHistory,
  restorePromptVersion,
  testPrompt,
  exportPrompts,
  previewImportPrompts,
  importPrompts,
} from './promptManagementApi';
import { AIModelEnum } from '../types/promptManagement';

import type {
  AllPromptsResponse,
  ModelPromptConfig,
  PromptHistoryResponse,
  PromptRestoreResponse,
  PromptsExportResponse,
  PromptsImportPreviewResponse,
  PromptsImportResponse,
  PromptTestResult,
  PromptUpdateRequest,
} from '../types/promptManagement';

// ============================================================================
// Mock Data
// ============================================================================

const mockNemotronConfig: ModelPromptConfig = {
  model: AIModelEnum.NEMOTRON,
  config: {
    system_prompt: 'You are an AI security analyst...',
    version: 5,
  },
  version: 5,
  created_at: '2025-01-07T10:00:00Z',
  created_by: 'admin',
  change_description: 'Improved risk scoring logic',
};

const mockAllPromptsResponse: AllPromptsResponse = {
  version: '1.0',
  exported_at: '2025-01-07T12:00:00Z',
  prompts: {
    nemotron: {
      system_prompt: 'You are an AI security analyst...',
      version: 5,
    },
    florence2: {
      queries: ['What objects are in this scene?', 'Describe the environment'],
    },
    yolo_world: {
      classes: ['person', 'car', 'dog', 'cat'],
      confidence_threshold: 0.35,
    },
  },
};

// Expected transformed result after fetchPromptHistory processes API response
const mockHistoryResponse: PromptHistoryResponse = {
  versions: [
    {
      id: 10,
      model: AIModelEnum.NEMOTRON,
      version: 5,
      created_at: '2025-01-07T10:00:00Z',
      created_by: 'admin',
      change_description: 'Improved risk scoring logic',
      is_active: true,
    },
    {
      id: 9,
      model: AIModelEnum.NEMOTRON,
      version: 4,
      created_at: '2025-01-06T15:30:00Z',
      created_by: 'admin',
      change_description: 'Updated context variables',
      is_active: false,
    },
    {
      id: 8,
      model: AIModelEnum.NEMOTRON,
      version: 3,
      created_at: '2025-01-05T08:00:00Z',
      created_by: 'admin',
      change_description: 'Initial production version',
      is_active: false,
    },
  ],
  total_count: 3,
};

// Raw API response format (keyed by model name)
const mockHistoryApiResponse = {
  [AIModelEnum.NEMOTRON]: {
    model_name: AIModelEnum.NEMOTRON,
    versions: mockHistoryResponse.versions,
    total_versions: mockHistoryResponse.total_count,
  },
};

const mockRestoreResponse: PromptRestoreResponse = {
  restored_version: 4,
  model: AIModelEnum.NEMOTRON,
  new_version: 6,
  message: 'Successfully restored version 4 as new version 6',
};

const mockTestResult: PromptTestResult = {
  model: AIModelEnum.NEMOTRON,
  before_score: 72,
  after_score: 85,
  before_response: { risk_score: 72, reasoning: 'Person detected at night' },
  after_response: {
    risk_score: 85,
    reasoning: 'Suspicious person detected at night near entry point',
  },
  improved: true,
  test_duration_ms: 1250,
};

const mockExportResponse: PromptsExportResponse = {
  version: '1.0',
  exported_at: '2025-01-07T12:00:00Z',
  prompts: {
    nemotron: {
      system_prompt: 'You are an AI security analyst...',
      version: 5,
    },
    florence2: {
      queries: ['What objects are in this scene?'],
    },
  },
};

const mockImportPreviewResponse: PromptsImportPreviewResponse = {
  version: '1.0',
  valid: true,
  validation_errors: [],
  diffs: [
    {
      model: 'nemotron',
      has_changes: true,
      current_version: 5,
      current_config: {
        system_prompt: 'Old prompt...',
      },
      imported_config: {
        system_prompt: 'New prompt...',
      },
      changes: ['~ Changed: system_prompt'],
    },
  ],
  total_changes: 1,
  unknown_models: [],
};

const mockImportResponse: PromptsImportResponse = {
  imported_models: ['nemotron', 'florence2'],
  skipped_models: [],
  new_versions: {
    nemotron: 6,
    florence2: 3,
  },
  message: 'Successfully imported 2 model configurations',
};

// ============================================================================
// Setup and Teardown
// ============================================================================

beforeEach(() => {
  // Mock fetch globally
  (globalThis as any).fetch = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ============================================================================
// Helper Functions
// ============================================================================

function mockFetchSuccess<T>(data: T, status: number = 200): void {
  ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    statusText: 'OK',
    json: () => Promise.resolve(data),
  } as Response);
}

function mockFetchError(status: number, message: string): void {
  ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: false,
    status,
    statusText: 'Error',
    json: () => Promise.resolve({ detail: message }),
  } as Response);
}

function mockFetchNetworkError(): void {
  ((globalThis as any).fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
    new Error('Network error')
  );
}

// ============================================================================
// Tests: fetchAllPrompts
// ============================================================================

describe('fetchAllPrompts', () => {
  it('should fetch all prompt configurations successfully', async () => {
    mockFetchSuccess(mockAllPromptsResponse);

    const result = await fetchAllPrompts();

    expect(result).toEqual(mockAllPromptsResponse);
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      '/api/ai-audit/prompts',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      })
    );
  });

  it('should throw PromptApiError on 404', async () => {
    mockFetchError(404, 'No prompts found');

    const promise = fetchAllPrompts();
    await expect(promise).rejects.toThrow(PromptApiError);

    // Mock again for second assertion
    mockFetchError(404, 'No prompts found');
    await expect(fetchAllPrompts()).rejects.toMatchObject({
      status: 404,
      message: 'No prompts found',
    });
  });

  it('should throw PromptApiError on network error', async () => {
    mockFetchNetworkError();

    await expect(fetchAllPrompts()).rejects.toThrow(PromptApiError);
  });
});

// ============================================================================
// Tests: fetchPromptForModel
// ============================================================================

describe('fetchPromptForModel', () => {
  it('should fetch prompt configuration for specific model', async () => {
    mockFetchSuccess(mockNemotronConfig);

    const result = await fetchPromptForModel(AIModelEnum.NEMOTRON);

    expect(result).toEqual(mockNemotronConfig);
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      '/api/ai-audit/prompts/nemotron',
      expect.any(Object)
    );
  });

  it('should throw PromptApiError when model not found', async () => {
    mockFetchError(404, 'No configuration found for model nemotron');

    await expect(fetchPromptForModel(AIModelEnum.NEMOTRON)).rejects.toThrow(PromptApiError);
  });
});

// ============================================================================
// Tests: updatePromptForModel
// ============================================================================

describe('updatePromptForModel', () => {
  it('should update prompt configuration successfully', async () => {
    const updateRequest: PromptUpdateRequest = {
      config: {
        system_prompt: 'Updated prompt...',
      },
      change_description: 'Improved accuracy',
    };

    const updatedConfig: ModelPromptConfig = {
      ...mockNemotronConfig,
      version: 6,
      config: updateRequest.config,
      change_description: updateRequest.change_description,
    };

    mockFetchSuccess(updatedConfig);

    const result = await updatePromptForModel(AIModelEnum.NEMOTRON, updateRequest);

    expect(result).toEqual(updatedConfig);
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      '/api/ai-audit/prompts/nemotron',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(updateRequest),
      })
    );
  });

  it('should throw PromptApiError on validation error', async () => {
    const updateRequest: PromptUpdateRequest = {
      config: {},
      change_description: 'Empty config',
    };

    mockFetchError(422, 'Configuration cannot be empty');

    await expect(updatePromptForModel(AIModelEnum.NEMOTRON, updateRequest)).rejects.toThrow(
      PromptApiError
    );
  });
});

// ============================================================================
// Tests: fetchPromptHistory
// ============================================================================

describe('fetchPromptHistory', () => {
  it('should fetch version history with default pagination', async () => {
    // API returns object keyed by model name, function transforms to {versions, total_count}
    mockFetchSuccess(mockHistoryApiResponse);

    const result = await fetchPromptHistory(AIModelEnum.NEMOTRON);

    expect(result).toEqual(mockHistoryResponse);
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ai-audit/prompts/history?'),
      expect.any(Object)
    );
  });

  it('should fetch version history with custom pagination', async () => {
    mockFetchSuccess(mockHistoryApiResponse);

    const result = await fetchPromptHistory(AIModelEnum.NEMOTRON, { limit: 10, offset: 20 });

    expect(result).toEqual(mockHistoryResponse);
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      expect.stringContaining('limit=10'),
      expect.any(Object)
    );
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      expect.stringContaining('offset=20'),
      expect.any(Object)
    );
  });

  it('should fetch version history with cursor pagination', async () => {
    mockFetchSuccess(mockHistoryApiResponse);

    const result = await fetchPromptHistory(AIModelEnum.NEMOTRON, { limit: 10, cursor: 'abc123' });

    expect(result).toEqual(mockHistoryResponse);
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      expect.stringContaining('limit=10'),
      expect.any(Object)
    );
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      expect.stringContaining('cursor=abc123'),
      expect.any(Object)
    );
  });

  it('should fetch history for all models when model not specified', async () => {
    // When no model specified, function aggregates all versions from all models
    mockFetchSuccess(mockHistoryApiResponse);

    const result = await fetchPromptHistory();

    // Should aggregate versions from all models (only nemotron in mock)
    expect(result).toEqual(mockHistoryResponse);
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/ai-audit/prompts/history?'),
      expect.any(Object)
    );
  });

  it('should return empty versions when model not found in response', async () => {
    mockFetchSuccess({}); // Empty response

    const result = await fetchPromptHistory(AIModelEnum.NEMOTRON);

    expect(result).toEqual({ versions: [], total_count: 0 });
  });
});

// ============================================================================
// Tests: restorePromptVersion
// ============================================================================

describe('restorePromptVersion', () => {
  it('should restore a previous version successfully', async () => {
    mockFetchSuccess(mockRestoreResponse);

    const result = await restorePromptVersion(9);

    expect(result).toEqual(mockRestoreResponse);
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      '/api/ai-audit/prompts/history/9',
      expect.objectContaining({
        method: 'POST',
      })
    );
  });

  it('should throw PromptApiError when version not found', async () => {
    mockFetchError(404, 'Version not found');

    await expect(restorePromptVersion(999)).rejects.toThrow(PromptApiError);
  });
});

// ============================================================================
// Tests: testPrompt
// ============================================================================

describe('testPrompt', () => {
  it('should test prompt configuration successfully', async () => {
    const testRequest = {
      model: AIModelEnum.NEMOTRON,
      config: {
        system_prompt: 'Test prompt...',
      },
      event_id: 42,
    };

    mockFetchSuccess(mockTestResult);

    const result = await testPrompt(testRequest);

    expect(result).toEqual(mockTestResult);
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      '/api/ai-audit/prompts/test',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(testRequest),
      })
    );
  });

  it('should return error in test result when test fails', async () => {
    const testRequest = {
      model: AIModelEnum.NEMOTRON,
      config: {
        system_prompt: 'Invalid prompt...',
      },
    };

    const errorResult: PromptTestResult = {
      model: AIModelEnum.NEMOTRON,
      test_duration_ms: 500,
      error: 'Invalid configuration format',
    };

    mockFetchSuccess(errorResult);

    const result = await testPrompt(testRequest);

    expect(result.error).toBeDefined();
    expect(result.error).toContain('Invalid configuration');
  });
});

// ============================================================================
// Tests: exportPrompts
// ============================================================================

describe('exportPrompts', () => {
  it('should export all prompt configurations', async () => {
    mockFetchSuccess(mockExportResponse);

    const result = await exportPrompts();

    expect(result).toEqual(mockExportResponse);
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      '/api/ai-audit/prompts/export',
      expect.any(Object)
    );
  });
});

// ============================================================================
// Tests: previewImportPrompts
// ============================================================================

describe('previewImportPrompts', () => {
  it('should preview import changes successfully', async () => {
    const importRequest = {
      version: '1.0',
      prompts: {
        nemotron: {
          system_prompt: 'New prompt...',
        },
      },
    };

    mockFetchSuccess(mockImportPreviewResponse);

    const result = await previewImportPrompts(importRequest);

    expect(result).toEqual(mockImportPreviewResponse);
    expect(result.valid).toBe(true);
    expect(result.total_changes).toBe(1);
  });

  it('should return validation errors for invalid import', async () => {
    const importRequest = {
      version: '2.0', // Invalid version
      prompts: {},
    };

    const invalidResponse: PromptsImportPreviewResponse = {
      version: '2.0',
      valid: false,
      validation_errors: ['Unsupported version: 2.0. Expected: 1.0'],
      diffs: [],
      total_changes: 0,
      unknown_models: [],
    };

    mockFetchSuccess(invalidResponse);

    const result = await previewImportPrompts(importRequest);

    expect(result.valid).toBe(false);
    expect(result.validation_errors).toHaveLength(1);
  });
});

// ============================================================================
// Tests: importPrompts
// ============================================================================

describe('importPrompts', () => {
  it('should import prompt configurations successfully', async () => {
    const importRequest = {
      version: '1.0',
      prompts: {
        nemotron: {
          system_prompt: 'Imported prompt...',
        },
        florence2: {
          queries: ['New query'],
        },
      },
    };

    mockFetchSuccess(mockImportResponse);

    const result = await importPrompts(importRequest);

    expect(result).toEqual(mockImportResponse);
    expect(result.imported_models).toHaveLength(2);
    expect((globalThis as any).fetch).toHaveBeenCalledWith(
      '/api/ai-audit/prompts/import',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(importRequest),
      })
    );
  });

  it('should throw PromptApiError on validation error', async () => {
    const importRequest = {
      version: '1.0',
      prompts: {},
    };

    mockFetchError(422, 'Prompts configuration cannot be empty');

    await expect(importPrompts(importRequest)).rejects.toThrow(PromptApiError);
  });
});

// ============================================================================
// Tests: PromptApiError
// ============================================================================

describe('PromptApiError', () => {
  it('should create error with status and message', () => {
    const error = new PromptApiError(404, 'Not found');

    expect(error).toBeInstanceOf(Error);
    expect(error.name).toBe('PromptApiError');
    expect(error.status).toBe(404);
    expect(error.message).toBe('Not found');
  });

  it('should include optional data', () => {
    const errorData = { detail: 'Validation failed', errors: ['field1'] };
    const error = new PromptApiError(422, 'Validation error', errorData);

    expect(error.data).toEqual(errorData);
  });
});
