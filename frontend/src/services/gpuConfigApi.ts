/**
 * GPU Configuration API Client
 *
 * Provides typed fetch wrappers for GPU configuration REST endpoints including:
 * - GPU detection and listing
 * - GPU assignment configuration (strategy-based and manual)
 * - Configuration application and service restart
 * - Service status monitoring
 *
 * @see backend/api/routes/gpu_config.py - Backend implementation
 * @see docs/plans/2025-01-23-multi-gpu-support-design.md - Design document
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
 * GPU device information including hardware specs and utilization.
 */
export interface GpuDevice {
  /** GPU index (0-based) */
  index: number;
  /** GPU model name (e.g., "RTX A5500") */
  name: string;
  /** Total VRAM in megabytes */
  vram_total_mb: number;
  /** Currently used VRAM in megabytes */
  vram_used_mb: number;
  /** CUDA compute capability (e.g., "8.6") */
  compute_capability: string;
}

/**
 * Response from GPU list endpoint.
 */
export interface GpuListResponse {
  /** List of detected GPU devices */
  gpus: GpuDevice[];
}

/**
 * GPU assignment for a single AI service.
 */
export interface GpuAssignment {
  /** Service name (e.g., "ai-llm", "ai-yolo26") */
  service: string;
  /** Assigned GPU index, or null for auto-assignment */
  gpu_index: number | null;
  /** Optional VRAM budget override in GB */
  vram_budget_override?: number | null;
}

/**
 * GPU configuration including strategy and all service assignments.
 * Matches backend GpuConfigResponse schema.
 */
export interface GpuConfig {
  /** Current assignment strategy */
  strategy: string;
  /** Service-to-GPU assignments */
  assignments: GpuAssignment[];
  /** Timestamp of last configuration update (ISO 8601 format) */
  updated_at: string | null;
}

/**
 * Request body for updating GPU configuration.
 */
export interface GpuConfigUpdateRequest {
  /** New assignment strategy (optional) */
  strategy?: string;
  /** New service assignments (optional) */
  assignments?: GpuAssignment[];
}

/**
 * Response from GPU configuration update.
 */
export interface GpuConfigUpdateResponse {
  /** Whether the update was successful */
  success: boolean;
  /** Any warnings about the configuration (e.g., VRAM overages) */
  warnings: string[];
}

/**
 * Result of applying GPU configuration (restarting services).
 * Matches backend GpuApplyResponse schema.
 */
export interface GpuApplyResult {
  /** Whether the apply operation was successful */
  success: boolean;
  /** Warnings encountered during apply */
  warnings: string[];
  /** List of services that were restarted */
  restarted_services: string[];
  /** Status of each affected service after apply */
  service_statuses: ServiceStatus[];
}

/**
 * Status of a single AI service after GPU config apply.
 * Matches backend ServiceStatus schema.
 */
export interface ServiceStatus {
  /** Service name */
  service: string;
  /** Service status (running, starting, stopped, error) */
  status: string;
  /** Optional status message or error details */
  message: string | null;
}

/**
 * Response from GPU status endpoint.
 * Matches backend GpuConfigStatusResponse schema.
 */
export interface GpuStatusResponse {
  /** Whether an apply operation is currently in progress */
  in_progress: boolean;
  /** Services still pending restart */
  services_pending: string[];
  /** Services that have completed restart */
  services_completed: string[];
  /** Current status of all affected services */
  service_statuses: ServiceStatus[];
}

/**
 * Response from strategy preview endpoint.
 */
export interface StrategyPreviewResponse {
  /** Strategy used for preview */
  strategy: string;
  /** Proposed assignments for the given strategy */
  proposed_assignments: GpuAssignment[];
  /** Warnings about the proposed configuration */
  warnings: string[];
}

/**
 * AI service information from backend.
 */
export interface AiService {
  /** Service name (e.g., 'ai-llm') */
  name: string;
  /** Human-readable display name */
  display_name: string;
  /** VRAM requirement in megabytes */
  vram_required_mb: number;
  /** VRAM requirement in gigabytes */
  vram_required_gb: number;
  /** Service description */
  description: string | null;
}

/**
 * Response from AI services endpoint.
 */
export interface AiServicesResponse {
  /** List of available AI services */
  services: AiService[];
}

/**
 * Service health status from the /gpu-config/services endpoint.
 * Provides comprehensive health information for GPU settings UI.
 */
export interface ServiceHealthStatus {
  /** Service name (e.g., 'ai-llm') */
  name: string;
  /** Container status (running, stopped, restarting, etc.) */
  status: string;
  /** Health check result (healthy, unhealthy, unknown, starting) */
  health: string;
  /** Assigned GPU index, or null if not assigned */
  gpu_index: number | null;
  /** Restart status if currently restarting (pending, completed) */
  restart_status: string | null;
}

/**
 * Response from service health endpoint.
 */
export interface ServiceHealthResponse {
  /** Status of all AI services */
  services: ServiceHealthStatus[];
}

// ============================================================================
// Error Handling
// ============================================================================

/**
 * Custom error class for GPU Configuration API failures.
 * Includes HTTP status code and parsed error data.
 */
export class GpuConfigApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'GpuConfigApiError';
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

    throw new GpuConfigApiError(response.status, errorMessage, errorData);
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new GpuConfigApiError(response.status, 'Failed to parse response JSON', error);
  }
}

/**
 * Perform a fetch request to the GPU Config API with error handling.
 *
 * @param endpoint - API endpoint path (relative to /api/system)
 * @param options - Optional fetch options
 * @returns Parsed JSON response
 */
async function fetchGpuConfigApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}/api/system${endpoint}`;

  const fetchOptions: RequestInit = {
    ...options,
    headers: buildHeaders(),
  };

  try {
    const response = await fetch(url, fetchOptions);
    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof GpuConfigApiError) {
      throw error;
    }
    throw new GpuConfigApiError(
      0,
      error instanceof Error ? error.message : 'Network request failed'
    );
  }
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get list of detected GPUs with current utilization.
 *
 * Returns all GPUs detected on the system with their hardware specifications
 * and current VRAM usage.
 *
 * @returns GpuListResponse containing detected GPUs
 * @throws GpuConfigApiError on server errors
 *
 * @example
 * ```typescript
 * const { gpus } = await getGpus();
 * gpus.forEach(gpu => {
 *   console.log(`GPU ${gpu.index}: ${gpu.name} (${gpu.vram_total_mb} MB)`);
 * });
 * ```
 */
export async function getGpus(): Promise<GpuListResponse> {
  return fetchGpuConfigApi<GpuListResponse>('/gpus');
}

/**
 * Get current GPU configuration including strategy and assignments.
 *
 * Returns the current GPU assignment strategy, all service-to-GPU mappings,
 * and the list of available strategies.
 *
 * @returns GpuConfig with current configuration
 * @throws GpuConfigApiError on server errors
 *
 * @example
 * ```typescript
 * const config = await getGpuConfig();
 * console.log(`Strategy: ${config.strategy}`);
 * config.assignments.forEach(a => {
 *   console.log(`${a.service} -> GPU ${a.gpu_index}`);
 * });
 * ```
 */
export async function getGpuConfig(): Promise<GpuConfig> {
  return fetchGpuConfigApi<GpuConfig>('/gpu-config');
}

/**
 * Update GPU configuration (strategy and/or assignments).
 *
 * Saves the new configuration to the database and syncs to the YAML file.
 * Does NOT restart services - use applyGpuConfig() after updating.
 *
 * @param config - New configuration to apply
 * @returns Response with success status and any warnings
 * @throws GpuConfigApiError on validation errors or server errors
 *
 * @example
 * ```typescript
 * const result = await updateGpuConfig({
 *   strategy: 'manual',
 *   assignments: [
 *     { service: 'ai-llm', gpu_index: 0 },
 *     { service: 'ai-enrichment', gpu_index: 1, vram_budget_override: 3.5 }
 *   ]
 * });
 * if (result.warnings.length > 0) {
 *   console.warn('Configuration warnings:', result.warnings);
 * }
 * ```
 */
export async function updateGpuConfig(
  config: GpuConfigUpdateRequest
): Promise<GpuConfigUpdateResponse> {
  return fetchGpuConfigApi<GpuConfigUpdateResponse>('/gpu-config', {
    method: 'PUT',
    body: JSON.stringify(config),
  });
}

/**
 * Apply GPU configuration and restart affected services.
 *
 * Generates the docker-compose override file and restarts any services
 * whose GPU assignments have changed.
 *
 * @returns Result with list of restarted services and any failures
 * @throws GpuConfigApiError on server errors
 *
 * @example
 * ```typescript
 * const result = await applyGpuConfig();
 * if (result.success) {
 *   console.log('Restarted services:', result.restarted);
 * } else {
 *   console.error('Failed to restart:', result.failed);
 * }
 * ```
 */
export async function applyGpuConfig(): Promise<GpuApplyResult> {
  return fetchGpuConfigApi<GpuApplyResult>('/gpu-config/apply', {
    method: 'POST',
  });
}

/**
 * Get current status of all AI services.
 *
 * Returns container status, health check results, and restart progress
 * for all AI services. Used for polling during service restarts.
 *
 * @returns Status of all AI services
 * @throws GpuConfigApiError on server errors
 *
 * @example
 * ```typescript
 * const { services } = await getGpuStatus();
 * const allHealthy = services.every(s => s.health === 'healthy');
 * ```
 */
export async function getGpuStatus(): Promise<GpuStatusResponse> {
  return fetchGpuConfigApi<GpuStatusResponse>('/gpu-config/status');
}

/**
 * Re-detect GPUs on the system.
 *
 * Triggers a fresh GPU scan and updates the gpu_devices table.
 * Useful when GPUs are added or removed from the system.
 *
 * @returns Updated list of detected GPUs
 * @throws GpuConfigApiError on server errors
 *
 * @example
 * ```typescript
 * const { gpus } = await detectGpus();
 * console.log(`Detected ${gpus.length} GPUs`);
 * ```
 */
export async function detectGpus(): Promise<GpuListResponse> {
  return fetchGpuConfigApi<GpuListResponse>('/gpu-config/detect', {
    method: 'POST',
  });
}

/**
 * Preview auto-assignment for a given strategy.
 *
 * Returns what the assignments would be if the given strategy were applied,
 * without actually changing the configuration.
 *
 * @param strategy - Strategy name to preview
 * @returns Proposed assignments for the strategy
 * @throws GpuConfigApiError if strategy is invalid or on server errors
 *
 * @example
 * ```typescript
 * const preview = await previewStrategy('isolation_first');
 * preview.proposed_assignments.forEach(a => {
 *   console.log(`${a.service} would be assigned to GPU ${a.gpu_index}`);
 * });
 * ```
 */
export async function previewStrategy(strategy: string): Promise<StrategyPreviewResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('strategy', strategy);

  return fetchGpuConfigApi<StrategyPreviewResponse>(
    `/gpu-config/preview?${queryParams.toString()}`
  );
}

/**
 * Get list of available AI services with VRAM requirements.
 *
 * Returns all AI services that can be assigned to GPUs, including
 * their display names and VRAM requirements.
 *
 * @returns AiServicesResponse containing available AI services
 * @throws GpuConfigApiError on server errors
 *
 * @example
 * ```typescript
 * const { services } = await getAiServices();
 * services.forEach(s => {
 *   console.log(`${s.display_name}: ${s.vram_required_gb} GB`);
 * });
 * ```
 */
export async function getAiServices(): Promise<AiServicesResponse> {
  return fetchGpuConfigApi<AiServicesResponse>('/ai-services');
}

/**
 * Get health status of all AI services.
 *
 * Returns comprehensive health information for all AI services including
 * container status, health check result, GPU assignment, and restart status.
 *
 * @returns ServiceHealthResponse with status of all AI services
 * @throws GpuConfigApiError on server errors
 *
 * @example
 * ```typescript
 * const { services } = await getServiceHealth();
 * const allHealthy = services.every(s => s.health === 'healthy');
 * const noneRestarting = services.every(s => !s.restart_status);
 * ```
 */
export async function getServiceHealth(): Promise<ServiceHealthResponse> {
  return fetchGpuConfigApi<ServiceHealthResponse>('/gpu-config/services');
}
