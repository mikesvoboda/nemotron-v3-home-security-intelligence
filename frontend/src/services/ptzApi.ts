/**
 * PTZ API Service (NEM-4885)
 *
 * API functions for PTZ camera control operations.
 * Matches backend endpoints in: backend/api/routes/onvif.py
 */

import type {
  PTZCommandRequest,
  PTZCommandResponse,
  PTZPresetsResponse,
  PTZGotoPresetResponse,
} from '../types/ptz';

const BASE_URL = '/api/cameras';

/**
 * Execute a PTZ command (pan, tilt, zoom, stop)
 */
export async function executePtzCommand(
  cameraId: string,
  command: PTZCommandRequest
): Promise<PTZCommandResponse> {
  const response = await fetch(`${BASE_URL}/${cameraId}/onvif/ptz`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(command),
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(errorData.detail ?? `PTZ command failed: ${response.status}`);
  }

  return response.json() as Promise<PTZCommandResponse>;
}

/**
 * Get available PTZ presets for a camera
 */
export async function getPtzPresets(cameraId: string): Promise<PTZPresetsResponse> {
  const response = await fetch(`${BASE_URL}/${cameraId}/onvif/presets`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(errorData.detail ?? `Failed to get presets: ${response.status}`);
  }

  return response.json() as Promise<PTZPresetsResponse>;
}

/**
 * Navigate to a PTZ preset position
 */
export async function gotoPtzPreset(
  cameraId: string,
  presetToken: string
): Promise<PTZGotoPresetResponse> {
  const response = await fetch(`${BASE_URL}/${cameraId}/onvif/presets/${presetToken}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(errorData.detail ?? `Failed to goto preset: ${response.status}`);
  }

  return response.json() as Promise<PTZGotoPresetResponse>;
}
