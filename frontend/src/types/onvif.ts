/**
 * ONVIF Discovery Types (NEM-4754 Phase 3)
 *
 * These types match the backend OnvifService structures in:
 * backend/services/onvif_service.py
 * backend/api/schemas/onvif.py
 */

/**
 * RTSP URL profile information from ONVIF device
 */
export interface OnvifRtspUrl {
  profile: string;
  url: string;
}

/**
 * Capability flags for an ONVIF device
 */
export interface OnvifCapabilities {
  video: boolean;
  ptz: boolean;
  events: boolean;
}

/**
 * Discovered ONVIF device information
 */
export interface OnvifDevice {
  device_url: string;
  ip: string;
  port: number;
  manufacturer: string;
  model: string;
  firmware_version: string | null;
  serial_number: string | null;
  hardware_id: string | null;
  rtsp_urls: OnvifRtspUrl[];
  capabilities: OnvifCapabilities;
}

/**
 * Request payload for ONVIF device discovery
 */
export interface OnvifDiscoveryRequest {
  subnet: string;
  timeout?: number;
}

/**
 * Response from ONVIF device discovery
 */
export interface OnvifDiscoveryResponse {
  devices: OnvifDevice[];
  count: number;
}
