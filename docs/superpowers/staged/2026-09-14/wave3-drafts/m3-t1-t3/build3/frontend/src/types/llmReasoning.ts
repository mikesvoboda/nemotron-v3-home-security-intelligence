/**
 * Types for LLM Reasoning Explorer feature.
 *
 * These types represent the data structures returned by the
 * /api/llm-reasoning endpoints for displaying LLM reasoning transparency.
 */

/**
 * Source of enrichment data that was used in analysis.
 */
export interface EnrichmentSource {
  /** Name of the enrichment source/model */
  name: string;
  /** Whether this source provided data */
  populated: boolean;
  /** Number of fields populated by this source */
  fieldCount: number;
  /** Sample field names from this source */
  sampleFields: string[];
}

/**
 * Information about what context was truncated due to token limits.
 */
export interface TruncationInfo {
  /** Whether any context was truncated */
  wasTruncated: boolean;
  /** Original context length in tokens */
  originalLength: number | null;
  /** Final context length in tokens */
  truncatedLength: number | null;
  /** Names of sections that were dropped/truncated */
  droppedSections: string[];
  /** Reason for truncation */
  truncationReason: string | null;
}

/**
 * A single reasoning step extracted from think blocks.
 */
export interface ReasoningStep {
  /** Sequential step number */
  stepNumber: number;
  /** The reasoning content for this step */
  content: string;
  /** Key factors identified in this reasoning step */
  keyFactors: string[];
  /** Confidence level mentioned in this step (high/medium/low) */
  confidenceIndicator: 'high' | 'medium' | 'low' | null;
}

/**
 * Parsed content from <think> blocks in LLM response.
 */
export interface ThinkBlockContent {
  /** Raw content of <think> block */
  rawThinkBlock: string | null;
  /** Parsed reasoning steps from the think block */
  reasoningSteps: ReasoningStep[];
  /** Key observations extracted from reasoning */
  keyObservations: string[];
  /** Risk factors explicitly mentioned in reasoning */
  riskFactorsMentioned: string[];
}

/**
 * A matched household member from the analysis.
 */
export interface HouseholdMatch {
  /** Type of entity (person, vehicle, pet) */
  entityType: string;
  /** Name of matched entity if available */
  entityName: string | null;
  /** Similarity score (0-1) */
  similarityScore: number;
  /** Method used for matching */
  matchMethod: string | null;
}

/**
 * Debug information for prompt inspection.
 */
export interface LLMReasoningDebugInfo {
  /** Length of the prompt sent to LLM */
  promptLength?: number;
  /** Keys present in the enrichment snapshot */
  enrichmentSnapshotKeys?: string[];
  /** Context sources tracking data */
  contextSources?: Record<string, boolean> | null;
  /** Validation result for synthetic data testing */
  validationResult?: Record<string, unknown> | null;
  /** Whether truncation log is present */
  hasTruncationLog?: boolean;
  /** Whether household matches are present */
  hasHouseholdMatches?: boolean;
}

/**
 * Full LLM reasoning explorer response for an event.
 */
export interface LLMReasoningResponse {
  /** LLM interaction record ID */
  id: number;
  /** Associated event ID */
  eventId: number;
  /** When the analysis occurred */
  createdAt: string;
  /** Full raw LLM response */
  rawResponse: string;
  /** Parsed content from <think> blocks */
  thinkBlock: ThinkBlockContent;
  /** Sources that contributed enrichment data */
  enrichmentSources: EnrichmentSource[];
  /** Information about context truncation */
  truncationInfo: TruncationInfo;
  /** Matched household members/vehicles */
  householdMatches: HouseholdMatch[];
  /** Additional debug information for prompt inspection */
  debugInfo: LLMReasoningDebugInfo;
}

/**
 * Response when no LLM reasoning data is available for an event.
 */
export interface LLMReasoningNotFoundResponse {
  /** The event ID that was queried */
  eventId: number;
  /** Human-readable message */
  message: string;
  /** Reason why reasoning data is not available */
  reason: string | null;
}

/**
 * Debug prompt data response.
 */
export interface LLMPromptDebugResponse {
  /** Event ID */
  eventId: number;
  /** Full prompt text sent to LLM */
  llmPrompt: string | null;
  /** Frozen enrichment data snapshot */
  enrichmentSnapshot: Record<string, unknown>;
  /** Context sources tracking */
  contextSources: Record<string, boolean> | null;
  /** Truncation log data */
  truncationLog: Record<string, unknown> | null;
  /** Household matches data */
  householdMatches: Record<string, unknown>[] | null;
  /** Validation result */
  validationResult: Record<string, unknown> | null;
}
