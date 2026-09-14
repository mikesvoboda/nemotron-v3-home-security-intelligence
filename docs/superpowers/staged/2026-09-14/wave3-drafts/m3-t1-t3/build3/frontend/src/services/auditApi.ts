/**
 * Audit API Client for AI Pipeline Audit endpoints
 *
 * Provides typed fetch wrappers for AI audit REST endpoints including
 * event audits, statistics, model leaderboards, and recommendations.
 *
 * @see backend/api/routes/ai_audit.py - Backend implementation
 * @see backend/api/schemas/ai_audit.py - Backend Pydantic schemas
 */

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for Audit API failures.
 * Includes HTTP status code and parsed error data.
 */
export class AuditApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'AuditApiError';
  }
}

// ============================================================================
// Types - AI Audit domain types
// ============================================================================

/**
 * Model contribution flags indicating which AI models contributed to an event.
 */
export interface ModelContributions {
  /** RT-DETR object detection */
  rtdetr: boolean;
  /** Florence-2 vision attributes */
  florence: boolean;
  /** CLIP embeddings */
  clip: boolean;
  /** Violence detection */
  violence: boolean;
  /** Clothing analysis */
  clothing: boolean;
  /** Vehicle classification */
  vehicle: boolean;
  /** Pet classification */
  pet: boolean;
  /** Weather classification */
  weather: boolean;
  /** Image quality assessment */
  image_quality: boolean;
  /** Zone analysis */
  zones: boolean;
  /** Baseline comparison */
  baseline: boolean;
  /** Cross-camera correlation */
  cross_camera: boolean;
}

/**
 * Self-evaluation quality scores (1-5 scale).
 */
export interface QualityScores {
  /** How well the model used the provided context */
  context_usage: number | null;
  /** Logical coherence of the reasoning */
  reasoning_coherence: number | null;
  /** Quality of risk score justification */
  risk_justification: number | null;
  /** Consistency with similar events */
  consistency: number | null;
  /** Overall quality score */
  overall: number | null;
}

/**
 * Prompt improvement suggestions from self-evaluation.
 */
export interface PromptImprovements {
  /** Context that was missing from the prompt */
  missing_context: string[];
  /** Sections that were confusing */
  confusing_sections: string[];
  /** Data that was provided but not used */
  unused_data: string[];
  /** Suggestions for format improvements */
  format_suggestions: string[];
  /** Gaps in model coverage */
  model_gaps: string[];
}

/**
 * Full audit response for a single event.
 */
export interface EventAudit {
  /** Audit record ID */
  id: number;
  /** Associated event ID */
  event_id: number;
  /** Timestamp when audit was created */
  audited_at: string;
  /** Whether full self-evaluation has been completed */
  is_fully_evaluated: boolean;
  /** Model contribution flags */
  contributions: ModelContributions;
  /** Length of the LLM prompt in characters */
  prompt_length: number;
  /** Estimated token count for the prompt */
  prompt_token_estimate: number;
  /** Percentage of enrichment data utilized (0-1) */
  enrichment_utilization: number;
  /** Quality scores from self-evaluation */
  scores: QualityScores;
  /** Risk score from consistency re-evaluation */
  consistency_risk_score: number | null;
  /** Difference from original risk score */
  consistency_diff: number | null;
  /** Text critique from self-evaluation */
  self_eval_critique: string | null;
  /** Prompt improvement suggestions */
  improvements: PromptImprovements;
}

/**
 * Audits by day entry for trending.
 */
export interface AuditsByDay {
  /** Date string (YYYY-MM-DD) */
  date: string;
  /** Number of audits on this day */
  count: number;
}

/**
 * Aggregate audit statistics.
 */
export interface AuditStats {
  /** Total number of events in the period */
  total_events: number;
  /** Number of events with audit records */
  audited_events: number;
  /** Number of events with full self-evaluation */
  fully_evaluated_events: number;
  /** Average overall quality score */
  avg_quality_score: number | null;
  /** Average consistency rate */
  avg_consistency_rate: number | null;
  /** Average enrichment utilization */
  avg_enrichment_utilization: number | null;
  /** Model contribution rates (0-1) by model name */
  model_contribution_rates: Record<string, number>;
  /** Audits by day for trending */
  audits_by_day: AuditsByDay[];
}

/**
 * Single entry in the model leaderboard.
 */
export interface LeaderboardEntry {
  /** Name of the model */
  model_name: string;
  /** Contribution rate (0-1) */
  contribution_rate: number;
  /** Correlation with quality score (null if insufficient data) */
  quality_correlation: number | null;
  /** Number of events this model contributed to */
  event_count: number;
}

/**
 * Model leaderboard response.
 */
export interface LeaderboardResponse {
  /** Ranked list of model entries */
  entries: LeaderboardEntry[];
  /** Number of days included in the analysis */
  period_days: number;
}

/**
 * Single recommendation item.
 */
export interface Recommendation {
  /** Category: missing_context, unused_data, model_gaps, etc. */
  category: string;
  /** The specific suggestion */
  suggestion: string;
  /** Number of events that mentioned this suggestion */
  frequency: number;
  /** Priority level: high, medium, low */
  priority: 'high' | 'medium' | 'low';
}

/**
 * Aggregated recommendations response.
 */
export interface RecommendationsResponse {
  /** List of prioritized recommendations */
  recommendations: Recommendation[];
  /** Total number of events analyzed */
  total_events_analyzed: number;
}

/**
 * Batch audit response.
 */
export interface BatchAuditResponse {
  /** Number of events queued for processing */
  queued_count: number;
  /** Status message */
  message: string;
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

    throw new AuditApiError(response.status, errorMessage, errorData);
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new AuditApiError(response.status, 'Failed to parse response JSON', error);
  }
}

/**
 * Perform a fetch request to the audit API with error handling.
 */
async function fetchAuditApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}/api/ai-audit${endpoint}`;

  const fetchOptions: RequestInit = {
    ...options,
    headers: buildHeaders(),
  };

  try {
    const response = await fetch(url, fetchOptions);
    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof AuditApiError) {
      throw error;
    }
    throw new AuditApiError(0, error instanceof Error ? error.message : 'Network request failed');
  }
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch audit information for a specific event.
 *
 * Retrieves the AI pipeline audit record for the given event, including
 * model contributions, quality scores, and prompt improvement suggestions.
 *
 * @param eventId - The ID of the event to get audit for
 * @returns EventAudit containing full audit details
 * @throws AuditApiError if event or audit not found (404) or other errors
 */
export async function fetchEventAudit(eventId: number): Promise<EventAudit> {
  return fetchAuditApi<EventAudit>(`/events/${eventId}`);
}

/**
 * Trigger full evaluation for a specific event's audit.
 *
 * Runs the complete self-evaluation pipeline (self-critique, rubric scoring,
 * consistency check, prompt improvement) for the given event.
 *
 * @param eventId - The ID of the event to evaluate
 * @param force - If true, re-evaluate even if already evaluated (default: false)
 * @returns EventAudit with updated evaluation results
 * @throws AuditApiError if event or audit not found (404) or other errors
 */
export async function triggerEvaluation(eventId: number, force?: boolean): Promise<EventAudit> {
  const queryParams = new URLSearchParams();
  if (force) {
    queryParams.append('force', 'true');
  }

  const queryString = queryParams.toString();
  const endpoint = queryString
    ? `/events/${eventId}/evaluate?${queryString}`
    : `/events/${eventId}/evaluate`;

  return fetchAuditApi<EventAudit>(endpoint, { method: 'POST' });
}

/**
 * Fetch aggregate AI audit statistics.
 *
 * Returns aggregate statistics including total events, quality scores,
 * model contribution rates, and audit trends over the specified period.
 *
 * @param days - Number of days to include in statistics (1-90, default 7)
 * @param cameraId - Optional camera ID to filter stats
 * @returns AuditStats with aggregate statistics
 */
export async function fetchAuditStats(days?: number, cameraId?: string): Promise<AuditStats> {
  const queryParams = new URLSearchParams();
  if (days !== undefined) {
    queryParams.append('days', String(days));
  }
  if (cameraId) {
    queryParams.append('camera_id', cameraId);
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/stats?${queryString}` : '/stats';

  return fetchAuditApi<AuditStats>(endpoint);
}

/**
 * Fetch model leaderboard ranked by contribution rate.
 *
 * Returns a ranked list of AI models by their contribution rate,
 * along with quality correlation data.
 *
 * @param days - Number of days to include (1-90, default 7)
 * @returns LeaderboardResponse with ranked model entries and period
 */
export async function fetchLeaderboard(days?: number): Promise<LeaderboardResponse> {
  const queryParams = new URLSearchParams();
  if (days !== undefined) {
    queryParams.append('days', String(days));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/leaderboard?${queryString}` : '/leaderboard';

  return fetchAuditApi<LeaderboardResponse>(endpoint);
}

/**
 * Fetch aggregated prompt improvement recommendations.
 *
 * Analyzes all audits to produce actionable recommendations for
 * improving the AI pipeline prompt templates.
 *
 * @param days - Number of days to analyze (1-90, default 7)
 * @returns RecommendationsResponse with prioritized recommendations
 */
export async function fetchRecommendations(days?: number): Promise<RecommendationsResponse> {
  const queryParams = new URLSearchParams();
  if (days !== undefined) {
    queryParams.append('days', String(days));
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/recommendations?${queryString}` : '/recommendations';

  return fetchAuditApi<RecommendationsResponse>(endpoint);
}

/**
 * Trigger batch audit processing for multiple events.
 *
 * Queues events for audit processing based on the provided criteria.
 * Events are processed synchronously in this implementation.
 *
 * @param limit - Maximum number of events to process (1-1000, default 100)
 * @param minRiskScore - Minimum risk score filter (0-100, optional)
 * @param forceReevaluate - Whether to re-evaluate already evaluated events (default: false)
 * @returns BatchAuditResponse with number of processed events
 */
export async function triggerBatchAudit(
  limit?: number,
  minRiskScore?: number,
  forceReevaluate?: boolean
): Promise<BatchAuditResponse> {
  const body: {
    limit?: number;
    min_risk_score?: number;
    force_reevaluate?: boolean;
  } = {};

  if (limit !== undefined) {
    body.limit = limit;
  }
  if (minRiskScore !== undefined) {
    body.min_risk_score = minRiskScore;
  }
  if (forceReevaluate !== undefined) {
    body.force_reevaluate = forceReevaluate;
  }

  return fetchAuditApi<BatchAuditResponse>('/batch', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
