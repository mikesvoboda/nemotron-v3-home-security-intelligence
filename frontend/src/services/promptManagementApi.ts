/**
 * Prompt Management API Client
 *
 * Provides typed fetch wrappers for prompt management REST endpoints including
 * version history, CRUD operations, testing, and import/export.
 *
 * @see backend/api/routes/prompt_management.py - Backend implementation
 * @see backend/api/schemas/prompt_management.py - Backend Pydantic schemas
 */

import type {
  AIModelEnum,
  AllPromptsResponse,
  ModelPromptConfig,
  PromptHistoryResponse,
  PromptRestoreResponse,
  PromptsExportResponse,
  PromptsImportPreviewRequest,
  PromptsImportPreviewResponse,
  PromptsImportRequest,
  PromptsImportResponse,
  PromptTestRequest,
  PromptTestResult,
  PromptUpdateRequest,
} from '../types/promptManagement';

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for Prompt Management API failures.
 * Includes HTTP status code and parsed error data.
 */
export class PromptApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'PromptApiError';
  }
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Build headers with optional API key authentication.
 */
function buildHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

/**
 * Handle API response with proper error handling.
 * Parses error details from FastAPI response format.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorData: unknown = undefined;

    try {
      const errorBody: unknown = await response.json();
      if (typeof errorBody === 'object' && errorBody !== null && 'detail' in errorBody) {
        errorMessage = String((errorBody as { detail: unknown }).detail);
        errorData = errorBody;
      } else if (typeof errorBody === 'string') {
        errorMessage = errorBody;
      } else {
        errorData = errorBody;
      }
    } catch {
      // If response body is not JSON, use status text
    }

    throw new PromptApiError(response.status, errorMessage, errorData);
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new PromptApiError(response.status, 'Failed to parse response JSON', error);
  }
}

/**
 * Perform a fetch request to the prompt management API with error handling.
 */
async function fetchPromptApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}/api/ai-audit/prompts${endpoint}`;

  const fetchOptions: RequestInit = {
    ...options,
    headers: buildHeaders(),
  };

  try {
    const response = await fetch(url, fetchOptions);
    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof PromptApiError) {
      throw error;
    }
    throw new PromptApiError(0, error instanceof Error ? error.message : 'Network request failed');
  }
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch current prompt configurations for all AI models.
 *
 * Returns the active prompt/configuration for each supported model:
 * - nemotron: System prompt for risk analysis
 * - florence2: Scene analysis queries
 * - yolo_world: Custom object classes and confidence threshold
 * - xclip: Action recognition classes
 * - fashion_clip: Clothing categories
 *
 * @returns AllPromptsResponse containing all current prompts
 * @throws PromptApiError on failure
 */
export async function fetchAllPrompts(): Promise<AllPromptsResponse> {
  return fetchPromptApi<AllPromptsResponse>('');
}

/**
 * Fetch prompt configuration for a specific AI model.
 *
 * @param model - The AI model to fetch configuration for
 * @returns ModelPromptConfig with current configuration
 * @throws PromptApiError if model not found (404) or other errors
 */
export async function fetchPromptForModel(model: AIModelEnum): Promise<ModelPromptConfig> {
  return fetchPromptApi<ModelPromptConfig>(`/${model}`);
}

/**
 * Update prompt configuration for a specific AI model.
 *
 * Creates a new version of the configuration while preserving history.
 *
 * @param model - The AI model to update
 * @param request - Update request with new config and optional description
 * @returns ModelPromptConfig with new version details
 * @throws PromptApiError on validation or server errors
 */
export async function updatePromptForModel(
  model: AIModelEnum,
  request: PromptUpdateRequest
): Promise<ModelPromptConfig> {
  return fetchPromptApi<ModelPromptConfig>(`/${model}`, {
    method: 'PUT',
    body: JSON.stringify(request),
  });
}

/**
 * Get version history for prompt configurations.
 *
 * Returns a list of all prompt versions, optionally filtered by model.
 *
 * @param model - Optional model filter
 * @param limit - Maximum results to return (1-100, default 50)
 * @param offset - Offset for pagination (default 0)
 * @returns PromptHistoryResponse with version list and total count
 * @throws PromptApiError on failure
 */
export async function fetchPromptHistory(
  model?: AIModelEnum,
  limit: number = 50,
  offset: number = 0
): Promise<PromptHistoryResponse> {
  const queryParams = new URLSearchParams();
  if (model) {
    queryParams.append('model', model);
  }
  queryParams.append('limit', String(limit));
  queryParams.append('offset', String(offset));

  const queryString = queryParams.toString();
  const endpoint = `/history?${queryString}`;

  // API returns object keyed by model name, transform to expected format
  const response = await fetchPromptApi<Record<string, { model_name: string; versions: PromptHistoryResponse['versions']; total_versions: number }>>(endpoint);

  // If model specified, extract that model's data
  if (model && response[model]) {
    return {
      versions: response[model].versions || [],
      total_count: response[model].total_versions || 0,
    };
  }

  // If no model specified, aggregate all versions
  const allVersions: PromptHistoryResponse['versions'] = [];
  let totalCount = 0;
  for (const modelData of Object.values(response)) {
    if (modelData.versions) {
      allVersions.push(...modelData.versions);
      totalCount += modelData.total_versions || modelData.versions.length;
    }
  }

  return {
    versions: allVersions,
    total_count: totalCount,
  };
}

/**
 * Restore a specific prompt version.
 *
 * Creates a new version with the configuration from the specified version,
 * making it the active configuration.
 *
 * @param versionId - The version ID to restore
 * @returns PromptRestoreResponse with restore details
 * @throws PromptApiError if version not found (404) or other errors
 */
export async function restorePromptVersion(versionId: number): Promise<PromptRestoreResponse> {
  return fetchPromptApi<PromptRestoreResponse>(`/history/${versionId}`, {
    method: 'POST',
  });
}

/**
 * Test a modified prompt configuration against an event or image.
 *
 * Runs inference with the modified configuration and compares results
 * with the original configuration.
 *
 * @param request - Test request with model, config, and optional event/image
 * @returns PromptTestResult with before/after comparison
 * @throws PromptApiError on validation or test errors
 */
export async function testPrompt(request: PromptTestRequest): Promise<PromptTestResult> {
  return fetchPromptApi<PromptTestResult>('/test', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Export all prompt configurations as JSON.
 *
 * Returns a complete export of all model configurations suitable for
 * backup, sharing, or importing into another instance.
 *
 * @returns PromptsExportResponse with all configurations
 * @throws PromptApiError on failure
 */
export async function exportPrompts(): Promise<PromptsExportResponse> {
  return fetchPromptApi<PromptsExportResponse>('/export');
}

/**
 * Preview import changes without applying them.
 *
 * Validates the import data and computes diffs against current configurations.
 *
 * @param request - Import preview request with version and prompts
 * @returns PromptsImportPreviewResponse with validation results and diffs
 * @throws PromptApiError on failure
 */
export async function previewImportPrompts(
  request: PromptsImportPreviewRequest
): Promise<PromptsImportPreviewResponse> {
  return fetchPromptApi<PromptsImportPreviewResponse>('/import/preview', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Import prompt configurations from JSON.
 *
 * Validates and imports configurations for each model, creating new
 * versions for each imported configuration.
 *
 * @param request - Import request with version and prompts
 * @returns PromptsImportResponse with import results
 * @throws PromptApiError on validation or server errors
 */
export async function importPrompts(request: PromptsImportRequest): Promise<PromptsImportResponse> {
  return fetchPromptApi<PromptsImportResponse>('/import', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}
