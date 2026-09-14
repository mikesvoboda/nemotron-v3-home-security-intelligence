/**
 * TypeScript types for Prompt Management API
 *
 * Mirrors backend schemas from:
 * @see backend/api/schemas/prompt_management.py
 * @see backend/api/routes/prompt_management.py
 */

// ============================================================================
// Enums
// ============================================================================

/**
 * Supported AI models for prompt configuration.
 */
export enum AIModelEnum {
  NEMOTRON = 'nemotron',
  FLORENCE2 = 'florence2',
  YOLO_WORLD = 'yolo_world',
  XCLIP = 'xclip',
  FASHION_CLIP = 'fashion_clip',
}

// ============================================================================
// Configuration Types
// ============================================================================

/**
 * Configuration for Nemotron risk analysis model.
 */
export interface NemotronConfig {
  system_prompt: string;
  version?: number;
}

/**
 * Configuration for Florence-2 scene analysis model.
 */
export interface Florence2Config {
  queries: string[];
}

/**
 * Configuration for YOLO-World custom object detection.
 */
export interface YoloWorldConfig {
  classes: string[];
  confidence_threshold: number;
}

/**
 * Configuration for X-CLIP action recognition model.
 */
export interface XClipConfig {
  action_classes: string[];
}

/**
 * Configuration for Fashion-CLIP clothing analysis model.
 */
export interface FashionClipConfig {
  clothing_categories: string[];
}

/**
 * Union type for all model configurations.
 */
export type ModelConfig =
  | NemotronConfig
  | Florence2Config
  | YoloWorldConfig
  | XClipConfig
  | FashionClipConfig;

// ============================================================================
// Request/Response Types
// ============================================================================

/**
 * Configuration for a specific AI model.
 */
export interface ModelPromptConfig {
  model: AIModelEnum;
  config: Record<string, unknown>;
  version: number;
  created_at?: string;
  created_by?: string;
  change_description?: string;
}

/**
 * Response containing prompts for all configurable models.
 */
export interface AllPromptsResponse {
  version: string;
  exported_at: string;
  prompts: Record<string, Record<string, unknown>>;
}

/**
 * Request to update a model's prompt configuration.
 */
export interface PromptUpdateRequest {
  config: Record<string, unknown>;
  change_description?: string;
}

/**
 * Information about a single prompt version.
 */
export interface PromptVersionInfo {
  id: number;
  model: AIModelEnum;
  version: number;
  created_at: string;
  created_by?: string;
  change_description?: string;
  is_active: boolean;
}

/**
 * Response containing version history for prompts.
 */
export interface PromptHistoryResponse {
  versions: PromptVersionInfo[];
  total_count: number;
}

/**
 * Request to test a prompt with modified configuration.
 */
export interface PromptTestRequest {
  model: AIModelEnum;
  config: Record<string, unknown>;
  event_id?: number;
  image_path?: string;
}

/**
 * Result of a prompt test.
 */
export interface PromptTestResult {
  model: AIModelEnum;
  before_score?: number;
  after_score?: number;
  before_response?: Record<string, unknown>;
  after_response?: Record<string, unknown>;
  improved?: boolean;
  test_duration_ms: number;
  error?: string;
}

/**
 * Response after restoring a prompt version.
 */
export interface PromptRestoreResponse {
  restored_version: number;
  model: AIModelEnum;
  new_version: number;
  message: string;
}

/**
 * Export of all prompt configurations.
 */
export interface PromptsExportResponse {
  version: string;
  exported_at: string;
  prompts: Record<string, Record<string, unknown>>;
}

/**
 * Request to import prompt configurations.
 */
export interface PromptsImportRequest {
  version: string;
  prompts: Record<string, Record<string, unknown>>;
}

/**
 * Response after importing prompt configurations.
 */
export interface PromptsImportResponse {
  imported_models: string[];
  skipped_models: string[];
  new_versions: Record<string, number>;
  message: string;
}

/**
 * Diff entry for a single model's configuration.
 */
export interface PromptDiffEntry {
  model: string;
  has_changes: boolean;
  current_version?: number;
  current_config?: Record<string, unknown>;
  imported_config: Record<string, unknown>;
  changes: string[];
}

/**
 * Request to preview prompt configuration import without applying.
 */
export interface PromptsImportPreviewRequest {
  version: string;
  prompts: Record<string, Record<string, unknown>>;
}

/**
 * Response with preview of import changes.
 */
export interface PromptsImportPreviewResponse {
  version: string;
  valid: boolean;
  validation_errors: string[];
  diffs: PromptDiffEntry[];
  total_changes: number;
  unknown_models: string[];
}
