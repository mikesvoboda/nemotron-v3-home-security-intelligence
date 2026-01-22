/**
 * AI Audit API Client
 *
 * Provides typed fetch wrappers for all 15 AI Audit REST endpoints including:
 * - Event audit operations (get, evaluate)
 * - Statistics and leaderboard
 * - Recommendations
 * - Batch processing
 * - Prompt management (CRUD, history, test)
 * - Prompt import/export
 * - Database-backed prompt config
 *
 * @see backend/api/routes/ai_audit.py - Backend implementation
 * @see backend/api/schemas/ai_audit.py - Backend Pydantic schemas
 */

import type {
  AiModelName,
  AllPromptsHistoryResponse,
  AllPromptsResponse,
  AuditStatsResponse,
  BatchAuditRequest,
  BatchAuditResponse,
  EventAuditResponse,
  LeaderboardResponse,
  ModelPromptResponse,
  PromptExportResponse,
  PromptImportRequest,
  PromptImportResponse,
  PromptTestRequest,
  PromptTestResponse,
  PromptUpdateRequest,
  PromptUpdateResponse,
  RecommendationsResponse,
} from '../types/aiAudit';

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for AI Audit API failures.
 * Includes HTTP status code and parsed error data.
 */
export class AiAuditApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'AiAuditApiError';
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

    throw new AiAuditApiError(response.status, errorMessage, errorData);
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new AiAuditApiError(response.status, 'Failed to parse response JSON', error);
  }
}

/**
 * Perform a fetch request to the AI Audit API with error handling.
 *
 * @param endpoint - API endpoint path (relative to /api/ai-audit)
 * @param options - Optional fetch options
 * @returns Parsed JSON response
 */
async function fetchAiAuditApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}/api/ai-audit${endpoint}`;

  const fetchOptions: RequestInit = {
    ...options,
    headers: buildHeaders(),
  };

  try {
    const response = await fetch(url, fetchOptions);
    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof AiAuditApiError) {
      throw error;
    }
    throw new AiAuditApiError(0, error instanceof Error ? error.message : 'Network request failed');
  }
}

/**
 * Perform a fetch request to the Prompts API with error handling.
 *
 * @param endpoint - API endpoint path (relative to /api/prompts)
 * @param options - Optional fetch options
 * @returns Parsed JSON response
 */
async function fetchPromptsApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}/api/prompts${endpoint}`;

  const fetchOptions: RequestInit = {
    ...options,
    headers: buildHeaders(),
  };

  try {
    const response = await fetch(url, fetchOptions);
    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof AiAuditApiError) {
      throw error;
    }
    throw new AiAuditApiError(0, error instanceof Error ? error.message : 'Network request failed');
  }
}

// ============================================================================
// Event Audit API Functions (Endpoints 1-2)
// ============================================================================

/**
 * Get audit information for a specific event.
 *
 * Retrieves the AI pipeline audit record for the given event, including
 * model contributions, quality scores, and prompt improvement suggestions.
 *
 * @param eventId - The ID of the event to get audit for
 * @returns EventAuditResponse containing full audit details
 * @throws AiAuditApiError if event or audit not found (404) or other errors
 *
 * @example
 * ```typescript
 * const audit = await getEventAudit(12345);
 * console.log(audit.scores.overall); // Quality score
 * console.log(audit.contributions.rtdetr); // RT-DETR contribution
 * ```
 */
export async function getEventAudit(eventId: number): Promise<EventAuditResponse> {
  return fetchAiAuditApi<EventAuditResponse>(`/events/${eventId}`);
}

/**
 * Trigger full evaluation for a specific event's audit.
 *
 * Runs the complete self-evaluation pipeline (self-critique, rubric scoring,
 * consistency check, prompt improvement) for the given event.
 *
 * @param eventId - The ID of the event to evaluate
 * @param force - If true, re-evaluate even if already evaluated (default: false)
 * @returns EventAuditResponse with updated evaluation results
 * @throws AiAuditApiError if event or audit not found (404) or other errors
 *
 * @example
 * ```typescript
 * // Evaluate event without forcing re-evaluation
 * const audit = await evaluateEvent(12345);
 *
 * // Force re-evaluation of already evaluated event
 * const audit = await evaluateEvent(12345, true);
 * ```
 */
export async function evaluateEvent(eventId: number, force?: boolean): Promise<EventAuditResponse> {
  const queryParams = new URLSearchParams();
  if (force) {
    queryParams.append('force', 'true');
  }

  const queryString = queryParams.toString();
  const endpoint = queryString
    ? `/events/${eventId}/evaluate?${queryString}`
    : `/events/${eventId}/evaluate`;

  return fetchAiAuditApi<EventAuditResponse>(endpoint, { method: 'POST' });
}

// ============================================================================
// Statistics API Functions (Endpoints 3-5)
// ============================================================================

/**
 * Get aggregate AI audit statistics.
 *
 * Returns aggregate statistics including total events, quality scores,
 * model contribution rates, and audit trends over the specified period.
 *
 * @param days - Number of days to include in statistics (1-90, default 7)
 * @param cameraId - Optional camera ID to filter stats
 * @returns AuditStatsResponse with aggregate statistics
 * @throws AiAuditApiError on server errors
 *
 * @example
 * ```typescript
 * // Get stats for last 7 days (default)
 * const stats = await getAuditStats();
 *
 * // Get stats for last 30 days
 * const stats = await getAuditStats(30);
 *
 * // Get stats for specific camera
 * const stats = await getAuditStats(7, 'front-door');
 * ```
 */
export async function getAuditStats(days?: number, cameraId?: string): Promise<AuditStatsResponse> {
  const queryParams = new URLSearchParams();
  if (days !== undefined) {
    queryParams.append('days', String(days));
  }
  if (cameraId) {
    queryParams.append('camera_id', cameraId);
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/stats?${queryString}` : '/stats';

  return fetchAiAuditApi<AuditStatsResponse>(endpoint);
}

/**
 * Get model leaderboard ranked by contribution rate.
 *
 * Returns a ranked list of AI models by their contribution rate,
 * along with quality correlation data.
 *
 * @param days - Number of days to include (1-90, default 7)
 * @returns LeaderboardResponse with ranked model entries and period
 * @throws AiAuditApiError on server errors
 *
 * @example
 * ```typescript
 * const leaderboard = await getLeaderboard(30);
 * leaderboard.entries.forEach(entry => {
 *   console.log(`${entry.model_name}: ${entry.contribution_rate}`);
 * });
 * ```
 */
export async function getLeaderboard(days?: number): Promise<LeaderboardResponse> {
  const queryParams = new URLSearchParams();
  if (days !== undefined) {
    queryParams.append('days', String(days));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/leaderboard?${queryString}` : '/leaderboard';

  return fetchAiAuditApi<LeaderboardResponse>(endpoint);
}

/**
 * Get aggregated prompt improvement recommendations.
 *
 * Analyzes all audits to produce actionable recommendations for
 * improving the AI pipeline prompt templates.
 *
 * @param days - Number of days to analyze (1-90, default 7)
 * @returns RecommendationsResponse with prioritized recommendations
 * @throws AiAuditApiError on server errors
 *
 * @example
 * ```typescript
 * const recommendations = await getRecommendations(14);
 * const highPriority = recommendations.recommendations.filter(
 *   r => r.priority === 'high'
 * );
 * ```
 */
export async function getRecommendations(days?: number): Promise<RecommendationsResponse> {
  const queryParams = new URLSearchParams();
  if (days !== undefined) {
    queryParams.append('days', String(days));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/recommendations?${queryString}` : '/recommendations';

  return fetchAiAuditApi<RecommendationsResponse>(endpoint);
}

// ============================================================================
// Batch Processing API Functions (Endpoint 6)
// ============================================================================

/**
 * Trigger batch audit processing for multiple events.
 *
 * Queues events for audit processing based on the provided criteria.
 * Events are processed synchronously in this implementation.
 *
 * @param request - Batch audit request with filtering criteria
 * @returns BatchAuditResponse with number of processed events
 * @throws AiAuditApiError on validation or server errors
 *
 * @example
 * ```typescript
 * // Process up to 100 events with risk score >= 50
 * const result = await triggerBatchAudit({
 *   limit: 100,
 *   min_risk_score: 50,
 *   force_reevaluate: false
 * });
 * console.log(`Processed ${result.queued_count} events`);
 * ```
 */
export async function triggerBatchAudit(request?: BatchAuditRequest): Promise<BatchAuditResponse> {
  const body: BatchAuditRequest = {};

  if (request?.limit !== undefined) {
    body.limit = request.limit;
  }
  if (request?.min_risk_score !== undefined) {
    body.min_risk_score = request.min_risk_score;
  }
  if (request?.force_reevaluate !== undefined) {
    body.force_reevaluate = request.force_reevaluate;
  }

  return fetchAiAuditApi<BatchAuditResponse>('/batch', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ============================================================================
// Prompt Management API Functions (Endpoints 7-13)
// ============================================================================

/**
 * Get current prompt configurations for all AI models.
 *
 * Returns configurations for nemotron, florence2, yolo_world, xclip,
 * and fashion_clip models with their current versions.
 *
 * @returns AllPromptsResponse containing all model configurations
 * @throws AiAuditApiError on server errors
 *
 * @example
 * ```typescript
 * const allPrompts = await getAllPrompts();
 * const nemotronConfig = allPrompts.prompts.nemotron;
 * console.log(`Nemotron version: ${nemotronConfig.version}`);
 * ```
 */
export async function getAllPrompts(): Promise<AllPromptsResponse> {
  return fetchPromptsApi<AllPromptsResponse>('');
}

/**
 * Test a modified prompt configuration against a specific event.
 *
 * Runs inference with both the current and modified configurations,
 * returning a comparison of the results to help evaluate changes.
 *
 * @param request - Test request with model name, config, and event ID
 * @returns PromptTestResponse with before/after comparison
 * @throws AiAuditApiError if model or event not found (404), config invalid (400)
 *
 * @example
 * ```typescript
 * const result = await testPrompt({
 *   model: 'nemotron',
 *   config: { system_prompt: 'Modified prompt...', temperature: 0.8 },
 *   event_id: 12345
 * });
 * console.log(`Improved: ${result.improved}`);
 * console.log(`Before: ${result.before.score}, After: ${result.after.score}`);
 * ```
 */
export async function testPrompt(request: PromptTestRequest): Promise<PromptTestResponse> {
  return fetchPromptsApi<PromptTestResponse>('/test', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Get version history for all AI models.
 *
 * Returns the most recent versions for each supported model.
 *
 * @param limit - Maximum number of versions to return per model (1-100, default 10)
 * @returns Dict mapping model names to their version histories
 * @throws AiAuditApiError on server errors
 *
 * @example
 * ```typescript
 * const history = await getPromptsHistory(20);
 * const nemotronHistory = history.nemotron;
 * console.log(`Nemotron has ${nemotronHistory.total_versions} versions`);
 * ```
 */
export async function getPromptsHistory(limit?: number): Promise<AllPromptsHistoryResponse> {
  const queryParams = new URLSearchParams();
  if (limit !== undefined) {
    queryParams.append('limit', String(limit));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/history?${queryString}` : '/history';

  return fetchPromptsApi<AllPromptsHistoryResponse>(endpoint);
}

/**
 * Import prompt configurations from JSON.
 *
 * Imports configurations for multiple models at once. By default,
 * existing configurations are not overwritten unless overwrite=true.
 *
 * @param request - Import request with configurations and overwrite flag
 * @returns PromptImportResponse with import results
 * @throws AiAuditApiError if no prompts provided (400) or validation errors (422)
 *
 * @example
 * ```typescript
 * const result = await importPrompts({
 *   prompts: {
 *     nemotron: { system_prompt: '...', temperature: 0.7 },
 *     florence2: { vqa_queries: ['What is this?'] }
 *   },
 *   overwrite: true
 * });
 * console.log(`Imported ${result.imported_count} models`);
 * ```
 */
export async function importPrompts(request: PromptImportRequest): Promise<PromptImportResponse> {
  return fetchPromptsApi<PromptImportResponse>('/import', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Export all AI model configurations as JSON.
 *
 * Returns all current configurations in a format suitable for
 * backup or transfer to another instance.
 *
 * @returns PromptExportResponse with all configurations
 * @throws AiAuditApiError on server errors
 *
 * @example
 * ```typescript
 * const exported = await exportPrompts();
 * const blob = new Blob([JSON.stringify(exported)], { type: 'application/json' });
 * // Download or store the exported configuration
 * ```
 */
export async function exportPrompts(): Promise<PromptExportResponse> {
  return fetchPromptsApi<PromptExportResponse>('/export');
}

/**
 * Get current prompt configuration for a specific AI model.
 *
 * @param model - Model name (nemotron, florence2, yolo_world, xclip, fashion_clip)
 * @returns ModelPromptResponse with current configuration
 * @throws AiAuditApiError if model not found (404)
 *
 * @example
 * ```typescript
 * const config = await getModelPrompt('nemotron');
 * console.log(`System prompt: ${config.config.system_prompt}`);
 * console.log(`Version: ${config.version}`);
 * ```
 */
export async function getModelPrompt(model: AiModelName): Promise<ModelPromptResponse> {
  return fetchPromptsApi<ModelPromptResponse>(`/${model}`);
}

/**
 * Update prompt configuration for a specific AI model.
 *
 * Creates a new version of the configuration with the provided changes.
 * The previous version is preserved in history.
 *
 * @param model - Model name to update
 * @param request - New configuration and optional description
 * @returns PromptUpdateResponse with new version info
 * @throws AiAuditApiError if model not found (404) or configuration invalid (400)
 *
 * @example
 * ```typescript
 * const result = await updateModelPrompt('nemotron', {
 *   config: {
 *     system_prompt: 'Updated system prompt...',
 *     temperature: 0.8,
 *     max_tokens: 2048
 *   },
 *   description: 'Added weather context'
 * });
 * console.log(`Updated to version ${result.version}`);
 * ```
 */
export async function updateModelPrompt(
  model: AiModelName,
  request: PromptUpdateRequest
): Promise<PromptUpdateResponse> {
  return fetchPromptsApi<PromptUpdateResponse>(`/${model}`, {
    method: 'PUT',
    body: JSON.stringify(request),
  });
}

// ============================================================================
// Database-backed Prompt Config API Functions (Deprecated - NEM-3255)
// ============================================================================
// NOTE: The /api/ai-audit/prompt-config/{model} endpoints were removed in NEM-2695.
// Use getModelPrompt() and updateModelPrompt() instead, which call /api/prompts/{model}.
// These deprecated functions are retained only for backwards compatibility with existing tests.
// ============================================================================

// ============================================================================
// Re-exports for convenience
// ============================================================================

export type {
  AiModelName,
  AllPromptsHistoryResponse,
  AllPromptsResponse,
  AuditsByDay,
  AuditStatsResponse,
  BatchAuditRequest,
  BatchAuditResponse,
  DbModelName,
  EventAuditResponse,
  LeaderboardResponse,
  ModelContributions,
  ModelLeaderboardEntry,
  ModelPromptResponse,
  PromptConfigRequest,
  PromptConfigResponse,
  PromptExportResponse,
  PromptHistoryEntry,
  PromptHistoryResponse,
  PromptImportRequest,
  PromptImportResponse,
  PromptImprovements,
  PromptTestRequest,
  PromptTestResponse,
  PromptTestResultAfter,
  PromptTestResultBefore,
  PromptUpdateRequest,
  PromptUpdateResponse,
  QualityScores,
  RecommendationItem,
  RecommendationPriority,
  RecommendationsResponse,
  RiskLevel,
} from '../types/aiAudit';
