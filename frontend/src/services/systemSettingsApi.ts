/**
 * API client for SystemSetting Key-Value Store (NEM-3638).
 *
 * Provides typed fetch wrappers for system settings REST endpoints.
 */

import { fetchApi } from './api';

/**
 * Response from GET /api/v1/system-settings/{key}
 */
export interface SystemSettingResponse {
  /** Setting key (primary key) */
  key: string;
  /** Setting value as JSON object */
  value: Record<string, unknown>;
  /** Last update timestamp */
  updated_at: string;
}

/**
 * Response from GET /api/v1/system-settings
 */
export interface SystemSettingListResponse {
  /** List of system settings */
  items: SystemSettingResponse[];
  /** Total number of settings */
  total: number;
}

/**
 * Request body for PATCH /api/v1/system-settings/{key}
 */
export interface SystemSettingUpdate {
  /** New value for the setting (replaces existing value entirely) */
  value: Record<string, unknown>;
}

/**
 * Fetch all system settings.
 *
 * @returns Promise resolving to list of all settings
 */
export async function fetchSystemSettings(): Promise<SystemSettingListResponse> {
  return fetchApi<SystemSettingListResponse>('/api/v1/system-settings');
}

/**
 * Fetch a specific system setting by key.
 *
 * @param key - Setting key to fetch
 * @returns Promise resolving to the setting
 * @throws Error if setting not found (404)
 */
export async function fetchSystemSetting(key: string): Promise<SystemSettingResponse> {
  return fetchApi<SystemSettingResponse>(`/api/v1/system-settings/${encodeURIComponent(key)}`);
}

/**
 * Update or create a system setting.
 *
 * If the setting exists, updates its value. If it doesn't exist, creates it.
 * This is an upsert operation.
 *
 * @param key - Setting key to update or create
 * @param value - New value for the setting
 * @returns Promise resolving to the updated setting
 * @throws Error if key format is invalid (400)
 */
export async function updateSystemSetting(
  key: string,
  value: Record<string, unknown>
): Promise<SystemSettingResponse> {
  return fetchApi<SystemSettingResponse>(
    `/api/v1/system-settings/${encodeURIComponent(key)}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ value }),
    }
  );
}

/**
 * Delete a system setting.
 *
 * @param key - Setting key to delete
 * @throws Error if setting not found (404)
 */
export async function deleteSystemSetting(key: string): Promise<void> {
  await fetchApi<void>(
    `/api/v1/system-settings/${encodeURIComponent(key)}`,
    {
      method: 'DELETE',
    }
  );
}
