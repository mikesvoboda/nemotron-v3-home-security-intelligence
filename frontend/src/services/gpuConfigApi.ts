/**
 * GPU Configuration API Client (F-176, F-178, F-182).
 */

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';

export interface GpuDevice {
  index: number;
  name: string;
  vram_total_mb: number;
  vram_used_mb: number;
  compute_capability: string;
}

export interface GpuListResponse {
  gpus: GpuDevice[];
}

export interface GpuAssignment {
  service: string;
  gpu_index: number | null;
  vram_budget_override?: number | null;
  exclusive_gpu?: boolean;
  priority_weight?: number;
  incompatible_with?: string[] | null;
}

export interface GpuConfig {
  strategy: string;
  assignments: GpuAssignment[];
  updated_at: string | null;
}

export interface StrategyPreviewResponse {
  strategy: string;
  proposed_assignments: GpuAssignment[];
  warnings: string[];
}

export interface AiService {
  name: string;
  display_name: string;
  vram_required_mb: number;
  vram_required_gb: number;
  description: string | null;
}

export interface AiServicesResponse {
  services: AiService[];
}

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

function buildHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  return headers;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorData: unknown = undefined;

    try {
      const errorBody: unknown = await response.json();
      if (typeof errorBody === 'object' && errorBody !== null && 'detail' in errorBody) {
        errorMessage = String(errorBody.detail);
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

export async function getGpus(): Promise<GpuListResponse> {
  return fetchGpuConfigApi<GpuListResponse>('/gpus');
}

export async function getGpuConfig(): Promise<GpuConfig> {
  return fetchGpuConfigApi<GpuConfig>('/gpu-config');
}

export async function previewStrategy(strategy: string): Promise<StrategyPreviewResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('strategy', strategy);

  return fetchGpuConfigApi<StrategyPreviewResponse>(
    `/gpu-config/preview?${queryParams.toString()}`
  );
}

export async function getAiServices(): Promise<AiServicesResponse> {
  return fetchGpuConfigApi<AiServicesResponse>('/ai-services');
}

export interface GpuConfigVersionSummary {
  id: string;
  version_number: number;
  strategy: string;
  description: string | null;
  created_at: string;
  created_by: string | null;
  assignment_count: number;
}

export interface GpuConfigVersionDetail extends GpuConfigVersionSummary {
  assignments: GpuAssignment[];
}

export interface GpuConfigVersionListResponse {
  versions: GpuConfigVersionSummary[];
  total_count: number;
}

export interface GpuConfigAssignmentChange {
  service: string;
  change_type: 'added' | 'removed' | 'modified';
  old_gpu_index: number | null;
  new_gpu_index: number | null;
  old_vram_override: number | null;
  new_vram_override: number | null;
}

export interface GpuConfigVersionDiffResponse {
  from_version: number;
  to_version: number;
  strategy_changed: boolean;
  old_strategy: string | null;
  new_strategy: string | null;
  assignment_changes: GpuConfigAssignmentChange[];
}

export interface GpuConfigExportData {
  export_version: string;
  exported_at: string;
  strategy: string;
  assignments: GpuAssignment[];
  source_version: number | null;
  description: string | null;
}

export async function getConfigVersions(
  limit: number = 20,
  offset: number = 0
): Promise<GpuConfigVersionListResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('limit', limit.toString());
  queryParams.append('offset', offset.toString());

  return fetchGpuConfigApi<GpuConfigVersionListResponse>(
    `/gpu-config/history?${queryParams.toString()}`
  );
}

export async function getConfigVersion(versionId: string): Promise<GpuConfigVersionDetail> {
  return fetchGpuConfigApi<GpuConfigVersionDetail>(`/gpu-config/history/${versionId}`);
}

export async function diffConfigVersions(
  fromVersion: number,
  toVersion: number
): Promise<GpuConfigVersionDiffResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('from_version', fromVersion.toString());
  queryParams.append('to_version', toVersion.toString());

  return fetchGpuConfigApi<GpuConfigVersionDiffResponse>(
    `/gpu-config/history/diff?${queryParams.toString()}`
  );
}

export async function exportGpuConfig(versionId?: string): Promise<GpuConfigExportData> {
  const queryParams = new URLSearchParams();
  if (versionId) {
    queryParams.append('version_id', versionId);
  }

  const queryString = queryParams.toString();
  const endpoint = queryString ? `/gpu-config/export?${queryString}` : '/gpu-config/export';

  return fetchGpuConfigApi<GpuConfigExportData>(endpoint);
}

export async function downloadGpuConfig(
  versionId?: string,
  format: 'json' | 'yaml' = 'json'
): Promise<void> {
  const exportData = await exportGpuConfig(versionId);

  let content: string;
  let mimeType: string;
  let extension: string;

  if (format === 'yaml') {
    const yamlLines: string[] = [
      '# GPU Configuration Export',
      `# Exported at: ${exportData.exported_at}`,
      '',
      `export_version: "${exportData.export_version}"`,
      `strategy: "${exportData.strategy}"`,
      exportData.source_version !== null ? `source_version: ${exportData.source_version}` : '',
      exportData.description ? `description: "${exportData.description}"` : '',
      '',
      'assignments:',
    ];

    for (const assignment of exportData.assignments) {
      yamlLines.push(`  - service: "${assignment.service}"`);
      yamlLines.push(`    gpu_index: ${assignment.gpu_index ?? 'null'}`);
      if (
        assignment.vram_budget_override !== null &&
        assignment.vram_budget_override !== undefined
      ) {
        yamlLines.push(`    vram_budget_override: ${assignment.vram_budget_override}`);
      }
    }

    content = yamlLines.filter((line) => line !== '').join('\n');
    mimeType = 'text/yaml';
    extension = 'yaml';
  } else {
    content = JSON.stringify(exportData, null, 2);
    mimeType = 'application/json';
    extension = 'json';
  }

  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `gpu-config-${new Date().toISOString().slice(0, 10)}.${extension}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
