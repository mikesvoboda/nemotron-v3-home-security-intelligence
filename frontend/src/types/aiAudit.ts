/**
 * TypeScript types for AI Audit API
 *
 * Mirrors backend schemas from:
 * @see backend/api/schemas/ai_audit.py
 * @see backend/api/routes/ai_audit.py
 */

// ============================================================================
// Model Enums
// ============================================================================

/**
 * Supported AI models for prompt configuration.
 * Uses underscore naming to match backend conventions.
 */
export type AiModelName = 'nemotron' | 'florence2' | 'yolo_world' | 'xclip' | 'fashion_clip';

/**
 * Supported AI models for database-backed prompt config.
 * Uses hyphen naming as specified in the API spec.
 */
export type DbModelName = 'nemotron' | 'florence-2' | 'yolo-world' | 'x-clip' | 'fashion-clip';

/**
 * Priority level for recommendations.
 */
export type RecommendationPriority = 'high' | 'medium' | 'low';

/**
 * Risk level for events.
 */
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

// ============================================================================
// Core Audit Types
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
export interface EventAuditResponse {
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

// ============================================================================
// Statistics Types
// ============================================================================

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
export interface AuditStatsResponse {
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

// ============================================================================
// Leaderboard Types
// ============================================================================

/**
 * Single entry in the model leaderboard.
 */
export interface ModelLeaderboardEntry {
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
  entries: ModelLeaderboardEntry[];
  /** Number of days included in the analysis */
  period_days: number;
}

// ============================================================================
// Recommendations Types
// ============================================================================

/**
 * Single recommendation item.
 */
export interface RecommendationItem {
  /** Category: missing_context, unused_data, model_gaps, etc. */
  category: string;
  /** The specific suggestion */
  suggestion: string;
  /** Number of events that mentioned this suggestion */
  frequency: number;
  /** Priority level: high, medium, low */
  priority: RecommendationPriority;
}

/**
 * Aggregated recommendations response.
 */
export interface RecommendationsResponse {
  /** List of prioritized recommendations */
  recommendations: RecommendationItem[];
  /** Total number of events analyzed */
  total_events_analyzed: number;
}

// ============================================================================
// Batch Audit Types
// ============================================================================

/**
 * Request for batch audit processing.
 */
export interface BatchAuditRequest {
  /** Maximum number of events to process (1-1000, default 100) */
  limit?: number;
  /** Minimum risk score filter (0-100, optional) */
  min_risk_score?: number;
  /** Whether to re-evaluate already evaluated events (default: false) */
  force_reevaluate?: boolean;
}

/**
 * Response for batch audit request.
 */
export interface BatchAuditResponse {
  /** Number of events queued for processing */
  queued_count: number;
  /** Status message */
  message: string;
}

// ============================================================================
// Prompt Playground Types
// ============================================================================

/**
 * Response for a single model's prompt configuration.
 */
export interface ModelPromptResponse {
  /** Name of the AI model */
  model_name: string;
  /** Current configuration for this model */
  config: Record<string, unknown>;
  /** Current version number */
  version: number;
  /** When last updated */
  updated_at: string;
}

/**
 * Response containing prompts for all models.
 */
export interface AllPromptsResponse {
  /** Dictionary mapping model names to their configurations */
  prompts: Record<string, ModelPromptResponse>;
}

/**
 * Request to update a model's prompt configuration.
 */
export interface PromptUpdateRequest {
  /** New configuration for the model */
  config: Record<string, unknown>;
  /** Description of the changes */
  description?: string;
}

/**
 * Response after updating a model's prompt.
 */
export interface PromptUpdateResponse {
  /** Model name */
  model_name: string;
  /** New version number */
  version: number;
  /** Success message */
  message: string;
  /** Updated configuration */
  config: Record<string, unknown>;
}

// ============================================================================
// Prompt Testing Types
// ============================================================================

/**
 * Request to test a modified prompt configuration against an event.
 */
export interface PromptTestRequest {
  /** Model name to test (nemotron, florence2, etc.) */
  model: AiModelName;
  /** Modified configuration to test */
  config: Record<string, unknown>;
  /** Event ID to test against */
  event_id: number;
}

/**
 * Result from the original (current) prompt.
 */
export interface PromptTestResultBefore {
  /** Risk score from original prompt */
  score: number;
  /** Risk level (low, medium, high, critical) */
  risk_level: RiskLevel;
  /** Summary from original analysis */
  summary: string;
}

/**
 * Result from the modified prompt.
 */
export interface PromptTestResultAfter {
  /** Risk score from modified prompt */
  score: number;
  /** Risk level (low, medium, high, critical) */
  risk_level: RiskLevel;
  /** Summary from modified analysis */
  summary: string;
}

/**
 * Response from testing a modified prompt.
 */
export interface PromptTestResponse {
  /** Results from original prompt */
  before: PromptTestResultBefore;
  /** Results from modified prompt */
  after: PromptTestResultAfter;
  /** Whether the modification improved results */
  improved: boolean;
  /** Time taken for inference in ms */
  inference_time_ms: number;
}

// ============================================================================
// Prompt History Types
// ============================================================================

/**
 * A single entry in prompt version history.
 */
export interface PromptHistoryEntry {
  /** Version number */
  version: number;
  /** Configuration at this version */
  config: Record<string, unknown>;
  /** When this version was created */
  created_at: string;
  /** Who created this version */
  created_by: string;
  /** Description of changes */
  description: string | null;
}

/**
 * Response containing version history for a model's prompts.
 */
export interface PromptHistoryResponse {
  /** Model name */
  model_name: string;
  /** List of version entries */
  versions: PromptHistoryEntry[];
  /** Total number of versions */
  total_versions: number;
}

/**
 * Response containing version history for all models.
 */
export interface AllPromptsHistoryResponse {
  /** Dictionary mapping model names to their version histories */
  [modelName: string]: PromptHistoryResponse;
}

// ============================================================================
// Prompt Import/Export Types
// ============================================================================

/**
 * Response containing all prompt configurations for export.
 */
export interface PromptExportResponse {
  /** When the export was created */
  exported_at: string;
  /** Export format version */
  version: string;
  /** All model configurations keyed by model name */
  prompts: Record<string, Record<string, unknown>>;
}

/**
 * Request to import prompt configurations.
 */
export interface PromptImportRequest {
  /** Model configurations to import, keyed by model name */
  prompts: Record<string, Record<string, unknown>>;
  /** Whether to overwrite existing configurations */
  overwrite?: boolean;
}

/**
 * Response after importing prompt configurations.
 */
export interface PromptImportResponse {
  /** Number of models imported */
  imported_count: number;
  /** Number of models skipped */
  skipped_count: number;
  /** Any errors encountered */
  errors: string[];
  /** Status message */
  message: string;
}

// ============================================================================
// Database-backed Prompt Config Types
// ============================================================================

/**
 * Request to update a model's prompt configuration (database-backed).
 */
export interface PromptConfigRequest {
  /** Full system prompt text for the model */
  systemPrompt: string;
  /** LLM temperature setting (0-2) */
  temperature?: number;
  /** Maximum tokens in response (100-8192) */
  maxTokens?: number;
}

/**
 * Response containing a model's prompt configuration (database-backed).
 */
export interface PromptConfigResponse {
  /** Model name */
  model: string;
  /** Full system prompt text for the model */
  systemPrompt: string;
  /** LLM temperature setting (0-2) */
  temperature: number;
  /** Maximum tokens in response (100-8192) */
  maxTokens: number;
  /** Configuration version number */
  version: number;
  /** When the configuration was last updated */
  updatedAt: string;
}
