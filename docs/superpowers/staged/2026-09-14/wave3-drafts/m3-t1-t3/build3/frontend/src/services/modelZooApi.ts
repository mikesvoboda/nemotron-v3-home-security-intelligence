/**
 * Model Zoo API Client
 *
 * Provides typed fetch wrappers for Model Zoo REST endpoints including:
 * - Model listing with runtime state
 * - Model load/unload operations
 * - VRAM summary per GPU
 *
 * @see docs/plans/2025-01-31-model-zoo-management-design.md - Design document
 * @see NEM-4788 - TDD tests for frontend
 */

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

// ============================================================================
// Types
// ============================================================================

/**
 * Runtime state of a model in GPU memory.
 */
export interface ModelRuntime {
  /** Whether the model is currently loaded in GPU memory */
  loaded: boolean;
  /** Actual VRAM usage in MB (null if not loaded) */
  actual_vram_mb: number | null;
  /** ISO timestamp of last use (null if never used) */
  last_used: string | null;
  /** Number of times the model has been loaded */
  load_count: number;
}

/**
 * Model status combining registry metadata and runtime state.
 */
export interface ModelStatus {
  /** Model identifier (e.g., "threat-detection-yolov8n") */
  name: string;
  /** Model category (e.g., "detection", "classification", "embedding") */
  category: string;
  /** Estimated VRAM usage in MB from registry */
  estimated_vram_mb: number;
  /** Whether the model is enabled in config */
  enabled: boolean;
  /** Enrichment service that handles this model */
  service: string;
  /** GPU index assigned to this model */
  gpu_id: number;
  /** Runtime state (null if enrichment service is down) */
  runtime: ModelRuntime | null;
}

/**
 * Service health status for model management.
 */
export type ServiceHealthStatus = 'healthy' | 'unhealthy' | 'unknown';

/**
 * Response from GET /api/system/models
 */
export interface ModelListResponse {
  /** List of all models with registry and runtime state */
  models: ModelStatus[];
  /** Health status of each enrichment service */
  service_status: Record<string, ServiceHealthStatus>;
}

/**
 * Per-GPU VRAM information.
 */
export interface GpuVRAMInfo {
  /** GPU index */
  gpu_id: number;
  /** Enrichment service handling this GPU */
  service: string;
  /** Total VRAM budget in MB */
  budget_mb: number;
  /** Currently used VRAM in MB */
  used_mb: number;
  /** Available VRAM in MB */
  available_mb: number;
  /** VRAM utilization percentage */
  utilization_percent: number;
  /** Names of currently loaded models */
  loaded_models: string[];
}

/**
 * VRAM summary totals across all GPUs.
 */
export interface VRAMTotals {
  /** Total VRAM budget across all GPUs in MB */
  budget_mb: number;
  /** Total used VRAM across all GPUs in MB */
  used_mb: number;
  /** Total available VRAM across all GPUs in MB */
  available_mb: number;
  /** Total number of loaded models */
  model_count: number;
}

/**
 * Response from GET /api/system/models/vram-summary
 */
export interface VRAMSummaryResponse {
  /** Per-GPU VRAM breakdown */
  gpus: GpuVRAMInfo[];
  /** Totals across all GPUs */
  totals: VRAMTotals;
}

/**
 * Response from POST /api/system/models/{name}/load
 */
export interface LoadModelResponse {
  /** Whether the load operation succeeded */
  success: boolean;
  /** Model name that was loaded */
  model_name: string;
  /** Service that loaded the model */
  service: string;
  /** GPU index where model was loaded */
  gpu_id: number;
  /** Time taken to load in milliseconds */
  load_time_ms: number;
  /** Actual VRAM used in MB */
  vram_mb: number;
}

/**
 * Response from POST /api/system/models/{name}/unload
 */
export interface UnloadModelResponse {
  /** Whether the unload operation succeeded */
  success: boolean;
  /** Model name that was unloaded */
  model_name: string;
  /** VRAM freed in MB */
  freed_vram_mb: number;
}

/**
 * Response from POST /api/system/models/unload-all
 */
export interface UnloadAllResponse {
  /** Whether all unload operations succeeded */
  success: boolean;
  /** Number of models unloaded */
  unloaded_count: number;
  /** Total VRAM freed in MB */
  total_freed_vram_mb: number;
  /** Any errors that occurred */
  errors: string[];
}

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for Model Zoo API failures.
 * Includes HTTP status code and parsed error data.
 */
export class ModelZooApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'ModelZooApiError';
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

    throw new ModelZooApiError(response.status, errorMessage, errorData);
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new ModelZooApiError(response.status, 'Failed to parse response JSON', error);
  }
}

/**
 * Perform a fetch request to the Model Zoo API with error handling.
 *
 * @param endpoint - API endpoint path (relative to /api/system)
 * @param options - Optional fetch options
 * @returns Parsed JSON response
 */
async function fetchModelZooApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}/api/system${endpoint}`;

  const fetchOptions: RequestInit = {
    ...options,
    headers: buildHeaders(),
  };

  try {
    const response = await fetch(url, fetchOptions);
    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof ModelZooApiError) {
      throw error;
    }
    throw new ModelZooApiError(
      0,
      error instanceof Error ? error.message : 'Network request failed'
    );
  }
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List all models with registry metadata and runtime state.
 *
 * Returns models from both enrichment services combined with their
 * static configuration and current runtime state.
 *
 * @returns ModelListResponse containing all models and service status
 * @throws ModelZooApiError on server errors
 *
 * @example
 * ```typescript
 * const { models, service_status } = await listModels();
 * const loadedModels = models.filter(m => m.runtime?.loaded);
 * ```
 */
export async function listModels(): Promise<ModelListResponse> {
  return fetchModelZooApi<ModelListResponse>('/models');
}

/**
 * Get VRAM usage summary per GPU.
 *
 * Returns detailed VRAM breakdown for each GPU including budget,
 * usage, and currently loaded models.
 *
 * @returns VRAMSummaryResponse with per-GPU and total VRAM info
 * @throws ModelZooApiError on server errors
 *
 * @example
 * ```typescript
 * const { gpus, totals } = await getVRAMSummary();
 * const gpu0Usage = gpus.find(g => g.gpu_id === 0);
 * console.log(`GPU 0: ${gpu0Usage.used_mb}/${gpu0Usage.budget_mb} MB`);
 * ```
 */
export async function getVRAMSummary(): Promise<VRAMSummaryResponse> {
  return fetchModelZooApi<VRAMSummaryResponse>('/models/vram-summary');
}

/**
 * Load a model into GPU memory.
 *
 * Proxies to the appropriate enrichment service based on model assignment.
 * The model must be enabled in the configuration.
 *
 * @param modelName - Name of the model to load
 * @returns LoadModelResponse with timing and VRAM info
 * @throws ModelZooApiError on load failure or if model not found
 *
 * @example
 * ```typescript
 * const result = await loadModel('threat-detection-yolov8n');
 * console.log(`Loaded in ${result.load_time_ms}ms, using ${result.vram_mb}MB`);
 * ```
 */
export async function loadModel(modelName: string): Promise<LoadModelResponse> {
  return fetchModelZooApi<LoadModelResponse>(`/models/${encodeURIComponent(modelName)}/load`, {
    method: 'POST',
  });
}

/**
 * Unload a model from GPU memory.
 *
 * Frees the VRAM used by the model. The model will need to be
 * reloaded on next use, which may cause latency.
 *
 * @param modelName - Name of the model to unload
 * @returns UnloadModelResponse with freed VRAM info
 * @throws ModelZooApiError on unload failure or if model not found
 *
 * @example
 * ```typescript
 * const result = await unloadModel('vehicle-segment-classification');
 * console.log(`Freed ${result.freed_vram_mb}MB VRAM`);
 * ```
 */
export async function unloadModel(modelName: string): Promise<UnloadModelResponse> {
  return fetchModelZooApi<UnloadModelResponse>(`/models/${encodeURIComponent(modelName)}/unload`, {
    method: 'POST',
  });
}

/**
 * Reload a model (unload then load).
 *
 * Useful for refreshing model state or after configuration changes.
 *
 * @param modelName - Name of the model to reload
 * @returns LoadModelResponse with timing and VRAM info
 * @throws ModelZooApiError on reload failure
 *
 * @example
 * ```typescript
 * const result = await reloadModel('fashion-clip');
 * console.log(`Reloaded in ${result.load_time_ms}ms`);
 * ```
 */
export async function reloadModel(modelName: string): Promise<LoadModelResponse> {
  return fetchModelZooApi<LoadModelResponse>(`/models/${encodeURIComponent(modelName)}/reload`, {
    method: 'POST',
  });
}

/**
 * Unload all models from all GPUs.
 *
 * Frees all VRAM used by loaded models. Models will need to be
 * reloaded on demand, which may cause initial latency.
 *
 * @returns UnloadAllResponse with total freed VRAM and any errors
 * @throws ModelZooApiError on server errors
 *
 * @example
 * ```typescript
 * const result = await unloadAllModels();
 * console.log(`Unloaded ${result.unloaded_count} models, freed ${result.total_freed_vram_mb}MB`);
 * ```
 */
export async function unloadAllModels(): Promise<UnloadAllResponse> {
  return fetchModelZooApi<UnloadAllResponse>('/models/unload-all', {
    method: 'POST',
  });
}

/**
 * Model Zoo API client object for convenient imports.
 */
export const modelZooApi = {
  listModels,
  getVRAMSummary,
  loadModel,
  unloadModel,
  reloadModel,
  unloadAllModels,
};
