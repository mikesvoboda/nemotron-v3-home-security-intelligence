/**
 * API client for LLM Reasoning Explorer feature.
 *
 * Provides functions to fetch LLM reasoning data from the backend,
 * including think blocks, enrichment sources, and debug information.
 */

import type {
  LLMReasoningResponse,
  LLMPromptDebugResponse,
  EnrichmentSource,
  TruncationInfo,
  ReasoningStep,
  ThinkBlockContent,
  HouseholdMatch,
  LLMReasoningDebugInfo,
} from '../types/llmReasoning';

/** Base URL for API requests, read from environment variable */
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';

/**
 * Custom error class for LLM Reasoning API errors.
 */
export class LLMReasoningApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public eventId?: number,
    public reason?: string
  ) {
    super(message);
    this.name = 'LLMReasoningApiError';
  }
}

/** API response shape for enrichment source */
interface ApiEnrichmentSource {
  name?: string;
  populated?: boolean;
  field_count?: number;
  sample_fields?: string[];
}

/** API response shape for truncation info */
interface ApiTruncationInfo {
  was_truncated?: boolean;
  original_length?: number | null;
  truncated_length?: number | null;
  dropped_sections?: string[];
  truncation_reason?: string | null;
}

/** API response shape for reasoning step */
interface ApiReasoningStep {
  step_number?: number;
  content?: string;
  key_factors?: string[];
  confidence_indicator?: string | null;
}

/** API response shape for think block */
interface ApiThinkBlock {
  raw_think_block?: string | null;
  reasoning_steps?: ApiReasoningStep[];
  key_observations?: string[];
  risk_factors_mentioned?: string[];
}

/** API response shape for household match */
interface ApiHouseholdMatch {
  entity_type?: string;
  entity_name?: string | null;
  similarity_score?: number;
  match_method?: string | null;
}

/** API response shape for debug info */
interface ApiDebugInfo {
  prompt_length?: number;
  enrichment_snapshot_keys?: string[];
  context_sources?: Record<string, boolean>;
  validation_result?: Record<string, unknown>;
  has_truncation_log?: boolean;
  has_household_matches?: boolean;
}

/** API response shape for LLM reasoning */
interface ApiLLMReasoningResponse {
  id?: number;
  event_id?: number;
  created_at?: string;
  raw_response?: string;
  think_block?: ApiThinkBlock;
  enrichment_sources?: ApiEnrichmentSource[];
  truncation_info?: ApiTruncationInfo;
  household_matches?: ApiHouseholdMatch[];
  debug_info?: ApiDebugInfo;
}

/** API response shape for LLM prompt debug */
interface ApiLLMPromptDebugResponse {
  event_id?: number;
  llm_prompt?: string | null;
  enrichment_snapshot?: Record<string, unknown>;
  context_sources?: Record<string, boolean> | null;
  truncation_log?: Record<string, unknown> | null;
  household_matches?: Record<string, unknown>[] | null;
  validation_result?: Record<string, unknown> | null;
}

/** API error detail shape */
interface ApiErrorDetail {
  message?: string;
  event_id?: number;
  reason?: string;
}

/** API error response shape */
interface ApiErrorResponse {
  detail?: ApiErrorDetail | string;
}

/**
 * Transform snake_case API response to camelCase for frontend.
 */
function transformEnrichmentSource(source: ApiEnrichmentSource): EnrichmentSource {
  return {
    name: source.name ?? '',
    populated: Boolean(source.populated),
    fieldCount: source.field_count ?? 0,
    sampleFields: source.sample_fields ?? [],
  };
}

function transformTruncationInfo(info: ApiTruncationInfo): TruncationInfo {
  return {
    wasTruncated: Boolean(info.was_truncated),
    originalLength: info.original_length ?? null,
    truncatedLength: info.truncated_length ?? null,
    droppedSections: info.dropped_sections ?? [],
    truncationReason: info.truncation_reason ?? null,
  };
}

function transformReasoningStep(step: ApiReasoningStep): ReasoningStep {
  const confidenceIndicator = step.confidence_indicator;
  return {
    stepNumber: step.step_number ?? 0,
    content: step.content ?? '',
    keyFactors: step.key_factors ?? [],
    confidenceIndicator:
      confidenceIndicator === 'high' || confidenceIndicator === 'medium' || confidenceIndicator === 'low'
        ? confidenceIndicator
        : null,
  };
}

function transformThinkBlock(block: ApiThinkBlock): ThinkBlockContent {
  return {
    rawThinkBlock: block.raw_think_block ?? null,
    reasoningSteps: (block.reasoning_steps ?? []).map(transformReasoningStep),
    keyObservations: block.key_observations ?? [],
    riskFactorsMentioned: block.risk_factors_mentioned ?? [],
  };
}

function transformHouseholdMatch(match: ApiHouseholdMatch): HouseholdMatch {
  return {
    entityType: match.entity_type ?? 'unknown',
    entityName: match.entity_name ?? null,
    similarityScore: match.similarity_score ?? 0,
    matchMethod: match.match_method ?? null,
  };
}

function transformDebugInfo(info: ApiDebugInfo): LLMReasoningDebugInfo {
  return {
    promptLength: info.prompt_length,
    enrichmentSnapshotKeys: info.enrichment_snapshot_keys,
    contextSources: info.context_sources,
    validationResult: info.validation_result,
    hasTruncationLog: info.has_truncation_log,
    hasHouseholdMatches: info.has_household_matches,
  };
}

function transformLLMReasoningResponse(data: ApiLLMReasoningResponse): LLMReasoningResponse {
  return {
    id: data.id ?? 0,
    eventId: data.event_id ?? 0,
    createdAt: data.created_at ?? '',
    rawResponse: data.raw_response ?? '',
    thinkBlock: transformThinkBlock(data.think_block ?? {}),
    enrichmentSources: (data.enrichment_sources ?? []).map(transformEnrichmentSource),
    truncationInfo: transformTruncationInfo(data.truncation_info ?? {}),
    householdMatches: (data.household_matches ?? []).map(transformHouseholdMatch),
    debugInfo: transformDebugInfo(data.debug_info ?? {}),
  };
}

function transformLLMPromptDebugResponse(data: ApiLLMPromptDebugResponse): LLMPromptDebugResponse {
  return {
    eventId: data.event_id ?? 0,
    llmPrompt: data.llm_prompt ?? null,
    enrichmentSnapshot: data.enrichment_snapshot ?? {},
    contextSources: data.context_sources ?? null,
    truncationLog: data.truncation_log ?? null,
    householdMatches: data.household_matches ?? null,
    validationResult: data.validation_result ?? null,
  };
}

/**
 * Fetch LLM reasoning data for a specific event.
 *
 * @param eventId - The event ID to fetch reasoning for
 * @param includeDebug - Whether to include debug information
 * @returns Promise resolving to LLMReasoningResponse
 * @throws LLMReasoningApiError on failure
 */
export async function fetchLLMReasoning(
  eventId: number,
  includeDebug = false
): Promise<LLMReasoningResponse> {
  const url = new URL(`${BASE_URL}/api/llm-reasoning/events/${eventId}`, window.location.origin);
  if (includeDebug) {
    url.searchParams.set('include_debug', 'true');
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as ApiErrorResponse;
    const detail = errorData.detail;

    if (response.status === 404) {
      const detailObj = typeof detail === 'object' ? detail : null;
      throw new LLMReasoningApiError(
        detailObj?.message ?? 'LLM reasoning not found',
        response.status,
        detailObj?.event_id ?? eventId,
        detailObj?.reason
      );
    }

    throw new LLMReasoningApiError(
      typeof detail === 'string' ? detail : 'Failed to fetch LLM reasoning',
      response.status,
      eventId
    );
  }

  const data = (await response.json()) as ApiLLMReasoningResponse;
  return transformLLMReasoningResponse(data);
}

/**
 * Fetch full prompt debug data for a specific event.
 *
 * @param eventId - The event ID to fetch prompt data for
 * @returns Promise resolving to LLMPromptDebugResponse
 * @throws LLMReasoningApiError on failure
 */
export async function fetchLLMPromptDebug(eventId: number): Promise<LLMPromptDebugResponse> {
  const url = `${BASE_URL}/api/llm-reasoning/events/${eventId}/prompt`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as ApiErrorResponse;
    const detail = errorData.detail;
    const detailObj = typeof detail === 'object' ? detail : null;

    throw new LLMReasoningApiError(
      typeof detail === 'string' ? detail : detailObj?.message ?? 'Failed to fetch prompt data',
      response.status,
      eventId
    );
  }

  const data = (await response.json()) as ApiLLMPromptDebugResponse;
  return transformLLMPromptDebugResponse(data);
}
