/**
 * PTZ (Pan-Tilt-Zoom) Control Types (NEM-4885)
 *
 * These types match the backend PTZ schemas in:
 * backend/api/schemas/onvif.py
 */

/**
 * PTZ command types
 */
export type PTZCommandType = 'pan' | 'tilt' | 'zoom' | 'stop';

/**
 * PTZ command request payload
 */
export interface PTZCommandRequest {
  command: PTZCommandType;
  /** Movement value from -1.0 to 1.0 */
  value: number;
  /** Movement speed from 0.0 to 1.0, defaults to 1.0 */
  speed?: number;
}

/**
 * PTZ preset position
 */
export interface PTZPreset {
  /** Unique preset token */
  token: string;
  /** User-friendly preset name */
  name: string;
}

/**
 * Response from PTZ command execution
 */
export interface PTZCommandResponse {
  success: boolean;
  message?: string;
}

/**
 * Response from get presets endpoint
 */
export interface PTZPresetsResponse {
  presets: PTZPreset[];
}

/**
 * Response from goto preset endpoint
 */
export interface PTZGotoPresetResponse {
  success: boolean;
  message?: string;
}

/**
 * PTZ movement direction for D-pad controls
 */
export type PTZDirection = 'up' | 'down' | 'left' | 'right' | 'zoom-in' | 'zoom-out';

/**
 * Maps D-pad direction to PTZ command
 */
export const PTZ_DIRECTION_MAP: Record<PTZDirection, PTZCommandRequest> = {
  up: { command: 'tilt', value: 1.0 },
  down: { command: 'tilt', value: -1.0 },
  left: { command: 'pan', value: -1.0 },
  right: { command: 'pan', value: 1.0 },
  'zoom-in': { command: 'zoom', value: 1.0 },
  'zoom-out': { command: 'zoom', value: -1.0 },
};
